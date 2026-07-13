import copy
import json

import pytest

import geology_model_schema as schema
from geology_model_schema import GeologyModelValidationError, require_valid_geology_model, validate_geology_model
from project_schema import build_project_document

from geology_test_helpers import borehole, boundary_feature, fault, valid_geology_model, with_model_change


def project(project_id="prj_schema"):
    return build_project_document(
        {
            "project_id": project_id,
            "name": "Schema Test",
            "crs": {"authority": "EPSG", "code": 32650, "wkt": None, "axis_order": "xy"},
            "units": {
                "horizontal_length": "m",
                "vertical_length": "m",
                "time": "day",
                "flow": "m3/day",
            },
        }
    )


def codes(model):
    return {item["code"] for item in model["diagnostics"]["errors"]}


def warning_codes(model):
    return {item["code"] for item in model["diagnostics"]["warnings"]}


def test_minimal_valid_geology_model():
    prj = project()
    model = validate_geology_model(valid_geology_model(prj, include_fault=False), prj)

    assert model["diagnostics"]["valid"] is True
    assert model["schema_name"] == "geology_model"
    assert model["schema_version"] == "1.0"
    assert model["project_id"] == prj["project_id"]
    assert model["diagnostics"]["summary"]["boundary_count"] == 1
    assert model["diagnostics"]["summary"]["borehole_count"] == 1
    assert model["diagnostics"]["summary"]["formation_count"] == 2
    assert "DERIVED_ARTIFACT_STALE" in warning_codes(model)


def test_complete_valid_geology_model_marks_fault_as_geologic_only():
    prj = project()
    model = validate_geology_model(valid_geology_model(prj, include_fault=True), prj)

    assert model["diagnostics"]["valid"] is True
    assert model["diagnostics"]["summary"]["fault_count"] == 1
    assert model["faults"][0]["properties"]["hydraulic_role"] == "geologic_partition_only"
    assert "FAULT_NOT_HFB" in warning_codes(model)


def test_unsupported_schema_version_returns_stable_error():
    prj = project()
    payload = valid_geology_model(prj)
    payload["schema_version"] = "9.9"

    with pytest.raises(GeologyModelValidationError) as exc:
        validate_geology_model(payload, prj)

    assert exc.value.diagnostics["errors"][0]["code"] == "SCHEMA_VERSION_UNSUPPORTED"


def test_missing_project_id_is_invalid_for_full_model():
    prj = project()
    payload = valid_geology_model(prj)
    payload.pop("project_id")

    model = validate_geology_model(payload, prj)

    assert model["diagnostics"]["valid"] is False
    assert "PROJECT_NOT_FOUND" in codes(model)


def test_project_crs_conflict_is_rejected_before_context_override():
    prj = project()
    payload = valid_geology_model(prj)
    payload["spatial_reference"] = {"project_crs_authority": "EPSG", "project_crs_code": 3857, "axis_order": "xy"}

    model = validate_geology_model(payload, prj)

    assert "PROJECT_CRS_MISMATCH" in codes(model)


def test_project_units_conflict_is_rejected_before_context_override():
    prj = project()
    payload = valid_geology_model(prj)
    payload["units"] = {"horizontal_length": "m", "vertical_length": "m", "time": "second", "flow": "m3/s"}

    model = validate_geology_model(payload, prj)

    assert "PROJECT_UNITS_MISMATCH" in codes(model)


def test_nan_and_infinity_are_rejected_as_json_invalid():
    prj = project()
    payload = valid_geology_model(prj)
    payload["boreholes"][0]["x"] = float("nan")

    with pytest.raises(GeologyModelValidationError) as exc:
        validate_geology_model(payload, prj)

    assert exc.value.diagnostics["errors"][0]["code"] == "JSON_INVALID"


def test_unknown_top_level_field_is_rejected():
    prj = project()
    payload = valid_geology_model(prj)
    payload["server_path"] = "C:/Users/example/private"

    with pytest.raises(GeologyModelValidationError) as exc:
        validate_geology_model(payload, prj)

    assert exc.value.diagnostics["errors"][0]["code"] == "UNKNOWN_FIELD"


def test_invalid_geology_model_id_is_reported_in_diagnostics():
    prj = project()
    payload = valid_geology_model(prj)
    payload["geology_model_id"] = "../bad"

    model = validate_geology_model(payload, prj)

    assert "GEOLOGY_MODEL_ID_INVALID" in codes(model)


def test_json_roundtrip_preserves_valid_standardized_model():
    prj = project()
    model = require_valid_geology_model(valid_geology_model(prj), prj)
    loaded = json.loads(json.dumps(model, ensure_ascii=False, allow_nan=False))
    revalidated = require_valid_geology_model(loaded, prj)

    assert revalidated["geology_model_id"] == model["geology_model_id"]
    assert revalidated["boreholes"] == model["boreholes"]


def test_boundary_rejects_unclosed_ring():
    prj = project()
    payload = with_model_change(
        valid_geology_model(prj),
        lambda model: model["boundary"]["geometry"]["coordinates"].__setitem__(
            0,
            [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]],
        ),
    )

    model = validate_geology_model(payload, prj)

    assert "BOUNDARY_INVALID" in codes(model)


def test_boundary_rejects_empty_and_zero_area_geometry():
    prj = project()
    payload = with_model_change(
        valid_geology_model(prj),
        lambda model: model.update(
            {
                "boundary": {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [2, 0], [0, 0]]]},
                }
            }
        ),
    )

    model = validate_geology_model(payload, prj)

    assert "BOUNDARY_INVALID" in codes(model)


def test_boundary_rejects_self_intersection():
    prj = project()
    payload = with_model_change(
        valid_geology_model(prj),
        lambda model: model.update(
            {
                "boundary": {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [100, 100], [0, 100], [100, 0], [0, 0]]],
                    },
                }
            }
        ),
    )

    model = validate_geology_model(payload, prj)

    assert "BOUNDARY_SELF_INTERSECTION" in codes(model)


def test_boundary_rejects_invalid_coordinate_and_point_limit(monkeypatch):
    prj = project()
    payload = valid_geology_model(prj)
    payload["boundary"]["geometry"]["coordinates"][0][1] = ["bad", 0]
    monkeypatch.setattr(schema, "MAX_BOUNDARY_POINTS", 3)

    model = validate_geology_model(payload, prj)

    assert "BOUNDARY_INVALID" in codes(model)


def test_borehole_and_formation_validation_errors():
    prj = project()
    cases = [
        ("duplicate id", lambda model: model["boreholes"].append(copy.deepcopy(model["boreholes"][0])), "BOREHOLE_ID_DUPLICATE"),
        ("empty intervals", lambda model: model["boreholes"][0].update({"intervals": []}), "BOREHOLE_INTERVAL_EMPTY"),
        (
            "negative thickness",
            lambda model: model["boreholes"][0]["intervals"][0].update({"top_elevation": 90.0, "bottom_elevation": 95.0}),
            "BOREHOLE_NEGATIVE_THICKNESS",
        ),
        (
            "overlap",
            lambda model: model["boreholes"][0]["intervals"][1].update({"top_elevation": 100.0}),
            "BOREHOLE_INTERVAL_OVERLAP",
        ),
        (
            "unknown formation",
            lambda model: model["boreholes"][0]["intervals"][0].update({"formation_id": "fm_missing"}),
            "FORMATION_UNKNOWN",
        ),
        (
            "order conflict",
            lambda model: model["stratigraphy"]["formations"][1].update({"order": 1}),
            "FORMATION_ORDER_CONFLICT",
        ),
        ("depth mode", lambda model: model["boreholes"][0].update({"interval_mode": "depth"}), "BOREHOLE_INTERVAL_EMPTY"),
    ]

    for _, mutator, expected_code in cases:
        model = validate_geology_model(with_model_change(valid_geology_model(prj), mutator), prj)
        assert expected_code in codes(model)


def test_outside_borehole_is_warning_not_silent_acceptance():
    prj = project()
    payload = valid_geology_model(prj)
    payload["boreholes"] = [borehole(x=500.0, y=500.0)]

    model = validate_geology_model(payload, prj)

    assert model["diagnostics"]["valid"] is True
    assert model["diagnostics"]["summary"]["outside_borehole_count"] == 1
    assert "BOREHOLE_OUTSIDE_BOUNDARY" in warning_codes(model)


def test_fault_validation_errors(monkeypatch):
    prj = project()
    cases = [
        ("duplicate", lambda model: model["faults"].append(copy.deepcopy(model["faults"][0])), "FAULT_ID_DUPLICATE"),
        (
            "too few points",
            lambda model: model["faults"][0]["geometry"].update({"coordinates": [[0.0, 0.0], [0.0, 0.0]]}),
            "FAULT_GEOMETRY_INVALID",
        ),
        (
            "non finite",
            lambda model: model["faults"][0]["geometry"].update({"coordinates": [[0.0, 0.0], [float("inf"), 1.0]]}),
            "JSON_INVALID",
        ),
    ]

    for _, mutator, expected_code in cases:
        payload = with_model_change(valid_geology_model(prj), mutator)
        if expected_code == "JSON_INVALID":
            with pytest.raises(GeologyModelValidationError) as exc:
                validate_geology_model(payload, prj)
            assert exc.value.diagnostics["errors"][0]["code"] == expected_code
        else:
            model = validate_geology_model(payload, prj)
            assert expected_code in codes(model)

    monkeypatch.setattr(schema, "MAX_FAULT_POINTS", 1)
    model = validate_geology_model(valid_geology_model(prj), prj)
    assert "FAULT_GEOMETRY_INVALID" in codes(model)


def test_missing_boundary_or_boreholes_can_be_warnings_in_partial_mode():
    prj = project()
    partial = {
        "schema_name": "geology_model",
        "schema_version": "1.0",
        "project_id": prj["project_id"],
        "stratigraphy": {"formations": []},
        "boreholes": [],
        "faults": [fault()],
    }

    model = validate_geology_model(partial, prj, allow_incomplete=True)

    assert model["diagnostics"]["valid"] is True
    assert "BOUNDARY_MISSING" in warning_codes(model)
    assert "BOREHOLE_INTERVAL_EMPTY" in warning_codes(model)
