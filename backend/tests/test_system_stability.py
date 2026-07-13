import json
import os
import subprocess
import sys
import time

import numpy as np
import pytest

from array_backend import resolve_array_backend
from process_control import is_process_identity_alive, process_identity, terminate_process_tree
from resource_guard import (
    ResourceLimitError,
    enforce_result_response_size,
    enforce_run_preflight,
    estimate_grid_resources,
)
from resource_controller import ResourceController, ResourceLimitExceeded
from run_manifest_schema import (
    STATUS_QUEUED,
    STATUS_RUNNING,
    build_run_manifest,
    validate_manifest,
)
from run_manifest_store import RunManifestStore
from run_scheduler import RunSchedulerStore
from run_service import RunFailure, RunService
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

    assert migrated["schema_version"] == "1.2"
    assert migrated["executor"]["worker_pid"] is None
    assert migrated["executor"]["timeout_seconds"] is None
    assert "resource_usage" in migrated


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


def _sleeping_process_tree():
    code = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print(child.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    child_pid = int(process.stdout.readline().strip())
    return process, child_pid


def test_terminate_process_tree_kills_real_child_process():
    process, child_pid = _sleeping_process_tree()
    parent_identity = process_identity(process.pid)
    child_identity = process_identity(child_pid)

    report = terminate_process_tree(process.pid, grace_seconds=1.0, reason="test_cancel")

    assert report["found"] is True
    assert is_process_identity_alive(parent_identity) is False
    assert is_process_identity_alive(child_identity) is False


def _write_slow_executable(tmp_path):
    if os.name == "nt":
        script = tmp_path / "slow_mf6.cmd"
        script.write_text(f'@echo off\n"{sys.executable}" -c "import time; time.sleep(60)"\n', encoding="utf-8")
    else:
        script = tmp_path / "slow_mf6.sh"
        script.write_text(f'#! /bin/sh\n"{sys.executable}" -c "import time; time.sleep(60)"\n', encoding="utf-8")
        script.chmod(0o755)
    return script


def test_run_service_timeout_terminates_real_process_tree(tmp_path):
    from project_store import ProjectStore

    store = ProjectStore(tmp_path / "projects")
    project = store.create(project_payload(project_id="prj_timeout_process"))
    run_store = RunManifestStore(store)
    manifest = run_store.create(project, "flow_1111111111111111")
    manifest["executor"]["timeout_seconds"] = 1
    manifest["status"] = STATUS_RUNNING
    manifest = run_store.save(manifest)

    service = RunService(store, config=RuntimeConfig(run_timeout_seconds=1, process_termination_grace_seconds=1))
    with pytest.raises(RunFailure) as exc:
        service._execute_mf6(_write_slow_executable(tmp_path), run_store.input_dir(project["project_id"], manifest["run_id"]), run_store.logs_dir(project["project_id"], manifest["run_id"]), manifest=manifest)

    latest = run_store.load(project["project_id"], manifest["run_id"])
    assert exc.value.status == "timed_out"
    assert latest["executor"]["mf6_pid"]
    assert latest["executor"]["termination"]["alive_pids"] == []
    assert latest["resource_usage"]["samples"] >= 1


def test_sqlite_scheduler_claim_is_single_winner(tmp_path):
    from project_store import ProjectStore

    store = ProjectStore(tmp_path / "projects")
    project = store.create(project_payload(project_id="prj_scheduler_claim"))
    manifest = RunManifestStore(store).create(project, "flow_1111111111111111")
    manifest = RunManifestStore(store).transition(manifest, STATUS_QUEUED)
    scheduler_a = RunSchedulerStore(store, RuntimeConfig(max_concurrent_runs=1, max_runs_per_project=1))
    scheduler_b = RunSchedulerStore(store, RuntimeConfig(max_concurrent_runs=1, max_runs_per_project=1))

    claim_a = scheduler_a.try_claim(manifest, owner_id="a", max_concurrent=1, max_per_project=1, lease_seconds=60)
    claim_b = scheduler_b.try_claim(manifest, owner_id="b", max_concurrent=1, max_per_project=1, lease_seconds=60)

    assert bool(claim_a) != bool(claim_b)
    stats = scheduler_a.stats()
    assert stats["states"]["starting"] == 1


def test_resource_controller_terminates_memory_limit_process(tmp_path):
    code = "import time\npayload = bytearray(20 * 1024 * 1024)\ntime.sleep(60)\n"
    process = subprocess.Popen([sys.executable, "-c", code])
    identity = process_identity(process.pid)
    controller = ResourceController(RuntimeConfig(max_process_memory_bytes=1 * 1024 * 1024, process_termination_grace_seconds=1))
    deadline = time.time() + 5
    with pytest.raises(ResourceLimitExceeded):
        while time.time() < deadline:
            controller.sample(process.pid, reason_prefix="test_resource")
            time.sleep(0.05)
        pytest.fail("resource controller did not terminate process")
    assert is_process_identity_alive(identity) is False


def test_result_cache_tracks_hits_misses_and_evictions():
    from result_service import ResultSliceCache

    cache = ResultSliceCache(max_bytes=16, enabled=True)
    key_a = ("a",)
    key_b = ("b",)

    assert cache.get(key_a) is None
    cache.put(key_a, np.ones(2, dtype=np.float64))
    assert cache.get(key_a) is not None
    cache.put(key_b, np.ones(2, dtype=np.float64))

    stats = cache.stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 1
    assert stats["evictions"] >= 1
    assert stats["scope"] == "per_process"
