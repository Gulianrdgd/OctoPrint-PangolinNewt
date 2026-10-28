# Pangolin Newt Client (OctoPrint-PangolinNewt): project handoff

## Goal

An OctoPrint plugin that makes a Raspberry Pi running OctoPrint reachable through [Pangolin](https://pangolin.net) with zero terminal work. The user installs the plugin via OctoPrint's Plugin Manager (URL install), enters the Pangolin endpoint, Newt ID and Newt secret in the settings page, and the plugin does the rest:

1. Detects the Pi's CPU architecture
2. Downloads the Newt build pinned in `newt_release.json`, verifies its sha256 and installs it into the plugin data folder
3. Starts Newt as a child process of OctoPrint and keeps a rolling log of its output
4. Pushes status, log and Start/Stop/Restart controls to the OctoPrint sidebar and settings page

Newt is Pangolin's userspace WireGuard client. Pangolin docs: https://docs.pangolin.net/manage/sites/install-site

## Current state

Version 0.4.0: changes from the plugin registry review. Added `setup.py` and aligned `pyproject.toml` with the OctoPrint cookiecutter (setuptools>=68, author email, SPDX license `AGPL-3.0-or-later`), added `PRIVACY.md` and the `cloud` attribute, and removed the daily Newt bump workflow because Newt updates itself. 0.3.0 renamed the plugin from OctoPrint-Pangolin (identifier `pangolin` -> `pangolin_newt`). 0.2.0 was confirmed working on a real Pi. 0.4.0 has been tested with pytest and a local OctoPrint 2.0.0rc7 on macOS (darwin Newt binary seeded into the data folder), not yet on a Pi.

GitHub repo: `Gulianrdgd/OctoPrint-PangolinNewt` (the softwareupdate hook and URLs depend on this name).

## Layout

```
octoprint_pangolin_newt/
  __init__.py                              Plugin class: settings, API, jobs, softwareupdate hook
  newt.py                                  Installer and NewtProcess manager, no OctoPrint imports
  newt_release.json                        Newt version for fresh installs, asset URLs and sha256
  templates/pangolin_newt_settings.jinja2  Status block, setup steps, validated fields
  templates/pangolin_newt_sidebar.jinja2   Status, buttons, log (admins only)
  static/js/pangolin_newt.js               Knockout view model for both, driven by plugin messages
  static/css/pangolin_newt.css
scripts/update_newt.py                     Pins latest Newt (run by hand before a release)
tests/                                     pytest (needs OctoPrint installed: pip install -e ".[develop]")
.github/workflows/ci.yml                   Tests (3.7, 3.12) and build
.github/workflows/release.yml              Tag -> test, build, GitHub release
docs/plugins.octoprint.org/pangolin_newt.md  Draft entry for the plugin registry (one-time PR)
PRIVACY.md                                 Privacy policy, linked from the registry entry (`privacypolicy`)
setup.py                                   Cookiecutter shim that sets the license string
```

## How it works

- `on_after_startup`: if autostart is set or Newt is installed, a job installs the pinned Newt when none is installed (`bin/newt` plus `bin/newt.sha256`), then starts it if autostart is on and ID and secret are set.
- Newt updates itself: every 6 hours it asks the Pangolin server (`/api/v1/auth/newt/version`), replaces its own binary and re-execs (same PID). The plugin therefore never replaces an installed binary unless the user clicks Reinstall, and re-reads `newt --version` on each start. Do not reintroduce automatic plugin releases per Newt version: the registry reviewer asked to avoid flooding users with update notifications.
- Jobs run one at a time on a background thread (`_run_job`).
- `NewtProcess.start` passes `NEWT_ID`, `NEWT_SECRET`, `PANGOLIN_ENDPOINT` and `HEALTH_FILE` through the environment. Newt writes the health file once the tunnel is up: that is the difference between `connecting` and `connected`. While connecting, Newt's latest `ERROR:` line becomes the status message.
- Each start bumps a generation counter. Threads of an older process never touch state (this was the old "status flips to stopped after restart" bug).
- State changes and log lines are coalesced (250 ms) and pushed with `send_plugin_message` (admin only). The UI fetches a full snapshot via `GET /api/plugin/pangolin_newt` on startup, login, reconnect and when settings open. Log lines carry a number so the UI only appends new ones.
- API (`POST /api/plugin/pangolin_newt`, admin only): `start`, `stop`, `restart`, `reinstall`.
- Settings: the secret is write-only (`on_settings_load` blanks it, an empty value on save keeps the stored one). Inputs are trimmed and invalid or non-https endpoints are dropped (`clean_settings`); the plugin registry requires https for external services. Changing ID, secret or endpoint restarts Newt when it is running or autostart is on.
- Release flow: plugin updates reach users through OctoPrint's Software Update (`github_release`, tags without `v`, pip installs `archive/{target_version}.zip`). The plugin registry only needs the one-time PR.

## Known issues and TODO

1. **No crash recovery.** If Newt exits, status shows the error and nothing restarts it. Newt reconnects on its own while running, so this only matters for real crashes. Add a supervisor with backoff that honours a user-initiated stop if it turns out to be needed.
2. **Untested on a Pi** since the 0.3.0 rework, including the 32-bit `arm32` / `arm32v6` builds.
3. **Registry entry** in `docs/plugins.octoprint.org/` needs screenshots and a check against the current registry template before the PR.
4. Settings from 0.2.x (`plugins.pangolin`) are not migrated.

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

On macOS the plugin picks the linux `arm64` asset, which cannot run. To test locally, copy the darwin Newt binary to `<basedir>/data/pangolin_newt/bin/newt` and write the pinned arm64 sha256 to `bin/newt.sha256`.

Run tests with `pip install -e ".[develop]" && pytest`.

## Conventions

- Python 3.7+ compatible (`__plugin_pythoncompat__ = ">=3.7,<4"`)
- No em dashes in prose or documentation
- Keep the user-facing setup to: install plugin, enter endpoint, ID and secret, save. Do not add steps that need a terminal.
