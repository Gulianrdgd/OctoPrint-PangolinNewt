import os
import threading
from urllib.parse import urlparse

import flask
import octoprint.plugin
from octoprint.access.permissions import Permissions

from . import newt

__plugin_name__ = "Pangolin Newt Client"
__plugin_pythoncompat__ = ">=3.7,<4"

GITHUB_USER = "Gulianrdgd"
GITHUB_REPO = "OctoPrint-PangolinNewt"
CREDENTIAL_KEYS = ("newt_id", "newt_secret", "pangolin_endpoint")


def valid_endpoint(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def clean_settings(data):
    """Trim credentials, drop an empty secret (keep the stored one) and an invalid endpoint."""
    for key in CREDENTIAL_KEYS:
        if isinstance(data.get(key), str):
            data[key] = data[key].strip()
    if not data.get("newt_secret"):
        data.pop("newt_secret", None)
    if "pangolin_endpoint" in data:
        endpoint = data["pangolin_endpoint"].rstrip("/")
        if valid_endpoint(endpoint):
            data["pangolin_endpoint"] = endpoint
        else:
            data.pop("pangolin_endpoint")
    return data


class PangolinNewtPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
):
    def initialize(self):
        data_folder = self.get_plugin_data_folder()
        self._pinned = newt.load_pinned_release()
        self._arch = newt.detect_arch()
        self._installed_version = None
        self._job_lock = threading.Lock()
        self._pushed_line = 0
        self._newt = newt.NewtProcess(
            binary_path=os.path.join(data_folder, "bin", "newt"),
            health_path=os.path.join(data_folder, "health"),
            on_change=self._push,
            logger=self._logger,
        )
        if newt.installed_sha256(self._newt.binary_path) is None:
            self._newt.set_state(newt.NOT_INSTALLED)

    # ------------------------------------------------------------------ #
    # Settings                                                             #
    # ------------------------------------------------------------------ #

    def get_settings_defaults(self):
        return dict(
            newt_id="",
            newt_secret="",
            pangolin_endpoint="https://app.pangolin.net",
            autostart=True,
        )

    def on_settings_load(self):
        data = octoprint.plugin.SettingsPlugin.on_settings_load(self)
        # The secret is write-only: never send it to the browser.
        data["newt_secret"] = ""
        return data

    def on_settings_save(self, data):
        before = self._credentials()
        result = octoprint.plugin.SettingsPlugin.on_settings_save(self, clean_settings(data))
        if self._credentials() != before and (
            self._newt.is_running() or self._settings.get_boolean(["autostart"])
        ):
            self._logger.info("Pangolin settings changed, restarting Newt.")
            self._run_job(self._restart_job)
        self._push()
        return result

    def _credentials(self):
        return {key: self._settings.get([key]) for key in CREDENTIAL_KEYS}

    def _configured(self):
        creds = self._credentials()
        return bool(creds["newt_id"] and creds["newt_secret"])

    # ------------------------------------------------------------------ #
    # Startup / Shutdown                                                   #
    # ------------------------------------------------------------------ #

    def on_after_startup(self):
        autostart = self._settings.get_boolean(["autostart"])
        installed = newt.installed_sha256(self._newt.binary_path) is not None

        def job():
            if not self._ensure_installed():
                return
            if autostart and self._configured():
                self._start()

        if autostart or installed:
            self._run_job(job)

    def on_shutdown(self):
        self._newt.stop()

    # ------------------------------------------------------------------ #
    # Jobs                                                                 #
    # ------------------------------------------------------------------ #

    def _run_job(self, fn):
        """Run fn in a background thread; jobs run one at a time."""
        def run():
            with self._job_lock:
                fn()

        threading.Thread(target=run, daemon=True, name="pangolin-newt-job").start()

    def _pinned_asset(self):
        return self._pinned["assets"].get(self._arch) if self._arch else None

    def _ensure_installed(self, force=False):
        asset = self._pinned_asset()
        if asset is None:
            self._newt.set_state(newt.ERROR, "Unsupported architecture.")
            return False

        if not force and newt.installed_sha256(self._newt.binary_path) == asset["sha256"]:
            if self._installed_version is None:
                self._installed_version = newt.binary_version(self._newt.binary_path)
            return True

        was_running = self._newt.is_running()
        if was_running:
            self._newt.stop()
        self._newt.set_state(newt.INSTALLING)
        self._newt.log("Installing Newt %s for %s ..." % (self._pinned["version"], self._arch))
        try:
            newt.install(asset, self._newt.binary_path, self._newt.log)
        except Exception as e:
            self._newt.log("ERROR: %s" % e)
            self._newt.set_state(newt.ERROR, "Install failed: %s" % e)
            return False
        self._installed_version = newt.binary_version(self._newt.binary_path)
        self._newt.set_state(newt.STOPPED)
        if was_running:
            self._start()
        return True

    def _start(self):
        if not self._configured():
            return False, "Enter your Newt ID and secret in the plugin settings first."
        creds = self._credentials()
        return self._newt.start(creds["newt_id"], creds["newt_secret"], creds["pangolin_endpoint"])

    def _restart_job(self):
        self._newt.stop()
        if self._ensure_installed():
            self._start()

    def _reinstall_job(self):
        was_running = self._newt.is_running()
        if self._ensure_installed(force=True) and not was_running and \
                self._settings.get_boolean(["autostart"]):
            self._start()

    # ------------------------------------------------------------------ #
    # State for the UI                                                     #
    # ------------------------------------------------------------------ #

    def _payload(self, since=0):
        data = self._newt.snapshot(since)
        data.update(
            configured=self._configured(),
            secret_set=bool(self._settings.get(["newt_secret"])),
            arch=self._arch or "unsupported",
            pinned_version=self._pinned["version"],
            installed_version=self._installed_version,
        )
        return data

    def _push(self):
        data = self._payload(self._pushed_line)
        self._pushed_line = data["last_line"]
        self._plugin_manager.send_plugin_message(
            self._identifier, data, permissions=[Permissions.ADMIN]
        )

    # ------------------------------------------------------------------ #
    # Simple API                                                           #
    # ------------------------------------------------------------------ #

    def is_api_adminonly(self):
        return True

    def is_api_protected(self):
        return True

    def get_api_commands(self):
        return dict(start=[], stop=[], restart=[], reinstall=[])

    def on_api_get(self, request):
        return flask.jsonify(self._payload())

    def on_api_command(self, command, data):
        if command == "start":
            if not self._configured():
                ok, msg = False, "Enter your Newt ID and secret in the plugin settings first."
            elif self._newt.is_running():
                ok, msg = False, "Newt is already running."
            else:
                self._run_job(self._restart_job)
                ok, msg = True, "Starting Newt..."
        elif command == "stop":
            ok, msg = self._newt.stop()
        elif command == "restart":
            self._run_job(self._restart_job)
            ok, msg = True, "Restarting Newt..."
        elif command == "reinstall":
            self._run_job(self._reinstall_job)
            ok, msg = True, "Reinstalling Newt..."
        else:
            return flask.abort(400)
        result = self._payload()
        result.update(ok=ok, msg=msg)
        return flask.jsonify(result)

    # ------------------------------------------------------------------ #
    # Templates & Assets                                                   #
    # ------------------------------------------------------------------ #

    def is_template_autoescaped(self):
        return True

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=True, name="Pangolin Newt Client"),
            dict(type="sidebar", custom_bindings=True, icon="plug", name="Pangolin"),
        ]

    def get_assets(self):
        return dict(
            js=["js/pangolin_newt.js"],
            css=["css/pangolin_newt.css"],
        )

    # ------------------------------------------------------------------ #
    # Software update                                                      #
    # ------------------------------------------------------------------ #

    def get_update_information(self):
        return {
            self._identifier: dict(
                displayName=__plugin_name__,
                displayVersion=self._plugin_version,
                type="github_release",
                user=GITHUB_USER,
                repo=GITHUB_REPO,
                current=self._plugin_version,
                pip="https://github.com/%s/%s/archive/{target_version}.zip"
                    % (GITHUB_USER, GITHUB_REPO),
            )
        }


__plugin_implementation__ = PangolinNewtPlugin()

__plugin_hooks__ = {
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
}
