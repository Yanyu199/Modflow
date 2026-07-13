from pathlib import Path

import flopy
import numpy as np
import pytest

import app as app_module
from mf6_executable import ExecutableResolutionError, resolve_mf6_executable
from steady_flow_benchmark import benchmark_definition, expected_heads
from test_flow_model import create_project_grid_flow
from test_project_api import client_with_store


@pytest.mark.integration
def test_run_api_creates_persistent_manifest_and_budget_report(tmp_path, monkeypatch):
    try:
        resolve_mf6_executable()
    except ExecutableResolutionError as exc:
        pytest.skip(f"MODFLOW 6 executable not available: {exc}")

    client, store = client_with_store(tmp_path, monkeypatch)
    project, _grid_model, flow_model = create_project_grid_flow(client, store, project_id="prj_run_api_success")

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        json={"flow_model_id": flow_model["flow_model_id"]},
    )
    body = response.get_json()

    assert response.status_code == 201, body
    assert body["success"] is True
    assert body["status"] in {"completed", "completed_with_warnings"}
    assert body["run_id"].startswith("run_")
    assert "work_dir" not in response.get_data(as_text=True)
    assert str(tmp_path) not in response.get_data(as_text=True)

    run_id = body["run_id"]
    run_dir = Path(store.project_dir(project["project_id"])) / "runs" / run_id
    manifest_path = run_dir / "run_manifest.json"
    assert manifest_path.exists()

    detail = client.get(f"/projects/{project['project_id']}/runs/{run_id}")
    manifest = detail.get_json()["run"]
    assert manifest["schema_name"] == "run_manifest"
    assert manifest["schema_version"] == "1.0"
    assert manifest["status"] in {"completed", "completed_with_warnings"}
    assert manifest["model_snapshot"]["project_checksum"]
    assert manifest["model_snapshot"]["grid_checksum"]
    assert manifest["model_snapshot"]["grid_arrays_checksum"]
    assert manifest["model_snapshot"]["flow_checksum"] == flow_model["provenance"]["definition_sha256"]
    assert manifest["mf6"]["return_code"] == 0
    assert manifest["mf6"]["normal_termination"] is True
    assert manifest["convergence"]["state"] == "converged"
    assert manifest["convergence"]["converged"] is True
    assert manifest["water_budget"]["within_tolerance"] is True
    assert manifest["water_budget"]["total_in"] == pytest.approx(3.0, abs=1.0e-7)
    assert manifest["water_budget"]["total_out"] == pytest.approx(3.0, abs=1.0e-7)
    assert manifest["water_budget"]["percent_discrepancy"] <= 1.0e-5
    package_budget = {item["name"]: item for item in manifest["package_budget"]["packages"]}
    assert package_budget["CHD"]["available"] is True
    assert package_budget["WEL"]["available"] is True
    assert package_budget["WEL"]["out"] == pytest.approx(1.0, abs=1.0e-7)
    for key in ("simulation_listing", "model_listing", "head", "budget"):
        assert manifest["outputs"][key]["exists"] is True
        assert manifest["outputs"][key]["size_bytes"] > 0
        assert not Path(manifest["outputs"][key]["name"]).is_absolute()

    heads = flopy.utils.HeadFile(str(run_dir / "input" / "gwf.hds")).get_data()
    definition = benchmark_definition()
    expected = expected_heads(definition)
    np.testing.assert_allclose(heads, expected, atol=definition.head_abs_tolerance, rtol=definition.head_rel_tolerance)

    summary = client.get(f"/projects/{project['project_id']}/runs/{run_id}/summary")
    assert summary.status_code == 200
    assert summary.get_json()["run"]["run_id"] == run_id
    assert summary.get_json()["run"]["water_budget"]["within_tolerance"] is True

    history = client.get(f"/projects/{project['project_id']}/runs?limit=5")
    assert history.status_code == 200
    assert history.get_json()["runs"][0]["run_id"] == run_id


def test_run_api_validation_failure_preserves_manifest(tmp_path, monkeypatch):
    client, _store = client_with_store(tmp_path, monkeypatch)
    project, _grid_model, flow_model = create_project_grid_flow(client, _store, project_id="prj_run_api_failed")
    app_module.flow_service.mark_active_stale(project["project_id"], "test stale flow")

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        json={"flow_model_id": flow_model["flow_model_id"]},
    )
    body = response.get_json()

    assert response.status_code == 400
    assert body["success"] is False
    assert body["run_id"].startswith("run_")
    assert body["status"] == "failed_validation"
    assert body["error"]["code"] == "RUN_FLOW_MODEL_STALE"
    assert "Traceback" not in response.get_data(as_text=True)
    assert str(tmp_path) not in response.get_data(as_text=True)

    detail = client.get(f"/projects/{project['project_id']}/runs/{body['run_id']}")
    manifest = detail.get_json()["run"]
    assert manifest["status"] == "failed_validation"
    assert manifest["error"]["code"] == "RUN_FLOW_MODEL_STALE"
    assert manifest["finished_at"]


def test_run_api_rejects_invalid_run_id_without_path_leak(tmp_path, monkeypatch):
    client, _store = client_with_store(tmp_path, monkeypatch)
    project, _grid_model, _flow_model = create_project_grid_flow(client, _store, project_id="prj_run_bad_id")

    response = client.get(f"/projects/{project['project_id']}/runs/not-a-run")

    assert response.status_code == 400
    assert response.get_json()["code"] == "run_validation_error"
    assert str(tmp_path) not in response.get_data(as_text=True)
