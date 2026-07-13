"""Asynchronous run executor with SQLite-backed single-machine claims."""

from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time
from typing import Dict, Optional

from process_control import is_process_identity_alive, process_identity, terminate_process_tree
from project_store import ProjectStore
from run_manifest_schema import (
    STATUS_CANCEL_REQUESTED,
    STATUS_CANCELLED,
    STATUS_COMPILING,
    STATUS_CREATED,
    STATUS_FAILED_CANCEL,
    STATUS_INTERRUPTED,
    STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
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
from run_scheduler import RunSchedulerStore, new_owner_id
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

WORKER_STATUSES = {
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
    run_store = RunManifestStore(store)
    try:
        manifest = run_store.load(project_id, run_id)
        manifest.setdefault("executor", {})
        manifest["executor"]["worker_pid"] = os.getpid()
        manifest["executor"]["worker_identity"] = process_identity(os.getpid())
        manifest = run_store.save(manifest)
    except Exception:
        manifest = RunManifestStore(store).load(project_id, run_id)
    service = RunService(store)
    service.run(project_id, manifest["flow_model_id"], run_id=run_id)


class LocalProcessRunExecutor:
    def __init__(
        self,
        project_store=None,
        config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG,
        *,
        auto_start: bool = True,
        recover_on_start: bool = True,
    ):
        self.project_store = project_store or ProjectStore()
        self.run_store = RunManifestStore(self.project_store)
        self.scheduler = RunSchedulerStore(self.project_store, config)
        self.config = config
        self.auto_start = bool(auto_start)
        self.owner_id = new_owner_id()
        self._lock = threading.RLock()
        self._processes: Dict[str, mp.Process] = {}
        self._claims: Dict[str, dict] = {}
        self._monitor_started = False
        if recover_on_start:
            self.recover_interrupted_runs()
        if self.auto_start:
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
        self.scheduler.enqueue(manifest)
        if self.auto_start:
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
            self.scheduler.cancel(run_id)

            cancel_started = time.time()
            reports = []
            process = self._processes.get(run_id)
            worker_pid = int((process.pid if process else None) or (manifest.get("executor") or {}).get("worker_pid") or 0)
            mf6_pid = int((manifest.get("executor") or {}).get("mf6_pid") or 0)

            if worker_pid:
                reports.append(
                    terminate_process_tree(
                        worker_pid,
                        grace_seconds=self.config.cancel_grace_seconds,
                        reason="cancel_worker_tree",
                    )
                )
            if mf6_pid and mf6_pid != worker_pid:
                reports.append(
                    terminate_process_tree(
                        mf6_pid,
                        process_group=(manifest.get("executor") or {}).get("process_group_id"),
                        grace_seconds=self.config.cancel_grace_seconds,
                        reason="cancel_mf6_tree",
                    )
                )

            if process:
                process.join(timeout=1.0)
                self._processes.pop(run_id, None)
                self._claims.pop(run_id, None)

            live_pids = [pid for report in reports for pid in report.get("alive_pids", [])]
            next_status = STATUS_FAILED_CANCEL if live_pids else STATUS_CANCELLED
            manifest = self.run_store.load(project_id, run_id)
            if manifest.get("status") not in TERMINAL_STATUSES:
                manifest = self.run_store.transition(manifest, next_status)
            manifest.setdefault("executor", {})
            manifest["executor"]["cancelled_at"] = utc_now_iso() if next_status == STATUS_CANCELLED else None
            manifest["executor"]["cancel_duration_seconds"] = time.time() - cancel_started
            manifest["executor"]["termination"] = {"reason": reason, "reports": reports}
            manifest["error"] = {
                "code": "RUN_CANCELLED" if next_status == STATUS_CANCELLED else "RUN_CANCEL_FAILED",
                "message": reason if next_status == STATUS_CANCELLED else "Cancel requested but some process IDs remained alive.",
                "details": {"alive_pids": live_pids},
            }
            manifest = self.run_store.save(manifest)
            return {"manifest": manifest, "changed": True}

    def recover_interrupted_runs(self):
        for manifest in self.run_store.iter_all():
            status = manifest.get("status")
            if status == STATUS_QUEUED:
                self.scheduler.enqueue(manifest)
                continue
            if status not in WORKER_STATUSES:
                continue
            try:
                recovered = self._recover_active_manifest(manifest)
                self.run_store.save(recovered)
                self.scheduler.finish(manifest["run_id"], recovered["status"])
            except Exception:
                continue

    def _recover_active_manifest(self, manifest):
        executor = manifest.get("executor") or {}
        reports = []
        worker_live = is_process_identity_alive(executor.get("worker_identity"))
        mf6_live = is_process_identity_alive(executor.get("mf6_identity"))
        if worker_live and executor.get("worker_pid"):
            reports.append(
                terminate_process_tree(
                    executor.get("worker_pid"),
                    grace_seconds=self.config.process_termination_grace_seconds,
                    reason="executor_recovery_worker",
                )
            )
        if mf6_live and executor.get("mf6_pid"):
            reports.append(
                terminate_process_tree(
                    executor.get("mf6_pid"),
                    process_group=executor.get("process_group_id"),
                    grace_seconds=self.config.process_termination_grace_seconds,
                    reason="executor_recovery_mf6",
                )
            )
        live_pids = [pid for report in reports for pid in report.get("alive_pids", [])]
        if live_pids:
            next_status = STATUS_INTERRUPTED_WITH_LIVE_PROCESS
            code = "RUN_INTERRUPTED_WITH_LIVE_PROCESS"
            message = "Executor recovery found process IDs that could not be terminated."
        elif manifest.get("status") == STATUS_CANCEL_REQUESTED:
            next_status = STATUS_CANCELLED
            code = "RUN_CANCELLED"
            message = "Cancel request was completed during executor recovery."
        else:
            next_status = STATUS_INTERRUPTED
            code = "RUN_INTERRUPTED"
            message = "Run was non-terminal when executor started; live processes were checked and terminated if present."
        updated = self.run_store.transition(manifest, next_status)
        updated.setdefault("executor", {})["termination"] = {"reason": "executor_recovery", "reports": reports}
        updated["error"] = {"code": code, "message": message, "details": {"live_pids": live_pids}}
        return updated

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
            time.sleep(float(self.config.scheduler_poll_interval_seconds))

    def _reap_finished(self):
        with self._lock:
            for run_id, claim in list(self._claims.items()):
                process = self._processes.get(run_id)
                if process and process.is_alive():
                    self.scheduler.heartbeat(run_id, owner_id=claim["owner_id"], lease_token=claim["lease_token"])
                    continue
                if not process:
                    continue
                self._processes.pop(run_id, None)
                self._claims.pop(run_id, None)
                process.join(timeout=0.1)
                try:
                    manifest = self._find_manifest_by_run_id(run_id)
                    if not manifest:
                        self.scheduler.finish(run_id, "terminal")
                        continue
                    if manifest.get("status") in TERMINAL_STATUSES:
                        self.scheduler.finish(run_id, manifest["status"])
                        continue
                    if manifest.get("status") == STATUS_CANCEL_REQUESTED:
                        updated = self.run_store.transition(manifest, STATUS_CANCELLED)
                        updated["error"] = {"code": "RUN_CANCELLED", "message": "Run worker exited after cancellation.", "details": []}
                    else:
                        updated = self.run_store.transition(manifest, STATUS_INTERRUPTED)
                        updated["error"] = {
                            "code": "RUN_WORKER_EXITED",
                            "message": "Run worker exited before writing a terminal manifest status.",
                            "details": {"exitcode": process.exitcode},
                        }
                    self.run_store.save(updated)
                    self.scheduler.finish(run_id, updated["status"])
                except Exception:
                    self.scheduler.finish(run_id, "unknown_finished")

    def _schedule(self):
        if not self.auto_start:
            return
        with self._lock:
            self._reap_finished()
            for manifest in self.run_store.iter_all():
                if manifest.get("status") != STATUS_QUEUED:
                    continue
                claim = self.scheduler.try_claim(
                    manifest,
                    owner_id=self.owner_id,
                    max_concurrent=self.config.max_concurrent_runs,
                    max_per_project=self.config.max_runs_per_project,
                    lease_seconds=self.config.scheduler_lease_seconds,
                )
                if not claim:
                    continue
                self._start(manifest, claim)

    def _start(self, manifest, claim):
        manifest = self.run_store.load(manifest["project_id"], manifest["run_id"])
        if manifest.get("status") != STATUS_QUEUED:
            self.scheduler.finish(manifest["run_id"], manifest.get("status", "not_queued"))
            return
        manifest = self.run_store.transition(manifest, STATUS_STARTING)
        manifest.setdefault("executor", {})
        manifest["executor"]["owner_id"] = claim["owner_id"]
        manifest["executor"]["lease_token"] = claim["lease_token"]
        manifest["executor"]["lease_expires_at"] = claim["lease_expires_at"]
        manifest["executor"]["type"] = "local_process"
        manifest = self.run_store.save(manifest)
        process = mp.Process(
            target=_worker_entry,
            args=(str(self.project_store.root), manifest["project_id"], manifest["run_id"]),
            name=f"flopy-{manifest['run_id']}",
            daemon=False,
        )
        process.start()
        manifest = self.run_store.load(manifest["project_id"], manifest["run_id"])
        manifest.setdefault("executor", {})
        manifest["executor"]["worker_pid"] = int(process.pid or 0)
        manifest["executor"]["worker_identity"] = process_identity(process.pid)
        manifest["executor"]["type"] = "local_process"
        self.run_store.save(manifest)
        self.scheduler.mark_running(
            manifest["run_id"],
            owner_id=claim["owner_id"],
            lease_token=claim["lease_token"],
            worker_pid=int(process.pid or 0),
        )
        self._processes[manifest["run_id"]] = process
        self._claims[manifest["run_id"]] = claim

    def _find_manifest_by_run_id(self, run_id: str):
        for manifest in self.run_store.iter_all():
            if manifest.get("run_id") == run_id:
                return manifest
        return None

    def active_count(self):
        with self._lock:
            self._reap_finished()
            return len(self._processes)

    def status(self):
        with self._lock:
            self._reap_finished()
            return {
                "executor_mode": "embedded" if self.auto_start else "queue_only",
                "owner_id": self.owner_id,
                "active_processes": len(self._processes),
                "scheduler": self.scheduler.stats(),
            }

    def serve_forever(self):
        self.auto_start = True
        self._ensure_monitor()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            return
