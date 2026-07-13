"""Process identity, monitoring, and full process-tree termination helpers."""

from __future__ import annotations

import os
import signal
import time
from typing import Any, Dict, Iterable, List, Optional

try:
    import psutil
except Exception:  # pragma: no cover - psutil is part of the supported env.
    psutil = None


def _safe_cmdline(process) -> List[str]:
    try:
        return [str(item) for item in process.cmdline()]
    except Exception:
        return []


def process_identity(pid: Optional[int]) -> Dict[str, Any]:
    if not pid or not psutil:
        return {"pid": int(pid or 0), "exists": False}
    try:
        process = psutil.Process(int(pid))
        return {
            "pid": int(pid),
            "exists": process.is_running(),
            "create_time": float(process.create_time()),
            "name": process.name(),
            "cmdline": _safe_cmdline(process),
        }
    except Exception:
        return {"pid": int(pid), "exists": False}


def is_process_identity_alive(identity: Optional[Dict[str, Any]], *, create_time_tolerance: float = 1.0) -> bool:
    if not identity or not identity.get("pid") or not psutil:
        return False
    try:
        process = psutil.Process(int(identity["pid"]))
        if not process.is_running():
            return False
        expected = identity.get("create_time")
        if expected is not None and abs(float(process.create_time()) - float(expected)) > create_time_tolerance:
            return False
        return True
    except Exception:
        return False


def process_group_id(pid: Optional[int]) -> Optional[int]:
    if not pid or os.name == "nt":
        return None
    try:
        return int(os.getpgid(int(pid)))
    except Exception:
        return None


def process_tree(pid: int) -> List[Any]:
    if not pid or not psutil:
        return []
    try:
        root = psutil.Process(int(pid))
        return [root] + root.children(recursive=True)
    except Exception:
        return []


def _pids(processes: Iterable[Any]) -> List[int]:
    values = []
    for process in processes:
        try:
            values.append(int(process.pid))
        except Exception:
            pass
    return values


def sample_process_tree(pid: Optional[int]) -> Dict[str, Any]:
    processes = process_tree(int(pid or 0))
    rss = 0
    cpu = 0.0
    alive = []
    for process in processes:
        try:
            if process.is_running():
                alive.append(int(process.pid))
            rss += int(process.memory_info().rss)
            times = process.cpu_times()
            cpu += float(times.user + times.system)
        except Exception:
            continue
    return {
        "pid": int(pid or 0),
        "process_count": len(processes),
        "alive_pids": alive,
        "rss_bytes": rss,
        "cpu_seconds": cpu,
        "sampled_at_epoch": time.time(),
    }


def terminate_process_tree(
    pid: Optional[int],
    *,
    process_group: Optional[int] = None,
    grace_seconds: float = 5.0,
    reason: str = "terminate",
) -> Dict[str, Any]:
    pid = int(pid or 0)
    started = time.time()
    report: Dict[str, Any] = {
        "requested_pid": pid,
        "process_group_id": process_group,
        "reason": reason,
        "started_at_epoch": started,
        "grace_seconds": float(grace_seconds),
        "found": False,
        "terminated_pids": [],
        "killed_pids": [],
        "alive_pids": [],
        "method": "psutil_process_tree" if psutil else "os_signal_fallback",
        "duration_seconds": 0.0,
    }
    if not pid:
        return report

    processes = process_tree(pid)
    report["found"] = bool(processes)
    if not processes:
        return report

    if os.name != "nt" and process_group:
        try:
            os.killpg(int(process_group), signal.SIGTERM)
        except Exception:
            pass

    for process in reversed(processes):
        try:
            process.terminate()
            report["terminated_pids"].append(int(process.pid))
        except Exception:
            pass

    gone, alive = psutil.wait_procs(processes, timeout=float(grace_seconds)) if psutil else ([], [])
    if alive and os.name != "nt" and process_group:
        try:
            os.killpg(int(process_group), signal.SIGKILL)
        except Exception:
            pass

    for process in alive:
        try:
            process.kill()
            report["killed_pids"].append(int(process.pid))
        except Exception:
            pass

    if alive and psutil:
        _gone, alive = psutil.wait_procs(alive, timeout=2.0)

    still_alive = []
    for process in alive:
        try:
            if process.is_running():
                still_alive.append(int(process.pid))
        except Exception:
            pass
    report["alive_pids"] = still_alive
    report["duration_seconds"] = time.time() - started
    return report
