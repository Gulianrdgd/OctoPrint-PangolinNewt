import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
import update_newt  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "newt_release_1.19.0.json")


@pytest.fixture
def release():
    with open(FIXTURE) as f:
        return json.load(f)


def test_manifest_matches_pinned_file(release):
    with open(update_newt.MANIFEST_PATH) as f:
        pinned = json.load(f)
    manifest = update_newt.build_manifest(release)
    assert manifest["version"] == "1.19.0"
    # The pinned file was generated from this fixture
    assert manifest == pinned


def test_asset_without_digest_is_hashed(release):
    for asset in release["assets"]:
        asset.pop("digest")
    seen = []

    def fake_hash(url):
        seen.append(url)
        return "a" * 64

    manifest = update_newt.build_manifest(release, hash_url=fake_hash)
    assert len(seen) == 4
    assert manifest["assets"]["arm64"]["sha256"] == "a" * 64


def test_missing_asset_fails(release):
    release = copy.deepcopy(release)
    release["assets"] = [a for a in release["assets"] if a["name"] != "newt_linux_arm32"]
    with pytest.raises(ValueError):
        update_newt.build_manifest(release)


def test_bump_patch():
    text = '[project]\nname = "x"\nversion = "0.3.9"\n'
    new_text, version = update_newt.bump_patch(text)
    assert version == "0.3.10"
    assert 'version = "0.3.10"' in new_text
    assert 'name = "x"' in new_text
