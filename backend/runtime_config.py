"""Runtime limits for run execution, result slicing, and rendering hints."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class RuntimeConfig:
    max_concurrent_runs: int = _int_env("FLOPY_MAX_CONCURRENT_RUNS", 1)
    max_runs_per_project: int = _int_env("FLOPY_MAX_RUNS_PER_PROJECT", 1)
    run_timeout_seconds: int = _int_env("FLOPY_RUN_TIMEOUT_SECONDS", 3600)
    max_grid_cells: int = _int_env("FLOPY_MAX_GRID_CELLS", 1_000_000)
    max_result_cache_bytes: int = _int_env("FLOPY_MAX_RESULT_CACHE_BYTES", 256 * 1024 * 1024)
    max_result_response_bytes: int = _int_env("FLOPY_MAX_RESULT_RESPONSE_BYTES", 8 * 1024 * 1024)
    max_render_cells: int = _int_env("FLOPY_MAX_RENDER_CELLS", 200_000)
    max_process_memory_bytes: int = _int_env("FLOPY_MAX_PROCESS_MEMORY_BYTES", 2 * 1024 * 1024 * 1024)
    result_json_cell_limit: int = _int_env("FLOPY_RESULT_JSON_CELL_LIMIT", 50_000)


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
