import copy
import io
import zipfile

import fiona
import pytest
from shapely.geometry import Polygon, mapping

import app as app_module
from geometry_utils import parse_boundary_shapefile_zip as real_parse_boundary_shapefile_zip
from geology_test_helpers import valid_geology_model
from test_project_api import client_with_store, create_project


def post_valid_geology_model(client, project):
    response = client.post(
        f"/projects/{project['project_id']}/geology-models",
        json=valid_geology_model(project),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["geology_model"]


def error_codes(response):
    data = response.get_json()
    details = data.get("details", {})
    if isinstance(details, dict):
        return {item["code"] for item in details.get("errors", [])}
    return set()


def shapefile_zip(tmp_path):
    source_dir = tmp_path / "shape"
    source_dir.mkdir(parents=True)
    shp_path = source_dir / "boundary.shp"
    polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    schema = {"geometry": "Polygon", "properties": {"id": "int"}}
    with fiona.open(shp_path, "w", driver="ESRI Shapefile", schema=schema) as dst:
        dst.write({"geometry": mapping(polygon), "properties": {"id": 1}})

    zip_path = tmp_path / "boundary.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file_path in source_dir.iterdir():
            zf.write(file_path, arcname=file_path.name)
    return zip_path


def test_validate_api_returns_normalized_valid_model(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_geo_validate")

    response = client.post(
        f"/projects/{project['project_id']}/geology-models/validate",
        json=valid_geology_model(project),
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["geology_model"]["diagnostics"]["valid"] is True
    assert data["geology_model"]["spatial_reference"]["project_crs_code"] == 32650


def test_validate_api_reports_invalid_model_without_traceback_or_path(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_geo_invalid")
    payload = valid_geology_model(project)
    payload.pop("project_id")

    response = client.post(f"/projects/{project['project_id']}/geology-models/validate", json=payload)
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.get_json()["geology_model"]["diagnostics"]["valid"] is False
    assert "PROJECT_NOT_FOUND" in {
        item["code"] for item in response.get_json()["geology_model"]["diagnostics"]["errors"]
    }
    assert "Traceback" not in body
    assert str(tmp_path) not in body


def test_create_get_update_and_rebuild_geology_model(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_geo_crud")
    saved = post_valid_geology_model(client, project)

    active = client.get(f"/projects/{project['project_id']}/geology-models/active")
    assert active.status_code == 200
    assert active.get_json()["geology_model"]["geology_model_id"] == saved["geology_model_id"]
    assert store.get(project["project_id"])["references"]["geology_model_id"] == saved["geology_model_id"]

    update_payload = copy.deepcopy(saved)
    update_payload["description"] = "updated"
    update_payload["boreholes"][0]["intervals"][0]["bottom_elevation"] = 96.0
    update = client.put(
        f"/projects/{project['project_id']}/geology-models/{saved['geology_model_id']}",
        json=update_payload,
    )
    assert update.status_code == 200, update.get_json()
    assert update.get_json()["geology_model"]["description"] == "updated"
    assert update.get_json()["geology_model"]["derived_artifacts"]["status"] == "stale"

    app_module.GEO_MODELS.clear()
    rebuild = client.post(
        f"/projects/{project['project_id']}/geology-models/{saved['geology_model_id']}/rebuild"
    )
    assert rebuild.status_code == 200, rebuild.get_json()
    assert project["project_id"] in app_module.GEO_MODELS
    assert rebuild.get_json()["frontend"]["layers_count"] == 2


def test_project_a_b_geology_models_are_isolated_and_rebuild_from_disk(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project_a = create_project(client, project_id="prj_geo_a", name="A")
    project_b = create_project(client, project_id="prj_geo_b", name="B")

    model_a = valid_geology_model(project_a)
    model_b = valid_geology_model(project_b)
    model_b["boreholes"][0]["collar_elevation"] = 220.0
    model_b["boreholes"][0]["intervals"][0]["top_elevation"] = 220.0
    model_b["boreholes"][0]["intervals"][0]["bottom_elevation"] = 205.0
    model_b["boreholes"][0]["intervals"][1]["top_elevation"] = 205.0
    model_b["boreholes"][0]["intervals"][1]["bottom_elevation"] = 190.0

    response_a = client.post(f"/projects/{project_a['project_id']}/geology-models", json=model_a)
    response_b = client.post(f"/projects/{project_b['project_id']}/geology-models", json=model_b)
    assert response_a.status_code == 201
    assert response_b.status_code == 201

    app_module.GEO_MODELS.clear()
    active_a = client.get(f"/projects/{project_a['project_id']}/geology-models/active").get_json()["geology_model"]
    active_b = client.get(f"/projects/{project_b['project_id']}/geology-models/active").get_json()["geology_model"]

    assert active_a["boreholes"][0]["collar_elevation"] == 110.0
    assert active_b["boreholes"][0]["collar_elevation"] == 220.0
    assert active_a["geology_model_id"] != active_b["geology_model_id"]


def test_update_with_cross_project_geology_model_id_is_rejected(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project_a = create_project(client, project_id="prj_geo_cross_a")
    project_b = create_project(client, project_id="prj_geo_cross_b")
    saved_a = post_valid_geology_model(client, project_a)
    saved_b = post_valid_geology_model(client, project_b)

    response = client.put(
        f"/projects/{project_a['project_id']}/geology-models/{saved_b['geology_model_id']}",
        json=saved_a,
    )

    assert response.status_code == 404
    assert response.get_json()["code"] == "geology_model_not_found"


def test_validation_failure_does_not_overwrite_existing_model(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_geo_no_overwrite")
    saved = post_valid_geology_model(client, project)
    invalid = copy.deepcopy(saved)
    invalid["boreholes"][0]["intervals"][0]["top_elevation"] = 90.0

    response = client.put(
        f"/projects/{project['project_id']}/geology-models/{saved['geology_model_id']}",
        json=invalid,
    )
    active = client.get(f"/projects/{project['project_id']}/geology-models/active").get_json()["geology_model"]

    assert response.status_code == 400
    assert "BOREHOLE_NEGATIVE_THICKNESS" in error_codes(response)
    assert active["boreholes"][0]["intervals"][0]["top_elevation"] == 110.0


def test_missing_project_and_missing_geology_model_errors_are_stable(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    missing_project = client.get("/projects/not_here/geology-models/active")
    assert missing_project.status_code == 404
    assert missing_project.get_json()["code"] == "project_not_found"

    project = create_project(client, project_id="prj_geo_missing_active")
    missing_model = client.get(f"/projects/{project['project_id']}/geology-models/active")
    assert missing_model.status_code == 404
    assert missing_model.get_json()["code"] == "geology_model_not_found"


def test_project_crs_and_units_are_locked_after_geology_model(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_geo_lock")
    post_valid_geology_model(client, project)

    changed = copy.deepcopy(project)
    changed["crs"] = {"authority": "EPSG", "code": 32651, "wkt": None, "axis_order": "xy"}
    response = client.put(f"/projects/{project['project_id']}", json=changed)

    assert response.status_code == 409
    assert response.get_json()["code"] == "project_context_locked_by_geology_model"


def test_shapefile_upload_requires_project_crs_match(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="prj_geo_shape")
    crs_results = iter(
        [
            {"authority": "EPSG", "code": 32650, "wkt": None, "axis_order": "xy"},
            None,
            None,
            None,
            {"authority": "EPSG", "code": 32651, "wkt": None, "axis_order": "xy"},
        ]
    )

    def parse_with_controlled_crs(file_obj):
        parsed = real_parse_boundary_shapefile_zip(file_obj)
        parsed["crs"] = next(crs_results)
        return parsed

    monkeypatch.setattr(app_module, "parse_boundary_shapefile_zip", parse_with_controlled_crs)

    ok_zip = shapefile_zip(tmp_path / "ok")
    ok = client.post(
        "/upload-shapefile",
        data={"project_id": project["project_id"], "file": (io.BytesIO(ok_zip.read_bytes()), "ok.zip")},
        content_type="multipart/form-data",
    )
    assert ok.status_code == 200, ok.get_json()
    assert ok.get_json()["shapefile_crs"]["code"] == 32650
    assert ok.get_json()["geology_model"]["boundary"]["geometry"]["type"] == "Polygon"
    ok_boundary = ok.get_json()["geology_model"]["boundary"]

    missing_zip = shapefile_zip(tmp_path / "missing")
    missing_bytes = missing_zip.read_bytes()
    missing = client.post(
        "/upload-shapefile",
        data={"project_id": project["project_id"], "file": (io.BytesIO(missing_bytes), "missing.zip")},
        content_type="multipart/form-data",
    )
    missing_body = missing.get_data(as_text=True)
    assert missing.status_code == 400
    assert missing.get_json()["code"] == "shapefile_crs_missing"
    assert "Traceback" not in missing_body
    assert str(tmp_path) not in missing_body
    active_after_missing = client.get(f"/projects/{project['project_id']}/geology-models/active")
    assert active_after_missing.status_code == 200
    assert active_after_missing.get_json()["geology_model"]["boundary"] == ok_boundary

    confirmed_missing = client.post(
        "/upload-shapefile",
        data={
            "project_id": project["project_id"],
            "assume_project_crs": "true",
            "file": (io.BytesIO(missing_bytes), "missing.zip"),
        },
        content_type="multipart/form-data",
    )
    assert confirmed_missing.status_code == 200, confirmed_missing.get_json()
    confirmed_data = confirmed_missing.get_json()
    assert confirmed_data["shapefile_crs"]["code"] == 32650
    assert confirmed_data["shapefile_crs"]["source"] == "user_confirmed_project_crs"
    last_source = confirmed_data["geology_model"]["provenance"]["last_boundary_source"]
    assert last_source["crs_source"] == "user_confirmed_project_crs"
    assert last_source["file_crs_missing"] is True
    assert last_source["declared_project_crs"] == project["crs"]

    next_missing_zip = shapefile_zip(tmp_path / "next_missing")
    next_missing = client.post(
        "/upload-shapefile",
        data={"project_id": project["project_id"], "file": (io.BytesIO(next_missing_zip.read_bytes()), "next_missing.zip")},
        content_type="multipart/form-data",
    )
    assert next_missing.status_code == 400
    assert next_missing.get_json()["code"] == "shapefile_crs_missing"
    active_after_scoped_missing = client.get(f"/projects/{project['project_id']}/geology-models/active")
    assert active_after_scoped_missing.status_code == 200
    assert (
        active_after_scoped_missing.get_json()["geology_model"]["provenance"]["last_boundary_source"]
        == last_source
    )

    mismatch_zip = shapefile_zip(tmp_path / "mismatch")
    mismatch = client.post(
        "/upload-shapefile",
        data={"project_id": project["project_id"], "file": (io.BytesIO(mismatch_zip.read_bytes()), "mismatch.zip")},
        content_type="multipart/form-data",
    )
    assert mismatch.status_code == 400
    assert mismatch.get_json()["code"] == "project_crs_mismatch"


def test_json_size_limit_returns_clear_error(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    response = client.post(
        "/projects/prj_too_big/geology-models/validate",
        data=b'{"padding":"' + (b"x" * (2 * 1024 * 1024)) + b'"}',
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json()["code"] == "json_request_too_large"
