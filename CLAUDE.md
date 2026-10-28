# OctoPrint-Pangolin: project handoff

## Goal

An OctoPrint plugin that makes a Raspberry Pi running OctoPrint reachable through [Pangolin](https://pangolin.net) with zero terminal work. The user installs the plugin via OctoPrint's Plugin Manager (URL install), enters the Pangolin endpoint, Newt ID and Newt secret in the settings page, and the plugin does the rest:

1. Detects the Pi's CPU architecture
2. Downloads the latest `newt` binary from GitHub releases and installs it to `/usr/local/bin/newt`
3. Starts Newt as a child process of OctoPrint and keeps a rolling log of its output
4. Shows status, log and Start/Stop/Restart controls in the OctoPrint sidebar

Newt is Pangolin's userspace WireGuard client. Pangolin docs: https://docs.pangolin.net/manage/sites/install-site

## Current state

Version 0.2.0. Tested by the author on a real Pi and confirmed working end to end (install, start, tunnel up). Everything under "Known issues and TODO" is unaddressed.

## Layout

```
octoprint_pangolin/
  __init__.py                         Plugin class, Newt installer, process management, API
  templates/pangolin_settings.jinja2  Settings page (endpoint, ID, secret, autostart)
  templates/pangolin_sidebar.jinja2   Sidebar widget (status dot, buttons, log)
  static/js/pangolin.js               Knockout view model, polls status every 10 s
  static/css/pangolin.css             Sidebar styling
pyproject.toml                        Packaging, entry point `octoprint.plugin: pangolin`
MANIFEST.in                           Includes templates and static in the sdist
```

OctoPrint mixins used: `StartupPlugin`, `ShutdownPlugin`, `SettingsPlugin`, `TemplatePlugin`, `AssetPlugin`, `SimpleApiPlugin`. Plugin docs: https://docs.octoprint.org/en/main/plugins/index.html

## How it works

- `on_after_startup`: if `autostart` is set, a background thread installs Newt when missing, then starts it.
- `_install_newt`: maps `platform.machine()` to `arm64` / `arm` / `amd64`, asks the GitHub API for the latest tag, downloads `newt-linux-<arch>` (falls back to `newt_linux_<arch>` on a 404), writes to `/usr/local/bin/newt.tmp`, chmods, moves into place. On `PermissionError` it retries with `sudo mv`.
- `_start_newt`: `subprocess.Popen([newt, --id, --secret, --endpoint])`, stdout and stderr merged and tailed by a daemon thread into `_run_log` (80 lines).
- API (`POST /api/plugin/pangolin`): commands `start`, `stop`, `restart`, `install`, `status`.
- `on_shutdown` terminates Newt.

## Known issues and TODO (rough priority order)

1. **Release asset names are unverified.** The hyphen vs underscore naming and the 32-bit ARM suffix (`arm` vs something else) were inferred from docs and blog posts, not checked against the actual release assets. Fetch the real asset list for the latest release and fix `_detect_arch` and the URL logic. Prefer reading `browser_download_url` from the API response over constructing URLs.
2. **Secret is visible in `ps`.** It is passed as `--secret` on the command line. Newt also reads `NEWT_ID`, `NEWT_SECRET` and `PANGOLIN_ENDPOINT` from the environment (see the systemd example in the Pangolin docs). Switch `Popen` to pass these via `env=` instead of argv.
3. **`sudo mv` assumes passwordless sudo.** OctoPi's default `pi` user has it, other setups may not. Better: install to a user-writable directory (via `self.get_plugin_data_folder()`) and drop the sudo path entirely. Newt is userspace WireGuard and does not need root.
4. **No integrity check.** The downloaded binary is not verified (no checksum, no signature). Check what the release publishes and verify if possible.
5. **No crash recovery.** If Newt exits, status flips to "stopped" and nothing restarts it. Add a supervisor loop with backoff that honours a user-initiated stop.
6. **"Connected" only means the process is alive.** Parse Newt's log output, or its metrics endpoint (default port 2112, verify), to report real connection state.
7. **Settings changes do not apply live.** Implement `on_settings_save` to restart Newt when ID, secret or endpoint change.
8. **No update path.** The binary is only installed when missing. Add an "Update Newt" action and show the installed version (check which version flag `newt` supports).
9. **Secret exposure to the UI.** The secret is part of the settings payload sent to the browser for any admin. Consider making it write-only in the UI.
10. **No permission check on the API.** Restrict start/stop/restart/install to admins using OctoPrint's permission system.
11. **Thread safety.** `_status`, `_run_log` and `_install_log` are mutated from several threads without a lock. Low risk, easy to tidy.
12. **Packaging chores.** Replace the `yourusername` placeholder URLs in `pyproject.toml` and `README.md`, choose a license (OctoPrint plugins are usually AGPLv3), add tests, add `octoprint.plugin.softwareupdate.check_config` so the plugin updates through OctoPrint's updater, and consider submitting to the official plugin repository (https://docs.octoprint.org/en/main/plugins/distributing.html).

## Dev workflow

OctoPrint plugin development setup (from the official tutorial):

```bash
git clone https://github.com/OctoPrint/OctoPrint && cd OctoPrint
python -m venv venv && source venv/bin/activate
pip install -e '.[develop,plugins]'
cd /path/to/OctoPrint-Pangolin
octoprint dev plugin:install      # editable install into that venv
octoprint serve
```

Developing on the Pi directly also works: `source ~/oprint/bin/activate && pip install -e .`, then restart OctoPrint (`sudo systemctl restart octoprint`).

The installer currently writes to `/usr/local/bin`, so testing it on a dev machine needs root. Fixing issue 3 first removes that.

## Conventions

- Python 3.7+ compatible (`__plugin_pythoncompat__ = ">=3.7,<4"`)
- No em dashes in prose or documentation
- Keep the user-facing setup to: install plugin, enter endpoint, ID and secret, save. Do not add steps that need a terminal.
