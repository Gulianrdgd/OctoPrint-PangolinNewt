import octoprint.plugin
import subprocess
import threading
import os
import stat
import platform
import urllib.request
import urllib.error
import json
import shutil

__plugin_name__ = "Pangolin Newt"
__plugin_pythoncompat__ = ">=3.7,<4"

NEWT_INSTALL_PATH = "/usr/local/bin/newt"
GITHUB_API_URL = "https://api.github.com/repos/fosrl/newt/releases/latest"


def _detect_arch():
    """Map Python platform to the Newt binary suffix."""
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    elif machine in ("armv7l", "armv6l"):
        return "arm"
    elif machine in ("x86_64", "amd64"):
        return "amd64"
    else:
        return None


class PangolinPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.ShutdownPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
):
    def __init__(self):
        self._newt_process = None
        self._newt_lock = threading.Lock()
        self._status = "stopped"       # stopped | running | error | installing
        self._install_log = []         # lines from the install process
        self._run_log = []             # rolling log from the newt process
        self._max_log = 80

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

    # ------------------------------------------------------------------ #
    # Startup / Shutdown                                                   #
    # ------------------------------------------------------------------ #

    def on_after_startup(self):
        self._logger.info("Pangolin plugin loaded.")
        if self._settings.get_boolean(["autostart"]):
            self._ensure_newt_and_start()

    def on_shutdown(self):
        self._stop_newt()

    # ------------------------------------------------------------------ #
    # Newt installation                                                    #
    # ------------------------------------------------------------------ #

    def _newt_installed(self):
        return os.path.isfile(NEWT_INSTALL_PATH) and os.access(NEWT_INSTALL_PATH, os.X_OK)

    def _install_newt(self):
        """Download the Newt binary from GitHub releases. Runs in a thread."""
        self._status = "installing"
        self._install_log = []

        def log(msg):
            self._logger.info("[pangolin-install] %s", msg)
            self._install_log.append(msg)

        arch = _detect_arch()
        if arch is None:
            log("ERROR: Unsupported architecture: %s" % platform.machine())
            self._status = "error"
            return False

        # Resolve latest version via GitHub API
        try:
            log("Fetching latest Newt release info from GitHub...")
            req = urllib.request.Request(GITHUB_API_URL,
                                         headers={"User-Agent": "OctoPrint-Pangolin"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                release = json.loads(resp.read().decode())
            tag = release["tag_name"]
            log("Latest release: %s" % tag)
        except Exception as e:
            log("ERROR: Could not fetch release info: %s" % e)
            self._status = "error"
            return False

        # Binary name changed between releases; try the modern name first, fall back
        binary_name = "newt-linux-%s" % arch        # e.g. newt-linux-arm64
        download_url = "https://github.com/fosrl/newt/releases/download/%s/%s" % (tag, binary_name)

        tmp_path = NEWT_INSTALL_PATH + ".tmp"
        try:
            log("Downloading %s ..." % download_url)
            req = urllib.request.Request(download_url,
                                         headers={"User-Agent": "OctoPrint-Pangolin"})
            with urllib.request.urlopen(req, timeout=60) as resp, \
                 open(tmp_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Try legacy underscore naming: newt_linux_arm64
                binary_name = "newt_linux_%s" % arch
                download_url = "https://github.com/fosrl/newt/releases/download/%s/%s" % (tag, binary_name)
                try:
                    log("Retrying with legacy name: %s" % download_url)
                    req = urllib.request.Request(download_url,
                                                 headers={"User-Agent": "OctoPrint-Pangolin"})
                    with urllib.request.urlopen(req, timeout=60) as resp, \
                         open(tmp_path, "wb") as f:
                        shutil.copyfileobj(resp, f)
                except Exception as e2:
                    log("ERROR: Download failed: %s" % e2)
                    self._status = "error"
                    return False
            else:
                log("ERROR: Download failed (%s): %s" % (e.code, e))
                self._status = "error"
                return False
        except Exception as e:
            log("ERROR: Download failed: %s" % e)
            self._status = "error"
            return False

        # Make executable and move into place (may need sudo on some setups)
        try:
            os.chmod(tmp_path, os.stat(tmp_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            shutil.move(tmp_path, NEWT_INSTALL_PATH)
            log("Newt installed at %s" % NEWT_INSTALL_PATH)
            return True
        except PermissionError:
            # Try with sudo mv (OctoPi runs octoprint as pi but /usr/local/bin needs root)
            log("Trying sudo to move binary into place...")
            try:
                os.chmod(tmp_path, 0o755)
                result = subprocess.run(
                    ["sudo", "mv", tmp_path, NEWT_INSTALL_PATH],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    log("ERROR: sudo mv failed: %s" % result.stderr)
                    self._status = "error"
                    return False
                log("Newt installed at %s (via sudo)" % NEWT_INSTALL_PATH)
                return True
            except Exception as e:
                log("ERROR: Could not install binary: %s" % e)
                self._status = "error"
                return False
        except Exception as e:
            log("ERROR: %s" % e)
            self._status = "error"
            return False

    # ------------------------------------------------------------------ #
    # Newt process management                                              #
    # ------------------------------------------------------------------ #

    def _ensure_newt_and_start(self):
        """Install Newt if missing, then start it. Runs in a background thread."""
        def _run():
            if not self._newt_installed():
                self._logger.info("Newt binary not found, installing...")
                ok = self._install_newt()
                if not ok:
                    return
            self._start_newt()

        t = threading.Thread(target=_run, daemon=True, name="pangolin-ensure")
        t.start()

    def _start_newt(self):
        with self._newt_lock:
            if self._newt_process and self._newt_process.poll() is None:
                return {"ok": False, "msg": "Newt is already running."}

            newt_id = self._settings.get(["newt_id"]).strip()
            newt_secret = self._settings.get(["newt_secret"]).strip()
            endpoint = self._settings.get(["pangolin_endpoint"]).strip()

            if not newt_id or not newt_secret:
                self._status = "error"
                msg = "Newt ID or secret not configured. Open Settings → Pangolin Newt."
                self._logger.warning(msg)
                return {"ok": False, "msg": msg}

            if not self._newt_installed():
                self._status = "error"
                return {"ok": False, "msg": "Newt binary not installed yet."}

            cmd = [NEWT_INSTALL_PATH,
                   "--id", newt_id,
                   "--secret", newt_secret,
                   "--endpoint", endpoint]

            self._logger.info("Starting Newt (endpoint: %s)", endpoint)
            try:
                self._newt_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self._status = "running"
                self._run_log = []
                t = threading.Thread(target=self._tail_output, daemon=True, name="pangolin-tail")
                t.start()
                return {"ok": True, "msg": "Newt started."}
            except Exception as e:
                self._status = "error"
                msg = "Failed to start Newt: %s" % e
                self._logger.error(msg)
                return {"ok": False, "msg": msg}

    def _stop_newt(self):
        with self._newt_lock:
            if not self._newt_process or self._newt_process.poll() is not None:
                self._status = "stopped"
                return {"ok": True, "msg": "Newt was not running."}
            try:
                self._newt_process.terminate()
                self._newt_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._newt_process.kill()
            self._newt_process = None
            self._status = "stopped"
            self._logger.info("Newt stopped.")
            return {"ok": True, "msg": "Newt stopped."}

    def _restart_newt(self):
        self._stop_newt()
        return self._start_newt()

    def _tail_output(self):
        proc = self._newt_process
        try:
            for line in proc.stdout:
                line = line.rstrip()
                self._run_log.append(line)
                if len(self._run_log) > self._max_log:
                    self._run_log.pop(0)
                self._logger.debug("[newt] %s", line)
        except Exception:
            pass
        finally:
            with self._newt_lock:
                if self._status == "running":
                    self._status = "stopped"

    # ------------------------------------------------------------------ #
    # Simple API                                                           #
    # ------------------------------------------------------------------ #

    def get_api_commands(self):
        return dict(start=[], stop=[], restart=[], status=[], install=[])

    def on_api_command(self, command, data):
        import flask
        if command == "start":
            result = self._start_newt()
        elif command == "stop":
            result = self._stop_newt()
        elif command == "restart":
            result = self._restart_newt()
        elif command == "install":
            def _do_install():
                ok = self._install_newt()
                if ok and self._settings.get_boolean(["autostart"]):
                    self._start_newt()
            threading.Thread(target=_do_install, daemon=True, name="pangolin-install").start()
            result = {"ok": True, "msg": "Installation started, check log for progress."}
        elif command == "status":
            running = self._newt_process is not None and self._newt_process.poll() is None
            result = {
                "ok": True,
                "status": self._status,
                "running": running,
                "installed": self._newt_installed(),
                "arch": _detect_arch() or "unknown",
                "log": (self._install_log + self._run_log)[-50:],
            }
        else:
            result = {"ok": False, "msg": "Unknown command."}
        return flask.jsonify(result)

    # ------------------------------------------------------------------ #
    # Templates & Assets                                                   #
    # ------------------------------------------------------------------ #

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=True,
                 template="pangolin_settings.jinja2"),
            dict(type="sidebar", custom_bindings=True,
                 template="pangolin_sidebar.jinja2",
                 icon="plug", name="Pangolin"),
        ]

    def get_assets(self):
        return dict(
            js=["js/pangolin.js"],
            css=["css/pangolin.css"],
        )


__plugin_implementation__ = PangolinPlugin()
