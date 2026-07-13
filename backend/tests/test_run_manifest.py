from pathlib import Path

import numpy as np
import pytest

from run_manifest_schema import (
    RunManifestValidationError,
    RunStateTransitionError,
    STATUS_COMPLETED,
    STATUS_CREATED,
    STATUS_RUNNING,
    STATUS_VALIDATING,
    build_run_manifest,
    to_jsonable,
    transition_manifest,
)
from run_manifest_store import RunManifestStore
from test_project_api import project_payload
from project_store import ProjectStore


def test_run_manifest_state_machine_blocks_illegal_transitions():
    project = project_payload(project_id="prj_run_state")
    manifest = build_run_manifest(project, "run_1111111111111111", "flow_1111111111111111")
    assert manifest["status"] == STATUS_CREATED

    running_directly = lambda: transition_manifest(manifest, STATUS_RUNNING)
    with pytest.raises(RunStateTransitionError):
        running_directly()

    validating = transition_manifest(manifest, STATUS_VALIDATING)
    completed = transition_manifest(
        transition_manifest(
            transition_manifest(
                transition_manifest(validating, "compiling"),
                "writing_input",
            ),
            STATUS_RUNNING,
        ),
        "postprocessing",
    )
    completed = transition_manifest(completed, STATUS_COMPLETED)
    assert completed["finished_at"]
    with pytest.raises(RunStateTransitionError):
        transition_manifest(completed, STATUS_RUNNING)


def test_run_manifest_store_persists_json_and_summaries(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create(project_payload(project_id="prj_run_store"))
    run_store = RunManifestStore(store)

    manifest = run_store.create(project, "flow_1111111111111111")
    assert manifest["schema_name"] == "run_manifest"
    assert manifest["schema_version"] == "1.0"
    assert manifest["run_id"].startswith("run_")

    manifest = run_store.transition(manifest, STATUS_VALIDATING)
    loaded = run_store.load(project["project_id"], manifest["run_id"])
    assert loaded["status"] == STATUS_VALIDATING

    runs = run_store.list(project["project_id"])
    assert runs[0]["run_id"] == manifest["run_id"]
    assert "project_id" in runs[0]


def test_run_manifest_rejects_non_json_values():
    assert to_jsonable({"value": np.float64(1.25)}) == {"value": 1.25}
    with pytest.raises(RunManifestValidationError):
        to_jsonable({"bad": float("nan")})
    with pytest.raises(RunManifestValidationError):
        to_jsonable({"path": Path("input/gwf.hds")})
