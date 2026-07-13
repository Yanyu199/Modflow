"""Runtime limits for run execution, result slicing, and rendering hints."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _str_env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return str(value)


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RuntimeConfig:
    executor_mode: str = _str_env("FLOPY_EXECUTOR_MODE", "embedded")
    max_concurrent_runs: int = _int_env("FLOPY_MAX_CONCURRENT_RUNS", 1)
    max_runs_per_project: int = _int_env("FLOPY_MAX_RUNS_PER_PROJECT", 1)
    run_timeout_seconds: int = _int_env("FLOPY_RUN_TIMEOUT_SECONDS", 3600)
    scheduler_lease_seconds: int = _int_env("FLOPY_SCHEDULER_LEASE_SECONDS", 120)
    scheduler_poll_interval_seconds: float = _float_env("FLOPY_SCHEDULER_POLL_INTERVAL_SECONDS", 0.5)
    cancel_grace_seconds: float = _float_env("FLOPY_CANCEL_GRACE_SECONDS", 5.0)
    process_termination_grace_seconds: float = _float_env("FLOPY_PROCESS_TERMINATION_GRACE_SECONDS", 5.0)
    resource_monitor_interval_seconds: float = _float_env("FLOPY_RESOURCE_MONITOR_INTERVAL_SECONDS", 0.2)
    max_grid_cells: int = _int_env("FLOPY_MAX_GRID_CELLS", 1_000_000)
    max_result_cache_bytes: int = _int_env("FLOPY_MAX_RESULT_CACHE_BYTES", 256 * 1024 * 1024)
    max_result_response_bytes: int = _int_env("FLOPY_MAX_RESULT_RESPONSE_BYTES", 8 * 1024 * 1024)
    max_render_cells: int = _int_env("FLOPY_MAX_RENDER_CELLS", 200_000)
    max_process_memory_bytes: int = _int_env("FLOPY_MAX_PROCESS_MEMORY_BYTES", 2 * 1024 * 1024 * 1024)
    max_process_cpu_seconds: int = _int_env("FLOPY_MAX_PROCESS_CPU_SECONDS", 0)
    result_json_cell_limit: int = _int_env("FLOPY_RESULT_JSON_CELL_LIMIT", 50_000)
    result_cache_enabled: bool = _bool_env("FLOPY_RESULT_CACHE_ENABLED", True)
    gpu_min_array_bytes: int = _int_env("FLOPY_GPU_MIN_ARRAY_BYTES", 100 * 1024 * 1024)


DEFAULT_RUNTIME_CONFIG = RuntimeConfig()


def scale_classification(total_cells: int, active_cells: int, layers: int) -> dict:
    total_cells = int(total_cells or 0)
    active_cells = int(active_cells or 0)
    layers = int(layers or 0)
    if total_cells <= 100_000 and active_cells <= 100_000:
        level = "small"
    elif total_cells <= 500_000 and active_cells <= 500_000:
        level = "medium"
    elif total_cells <= 1_000_000 and active_cells <= 1_000_000:
        level = "large"
    else:
        level = "too_large"
    return {
        "level": level,
        "total_cells": total_cells,
        "active_cells": active_cells,
        "layers": layers,
        "recommendations": {
            "async_run_required": True,
            "default_visible_layers": 1,
            "allow_all_layers_3d": level in {"small"},
            "use_layer_slices": level in {"medium", "large", "too_large"},
            "use_downsampling": level in {"large", "too_large"},
        },
    }
