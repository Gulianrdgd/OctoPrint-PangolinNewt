# Pangolin Newt Client for OctoPrint

Reach your OctoPrint from anywhere through [Pangolin](https://pangolin.net), without opening ports and without touching a terminal.

The plugin downloads Pangolin's **Newt** client, verifies its checksum, runs it alongside OctoPrint and shows the tunnel status in the sidebar.

## Setup

1. In OctoPrint, open **Settings → Plugin Manager → Get More**, search for **Pangolin Newt Client** and install it. You can also install it from this URL:
   ```
   https://github.com/Gulianrdgd/OctoPrint-PangolinNewt/archive/main.zip
   ```
2. Restart OctoPrint when prompted.
3. In your Pangolin dashboard, open **Sites** and add a site of type **Newt**. Copy the **Newt ID** and **Newt secret**. The secret is shown only once.
4. In OctoPrint, open **Settings → Pangolin Newt Client**, paste both values and click **Save**.

The tunnel comes up within a few seconds. Leave the endpoint at `https://app.pangolin.net` unless you host Pangolin yourself. The endpoint must use https.

## Sidebar

- Status: Connected, Connecting (with Newt's last error, if any), Stopped, Installing or Error
- Start, Stop and Restart buttons
- Live Newt log

The sidebar and the status block in the settings are only shown to administrators.

## Updates

On first install the plugin downloads the Newt version pinned in the plugin release and verifies its sha256 checksum. After that Newt updates itself: every 6 hours it asks your Pangolin server for the latest version and replaces its own binary when there is a newer one. The plugin keeps an installed Newt as it is, so a plugin update never downgrades it. **Reinstall** puts the pinned version back.

Plugin updates arrive through OctoPrint's Software Update.

## Supported platforms

| `uname -m` | Newt build | Typical device |
|---|---|---|
| `aarch64` | `arm64` | Pi 3 / 4 / 5 with a 64-bit OS |
| `armv7l` | `arm32` | Pi 2 / 3 / 4 with a 32-bit OS |
| `armv6l` | `arm32v6` | Pi Zero / Pi 1 |
| `x86_64` | `amd64` | x86 servers and PCs |

## Notes

- Newt is installed inside OctoPrint's plugin data folder (`~/.octoprint/data/pangolin_newt/bin/newt`). It does not need root or sudo.
- The Newt secret is stored in OctoPrint's `config.yaml`. It is never sent back to the browser and is passed to Newt through its environment, not its command line.
- Upgrading from 0.2.x (`OctoPrint-Pangolin`): uninstall the old plugin, install this one and enter your ID and secret again. You can delete the old `/usr/local/bin/newt`.

## Development

```bash
pip install -e ".[develop]"
pytest
```

`scripts/update_newt.py` pins the latest Newt release into `octoprint_pangolin_newt/newt_release.json`. Run it by hand before a release when fresh installs should start with a newer Newt.

To release, bump `version` in `pyproject.toml`, commit and push a tag with the same version (no `v`). `.github/workflows/release.yml` tests, builds and publishes the GitHub release.

## Privacy

See [PRIVACY.md](PRIVACY.md) for the data the plugin and Newt send to Pangolin, Fossorial and GitHub.

## License

AGPL-3.0-or-later
