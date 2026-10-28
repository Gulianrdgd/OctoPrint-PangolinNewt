---
layout: plugin

id: pangolin_newt
title: Pangolin Newt Client
description: Reach OctoPrint from anywhere through Pangolin. Installs, verifies and runs the Newt tunnel client for you.
authors:
- Julian van der Horst
license: AGPLv3

date: 2026-10-28

homepage: https://github.com/Gulianrdgd/OctoPrint-PangolinNewt
source: https://github.com/Gulianrdgd/OctoPrint-PangolinNewt
archive: https://github.com/Gulianrdgd/OctoPrint-PangolinNewt/archive/main.zip

tags:
- remote access
- tunnel
- pangolin
- wireguard

screenshots:
- url: /assets/img/plugins/pangolin_newt/sidebar.png
  alt: Sidebar showing the tunnel status, controls and Newt log
  caption: Sidebar
- url: /assets/img/plugins/pangolin_newt/settings.png
  alt: Settings page with status, version and connection fields
  caption: Settings

featuredimage: /assets/img/plugins/pangolin_newt/sidebar.png

compatibility:
  octoprint:
  - 1.10.0
  os:
  - linux
  python: ">=3.7,<4"

---

Makes your OctoPrint reachable through [Pangolin](https://pangolin.net) without opening ports and without a terminal.

Enter your Pangolin endpoint, Newt ID and Newt secret in the settings and save. The plugin downloads the matching
[Newt](https://github.com/fosrl/newt) build for your Pi, verifies its sha256 checksum and keeps it running alongside
OctoPrint. The sidebar shows whether the tunnel is connected, along with Start, Stop and Restart buttons and Newt's live log.

New Newt releases are shipped as plugin updates through OctoPrint's Software Update.
