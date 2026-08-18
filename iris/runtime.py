"""Local runtime ownership and observable daemon health for Iris."""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import shutil
import socket
import threading
import time
import uuid


@dataclasses.dataclass(frozen=True)
class RuntimeStatus:
    pid: int
    boot_id: str
    state: str
    updated_at: float
    last_inbound_at: float | None = None
    last_outbound_at: float | None = None
    last_error: str | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "RuntimeStatus":
        return cls(**value)


class StatusStore:
    """Atomically replace runtime state; a partial file is never a verdict."""

    def __init__(self, path: pathlib.Path | str, *, clock=time.time):
        self.path = pathlib.Path(path)
        self._clock = clock

    def write(self, status: RuntimeStatus) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(dataclasses.asdict(status), sort_keys=True))
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def read(self) -> RuntimeStatus | None:
        try:
            return RuntimeStatus.from_dict(json.loads(self.path.read_text()))
        except (FileNotFoundError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def healthy(self, *, max_age: float = 90.0) -> bool:
        status = self.read()
        return bool(status and status.state == "online" and self._clock() - status.updated_at <= max_age)


class SingleInstanceLock:
    """An age-first lock that cannot be wedged by PID reuse after a crash."""

    def __init__(self, path: pathlib.Path | str, *, clock=time.time, pid=os.getpid):
        self.path = pathlib.Path(path)
        self._clock = clock
        self._pid = pid
        self.acquired = False

    def acquire(self, *, max_age: float = 300.0) -> bool:
        try:
            self.path.mkdir(parents=True)
        except FileExistsError:
            if not self._stale(max_age=max_age):
                return False
            shutil.rmtree(self.path, ignore_errors=True)
            try:
                self.path.mkdir(parents=True)
            except FileExistsError:
                return False
        (self.path / "pid").write_text(str(self._pid()))
        self.acquired = True
        return True

    def release(self) -> None:
        if self.acquired:
            shutil.rmtree(self.path, ignore_errors=True)
            self.acquired = False

    def _stale(self, *, max_age: float) -> bool:
        try:
            age = self._clock() - self.path.stat().st_mtime
        except FileNotFoundError:
            return True
        if age > max_age:
            return True
        try:
            pid = int((self.path / "pid").read_text())
            os.kill(pid, 0)
        except (FileNotFoundError, ValueError, ProcessLookupError):
            return True
        except PermissionError:
            return False
        return False


class RuntimeSupervisor:
    """Records online/offline transitions while a single daemon owns Socket Mode."""

    def __init__(self, state_dir: pathlib.Path | str, *, store=None, lock=None, clock=time.time,
                 pid=os.getpid, boot_id=None):
        directory = pathlib.Path(state_dir)
        self._clock = clock
        self.store = store or StatusStore(directory / "runtime.json", clock=clock)
        self.lock = lock or SingleInstanceLock(directory / "runtime.lock", clock=clock, pid=pid)
        self._pid = pid
        self.boot_id = boot_id or uuid.uuid4().hex
        self.state = "starting"
        self.last_inbound_at: float | None = None
        self.last_outbound_at: float | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def start(self) -> bool:
        if not self.lock.acquire():
            return False
        self._write("starting")
        return True

    def connected(self) -> None:
        self._write("online")

    def disconnected(self, error: Exception | None = None) -> None:
        self._write("offline", type(error).__name__ if error else None)

    def inbound(self) -> None:
        self.last_inbound_at = self._clock()
        self._write(self.state)

    def outbound(self) -> None:
        self.last_outbound_at = self._clock()
        self._write(self.state)

    def heartbeat(self) -> None:
        self._write(self.state)

    def start_heartbeat(self, *, interval: float = 20.0) -> None:
        if self._heartbeat_thread is not None:
            return

        def run() -> None:
            while not self._heartbeat_stop.wait(interval):
                self.heartbeat()

        self._heartbeat_thread = threading.Thread(target=run, daemon=True, name="iris-runtime-heartbeat")
        self._heartbeat_thread.start()

    def close(self, error: Exception | None = None) -> None:
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1)
        self.disconnected(error)
        self.lock.release()

    def _write(self, state: str, error: str | None = None) -> None:
        self.state = state
        self.store.write(RuntimeStatus(self._pid(), self.boot_id, state, self._clock(),
                                       self.last_inbound_at, self.last_outbound_at, error))
