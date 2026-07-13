import copy
import json

import numpy as np
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, mapping, shape

import app as app_module
from geology_model_service import GeologyModelService
from geology_test_helpers import valid_geology_model
from grid_model_schema import (
    GridModelValidationError,
    cell_id,
    parse_cell_id,
    validate_grid_config,
)
from grid_model_service import GridModelService, build_quality_report
from project_schema import ProjectValidationError
from project_store import ProjectStore
from test_project_api import client_with_store, create_project


def post_valid_geology(client, project, model=None):
    response = client.post(
        f"/projects/{project['project_id']}/geology-models",
        json=model or valid_geology_model(project, include_fault=False),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["geology_model"]


def create_grid(client, project, payload=None):
    response = client.post(
        f"/projects/{project['project_id']}/grids",
        json=payload or {"cell_size": {"x": 25.0, "y": 25.0}, "minimum_boundary_overlap": 0.1},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["grid_model"]


def quality_codes(report, key="errors"):
    return {item["code"] for item in report.get(key, [])}


def test_grid_config_validation_accepts_legacy_cell_size_and_rejects_invalid_values(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_grid_config")

    response = client.post(
        f"/projects/{project['project_id']}/grids/validate-config",
        json={"x_val": 50.0, "y_val": 75.0, "rotation": 10.0},
    )
    assert response.status_code == 200
    assert response.get_json()["config"]["cell_size"] == {"x": 50.0, "y": 75.0}
    assert response.get_json()["config"]["rotation"] == 10.0

    invalid = client.post(
        f"/projects/{project['project_id']}/grids/validate-config",
        json={"cell_size": {"x": 0.0, "y": 10.0}, "rotation": 999.0},
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["code"] == "grid_model_validation_error"
    assert quality_codes(invalid.get_json()["details"]) == {"GRID_CONFIG_INVALID"}

    with pytest.raises(GridModelValidationError):
        validate_grid_config({"top": [[1.0]], "cell_size": {"x": 10.0, "y": 10.0}})


def test_cell_id_generation_and_strict_parse_validation():
    grid_id = "grid_" + "a" * 16
    value = cell_id(grid_id, 0, 12, 18)

    assert value == f"{grid_id}:L0:R12:C18"
    assert parse_cell_id(value, expected_grid_model_id=grid_id, shape=(1, 20, 20)) == {
        "grid_model_id": grid_id,
        "layer": 0,
        "row": 12,
        "column": 18,
    }

    with pytest.raises(ProjectValidationError):
        parse_cell_id(value, expected_grid_model_id="grid_" + "b" * 16)
    with pytest.raises(ProjectValidationError):
        parse_cell_id(value, expected_grid_model_id=grid_id, shape=(1, 10, 20))
    with pytest.raises(ProjectValidationError):
        parse_cell_id("grid_bad:L0:R0:C0")


def test_grid_api_persists_manifest_arrays_render_data_and_project_reference(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_grid_api")
    post_valid_geology(client, project)

    response = client.post(
        f"/projects/{project['project_id']}/grids",
        json={"cell_size": {"x": 25.0, "y": 25.0}, "minimum_boundary_overlap": 0.1},
    )
    body = response.get_data(as_text=True)
    data = response.get_json()

    assert response.status_code == 201, data
    assert data["success"] is True
    grid_model = data["grid_model"]
    grid_model_id = grid_model["grid_model_id"]
    assert grid_model["schema_name"] == "grid_model"
    assert grid_model["schema_version"] == "1.0"
    assert grid_model["status"] == "ready"
    assert grid_model["geometry"]["nlay"] == 2
    assert grid_model["geometry"]["nrow"] == 4
    assert grid_model["geometry"]["ncol"] == 4
    assert grid_model["artifacts"]["arrays_path"] == "artifacts/grid_arrays.npz"
    assert str(tmp_path) not in body
    assert store.get(project["project_id"])["references"]["grid_model_id"] == grid_model_id

    manifest_path = store.project_dir(project["project_id"]) / "grid" / "grid_model.json"
    artifact_path = store.project_dir(project["project_id"]) / "grid" / "artifacts" / "grid_arrays.npz"
    assert manifest_path.exists()
    assert artifact_path.exists()

    service_after_restart = GridModelService(ProjectStore(store.root))
    manifest, arrays = service_after_restart.load_arrays(project["project_id"], grid_model_id)
    assert manifest["grid_model_id"] == grid_model_id
    assert arrays["top"].shape == (4, 4)
    assert arrays["botm"].shape == (2, 4, 4)
    assert arrays["idomain"].shape == (2, 4, 4)
    assert int(np.count_nonzero(arrays["idomain"][0])) == 16
    assert int(np.count_nonzero(arrays["idomain"][1])) == 16
    assert np.all(arrays["idomain"][0] == arrays["idomain"][1])

    render = client.get(f"/projects/{project['project_id']}/grids/{grid_model_id}/render-data")
    render_data = render.get_json()
    assert render.status_code == 200
    assert len(render_data["points"]) == 32
    first_cell = render_data["points"][0]
    assert first_cell["cell_id"].startswith(f"{grid_model_id}:L0:R0:C0")
    assert first_cell["footprint"]
    assert "top" in first_cell and "bottom" in first_cell and "idomain" in first_cell

    detail = client.get(f"/projects/{project['project_id']}/grids/{grid_model_id}/cells/{first_cell['cell_id']}")
    assert detail.status_code == 200
    assert detail.get_json()["cell"]["cell_id"] == first_cell["cell_id"]

    other_project = create_project(client, project_id="prj_grid_api_other")
    cross = client.get(f"/projects/{other_project['project_id']}/grids/{grid_model_id}/summary")
    assert cross.status_code == 404
    assert "Traceback" not in cross.get_data(as_text=True)


def test_boundary_intersection_activates_cells_when_center_is_outside_boundary(tmp_path):
    store = ProjectStore(tmp_path / "projects")
    project = store.create(
        {
            "project_id": "prj_grid_intersection",
            "name": "Intersection",
            "crs": {"authority": "EPSG", "code": 32650, "wkt": None, "axis_order": "xy"},
            "units": {"horizontal_length": "m", "vertical_length": "m", "time": "day", "flow": "m3/day"},
            "model_settings": {"model_type": "groundwater_flow", "flow_regime": "steady"},
            "references": {"geology_model_id": None, "grid_model_id": None, "flow_model_id": None},
        }
    )
    model = valid_geology_model(project, include_fault=False)
    small_a = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    small_b = Polygon([(90, 90), (100, 90), (100, 100), (90, 100), (90, 90)])
    model["boundary"]["geometry"] = mapping(MultiPolygon([small_a, small_b]))

    service = GridModelService(store)
    config = validate_grid_config({"cell_size": {"x": 100.0, "y": 100.0}, "minimum_boundary_overlap": 0.01})
    arrays, _, quality, _ = service._generate_arrays(model, config)

    center = Point(float(arrays["x_centers"][0, 0]), float(arrays["y_centers"][0, 0]))
    assert not shape(model["boundary"]["geometry"]).contains(center)
    assert int(arrays["idomain"][0, 0, 0]) == 1
    assert quality["summary"]["boundary"]["edge_intersection_cell_count"] == 1


def test_grid_quality_report_flags_blocking_and_warning_conditions():
    manifest = {
        "geometry": {"nlay": 2, "nrow": 2, "ncol": 2},
        "generation": {"minimum_thickness": 1.0},
    }
    arrays = {
        "delr": np.array([10.0, 10.0]),
        "delc": np.array([10.0, 10.0]),
        "top": np.full((2, 2), 10.0),
        "botm": np.array(
            [
                [[9.0, 9.0], [9.0, 9.0]],
                [[12.0, 8.5], [8.5, 8.5]],
            ]
        ),
        "idomain": np.array(
            [
                [[1, 0], [0, 1]],
                [[0, 0], [0, 0]],
            ],
            dtype=np.int32,
        ),
    }

    report = build_quality_report(manifest, arrays)
    assert {"GRID_NEGATIVE_THICKNESS", "GRID_SURFACE_CROSSING", "GRID_EMPTY_LAYER"}.issubset(
        quality_codes(report)
    )
    assert "GRID_DISCONNECTED_COMPONENTS" in quality_codes(report, key="warnings")

    bad_shape = copy.deepcopy(arrays)
    bad_shape["top"] = np.full((1, 2), 10.0)
    report = build_quality_report(manifest, bad_shape)
    assert "GRID_ARRAY_SHAPE_INVALID" in quality_codes(report)


def test_geology_update_marks_active_grid_stale_and_run_model_rejects_it(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_grid_stale")
    geology = post_valid_geology(client, project)
    grid_model = create_grid(client, project)
    grid_model_id = grid_model["grid_model_id"]

    changed = copy.deepcopy(geology)
    changed["description"] = "updated geology"
    changed["boreholes"][0]["intervals"][0]["bottom_elevation"] = 96.0
    changed["boreholes"][0]["intervals"][1]["top_elevation"] = 96.0
    update = client.put(
        f"/projects/{project['project_id']}/geology-models/{geology['geology_model_id']}",
        json=changed,
    )
    assert update.status_code == 200, update.get_json()

    active = client.get(f"/projects/{project['project_id']}/grids/active")
    assert active.status_code == 200
    assert active.get_json()["grid_model"]["status"] == "stale"
    assert active.get_json()["grid_model"]["quality"]["stale_reasons"]

    run = client.post(
        "/run-model",
        json={
            "project_id": project["project_id"],
            "grid_model_id": grid_model_id,
            "params": {},
            "allow_legacy_flow_model": True,
        },
    )
    assert run.status_code == 400
    assert run.get_json()["code"] == "grid_model_validation_error"
    assert "GRID_ARTIFACT_STALE" in quality_codes(run.get_json()["details"])


def test_run_model_requires_grid_store_and_normalizes_legacy_cell_selection(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_grid_run")

    missing_grid = client.post("/run-model", json={"project_id": project["project_id"], "params": {}})
    assert missing_grid.status_code == 400
    assert missing_grid.get_json()["code"] == "grid_model_id_required"

    post_valid_geology(client, project)
    grid_model = create_grid(client, project)
    grid_model_id = grid_model["grid_model_id"]

    override = client.post(
        "/run-model",
        json={"project_id": project["project_id"], "grid_model_id": grid_model_id, "top": [[1.0]]},
    )
    assert override.status_code == 400
    assert override.get_json()["code"] == "grid_authoritative_arrays"

    captured = {}

    def fake_run_simulation(**kwargs):
        captured.update(kwargs)
        return {"points": [], "pathlines": []}, "simulation stub"

    monkeypatch.setattr(app_module, "run_simulation", fake_run_simulation)
    response = client.post(
        "/run-model",
        json={
            "project_id": project["project_id"],
            "grid_model_id": grid_model_id,
            "params": {},
            "allow_legacy_flow_model": True,
            "wells": [{"layer": 0, "row": 0, "col": 0, "rate": -100.0}],
            "k_cells": [{"cell_id": cell_id(grid_model_id, 0, 0, 1), "k_val": 10.0}],
        },
    )
    assert response.status_code == 200, response.get_json()
    assert captured["grid_model"]["manifest"]["grid_model_id"] == grid_model_id
    assert captured["wells"][0]["cell_id"] == cell_id(grid_model_id, 0, 0, 0)
    assert captured["k_cells"][0]["cell_id"] == cell_id(grid_model_id, 0, 0, 1)
    assert "LEGACY_ROW_COLUMN_SELECTION" in response.get_json()["logs"]

    invalid_legacy = client.post(
        "/run-model",
        json={
            "project_id": project["project_id"],
            "grid_model_id": grid_model_id,
            "params": {},
            "allow_legacy_flow_model": True,
            "wells": [{"row": 0, "rate": -1.0}],
        },
    )
    assert invalid_legacy.status_code == 400
    assert invalid_legacy.get_json()["code"] == "project_validation_error"
    assert "Traceback" not in invalid_legacy.get_data(as_text=True)
