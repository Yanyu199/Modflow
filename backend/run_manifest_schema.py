"""Schema helpers and state machine for persistent run manifests."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is part of the backend deps.
    np = None


SCHEMA_NAME = "run_manifest"
SCHEMA_VERSION = "1.2"
RUN_ID_PATTERN = re.compile(r"^run_[0-9a-f]{16,32}$")

STATUS_CREATED = "created"
STATUS_QUEUED = "queued"
STATUS_STARTING = "starting"
STATUS_VALIDATING = "validating"
STATUS_COMPILING = "compiling"
STATUS_WRITING_INPUT = "writing_input"
STATUS_RUNNING = "running"
STATUS_POSTPROCESSING = "postprocessing"
STATUS_CANCEL_REQUESTED = "cancel_requested"
STATUS_COMPLETED = "completed"
STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
STATUS_CANCELLED = "cancelled"
STATUS_TIMED_OUT = "timed_out"
STATUS_INTERRUPTED = "interrupted"
STATUS_INTERRUPTED_WITH_LIVE_PROCESS = "interrupted_with_live_process"
STATUS_FAILED_CANCEL = "failed_cancel"
STATUS_FAILED_VALIDATION = "failed_validation"
STATUS_FAILED_COMPILE = "failed_compile"
STATUS_FAILED_EXECUTABLE = "failed_executable"
STATUS_FAILED_INPUT_WRITE = "failed_input_write"
STATUS_FAILED_EXECUTION = "failed_execution"
STATUS_FAILED_RESOURCE_LIMIT = "failed_resource_limit"
STATUS_FAILED_CONVERGENCE = "failed_convergence"
STATUS_FAILED_OUTPUTS = "failed_outputs"
STATUS_FAILED_BUDGET = "failed_budget"
STATUS_FAILED_POSTPROCESSING = "failed_postprocessing"

TERMINAL_STATUSES = {
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_WARNINGS,
    STATUS_CANCELLED,
    STATUS_TIMED_OUT,
    STATUS_INTERRUPTED,
    STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
    STATUS_FAILED_CANCEL,
    STATUS_FAILED_VALIDATION,
    STATUS_FAILED_COMPILE,
    STATUS_FAILED_EXECUTABLE,
    STATUS_FAILED_INPUT_WRITE,
    STATUS_FAILED_EXECUTION,
    STATUS_FAILED_RESOURCE_LIMIT,
    STATUS_FAILED_CONVERGENCE,
    STATUS_FAILED_OUTPUTS,
    STATUS_FAILED_BUDGET,
    STATUS_FAILED_POSTPROCESSING,
}

ALLOWED_TRANSITIONS = {
    STATUS_CREATED: {STATUS_QUEUED, STATUS_VALIDATING, STATUS_FAILED_VALIDATION},
    STATUS_QUEUED: {STATUS_STARTING, STATUS_CANCEL_REQUESTED, STATUS_FAILED_VALIDATION, STATUS_INTERRUPTED, STATUS_CANCELLED},
    STATUS_STARTING: {
        STATUS_VALIDATING,
        STATUS_CANCEL_REQUESTED,
        STATUS_FAILED_VALIDATION,
        STATUS_INTERRUPTED,
        STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
        STATUS_FAILED_CANCEL,
    },
    STATUS_VALIDATING: {
        STATUS_COMPILING,
        STATUS_FAILED_VALIDATION,
        STATUS_FAILED_EXECUTABLE,
        STATUS_CANCEL_REQUESTED,
        STATUS_INTERRUPTED,
        STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
        STATUS_FAILED_CANCEL,
        STATUS_FAILED_RESOURCE_LIMIT,
    },
    STATUS_COMPILING: {
        STATUS_WRITING_INPUT,
        STATUS_FAILED_COMPILE,
        STATUS_CANCEL_REQUESTED,
        STATUS_INTERRUPTED,
        STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
        STATUS_FAILED_CANCEL,
        STATUS_FAILED_RESOURCE_LIMIT,
    },
    STATUS_WRITING_INPUT: {
        STATUS_RUNNING,
        STATUS_FAILED_INPUT_WRITE,
        STATUS_CANCEL_REQUESTED,
        STATUS_INTERRUPTED,
        STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
        STATUS_FAILED_CANCEL,
        STATUS_FAILED_RESOURCE_LIMIT,
    },
    STATUS_RUNNING: {
        STATUS_POSTPROCESSING,
        STATUS_FAILED_EXECUTION,
        STATUS_FAILED_RESOURCE_LIMIT,
        STATUS_FAILED_CONVERGENCE,
        STATUS_CANCEL_REQUESTED,
        STATUS_TIMED_OUT,
        STATUS_INTERRUPTED,
        STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
        STATUS_FAILED_CANCEL,
    },
    STATUS_CANCEL_REQUESTED: {
        STATUS_CANCELLED,
        STATUS_TIMED_OUT,
        STATUS_INTERRUPTED,
        STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
        STATUS_FAILED_CANCEL,
        STATUS_FAILED_RESOURCE_LIMIT,
    },
    STATUS_POSTPROCESSING: {
        STATUS_COMPLETED,
        STATUS_COMPLETED_WITH_WARNINGS,
        STATUS_FAILED_CONVERGENCE,
        STATUS_FAILED_OUTPUTS,
        STATUS_FAILED_BUDGET,
        STATUS_FAILED_POSTPROCESSING,
        STATUS_CANCEL_REQUESTED,
        STATUS_INTERRUPTED,
        STATUS_INTERRUPTED_WITH_LIVE_PROCESS,
        STATUS_FAILED_CANCEL,
        STATUS_FAILED_RESOURCE_LIMIT,
    },
}

ERROR_BY_STATUS = {
    STATUS_FAILED_VALIDATION: "RUN_MODEL_CHECK_FAILED",
    STATUS_FAILED_COMPILE: "RUN_PACKAGE_COMPILE_FAILED",
    STATUS_FAILED_EXECUTABLE: "RUN_MF6_NOT_FOUND",
    STATUS_FAILED_INPUT_WRITE: "RUN_INPUT_WRITE_FAILED",
    STATUS_FAILED_EXECUTION: "RUN_MF6_NONZERO_EXIT",
    STATUS_FAILED_CONVERGENCE: "RUN_SOLVER_NOT_CONVERGED",
    STATUS_FAILED_OUTPUTS: "RUN_OUTPUT_MISSING",
    STATUS_FAILED_BUDGET: "RUN_BUDGET_OUT_OF_TOLERANCE",
    STATUS_FAILED_POSTPROCESSING: "RUN_POSTPROCESSING_FAILED",
    STATUS_CANCELLED: "RUN_CANCELLED",
    STATUS_TIMED_OUT: "RUN_TIMED_OUT",
    STATUS_INTERRUPTED: "RUN_INTERRUPTED",
    STATUS_INTERRUPTED_WITH_LIVE_PROCESS: "RUN_INTERRUPTED_WITH_LIVE_PROCESS",
    STATUS_FAILED_CANCEL: "RUN_CANCEL_FAILED",
    STATUS_FAILED_RESOURCE_LIMIT: "RUN_RESOURCE_LIMIT_EXCEEDED",
}


class RunManifestValidationError(ValueError):
    pass


class RunStateTransitionError(RunManifestValidationError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def generate_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:16]}"


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        raise RunManifestValidationError("run_id must match run_[0-9a-f]{16,32}")
    return run_id


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RunManifestValidationError("run manifest must not contain NaN or Infinity")
        return value
    if np is not None:
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            number = float(value)
            if not math.isfinite(number):
                raise RunManifestValidationError("run manifest must not contain NaN or Infinity")
            return number
        if isinstance(value, np.ndarray):
            return [to_jsonable(item) for item in value.tolist()]
    if isinstance(value, Path):
        raise RunManifestValidationError("run manifest must store logical relative path strings, not Path objects")
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RunManifestValidationError("run manifest JSON object keys must be strings")
            converted[key] = to_jsonable(item)
        return converted
    raise RunManifestValidationError(f"run manifest contains unsupported type {type(value).__name__}")


def validate_status_transition(current_status: str, next_status: str) -> None:
    if current_status in TERMINAL_STATUSES:
        raise RunStateTransitionError(f"terminal run status {current_status} cannot transition to {next_status}")
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise RunStateTransitionError(f"illegal run status transition: {current_status} -> {next_status}")


def transition_manifest(manifest: Dict[str, Any], next_status: str) -> Dict[str, Any]:
    current_status = manifest.get("status")
    validate_status_transition(current_status, next_status)
    updated = dict(manifest)
    updated["status"] = next_status
    now = utc_now_iso()
    if next_status in {STATUS_STARTING, STATUS_VALIDATING} and not updated.get("started_at"):
        updated["started_at"] = now
    if next_status in TERMINAL_STATUSES:
        updated["finished_at"] = now
    return updated


def build_run_manifest(project: Dict[str, Any], run_id: str, flow_model_id: str) -> Dict[str, Any]:
    validate_run_id(run_id)
    references = project.get("references") or {}
    now = utc_now_iso()
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "project_id": project["project_id"],
        "geology_model_id": references.get("geology_model_id"),
        "grid_model_id": references.get("grid_model_id"),
        "flow_model_id": flow_model_id,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "status": STATUS_CREATED,
        "executor": {
            "type": None,
            "idempotency_key": None,
            "owner_id": None,
            "lease_token": None,
            "lease_expires_at": None,
            "run_token": None,
            "worker_pid": None,
            "worker_identity": None,
            "mf6_pid": None,
            "mf6_identity": None,
            "process_group_id": None,
            "timeout_seconds": None,
            "timed_out_at": None,
            "run_duration_seconds": None,
            "cancel_requested_at": None,
            "cancelled_at": None,
            "cancel_reason": None,
            "cancel_source": None,
            "cancel_duration_seconds": None,
            "termination": None,
            "resource_estimate": None,
        },
        "resource_usage": {
            "monitor": None,
            "samples": 0,
            "peak_rss_bytes": 0,
            "peak_cpu_seconds": 0.0,
            "last_sample": None,
            "limits": {},
        },
        "model_snapshot": {
            "project_checksum": None,
            "geology_checksum": None,
            "grid_checksum": None,
            "grid_arrays_checksum": None,
            "flow_checksum": None,
        },
        "mf6": {
            "executable_source": None,
            "version": None,
            "return_code": None,
            "normal_termination": None,
            "stdout": None,
            "stderr": None,
        },
        "model": {
            "simulation_name": None,
            "gwf_model_name": None,
            "nlay": None,
            "nrow": None,
            "ncol": None,
            "nper": None,
            "packages": [],
        },
        "checker": None,
        "package_preview": None,
        "convergence": {
            "state": "not_checked",
            "converged": None,
            "normal_termination": None,
            "evidence": [],
            "warnings": [],
        },
        "water_budget": {
            "state": "not_checked",
            "kstp": None,
            "kper": None,
            "totim": None,
            "time_unit": project.get("units", {}).get("time", "day"),
            "flow_unit": project.get("units", {}).get("flow", "m3/day"),
            "total_in": None,
            "total_out": None,
            "difference": None,
            "percent_discrepancy": None,
            "tolerance": None,
            "within_tolerance": None,
        },
        "package_budget": {
            "state": "not_checked",
            "packages": [],
            "warnings": [],
        },
        "outputs": {},
        "warnings": [],
        "error": None,
        "retention": {"artifacts_retained": True},
    }


def validate_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    manifest = to_jsonable(manifest)
    if manifest.get("schema_name") != SCHEMA_NAME:
        raise RunManifestValidationError("run manifest schema_name is invalid")
    if manifest.get("schema_version") in {"1.0", "1.1"}:
        manifest = dict(manifest)
        manifest["schema_version"] = SCHEMA_VERSION
        manifest.setdefault("executor", {})
        manifest["executor"] = {
            "type": None,
            "idempotency_key": None,
            "owner_id": None,
            "lease_token": None,
            "lease_expires_at": None,
            "run_token": None,
            "worker_pid": None,
            "worker_identity": None,
            "mf6_pid": None,
            "mf6_identity": None,
            "process_group_id": None,
            "timeout_seconds": None,
            "timed_out_at": None,
            "run_duration_seconds": None,
            "cancel_requested_at": None,
            "cancelled_at": None,
            "cancel_reason": None,
            "cancel_source": None,
            "cancel_duration_seconds": None,
            "termination": None,
            "resource_estimate": None,
            **manifest["executor"],
        }
        manifest.setdefault("resource_usage", {
            "monitor": None,
            "samples": 0,
            "peak_rss_bytes": 0,
            "peak_cpu_seconds": 0.0,
            "last_sample": None,
            "limits": {},
        })
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise RunManifestValidationError("run manifest schema_version is unsupported")
    manifest.setdefault("executor", {})
    executor_defaults = {
        "type": None,
        "idempotency_key": None,
        "owner_id": None,
        "lease_token": None,
        "lease_expires_at": None,
        "run_token": None,
        "worker_pid": None,
        "worker_identity": None,
        "mf6_pid": None,
        "mf6_identity": None,
        "process_group_id": None,
        "timeout_seconds": None,
        "timed_out_at": None,
        "run_duration_seconds": None,
        "cancel_requested_at": None,
        "cancelled_at": None,
        "cancel_reason": None,
        "cancel_source": None,
        "cancel_duration_seconds": None,
        "termination": None,
        "resource_estimate": None,
    }
    manifest["executor"] = {**executor_defaults, **manifest["executor"]}
    manifest.setdefault("resource_usage", {
        "monitor": None,
        "samples": 0,
        "peak_rss_bytes": 0,
        "peak_cpu_seconds": 0.0,
        "last_sample": None,
        "limits": {},
    })
    validate_run_id(manifest.get("run_id"))
    if manifest.get("status") not in (set(ALLOWED_TRANSITIONS) | TERMINAL_STATUSES):
        raise RunManifestValidationError("run manifest status is invalid")
    return manifest


def run_summary(manifest: Dict[str, Any]) -> Dict[str, Any]:
    budget = manifest.get("water_budget") or {}
    return {
        "run_id": manifest.get("run_id"),
        "project_id": manifest.get("project_id"),
        "geology_model_id": manifest.get("geology_model_id"),
        "grid_model_id": manifest.get("grid_model_id"),
        "flow_model_id": manifest.get("flow_model_id"),
        "status": manifest.get("status"),
        "created_at": manifest.get("created_at"),
        "started_at": manifest.get("started_at"),
        "finished_at": manifest.get("finished_at"),
        "mf6": {
            "executable_source": (manifest.get("mf6") or {}).get("executable_source"),
            "version": (manifest.get("mf6") or {}).get("version"),
            "return_code": (manifest.get("mf6") or {}).get("return_code"),
            "normal_termination": (manifest.get("mf6") or {}).get("normal_termination"),
        },
        "convergence": manifest.get("convergence"),
        "water_budget": budget,
        "package_budget": manifest.get("package_budget"),
        "outputs": manifest.get("outputs"),
        "warnings": manifest.get("warnings", []),
        "error": manifest.get("error"),
        "executor": manifest.get("executor"),
    }
