from pathlib import Path

import flopy
import numpy as np
import pytest

from flow_model_service import FlowModelService
from flow_test_helpers import create_simple_flow_grid, steady_flow_payload
from grid_model_schema import cell_id
from grid_model_store import GridModelStore
from mf6_executable import ExecutableResolutionError, resolve_mf6_executable
from mf6_wrapper import MF6Builder
from riv_benchmark import (
    expected_chd_budget,
    expected_heads,
    expected_riv_exchange,
    riv_bottom_limited_definition,
    riv_head_above_bottom_definition,
)
from test_flow_model import diagnostic_codes
from test_project_api import client_with_store, create_project


def riv_payload(project, grid_model_id, definition=None, *, include_wel=False, riv_cell=None):
    definition = definition or riv_head_above_bottom_definition()
    payload = steady_flow_payload(project, grid_model_id)
    if not include_wel:
        payload["boundaries"]["wel"] = []
    payload["boundaries"]["riv"] = [
        {
            "boundary_id": "main_river",
            "name": "Main river",
            "description": "Grid-cell RIV benchmark boundary",
            "cells": [
                {
                    "cell_id": riv_cell or cell_id(grid_model_id, 0, 0, 2),
                    "stage": definition.stage,
                    "conductance": definition.conductance,
                    "river_bottom": definition.river_bottom,
                }
            ],
        }
    ]
    return payload


def package_by_name(manifest, name):
    return {item["name"]: item for item in manifest["package_budget"]["packages"]}[name]


def create_project_grid(client, store, project_id="prj_riv"):
    project = create_project(client, project_id=project_id)
    grid_model, arrays = create_simple_flow_grid(store, project)
    return project, grid_model, arrays


def test_legacy_line_riv_rejects_missing_conductance_and_bottom(tmp_path):
    builder = MF6Builder("legacy_riv", str(tmp_path / "legacy_riv"), mf6_executable="mf6")
    builder.initialize_sim()
    builder.setup_dis(
        nlay=1,
        nrow=1,
        ncol=1,
        delr=1.0,
        delc=1.0,
        top=10.0,
        botm=[0.0],
        idomain=np.ones((1, 1, 1), dtype=int),
        origin_x=0.0,
        origin_y=1.0,
    )
    grid_info = {
        "origin_x": 0.0,
        "origin_y": 1.0,
        "delr": 1.0,
        "delc": 1.0,
        "x_centers": np.array([[0.5]]),
        "y_centers": np.array([[0.5]]),
    }
    with pytest.raises(ValueError, match="requires explicit stage, conductance, and river bottom"):
        builder.setup_boundary_conditions(
            np.ones((1, 1), dtype=int),
            [{
                "type": "RIV",
                "p1": {"x": 0.0, "y": 0.5},
                "p2": {"x": 1.0, "y": 0.5},
                "stage_start": 9.5,
                "stage_end": 9.5,
            }],
            wells=[],
            rch_array=np.zeros((1, 1), dtype=float),
            evt_array=np.zeros((1, 1), dtype=float),
            top_layer=np.full((1, 1), 10.0, dtype=float),
            grid_info=grid_info,
        )


def test_riv_schema_checker_and_preview_rules(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project, grid_model, arrays = create_project_grid(client, store, "prj_riv_schema")
    grid_id = grid_model["grid_model_id"]

    legal = client.post(
        f"/projects/{project['project_id']}/flow-models/validate",
        json=riv_payload(project, grid_id),
    )
    checker = legal.get_json()["checker"]
    assert legal.status_code == 200
    assert checker["runnable"] is True
    assert "RIV" in checker["summary"]["packages"]
    assert checker["summary"]["riv_cells"] == 1

    duplicate_id = riv_payload(project, grid_id)
    duplicate_id["boundaries"]["riv"].append(
        {
            "boundary_id": "main_river",
            "cells": [
                {
                    "cell_id": cell_id(grid_id, 0, 0, 3),
                    "stage": 9.4,
                    "conductance": 2.0,
                    "river_bottom": 8.0,
                }
            ],
        }
    )
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=duplicate_id)
    assert "FLOW_RIV_ID_DUPLICATE" in diagnostic_codes(response.get_json()["checker"])

    duplicate_cell = riv_payload(project, grid_id)
    duplicate_cell["boundaries"]["riv"].append(
        {
            "boundary_id": "secondary_river",
            "cells": [
                {
                    "cell_id": cell_id(grid_id, 0, 0, 2),
                    "stage": 9.7,
                    "conductance": 2.0,
                    "river_bottom": 8.0,
                }
            ],
        }
    )
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=duplicate_cell)
    assert "FLOW_RIV_CELL_DUPLICATE" in diagnostic_codes(response.get_json()["checker"])

    invalid = riv_payload(project, grid_id)
    cell = invalid["boundaries"]["riv"][0]["cells"][0]
    cell["stage"] = float("nan")
    cell["conductance"] = 0.0
    cell["river_bottom"] = 9.6
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=invalid)
    codes = diagnostic_codes(response.get_json()["checker"])
    assert "FLOW_RIV_STAGE_NONFINITE" in codes
    assert "FLOW_RIV_CONDUCTANCE_INVALID" in codes

    bad_relation = riv_payload(project, grid_id)
    bad_relation["boundaries"]["riv"][0]["cells"][0]["river_bottom"] = bad_relation["boundaries"]["riv"][0]["cells"][0]["stage"]
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=bad_relation)
    assert "FLOW_RIV_STAGE_NOT_ABOVE_BOTTOM" in diagnostic_codes(response.get_json()["checker"])

    wrong_grid = riv_payload(project, grid_id)
    wrong_grid["boundaries"]["riv"][0]["cells"][0]["cell_id"] = "grid_2222222222222222:L0:R0:C2"
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=wrong_grid)
    assert "FLOW_RIV_CELL_INVALID" in diagnostic_codes(response.get_json()["checker"])

    arrays["idomain"][0, 0, 2] = 0
    GridModelStore(store).save(store.get(project["project_id"]), grid_model, arrays)
    response = client.post(
        f"/projects/{project['project_id']}/flow-models/validate",
        json=riv_payload(project, grid_id),
    )
    assert "FLOW_RIV_CELL_INACTIVE" in diagnostic_codes(response.get_json()["checker"])
    arrays["idomain"][0, 0, 2] = 1
    GridModelStore(store).save(store.get(project["project_id"]), grid_model, arrays)

    chd_conflict = riv_payload(project, grid_id, riv_cell=cell_id(grid_id, 0, 0, 0))
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=chd_conflict)
    assert "FLOW_RIV_CHD_CONFLICT" in diagnostic_codes(response.get_json()["checker"])

    wel_shared = riv_payload(project, grid_id, include_wel=True)
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=wel_shared)
    checker = response.get_json()["checker"]
    assert checker["runnable"] is True
    assert "FLOW_RIV_WEL_SHARED_CELL" in diagnostic_codes(checker, bucket="warnings")

    outside_cell = riv_payload(project, grid_id)
    outside_cell["boundaries"]["riv"][0]["cells"][0]["stage"] = 20.0
    outside_cell["boundaries"]["riv"][0]["cells"][0]["river_bottom"] = -1.0
    response = client.post(f"/projects/{project['project_id']}/flow-models/validate", json=outside_cell)
    warning_codes = diagnostic_codes(response.get_json()["checker"], bucket="warnings")
    assert "FLOW_RIV_STAGE_ABOVE_CELL_TOP" in warning_codes
    assert "FLOW_RIV_BOTTOM_BELOW_CELL_BOTTOM" in warning_codes


def test_riv_compiler_writes_flopy_package_and_input_file(tmp_path):
    from project_store import ProjectStore

    store = ProjectStore(tmp_path / "projects")
    project = store.create(
        {
            "project_id": "prj_riv_compile",
            "name": "RIV Compile",
            "crs": {"authority": "EPSG", "code": 32650, "wkt": None, "axis_order": "xy"},
            "units": {"horizontal_length": "m", "vertical_length": "m", "time": "day", "flow": "m3/day"},
            "model_settings": {"model_type": "groundwater_flow", "flow_regime": "steady"},
            "references": {"geology_model_id": None, "grid_model_id": None, "flow_model_id": None},
        }
    )
    grid_model, _arrays = create_simple_flow_grid(store, project)
    service = FlowModelService(store)
    created = service.create(project["project_id"], grid_model["grid_model_id"], riv_payload(project, grid_model["grid_model_id"]))
    flow_model = created["flow_model"]

    assert "RIV" in flow_model["provenance"]["package_summary"]["packages"]
    assert flow_model["provenance"]["package_summary"]["riv"]["conductance_unit"] == "m2/day"

    compiled = service.compile_to_simulation(
        project["project_id"],
        flow_model["flow_model_id"],
        str(tmp_path / "compile"),
        mf6_executable="mf6",
    )
    gwf = compiled["gwf"]
    package_names = {package.package_type for package in gwf.packagelist}
    assert "riv" in package_names
    assert "wel" not in package_names

    riv = gwf.get_package("riv")
    data = riv.stress_period_data.get_data(key=0)
    assert tuple(data[0]["cellid"]) == (0, 0, 2)
    assert data[0]["stage"] == pytest.approx(9.6)
    assert data[0]["cond"] == pytest.approx(5.0)
    assert data[0]["rbot"] == pytest.approx(8.0)
    assert str(data[0]["boundname"]).startswith("main_river")

    compiled["simulation"].write_simulation()
    riv_file = Path(tmp_path / "compile" / "gwf.riv")
    text = riv_file.read_text(encoding="utf-8")
    assert "BEGIN period  1" in text
    assert "9.60000000" in text
    assert "5.00000000" in text
    assert "8.00000000" in text


@pytest.mark.integration
@pytest.mark.parametrize(
    "definition_factory",
    [riv_head_above_bottom_definition, riv_bottom_limited_definition],
)
def test_riv_run_api_benchmark_branches(tmp_path, monkeypatch, definition_factory):
    try:
        resolve_mf6_executable()
    except ExecutableResolutionError as exc:
        pytest.skip(f"MODFLOW 6 executable not available: {exc}")

    definition = definition_factory()
    client, store = client_with_store(tmp_path, monkeypatch)
    project, grid_model, _arrays = create_project_grid(client, store, f"prj_{definition.name.replace('-', '_')}")
    payload = riv_payload(project, grid_model["grid_model_id"], definition)
    create = client.post(f"/projects/{project['project_id']}/flow-models", json=payload)
    assert create.status_code == 201, create.get_json()
    flow_model = create.get_json()["flow_model"]

    response = client.post(
        f"/projects/{project['project_id']}/runs",
        json={"flow_model_id": flow_model["flow_model_id"]},
    )
    body = response.get_json()
    assert response.status_code == 201, body
    assert body["success"] is True
    assert body["status"] == "completed"

    run_id = body["run_id"]
    run_dir = Path(store.project_dir(project["project_id"])) / "runs" / run_id
    detail = client.get(f"/projects/{project['project_id']}/runs/{run_id}")
    manifest = detail.get_json()["run"]
    assert manifest["status"] == "completed"
    assert "RIV" in manifest["model"]["packages"]
    assert manifest["mf6"]["return_code"] == 0
    assert manifest["mf6"]["normal_termination"] is True
    assert manifest["convergence"]["converged"] is True
    assert manifest["outputs"]["riv"]["exists"] is True

    heads = flopy.utils.HeadFile(str(run_dir / "input" / "gwf.hds")).get_data()
    expected = expected_heads(definition)
    abs_diff = np.abs(heads - expected)
    rel_diff = abs_diff / np.maximum(np.abs(expected), 1.0e-30)
    np.testing.assert_allclose(heads, expected, atol=definition.head_abs_tolerance, rtol=definition.head_rel_tolerance)

    expected_riv_q = expected_riv_exchange(definition, expected)
    chd_budget = expected_chd_budget(definition, expected)
    riv_budget = package_by_name(manifest, "RIV")
    assert riv_budget["available"] is True
    assert riv_budget["in"] == pytest.approx(max(expected_riv_q, 0.0), abs=definition.budget_abs_tolerance)
    assert riv_budget["out"] == pytest.approx(max(-expected_riv_q, 0.0), abs=definition.budget_abs_tolerance)
    assert riv_budget["net"] == pytest.approx(expected_riv_q, abs=definition.budget_abs_tolerance)
    assert manifest["water_budget"]["total_in"] == pytest.approx(
        chd_budget["in"] + max(expected_riv_q, 0.0),
        abs=definition.budget_abs_tolerance,
    )
    assert manifest["water_budget"]["total_out"] == pytest.approx(
        chd_budget["out"] + max(-expected_riv_q, 0.0),
        abs=definition.budget_abs_tolerance,
    )
    assert manifest["water_budget"]["percent_discrepancy"] <= definition.percent_discrepancy_tolerance
    if definition.name == "riv-bottom-limited":
        assert float(heads[0, 0, 2]) <= definition.river_bottom
    else:
        assert float(heads[0, 0, 2]) > definition.river_bottom
    assert float(abs_diff.max()) <= definition.head_abs_tolerance
    assert float(rel_diff.max()) <= definition.head_rel_tolerance
