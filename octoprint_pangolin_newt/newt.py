"""Newt installer and process manager. No OctoPrint imports, so it can be tested standalone."""
import collections
import hashlib
import json
import os
import platform
import re
import subprocess
import threading
import time
import urllib.request

PINNED_RELEASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "newt_release.json")

# States reported to the UI
NOT_INSTALLED = "not_installed"
INSTALLING = "installing"
STOPPED = "stopped"
CONNECTING = "connecting"
CONNECTED = "connected"
ERROR = "error"

# "ERROR: 2026/10/28 13:11:34 Failed to connect: ..." -> "Failed to connect: ..."
_ERROR_LINE = re.compile(r"^ERROR: \S+ \S+ (.*)$")


class InstallError(Exception):
    pass


def detect_arch(machine=None):
    """Map platform.machine() to a key in newt_release.json, or None if unsupported."""
    machine = (machine or platform.machine()).lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    if machine in ("armv7l", "armv8l"):
        return "arm32"
    if machine == "armv6l":
        return "arm32v6"
    if machine in ("x86_64", "amd64"):
        return "amd64"
    return None


def load_pinned_release(path=PINNED_RELEASE_PATH):
    with open(path) as f:
        return json.load(f)


def installed_sha256(binary_path):
    """The sha256 recorded when the binary was installed, or None."""
    if not (os.path.isfile(binary_path) and os.access(binary_path, os.X_OK)):
        return None
    try:
        with open(binary_path + ".sha256") as f:
            return f.read().strip()
    except OSError:
        return None


def install(asset, binary_path, log, opener=urllib.request.urlopen):
    """Download asset["url"], verify asset["sha256"] and move it to binary_path."""
    os.makedirs(os.path.dirname(binary_path), exist_ok=True)
    tmp_path = binary_path + ".tmp"
    log("Downloading %s ..." % asset["url"])
    sha = hashlib.sha256()
    try:
        req = urllib.request.Request(asset["url"], headers={"User-Agent": "OctoPrint-PangolinNewt"})
        with opener(req, timeout=120) as resp, open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                sha.update(chunk)
                f.write(chunk)
    except Exception as e:
        _remove(tmp_path)
        raise InstallError("Download failed: %s" % e)

    if sha.hexdigest() != asset["sha256"]:
        _remove(tmp_path)
        raise InstallError("Checksum mismatch: expected %s, got %s" % (asset["sha256"], sha.hexdigest()))

    os.chmod(tmp_path, 0o755)
    os.replace(tmp_path, binary_path)
    with open(binary_path + ".sha256", "w") as f:
        f.write(asset["sha256"])
    log("Checksum verified, Newt installed at %s" % binary_path)


def binary_version(binary_path):
    """First line of `newt --version`, or None."""
    try:
        out = subprocess.run([binary_path, "--version"], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=10, universal_newlines=True)
        lines = out.stdout.strip().splitlines()
        return lines[0].strip() if lines else None
    except Exception:
        return None


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


class NewtProcess(object):
    """Runs Newt as a child process and tracks its state and output.

    Every start bumps `generation`; threads belonging to an older process never
    touch the state, so a restart cannot be undone by the old process exiting.
    """

    def __init__(self, binary_path, health_path, on_change=None, logger=None,
                 max_log=200, health_interval=2.0, notify_delay=0.25):
        self.binary_path = binary_path
        self.health_path = health_path
        self._on_change = on_change
        self._logger = logger
        self._health_interval = health_interval
        self._notify_delay = notify_delay

        self._lock = threading.RLock()
        self._proc = None
        self._generation = 0
        self._state = STOPPED
        self._message = ""
        self._log = collections.deque(maxlen=max_log)
        self._line_no = 0
        self._notify_timer = None

    # ---- state ----

    def snapshot(self, since=0):
        """State plus log lines numbered above `since`."""
        with self._lock:
            return {
                "state": self._state,
                "message": self._message,
                "log": [{"n": n, "line": line} for n, line in self._log if n > since],
                "last_line": self._line_no,
            }

    @property
    def state(self):
        with self._lock:
            return self._state

    def is_running(self):
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def set_state(self, state, message=""):
        with self._lock:
            if (state, message) == (self._state, self._message):
                return
            self._state = state
            self._message = message
        self._notify()

    def log(self, line):
        with self._lock:
            self._line_no += 1
            self._log.append((self._line_no, line))
        if self._logger:
            self._logger.info("[newt] %s", line)
        self._notify()

    def _notify(self):
        """Coalesce bursts of changes into one callback every notify_delay seconds."""
        if not self._on_change:
            return
        with self._lock:
            if self._notify_timer is not None:
                return
            self._notify_timer = threading.Timer(self._notify_delay, self._fire)
            self._notify_timer.daemon = True
            self._notify_timer.start()

    def _fire(self):
        with self._lock:
            self._notify_timer = None
        try:
            self._on_change()
        except Exception:
            if self._logger:
                self._logger.exception("Error in Newt state callback")

    # ---- process control ----

    def start(self, newt_id, newt_secret, endpoint):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return False, "Newt is already running."
            if installed_sha256(self.binary_path) is None:
                self._set_locked(NOT_INSTALLED, "")
                return False, "Newt is not installed yet."

            _remove(self.health_path)
            env = dict(os.environ)
            env.update({
                "NEWT_ID": newt_id,
                "NEWT_SECRET": newt_secret,
                "PANGOLIN_ENDPOINT": endpoint,
                "HEALTH_FILE": self.health_path,
            })
            try:
                proc = subprocess.Popen([self.binary_path], env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        universal_newlines=True, bufsize=1)
            except Exception as e:
                self._set_locked(ERROR, "Failed to start Newt: %s" % e)
                return False, self._message

            self._generation += 1
            gen = self._generation
            self._proc = proc
            self._set_locked(CONNECTING, "")

        threading.Thread(target=self._tail, args=(proc, gen), daemon=True,
                         name="pangolin-newt-tail").start()
        threading.Thread(target=self._watch_health, args=(proc, gen), daemon=True,
                         name="pangolin-newt-health").start()
        self.log("Newt started (endpoint: %s)" % endpoint)
        return True, "Newt started."

    def stop(self):
        with self._lock:
            proc = self._proc
            self._proc = None
            self._generation += 1
            if self._state in (CONNECTING, CONNECTED, ERROR):
                self._set_locked(STOPPED, "")
        if proc is None or proc.poll() is not None:
            return True, "Newt was not running."
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        _remove(self.health_path)
        self.log("Newt stopped.")
        return True, "Newt stopped."

    def _set_locked(self, state, message):
        # Caller holds the lock; notification is coalesced and fires later.
        if (state, message) != (self._state, self._message):
            self._state = state
            self._message = message
            self._notify()

    def _tail(self, proc, gen):
        try:
            for line in proc.stdout:
                line = line.rstrip()
                self.log(line)
                match = _ERROR_LINE.match(line)
                if match:
                    # Show why the tunnel is not coming up while still connecting
                    with self._lock:
                        if gen == self._generation and self._state == CONNECTING:
                            self._set_locked(CONNECTING, match.group(1))
        except Exception:
            pass
        code = proc.wait()
        with self._lock:
            if gen != self._generation:
                return
            self._proc = None
            if code == 0:
                self._set_locked(STOPPED, "")
            else:
                self._set_locked(ERROR, "Newt exited with code %s." % code)

    def _watch_health(self, proc, gen):
        while proc.poll() is None:
            with self._lock:
                if gen != self._generation or self._proc is not proc:
                    return
                if os.path.exists(self.health_path):
                    self._set_locked(CONNECTED, "")
                elif self._state == CONNECTED:
                    self._set_locked(CONNECTING, "")
            time.sleep(self._health_interval)
