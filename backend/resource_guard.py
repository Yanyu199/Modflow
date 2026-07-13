"""Resource estimation and preflight checks before allocating large arrays or runs."""

from __future__ import annotations

from typing import Any, Dict

from runtime_config import DEFAULT_RUNTIME_CONFIG, RuntimeConfig, scale_classification


class ResourceLimitError(ValueError):
    def __init__(self, code: str, message: str, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def estimate_grid_resources(grid_manifest: Dict[str, Any], config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG) -> Dict[str, Any]:
    geometry = grid_manifest.get("geometry") or {}
    nlay = int(geometry.get("nlay") or 0)
    nrow = int(geometry.get("nrow") or 0)
    ncol = int(geometry.get("ncol") or 0)
    total_cells = nlay * nrow * ncol
    active_cells = int(((grid_manifest.get("quality") or {}).get("summary") or {}).get("active_cell_count") or total_cells)
    grid_array_bytes = (
        nrow * ncol * 8
        + nlay * nrow * ncol * 8
        + nlay * nrow * ncol * 4
    )
    head_bytes = nlay * nrow * ncol * 8
    budget_estimate_bytes = max(active_cells, 1) * 6 * 8
    scale = scale_classification(total_cells, active_cells, nlay)
    return {
        "nlay": nlay,
        "nrow": nrow,
        "ncol": ncol,
        "total_cells": total_cells,
        "active_cells": active_cells,
        "estimated_grid_array_bytes": int(grid_array_bytes),
        "estimated_head_bytes": int(head_bytes),
        "estimated_budget_bytes": int(budget_estimate_bytes),
        "estimated_result_bytes": int(head_bytes + budget_estimate_bytes),
        "scale": scale,
        "limits": {
            "max_grid_cells": config.max_grid_cells,
            "max_render_cells": config.max_render_cells,
            "max_result_response_bytes": config.max_result_response_bytes,
            "max_process_memory_bytes": config.max_process_memory_bytes,
        },
    }


def enforce_run_preflight(grid_manifest: Dict[str, Any], config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG) -> Dict[str, Any]:
    estimate = estimate_grid_resources(grid_manifest, config)
    if estimate["total_cells"] > config.max_grid_cells:
        raise ResourceLimitError(
            "RUN_GRID_TOO_LARGE",
            "Grid cell count exceeds configured run limit.",
            estimate,
        )
    if estimate["estimated_result_bytes"] > config.max_process_memory_bytes:
        raise ResourceLimitError(
            "RUN_ESTIMATED_MEMORY_TOO_LARGE",
            "Estimated result memory exceeds configured process limit.",
            estimate,
        )
    return estimate


def enforce_result_response_size(cell_count: int, dtype_bytes: int, fmt: str, config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG):
    expected = int(cell_count) * int(dtype_bytes)
    if fmt == "json" and cell_count > config.result_json_cell_limit:
        raise ResourceLimitError(
            "RESULT_JSON_TOO_LARGE",
            "Requested result slice is too large for JSON; request format=binary.",
            {"cell_count": cell_count, "limit": config.result_json_cell_limit, "expected_bytes": expected},
        )
    if expected > config.max_result_response_bytes and fmt != "binary":
        raise ResourceLimitError(
            "RESULT_RESPONSE_TOO_LARGE",
            "Requested result slice exceeds response limit; request format=binary or a smaller slice.",
            {"cell_count": cell_count, "expected_bytes": expected, "limit": config.max_result_response_bytes},
        )
    return expected
