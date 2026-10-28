# OctoPrint-Pangolin

Manage a [Pangolin](https://pangolin.net) **Newt** tunnel directly from OctoPrint, no terminal required.

## What it does

1. **Auto-downloads and installs the Newt binary** on first run (detects Pi architecture automatically)
2. **Starts Newt automatically** when OctoPrint boots (optional)
3. Adds a **sidebar widget** showing connection status, a live log, and Start/Stop/Restart buttons
4. Adds a **settings page** where you enter your Newt ID, secret and endpoint

## Setup

1. Install the plugin via OctoPrint's Plugin Manager → "Get More" → paste the URL:
   ```
   https://github.com/yourusername/OctoPrint-Pangolin/archive/main.zip
   ```
2. Restart OctoPrint when prompted
3. Go to **Settings → Pangolin Newt** and fill in:
   - **Pangolin Endpoint** (leave as `https://app.pangolin.net` for Pangolin Cloud)
   - **Newt ID**: from your Pangolin dashboard (Sites → your site)
   - **Newt Secret**: same place (shown only once when you create the site)
4. Save. The plugin downloads Newt and starts it automatically.

That's it. Your OctoPrint is now accessible via Pangolin.

## Sidebar

The **Pangolin** sidebar entry shows:
- 🟢 Connected / ⚫ Stopped / 🟡 Installing / 🔴 Error
- Start / Stop / Restart controls
- Live log output from Newt (last 50 lines, refreshed every 10 s)
- "Install now" button if Newt isn't installed yet

## Supported platforms

| Architecture | Pi model |
|---|---|
| `arm64` / `aarch64` | Pi 3 / 4 / 5 (64-bit OS) |
| `armv7l` | Pi 2 / 3 (32-bit OS) |
| `amd64` / `x86_64` | x86 server/desktop |

## Notes

- The Newt binary is installed to `/usr/local/bin/newt`. On OctoPi the `pi` user may need `sudo` rights to write there. The plugin tries `sudo mv` automatically if a direct write fails.
- Your Newt secret is stored in OctoPrint's `config.yaml` (the same file that holds your API key).
