import hashlib
import io
import os
import stat
import sys
import time

import pytest

from octoprint_pangolin_newt import newt


def wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.mark.parametrize("machine,arch", [
    ("aarch64", "arm64"),
    ("armv7l", "arm32"),
    ("armv8l", "arm32"),
    ("armv6l", "arm32v6"),
    ("x86_64", "amd64"),
    ("mips", None),
])
def test_detect_arch(machine, arch):
    assert newt.detect_arch(machine) == arch


def test_pinned_release_covers_every_arch():
    release = newt.load_pinned_release()
    for arch in ("arm64", "arm32", "arm32v6", "amd64"):
        asset = release["assets"][arch]
        assert asset["url"].endswith("/%s/%s" % (release["version"], asset["name"]))
        assert len(asset["sha256"]) == 64


def _opener(payload):
    def opener(req, timeout):
        return io.BytesIO(payload)
    return opener


def test_install_verifies_checksum(tmp_path):
    payload = b"#!/bin/sh\necho newt\n"
    asset = {"url": "https://example/newt", "sha256": hashlib.sha256(payload).hexdigest()}
    dest = str(tmp_path / "bin" / "newt")

    newt.install(asset, dest, lambda msg: None, opener=_opener(payload))

    assert open(dest, "rb").read() == payload
    assert os.stat(dest).st_mode & stat.S_IXUSR
    assert newt.installed_sha256(dest) == asset["sha256"]


def test_install_rejects_checksum_mismatch(tmp_path):
    asset = {"url": "https://example/newt", "sha256": "0" * 64}
    dest = str(tmp_path / "bin" / "newt")

    with pytest.raises(newt.InstallError):
        newt.install(asset, dest, lambda msg: None, opener=_opener(b"tampered"))

    assert not os.path.exists(dest)
    assert not os.path.exists(dest + ".tmp")


FAKE_NEWT = """#!/bin/sh
echo "fake newt id=$NEWT_ID endpoint=$PANGOLIN_ENDPOINT args=$*"
sleep 0.3
echo ok > "$HEALTH_FILE"
trap 'exit 0' TERM
while true; do sleep 0.1; done
"""


@pytest.fixture
def fake_newt(tmp_path):
    binary = tmp_path / "bin" / "newt"
    binary.parent.mkdir()
    binary.write_text(FAKE_NEWT)
    binary.chmod(0o755)
    (tmp_path / "bin" / "newt.sha256").write_text("x" * 64)
    proc = newt.NewtProcess(str(binary), str(tmp_path / "health"),
                            health_interval=0.05, notify_delay=0.01)
    yield proc
    proc.stop()


@pytest.mark.skipif(sys.platform == "win32", reason="needs /bin/sh")
def test_credentials_go_through_env_and_health_file_means_connected(fake_newt):
    ok, _ = fake_newt.start("my-id", "my-secret", "https://pangolin.example")
    assert ok
    assert fake_newt.state == newt.CONNECTING
    assert wait_for(lambda: fake_newt.state == newt.CONNECTED)

    lines = [entry["line"] for entry in fake_newt.snapshot()["log"]]
    assert "fake newt id=my-id endpoint=https://pangolin.example args=" in lines
    assert not any("my-secret" in line for line in lines)


@pytest.mark.skipif(sys.platform == "win32", reason="needs /bin/sh")
def test_restart_is_not_undone_by_old_process_exiting(fake_newt):
    for _ in range(10):
        fake_newt.stop()
        ok, _ = fake_newt.start("id", "secret", "https://pangolin.example")
        assert ok
    time.sleep(0.5)
    assert fake_newt.is_running()
    assert fake_newt.state in (newt.CONNECTING, newt.CONNECTED)


@pytest.mark.skipif(sys.platform == "win32", reason="needs /bin/sh")
def test_unexpected_exit_is_reported_as_error(fake_newt):
    with open(fake_newt.binary_path, "w") as f:
        f.write("#!/bin/sh\necho boom\nexit 3\n")
    fake_newt.start("id", "secret", "https://pangolin.example")
    assert wait_for(lambda: fake_newt.state == newt.ERROR)
    assert "code 3" in fake_newt.snapshot()["message"]


def test_snapshot_returns_only_new_lines(tmp_path):
    proc = newt.NewtProcess(str(tmp_path / "newt"), str(tmp_path / "health"), max_log=3)
    for i in range(5):
        proc.log("line %d" % i)
    snap = proc.snapshot()
    assert [e["line"] for e in snap["log"]] == ["line 2", "line 3", "line 4"]
    assert [e["line"] for e in proc.snapshot(since=4)["log"]] == ["line 4"]
    assert snap["last_line"] == 5


def test_start_without_binary_reports_not_installed(tmp_path):
    proc = newt.NewtProcess(str(tmp_path / "newt"), str(tmp_path / "health"))
    ok, _ = proc.start("id", "secret", "https://pangolin.example")
    assert not ok
    assert proc.state == newt.NOT_INSTALLED


@pytest.mark.skipif(sys.platform == "win32", reason="needs /bin/sh")
def test_newt_error_is_shown_while_connecting(fake_newt):
    with open(fake_newt.binary_path, "w") as f:
        f.write("#!/bin/sh\necho 'ERROR: 2026/10/28 13:11:34 No newt found with that newtId'\n"
                "trap 'exit 0' TERM\nwhile true; do sleep 0.1; done\n")
    fake_newt.start("id", "secret", "https://pangolin.example")
    assert wait_for(lambda: fake_newt.snapshot()["message"] == "No newt found with that newtId")
    assert fake_newt.state == newt.CONNECTING
