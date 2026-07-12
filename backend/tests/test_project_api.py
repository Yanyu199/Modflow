import io

import app as app_module
from project_store import ProjectStore


def project_payload(project_id=None, name="Project"):
    payload = {
        "name": name,
        "description": "",
        "crs": {
            "authority": "EPSG",
            "code": 32650,
            "wkt": None,
            "axis_order": "xy",
        },
        "units": {
            "horizontal_length": "m",
            "vertical_length": "m",
            "time": "day",
            "flow": "m3/day",
        },
        "model_settings": {
            "model_type": "groundwater_flow",
            "flow_regime": "steady",
        },
        "references": {
            "geology_model_id": None,
            "flow_model_id": None,
        },
        "metadata": {},
    }
    if project_id:
        payload["project_id"] = project_id
    return payload


def client_with_store(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "projects")
    monkeypatch.setattr(app_module, "project_store", store)
    app_module.GEO_MODELS.clear()
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client(), store


def create_project(client, project_id=None, name="Project"):
    response = client.post("/projects", json=project_payload(project_id=project_id, name=name))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["project"]


def test_create_get_and_update_project(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, name="Initial")

    get_response = client.get(f"/projects/{project['project_id']}")
    assert get_response.status_code == 200
    assert get_response.get_json()["project"]["name"] == "Initial"

    update_response = client.put(
        f"/projects/{project['project_id']}",
        json={"name": "Updated", "description": "new description"},
    )
    assert update_response.status_code == 200
    updated = update_response.get_json()["project"]
    assert updated["name"] == "Updated"
    assert updated["description"] == "new description"
    assert updated["project_id"] == project["project_id"]


def test_get_missing_project_returns_stable_error(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)

    response = client.get("/projects/not_here")
    data = response.get_json()

    assert response.status_code == 404
    assert data["code"] == "project_not_found"
    assert "Traceback" not in response.get_data(as_text=True)


def test_duplicate_project_id_returns_conflict(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    create_project(client, project_id="project_dupe")

    response = client.post("/projects", json=project_payload(project_id="project_dupe"))

    assert response.status_code == 409
    assert response.get_json()["code"] == "project_conflict"


def test_missing_required_fields_are_rejected(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)

    response = client.post("/projects", json={"name": "No CRS"})

    assert response.status_code == 400
    assert response.get_json()["code"] == "project_validation_error"


def test_project_id_path_traversal_is_rejected_without_absolute_path_leak(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)

    response = client.post("/projects", json=project_payload(project_id="../outside"))
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert "Traceback" not in body
    assert str(tmp_path) not in body


def test_missing_project_id_request_is_rejected(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)

    response = client.post("/preview-geometry", json={"params": {}, "boundary": []})

    assert response.status_code == 400
    assert response.get_json()["code"] == "project_validation_error"


def test_default_is_not_an_implicit_project_id(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)

    response = client.post("/preview-geometry", json={"project_id": "default", "params": {}, "boundary": []})

    assert response.status_code == 400
    assert response.get_json()["code"] == "project_validation_error"


def test_project_definitions_survive_store_recreation(tmp_path, monkeypatch):
    client, store = client_with_store(tmp_path, monkeypatch)
    project = create_project(client, project_id="persistent_project")

    reloaded_store = ProjectStore(store.root)
    reloaded = reloaded_store.get(project["project_id"])

    assert reloaded["name"] == project["name"]


def borehole_csv(z):
    return (
        "钻孔名称,X,Y,Z,分层ID,Top,Bottom,含水层岩性\n"
        f"BH1,0,0,{z},1,{z},{z - 10},sand\n"
    ).encode("utf-8")


def test_geological_cache_is_isolated_by_project_id(tmp_path, monkeypatch):
    client, _ = client_with_store(tmp_path, monkeypatch)
    project_a = create_project(client, project_id="project_a", name="A")
    project_b = create_project(client, project_id="project_b", name="B")

    for project, z in ((project_a, 100), (project_b, 200)):
        response = client.post(
            "/upload-boreholes",
            data={
                "project_id": project["project_id"],
                "file": (io.BytesIO(borehole_csv(z)), f"{project['project_id']}.csv"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 200, response.get_json()

    assert set(app_module.GEO_MODELS) == {"project_a", "project_b"}
    assert app_module.GEO_MODELS["project_a"].boreholes["BH1"]["Z"] == 100
    assert app_module.GEO_MODELS["project_b"].boreholes["BH1"]["Z"] == 200
