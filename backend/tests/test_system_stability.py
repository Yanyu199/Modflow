import json

import numpy as np
import pytest

from array_backend import resolve_array_backend
from resource_guard import (
    ResourceLimitError,
    enforce_result_response_size,
    enforce_run_preflight,
    estimate_grid_resources,
)
from run_manifest_schema import build_run_manifest, validate_manifest
from runtime_config import RuntimeConfig, scale_classification
from test_project_api import project_payload


def grid_manifest(nlay=1, nrow=10, ncol=10, active=None):
    total = nlay * nrow * ncol
    return {
        "geometry": {"nlay": nlay, "nrow": nrow, "ncol": ncol},
        "quality": {"summary": {"active_cell_count": active if active is not None else total}},
    }


def test_resource_estimate_and_scale_classification_rejects_before_large_allocation():
    config = RuntimeConfig(max_grid_cells=100, max_process_memory_bytes=10**9)
    manifest = grid_manifest(nlay=2, nrow=10, ncol=10)

    estimate = estimate_grid_resources(manifest, config)
    assert estimate["total_cells"] == 200
    assert estimate["scale"]["level"] == "small"

    with pytest.raises(ResourceLimitError) as exc:
        enforce_run_preflight(manifest, config)
    assert exc.value.code == "RUN_GRID_TOO_LARGE"
    assert exc.value.details["total_cells"] == 200


def test_result_json_limit_requires_slice_or_binary():
    config = RuntimeConfig(result_json_cell_limit=2, max_result_response_bytes=1024)

    with pytest.raises(ResourceLimitError) as exc:
        enforce_result_response_size(3, 8, "json", config)
    assert exc.value.code == "RESULT_JSON_TOO_LARGE"

    assert enforce_result_response_size(3, 8, "binary", config) == 24


def test_scale_classification_boundaries():
    assert scale_classification(100_000, 100_000, 1)["level"] == "small"
    assert scale_classification(500_000, 400_000, 10)["level"] == "medium"
    assert scale_classification(1_000_000, 900_000, 20)["level"] == "large"
    assert scale_classification(1_000_001, 900_000, 20)["level"] == "too_large"


def test_run_manifest_v1_migrates_executor_fields():
    project = project_payload(project_id="prj_manifest_migration")
    manifest = build_run_manifest(project, "run_1111111111111111", "flow_1111111111111111")
    manifest["schema_version"] = "1.0"
    manifest.pop("executor")

    migrated = validate_manifest(json.loads(json.dumps(manifest)))

    assert migrated["schema_version"] == "1.1"
    assert migrated["executor"]["worker_pid"] is None
    assert migrated["executor"]["timeout_seconds"] is None


def test_array_backend_defaults_to_numpy_and_gpu_is_optional(monkeypatch):
    monkeypatch.delenv("FLOPY_USE_GPU", raising=False)
    backend = resolve_array_backend()

    assert backend.info.name == "numpy"
    assert backend.info.gpu_requested is False
    assert backend.finite_min_max(np.array([1.0, np.nan, 3.0])) == (1.0, 3.0)

    gpu_backend = resolve_array_backend(prefer_gpu=True)
    assert gpu_backend.info.name in {"numpy", "cupy"}
    if gpu_backend.info.name == "numpy":
        assert gpu_backend.info.gpu_requested is True
        assert gpu_backend.info.warnings
