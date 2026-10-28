# Privacy Policy

Last updated: 2026-10-28

This policy covers the OctoPrint plugin **Pangolin Newt Client** (`OctoPrint-PangolinNewt`). It explains which data the plugin handles, where that data goes and which third parties are involved.

## Summary

- The plugin author does not run any server and receives no data from your installation. There is no tracking, analytics or telemetry in the plugin.
- The plugin exists to connect your OctoPrint to a [Pangolin](https://pangolin.net) server. Everything you access through that tunnel passes through the Pangolin server you configure.
- The plugin downloads the Newt client from GitHub. Newt itself contacts the Pangolin server and Fossorial (the company behind Pangolin) to check for updates.

## Data stored on your device

- **Pangolin endpoint, Newt ID and Newt secret**: stored in OctoPrint's `config.yaml`, like any other plugin setting. The secret is never sent back to the browser and is passed to Newt through its environment, not its command line.
- **Newt binary**: stored in OctoPrint's plugin data folder (`~/.octoprint/data/pangolin_newt/`).
- **Newt log**: the last 200 lines of Newt's output are kept in memory for the sidebar and are also written to `octoprint.log`. The log contains connection details such as the endpoint and server addresses, but not the Newt secret.

Removing the plugin and its data folder removes all of this.

## Data sent to third parties

### Your Pangolin server

When the tunnel is enabled, Newt connects to the endpoint you entered (Pangolin Cloud at `https://app.pangolin.net` by default, or your own self-hosted server). It sends:

- the Newt ID and secret, to authenticate the site,
- your device's public IP address, as with any network connection,
- Newt's version and platform, including during its periodic update check (every 6 hours),
- all traffic for the resources you expose through Pangolin, for example the OctoPrint web interface, webcam streams and uploaded files.

If you use Pangolin Cloud, Fossorial processes this data under the [Pangolin privacy policy](https://pangolin.net/privacy). If you host Pangolin yourself, the data stays with your own server and you are its operator.

### Fossorial versions API

Each time Newt starts, it fetches `https://api.fossorial.io/api/v1/versions` to show an "update available" notice in its log. This request reveals your public IP address and does not include your Newt ID or secret. See the [Pangolin privacy policy](https://pangolin.net/privacy).

### GitHub

- The plugin downloads the Newt binary from [Newt's GitHub releases](https://github.com/fosrl/newt/releases) on first install and when you click Reinstall.
- When Newt updates itself, it downloads the new binary from the URL your Pangolin server provides, which is normally GitHub as well.
- OctoPrint's Software Update checks this plugin's [GitHub releases](https://github.com/Gulianrdgd/OctoPrint-PangolinNewt/releases) for new versions.

These requests reveal your public IP address to GitHub. See the [GitHub General Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## Metrics

Newt supports Prometheus metrics and OpenTelemetry export. Both are off by default and the plugin does not turn them on.

## Contact

Questions about this policy: open an issue at https://github.com/Gulianrdgd/OctoPrint-PangolinNewt/issues or email julianvanderhorst2001@googlemail.com.
