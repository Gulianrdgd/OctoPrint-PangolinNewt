# CSRF and socket errors behind Pangolin on OctoPi

Investigated 2026-11-23 and 2026-11-24.

## Symptoms

Through the Pangolin URL, on OctoPrint 2.0 on an OctoPi:

1. Login shows "CSRF protection error. Reloading the page might fix this." Reloading does not help.
2. After the login is fixed, the UI shows "Socket connection failed" and Firefox logs `NS_ERROR_WEBSOCKET_CONNECTION_REFUSED` for `wss://<host>/sockjs/.../websocket`.

Login and the UI work fine on the local network over http.

## Fix

In Pangolin, open the resource for OctoPrint, go to the **Proxy** tab and add a custom **request** header (not a response header):

```
X-Scheme: https
```

Confirmed working on the real setup on 2026-11-24. It fixes both symptoms and needs no change on the Pi. The README and the plugin settings page now list it as a setup step.

## Cause

The plugin and Newt are not involved: Newt only tunnels the traffic and never touches HTTP headers.

The request path on an OctoPi is:

1. Browser over https to Pangolin's Traefik, which sets `X-Forwarded-Proto: https` and `X-Forwarded-Host`, but no `X-Scheme`.
2. Newt hands it to HAProxy on port 80. Because that hop is plain http, HAProxy adds `X-Scheme: http`. It only does this when the request has no `X-Scheme` yet (`needs_scheme` acl in OctoPi's `haproxy.2.x.cfg`).
3. OctoPrint receives both `X-Forwarded-Proto: https` and `X-Scheme: http`.

OctoPrint reads the scheme in two places, and both end up with http.

**CSRF cookie (Flask layer).** On every page load the server sets a cookie named `csrf_token_P<port>`. The port comes from the forwarded host and scheme, so https gives 443 and http gives 80. The browser script works out the cookie name from the address bar (`https://` gives `csrf_token_P443`) and sends the value back as `X-CSRF-Token`. If the names differ, no header is sent and the login POST fails with HTTP 400.

OctoPrint 2.0.0 (released 2026-11-16) changed the default of `server.reverseProxy.schemeHeader` from unset to `"X-Scheme"` in commit `ac2998d` ("docs: improve config docs", 2025-10-21).

- **1.11.x:** unset meant OctoPrint checked `X-Forwarded-Proto` first, then `X-Scheme`.
- **2.0.x:** it reads only `X-Scheme`.

The same commit changed `prefixHeader` to `X-Script-Name` only (it used to also accept `X-Forwarded-Prefix`). See `src/octoprint/schema/config/server.py` and `ReverseProxiedEnvironment` in `src/octoprint/server/util/flask.py`.

**Websocket (Tornado layer).** `fix_tornado_xheader_handling` in `src/octoprint/server/util/tornado.py` sets the request protocol from `X-Scheme` first, then `X-Forwarded-Proto`, and no setting changes that order. The websocket origin check (`fix_websocket_check_origin`) compares the browser's `Origin` (`https://...:443`) with the request URL (`http://...:80`), refuses the handshake with 403, and `websocket_allow_origin` is empty unless CORS is enabled. 1.11.8 behaves the same here.

## Reproduction

`curl` against a local `octoprint serve`, with `X-Forwarded-Host: octo.example.com` and `X-Forwarded-Proto: https`:

| Version and headers | CSRF cookie | Websocket handshake |
|---|---|---|
| 1.11.8, plus `X-Scheme: http` (HAProxy) | `csrf_token_P443` | 403 |
| 2.0.1, plus `X-Scheme: http` (HAProxy) | `csrf_token_P80` | 403 |
| 2.0.1, plus `X-Scheme: https` (Pangolin header) | `csrf_token_P443` | 101 |
| 2.0.1, no `X-Scheme` (Pangolin target port 5000) | `csrf_token_P443` | 101 |

Not explained: why the UI worked through Pangolin on 1.11 when its websocket handshake is refused too. The SockJS fallback transports (`xhr_streaming`, `xhr`) answer 200 on both versions and the client socket code did not change.

## Other workarounds (not needed with the header)

- **`schemeHeader` setting.** `octoprint config set server.reverseProxy.schemeHeader X-Forwarded-Proto` (or `null`) fixes only the CSRF cookie, not the websocket. It is set on the real Pi from testing and is harmless with the header in place. Tested: LAN http and LAN https through HAProxy still get the right cookie.
- **Pangolin target port 5000.** Skips HAProxy, which fixes both, but loses HAProxy's `/webcam/` routing.
- **Running a shell command without SSH.** OctoPrint runs **Settings → Server → Commands → Restart OctoPrint** through a shell, so a command can be swapped in temporarily and triggered from the System menu. Restore `sudo service octoprint restart` afterwards; an empty field removes the menu entry.
- **SSH password on OctoPi.** The image ships `/etc/init.d/change_password`, which sets the `pi` password from `octopi-password.txt` on the boot partition and then deletes the file. It only works for a user named `pi`.

## Debugging

`https://<host>/reverse_proxy_test/` compares client and server cookie suffixes and lists the received headers. `octoprint.log` logs `CSRF validation failed for POST /api/login from <ip>`.

## Open follow-ups

- Upstream: the 2.0 `schemeHeader` default is a behaviour change hidden in a docs commit, and the Tornado layer prefers `X-Scheme` over `X-Forwarded-Proto`. Neither is reported upstream as of 2026-11-24. A possible issue: when both headers are present and disagree, OctoPrint should prefer `X-Forwarded-Proto`, or OctoPi's HAProxy should derive `X-Scheme` from it.

## Sources

- [OctoPrint FAQ: can't log in behind a reverse proxy since 1.8.3](https://community.octoprint.org/t/i-can-no-longer-login-after-upgrading-to-1-8-3-and-im-accessing-octoprint-through-a-reverse-proxy/46843)
- [OctoPrint #4740: CSRF cookie port suffix mismatch](https://github.com/OctoPrint/OctoPrint/issues/4740)
- [Reverse proxy configuration guide](https://community.octoprint.org/t/reverse-proxy-configuration/1107)
- [OctoPrint 1.8.4 release (adds `/reverse_proxy_test/`)](https://octoprint.org/blog/2022/09/27/new-release-1.8.4/)
- [config.yaml docs](https://docs.octoprint.org/en/dev/configuration/config_yaml.html)
- [Pangolin docs: resource targets and proxy settings](https://docs.pangolin.net/manage/resources/public/targets)
- OctoPrint source: commit `ac2998d`, `src/octoprint/server/util/tornado.py`
- OctoPi: `src/modules/octopi/filesystem/root/etc/haproxy/haproxy.2.x.cfg`, `src/modules/octopi/filesystem/root/etc/init.d/change_password`
