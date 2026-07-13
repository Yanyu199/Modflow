import json
import math

import pytest

from project_schema import (
    ProjectValidationError,
    build_project_document,
    migrate_project_document,
    validate_project_document,
)


def valid_payload():
    return {
        "project_id": "project_alpha",
        "name": "Alpha Project",
        "description": "schema test",
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
            "grid_model_id": None,
            "flow_model_id": None,
        },
        "metadata": {},
    }


def test_build_minimal_legal_project():
    project = build_project_document(valid_payload())

    assert project["schema_name"] == "modflow_project"
    assert project["schema_version"] == "1.1"
    assert project["project_id"] == "project_alpha"
    assert project["references"]["grid_model_id"] is None
    assert project["created_at"].endswith("+00:00")
    assert project["modified_at"].endswith("+00:00")


def test_validate_complete_legal_project_round_trips_json():
    project = build_project_document(valid_payload())
    encoded = json.dumps(project, allow_nan=False)
    decoded = json.loads(encoded)

    assert validate_project_document(decoded) == project


@pytest.mark.parametrize(
    "field",
    ["project_id", "crs", "units"],
)
def test_required_fields_are_enforced(field):
    project = build_project_document(valid_payload())
    project.pop(field)

    with pytest.raises(ProjectValidationError):
        validate_project_document(project)


def test_unsupported_schema_version_is_rejected():
    project = build_project_document(valid_payload())
    project["schema_version"] = "2.0"

    with pytest.raises(ProjectValidationError) as exc:
        validate_project_document(project)

    assert "unsupported schema_version" in str(exc.value)


def test_schema_1_0_migrates_grid_reference():
    project = build_project_document(valid_payload())
    project["schema_version"] = "1.0"
    project["references"].pop("grid_model_id")

    migrated, changed = migrate_project_document(project)
    validated = validate_project_document(project)

    assert changed is True
    assert migrated["schema_version"] == "1.1"
    assert migrated["references"]["grid_model_id"] is None
    assert validated["schema_version"] == "1.1"
    assert validated["references"]["geology_model_id"] is None


def test_illegal_unit_is_rejected():
    project = build_project_document(valid_payload())
    project["units"]["horizontal_length"] = "km"

    with pytest.raises(ProjectValidationError) as exc:
        validate_project_document(project)

    assert "units.horizontal_length" in str(exc.value)


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_nan_and_infinity_are_rejected(bad_value):
    project = build_project_document(valid_payload())
    project["metadata"]["bad"] = bad_value

    with pytest.raises(ProjectValidationError):
        validate_project_document(project)


def test_time_format_must_include_timezone():
    project = build_project_document(valid_payload())
    project["created_at"] = "2026-07-12T10:00:00"

    with pytest.raises(ProjectValidationError) as exc:
        validate_project_document(project)

    assert "timezone" in str(exc.value)


def test_unknown_fields_are_rejected():
    project = build_project_document(valid_payload())
    project["ui_active_tab"] = "flow"

    with pytest.raises(ProjectValidationError) as exc:
        validate_project_document(project)

    assert "unsupported fields" in str(exc.value)


def test_geographic_crs_is_rejected_for_modflow_grid():
    project = build_project_document(valid_payload())
    project["crs"]["code"] = 4326

    with pytest.raises(ProjectValidationError) as exc:
        validate_project_document(project)

    assert "geographic" in str(exc.value)
