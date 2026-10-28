"""Pin the latest Newt release into octoprint_pangolin_newt/newt_release.json.

Used by the newt-bump workflow. When the pinned Newt changes, the patch
version in pyproject.toml is bumped and the new plugin version is printed
(and written to $GITHUB_OUTPUT as `version=...`). Prints nothing and exits 0
when already up to date.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(ROOT, "octoprint_pangolin_newt", "newt_release.json")
PYPROJECT_PATH = os.path.join(ROOT, "pyproject.toml")
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


def bump_patch(pyproject_text):
    """Return (new_text, new_version) with the patch version incremented."""
    match = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"$', pyproject_text, re.M)
    if not match:
        raise ValueError("No version line found in pyproject.toml")
    major, minor, patch = (int(x) for x in match.groups())
    new_version = "%d.%d.%d" % (major, minor, patch + 1)
    new_text = (pyproject_text[:match.start()]
                + 'version = "%s"' % new_version
                + pyproject_text[match.end():])
    return new_text, new_version


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

    with open(PYPROJECT_PATH) as f:
        text, version = bump_patch(f.read())
    with open(PYPROJECT_PATH, "w") as f:
        f.write(text)

    print(version)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as f:
            f.write("version=%s\nnewt_version=%s\n" % (version, manifest["version"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
