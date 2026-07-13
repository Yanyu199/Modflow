from pathlib import Path

import flopy
import numpy as np
import pytest

import app as app_module
from flow_model_service import FlowModelService
from flow_test_helpers import create_simple_flow_grid, steady_flow_payload
from grid_model_schema import cell_id
from mf6_executable import ExecutableResolutionError, resolve_mf6_executable
from steady_flow_benchmark import (
    benchmark_definition,
    expected_heads,
    listing_indicates_normal_termination,
    read_budget_totals,
    read_percent_discrepancy,
)
from test_project_api import client_with_store, create_project


def create_project_grid_flow(client, store, project_id="prj_flow_api"):
    project = create_project(client, project_id=project_id)
    grid_model, _arrays = create_simple_flow_grid(store, project)
    payload = steady_flow_payload(project, grid_model["grid_model_id"])
    response = client.post(f"/projects/{project['project_id']}/flow-models", json=payload)
    assert response.status_code == 201, response.get_json()
    return project, grid_model, response.get_json()["flow_model"]


def diagnostic_codes(checker, bucket="errors"):
    return {item["code"] for item in checker["diagnostics"].get(bucket, [])}


def diagnostic_paths(checker, code, bucket="errors"):
    return {item.get("path") for item in checker["diagnostics"].get(bucket, []) if item["code"] == code}


def test_flow_model_api_persists_checker_and_project_reference(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project, grid_model, flow_model = create_project_grid_flow(client, store)

    assert flow_model["schema"] == "flow_model"
    assert flow_model["schema_name"] == "flow_model"
    assert flow_model["schema_version"] == "1.0"
    assert flow_model["status"] == "ready"
    assert flow_model["project_id"] == project["project_id"]
    assert flow_model["grid_model_id"] == grid_model["grid_model_id"]
    assert flow_model["provenance"]["package_summary"]["packages"] == [
        "TDIS",
        "IMS",
        "GWF",
        "DIS",
        "IC",
        "NPF",
        "CHD",
        "WEL",
        "OC",
    ]
    assert store.get(project["project_id"])["references"]["flow_model_id"] == flow_model["flow_model_id"]

    active = client.get(f"/projects/{project['project_id']}/flow-models/active")
    assert active.status_code == 200
    assert active.get_json()["flow_model"]["flow_model_id"] == flow_model["flow_model_id"]

    preview = client.get(
        f"/projects/{project['project_id']}/flow-models/{flow_model['flow_model_id']}/package-preview"
    )
    assert preview.status_code == 200
    body = preview.get_data(as_text=True)
    assert str(tmp_path) not in body
    assert preview.get_json()["package_preview"]["chd_cell_count"] == 2
    assert preview.get_json()["package_preview"]["wel_cell_count"] == 1


def test_flow_model_checker_blocks_missing_chd_inactive_cells_and_conflicts(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_flow_checker")
    grid_model, arrays = create_simple_flow_grid(store, project)

    payload = steady_flow_payload(project, grid_model["grid_model_id"])
    payload["boundaries"]["chd"] = []
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=payload)
    assert response.status_code == 200
    checker = response.get_json()["checker"]
    assert checker["runnable"] is False
    assert "FLOW_CHD_REQUIRED" in diagnostic_codes(checker)

    create = client.post(f"/projects/{project['project_id']}/flow-models", json=payload)
    assert create.status_code == 400
    assert create.get_json()["code"] == "flow_model_validation_error"

    arrays["idomain"][0, 0, 2] = 0
    from grid_model_store import GridModelStore

    GridModelStore(store).save(store.get(project["project_id"]), grid_model, arrays)
    payload = steady_flow_payload(project, grid_model["grid_model_id"])
    payload["boundaries"]["chd"][0]["cells"].append(
        {"cell_id": cell_id(grid_model["grid_model_id"], 0, 0, 2), "head": 9.4}
    )
    payload["initial_conditions"]["overrides"] = [
        {"cell_id": cell_id(grid_model["grid_model_id"], 0, 0, 2), "head": 9.4}
    ]
    payload["hydraulic_properties"]["kx"]["overrides"] = [
        {"cell_id": cell_id(grid_model["grid_model_id"], 0, 0, 2), "value": 2.0}
    ]
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=payload)
    checker = response.get_json()["checker"]
    assert "FLOW_CELL_INACTIVE" in diagnostic_codes(checker)
    assert "initial_conditions.overrides[0].cell_id" in diagnostic_paths(checker, "FLOW_CELL_INACTIVE")
    assert "hydraulic_properties.kx.overrides[0].cell_id" in diagnostic_paths(checker, "FLOW_CELL_INACTIVE")

    arrays["idomain"][0, 0, 2] = 1
    GridModelStore(store).save(store.get(project["project_id"]), grid_model, arrays)
    payload = steady_flow_payload(project, grid_model["grid_model_id"])
    payload["boundaries"]["chd"][0]["cells"].append(
        {"cell_id": cell_id(grid_model["grid_model_id"], 0, 0, 2), "head": 9.4}
    )
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=payload)
    checker = response.get_json()["checker"]
    assert "FLOW_WEL_CHD_CONFLICT" in diagnostic_codes(checker)


def test_flow_model_checker_blocks_stale_or_bad_grid(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_flow_grid_state")
    grid_model, arrays = create_simple_flow_grid(store, project)

    from grid_model_store import GridModelStore

    grid_model["status"] = "stale"
    GridModelStore(store).save(store.get(project["project_id"]), grid_model, arrays)
    payload = steady_flow_payload(project, grid_model["grid_model_id"])
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=payload)
    checker = response.get_json()["checker"]
    assert checker["runnable"] is False
    assert "FLOW_GRID_STALE" in diagnostic_codes(checker)

    grid_model["status"] = "ready"
    grid_model["quality"]["errors"] = [{"code": "GRID_TEST_ERROR", "message": "blocking grid issue"}]
    GridModelStore(store).save(store.get(project["project_id"]), grid_model, arrays)
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=payload)
    checker = response.get_json()["checker"]
    assert checker["runnable"] is False
    assert "FLOW_GRID_QUALITY_ERROR" in diagnostic_codes(checker)


def test_flow_model_compiles_expected_flopy_packages(tmp_path):
    from project_store import ProjectStore

    store = ProjectStore(tmp_path / "projects")
    project = store.create(
        {
            "project_id": "prj_flow_compile",
            "name": "Flow Compile",
            "crs": {"authority": "EPSG", "code": 32650, "wkt": None, "axis_order": "xy"},
            "units": {"horizontal_length": "m", "vertical_length": "m", "time": "day", "flow": "m3/day"},
            "model_settings": {"model_type": "groundwater_flow", "flow_regime": "steady"},
            "references": {"geology_model_id": None, "grid_model_id": None, "flow_model_id": None},
        }
    )
    grid_model, _arrays = create_simple_flow_grid(store, project)
    service = FlowModelService(store)
    created = service.create(project["project_id"], grid_model["grid_model_id"], steady_flow_payload(project, grid_model["grid_model_id"]))
    flow_model = created["flow_model"]

    compiled = service.compile_to_simulation(
        project["project_id"],
        flow_model["flow_model_id"],
        str(tmp_path / "compile"),
        mf6_executable="mf6",
    )
    gwf = compiled["gwf"]
    package_names = {package.package_type for package in gwf.packagelist}
    assert {"dis", "ic", "npf", "chd", "wel", "oc"}.issubset(package_names)
    assert compiled["simulation"].get_package("tdis") is not None
    assert compiled["simulation"].get_package("ims") is not None
    np.testing.assert_allclose(gwf.npf.k.get_data(), 1.0)
    np.testing.assert_allclose(gwf.npf.k22.get_data(), 1.0)
    np.testing.assert_allclose(gwf.npf.k33.get_data(), 1.0)
    assert gwf.npf.icelltype.get_data().shape == (1, 1, 5)

    chd = gwf.chd.stress_period_data.get_data(key=0)
    wel = gwf.wel.stress_period_data.get_data(key=0)
    assert tuple(chd[0]["cellid"]) == (0, 0, 0)
    assert chd[0]["head"] == pytest.approx(10.0)
    assert tuple(chd[1]["cellid"]) == (0, 0, 4)
    assert chd[1]["head"] == pytest.approx(9.0)
    assert tuple(wel[0]["cellid"]) == (0, 0, 2)
    assert wel[0]["q"] == pytest.approx(-1.0)


def test_run_model_requires_saved_flow_model_and_rejects_legacy_overrides(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project, grid_model, flow_model = create_project_grid_flow(client, store, project_id="prj_flow_run_route")

    missing = client.post("/run-model", json={"project_id": project["project_id"], "grid_model_id": grid_model["grid_model_id"]})
    assert missing.status_code == 400
    assert missing.get_json()["code"] == "flow_model_id_required"

    override = client.post(
        "/run-model",
        json={
            "project_id": project["project_id"],
            "grid_model_id": grid_model["grid_model_id"],
            "flow_model_id": flow_model["flow_model_id"],
            "params": {"k": 99.0},
        },
    )
    assert override.status_code == 400
    assert override.get_json()["code"] == "flow_model_authoritative"

    class FakeExecutor:
        def submit(self, project_id, flow_model_id, keep_artifacts=None, idempotency_key=None):
            return {
                "duplicate": False,
                "manifest": {
                    "run_id": "run_1111111111111111",
                    "project_id": project_id,
                    "flow_model_id": flow_model_id,
                    "grid_model_id": grid_model["grid_model_id"],
                    "status": "queued",
                    "created_at": "2026-07-13T00:00:00Z",
                    "started_at": None,
                    "finished_at": None,
                    "geology_model_id": None,
                    "mf6": {},
                    "convergence": {},
                    "water_budget": {},
                    "package_budget": {},
                    "outputs": {},
                    "warnings": [],
                    "error": None,
                    "executor": {},
                },
            }

    monkeypatch.setattr(app_module, "ensure_run_executor", lambda: FakeExecutor())
    response = client.post(
        "/run-model",
        json={
            "project_id": project["project_id"],
            "grid_model_id": grid_model["grid_model_id"],
            "flow_model_id": flow_model["flow_model_id"],
        },
    )
    assert response.status_code == 202
    assert response.get_json()["flow_model_id"] == flow_model["flow_model_id"]
    assert response.get_json()["deprecated_run_model_entrypoint"] is True
    assert response.get_json()["status"] == "queued"
    assert "work_dir" not in response.get_data(as_text=True)


@pytest.mark.integration
def test_persistent_flow_model_benchmark_runs_and_matches(tmp_path):
    from project_store import ProjectStore

    try:
        resolve_mf6_executable()
    except ExecutableResolutionError as exc:
        pytest.skip(f"MODFLOW 6 executable not available: {exc}")

    store = ProjectStore(tmp_path / "projects")
    project = store.create(
        {
            "project_id": "prj_flow_benchmark",
            "name": "Flow Benchmark",
            "crs": {"authority": "EPSG", "code": 32650, "wkt": None, "axis_order": "xy"},
            "units": {"horizontal_length": "m", "vertical_length": "m", "time": "day", "flow": "m3/day"},
            "model_settings": {"model_type": "groundwater_flow", "flow_regime": "steady"},
            "references": {"geology_model_id": None, "grid_model_id": None, "flow_model_id": None},
        }
    )
    grid_model, _arrays = create_simple_flow_grid(store, project)
    service = FlowModelService(store)
    created = service.create(project["project_id"], grid_model["grid_model_id"], steady_flow_payload(project, grid_model["grid_model_id"]))
    flow_model = created["flow_model"]

    result = service.run(project["project_id"], flow_model["flow_model_id"], keep_run_dir=True)
    run_dir = Path(store.project_dir(project["project_id"])) / "runs" / result["run_id"]
    work_dir = run_dir / "input"
    definition = benchmark_definition()
    heads = flopy.utils.HeadFile(str(work_dir / "gwf.hds")).get_data()
    expected = expected_heads(definition)
    abs_diff = np.abs(heads - expected)
    rel_diff = abs_diff / np.maximum(np.abs(expected), 1.0e-30)
    total_in, total_out = read_budget_totals(work_dir / "gwf.bud")
    percent_discrepancy = read_percent_discrepancy(work_dir / "gwf.lst")

    assert result["success"] is True
    assert result["status"] in {"completed", "completed_with_warnings"}
    assert (run_dir / "run_manifest.json").exists()
    assert listing_indicates_normal_termination(work_dir / "mfsim.lst")
    for filename in (
        "mfsim.nam",
        "sim.tdis",
        "sim.ims",
        "gwf.nam",
        "gwf.dis",
        "gwf.ic",
        "gwf.npf",
        "gwf.chd",
        "gwf.wel",
        "gwf.oc",
        "gwf.lst",
        "mfsim.lst",
        "gwf.hds",
        "gwf.bud",
    ):
        assert (work_dir / filename).exists(), filename
    assert heads.shape == (1, 1, 5)
    assert np.isfinite(heads).all()
    np.testing.assert_allclose(heads, expected, atol=definition.head_abs_tolerance, rtol=definition.head_rel_tolerance)
    assert float(abs_diff.max()) <= definition.head_abs_tolerance
    assert float(rel_diff.max()) <= definition.head_rel_tolerance
    assert total_in == pytest.approx(3.0, abs=definition.budget_abs_tolerance)
    assert total_out == pytest.approx(3.0, abs=definition.budget_abs_tolerance)
    assert abs(total_in - total_out) <= definition.budget_abs_tolerance
    assert percent_discrepancy <= definition.percent_discrepancy_tolerance
