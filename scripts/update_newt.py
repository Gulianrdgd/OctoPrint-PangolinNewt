"""Pin the latest Newt release into octoprint_pangolin_newt/newt_release.json.

Run by hand before a plugin release. The pin only decides which Newt a fresh
install starts with: Newt updates itself afterwards. Prints the new Newt
version, or nothing when already up to date.
"""
import hashlib
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(ROOT, "octoprint_pangolin_newt", "newt_release.json")
RELEASES_URL = "https://api.github.com/repos/fosrl/newt/releases/latest"

# manifest arch key -> release asset name
ASSETS = {
    "amd64": "newt_linux_amd64",
    "arm64": "newt_linux_arm64",
    "arm32": "newt_linux_arm32",
    "arm32v6": "newt_linux_arm32v6",
}


def _get(url):
    headers = {"User-Agent": "OctoPrint-PangolinNewt"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _sha256_of_url(url):
    return hashlib.sha256(_get(url)).hexdigest()


def build_manifest(release, hash_url=_sha256_of_url):
    """Turn a GitHub release API response into the pinned manifest."""
    by_name = {a["name"]: a for a in release["assets"]}
    assets = {}
    for arch, name in ASSETS.items():
        asset = by_name.get(name)
        if asset is None:
            raise ValueError("Release %s has no asset %s" % (release["tag_name"], name))
        digest = asset.get("digest") or ""
        if digest.startswith("sha256:"):
            sha = digest[len("sha256:"):]
        else:
            sha = hash_url(asset["browser_download_url"])
        assets[arch] = {
            "name": name,
            "url": asset["browser_download_url"],
            "sha256": sha,
        }
    return {"version": release["tag_name"], "assets": assets}


def main():
    release = json.loads(_get(RELEASES_URL).decode())
    manifest = build_manifest(release)

    with open(MANIFEST_PATH) as f:
        current = json.load(f)
    if current == manifest:
        return 0

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(manifest["version"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
