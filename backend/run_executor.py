"""Asynchronous run executor with local process workers.

This module intentionally keeps the queue implementation small and replaceable.
It persists truth in run manifests and uses in-memory process tracking only for
currently running local workers.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time
from typing import Dict, Optional

from project_store import ProjectStore
from run_manifest_schema import (
    STATUS_CANCEL_REQUESTED,
    STATUS_CANCELLED,
    STATUS_COMPILING,
    STATUS_CREATED,
    STATUS_INTERRUPTED,
    STATUS_POSTPROCESSING,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_STARTING,
    STATUS_VALIDATING,
    STATUS_WRITING_INPUT,
    TERMINAL_STATUSES,
    utc_now_iso,
)
from run_manifest_store import RunManifestStore
from run_service import RunService
from runtime_config import DEFAULT_RUNTIME_CONFIG, RuntimeConfig


ACTIVE_STATUSES = {
    STATUS_CREATED,
    STATUS_QUEUED,
    STATUS_STARTING,
    STATUS_VALIDATING,
    STATUS_COMPILING,
    STATUS_WRITING_INPUT,
    STATUS_RUNNING,
    STATUS_POSTPROCESSING,
    STATUS_CANCEL_REQUESTED,
}


def _worker_entry(project_root: str, project_id: str, run_id: str):
    store = ProjectStore(project_root)
    service = RunService(store)
    manifest = RunManifestStore(store).load(project_id, run_id)
    service.run(project_id, manifest["flow_model_id"], run_id=run_id)


class LocalProcessRunExecutor:
    def __init__(self, project_store=None, config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG):
        self.project_store = project_store or ProjectStore()
        self.run_store = RunManifestStore(self.project_store)
        self.config = config
        self._lock = threading.RLock()
        self._processes: Dict[str, mp.Process] = {}
        self._monitor_started = False
        self.recover_interrupted_runs()
        self._ensure_monitor()

    def submit(
        self,
        project_id: str,
        flow_model_id: str,
        *,
        keep_artifacts: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
    ):
        service = RunService(self.project_store, config=self.config)
        result = service.create_queued_run(
            project_id,
            flow_model_id,
            keep_artifacts=keep_artifacts,
            idempotency_key=idempotency_key,
        )
        manifest = result["manifest"]
        self._schedule()
        return {"manifest": manifest, "duplicate": result["duplicate"]}

    def cancel(self, project_id: str, run_id: str, *, reason: str = "cancel requested", source: str = "api"):
        with self._lock:
            manifest = self.run_store.load(project_id, run_id)
            if manifest.get("status") in TERMINAL_STATUSES:
                return {"manifest": manifest, "changed": False}
            if manifest.get("status") != STATUS_CANCEL_REQUESTED:
                manifest = self.run_store.transition(manifest, STATUS_CANCEL_REQUESTED)
                manifest.setdefault("executor", {})
                manifest["executor"]["cancel_requested_at"] = utc_now_iso()
                manifest["executor"]["cancel_reason"] = reason
                manifest["executor"]["cancel_source"] = source
                manifest = self.run_store.save(manifest)
            if run_id not in self._processes and manifest.get("status") == STATUS_CANCEL_REQUESTED:
                manifest = self.run_store.transition(manifest, STATUS_CANCELLED)
                manifest.setdefault("executor", {})["cancelled_at"] = utc_now_iso()
                manifest["error"] = {"code": "RUN_CANCELLED", "message": reason, "details": []}
                manifest = self.run_store.save(manifest)
            return {"manifest": manifest, "changed": True}

    def recover_interrupted_runs(self):
        recoverable = {
            STATUS_STARTING,
            STATUS_VALIDATING,
            STATUS_COMPILING,
            STATUS_WRITING_INPUT,
            STATUS_RUNNING,
            STATUS_POSTPROCESSING,
            STATUS_CANCEL_REQUESTED,
        }
        for manifest in self.run_store.iter_all():
            if manifest.get("status") not in recoverable:
                continue
            try:
                updated = self.run_store.transition(manifest, STATUS_INTERRUPTED)
                updated["error"] = {
                    "code": "RUN_INTERRUPTED",
                    "message": "Run was left non-terminal when the API process started.",
                    "details": [],
                }
                self.run_store.save(updated)
            except Exception:
                continue

    def _ensure_monitor(self):
        if self._monitor_started:
            return
        self._monitor_started = True
        thread = threading.Thread(target=self._monitor_loop, name="flopy-run-monitor", daemon=True)
        thread.start()

    def _monitor_loop(self):
        while True:
            try:
                self._reap_finished()
                self._schedule()
            except Exception:
                pass
            time.sleep(0.5)

    def _reap_finished(self):
        with self._lock:
            finished = [run_id for run_id, process in self._processes.items() if not process.is_alive()]
            for run_id in finished:
                process = self._processes.pop(run_id, None)
                if process:
                    process.join(timeout=0.1)
                try:
                    for manifest in self.run_store.iter_all():
                        if manifest.get("run_id") != run_id:
                            continue
                        if manifest.get("status") in TERMINAL_STATUSES:
                            break
                        updated = self.run_store.transition(manifest, STATUS_INTERRUPTED)
                        updated["error"] = {
                            "code": "RUN_WORKER_EXITED",
                            "message": "Run worker exited before writing a terminal manifest status.",
                            "details": [],
                        }
                        self.run_store.save(updated)
                        break
                except Exception:
                    pass

    def _schedule(self):
        with self._lock:
            self._reap_finished()
            available = max(0, int(self.config.max_concurrent_runs) - len(self._processes))
            if available <= 0:
                return
            for manifest in self.run_store.iter_all():
                if available <= 0:
                    break
                if manifest.get("status") != STATUS_QUEUED:
                    continue
                project_id = manifest["project_id"]
                if self._active_project_count(project_id) >= int(self.config.max_runs_per_project):
                    continue
                self._start(manifest)
                available -= 1

    def _start(self, manifest):
        manifest = self.run_store.transition(manifest, STATUS_STARTING)
        process = mp.Process(
            target=_worker_entry,
            args=(str(self.project_store.root), manifest["project_id"], manifest["run_id"]),
            name=f"flopy-{manifest['run_id']}",
            daemon=False,
        )
        process.start()
        manifest.setdefault("executor", {})
        manifest["executor"]["worker_pid"] = int(process.pid or 0)
        manifest["executor"]["type"] = "local_process"
        self.run_store.save(manifest)
        self._processes[manifest["run_id"]] = process

    def _active_project_count(self, project_id: str) -> int:
        count = 0
        for manifest in self.run_store.list_full(project_id):
            if manifest.get("status") in ACTIVE_STATUSES and manifest.get("run_id") in self._processes:
                count += 1
        return count

    def active_count(self):
        with self._lock:
            self._reap_finished()
            return len(self._processes)


def terminate_process_tree(pid: int):
    if not pid:
        return
    if os.name == "nt":
        import subprocess

        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
        return
    try:
        os.kill(pid, 15)
    except Exception:
        return
