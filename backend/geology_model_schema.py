import copy
import hashlib
import json
import math
import platform
import sys
import uuid
from datetime import datetime, timezone

import numpy as np
import scipy
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, shape

from geology_limits import (
    DEFAULT_INTERPOLATION,
    MAX_BOREHOLES,
    MAX_BOUNDARY_POINTS,
    MAX_FAULT_POINTS,
    MAX_FAULTS,
    MAX_FORMATIONS,
    MAX_INTERVALS_PER_BOREHOLE,
    MAX_JSON_DEPTH,
    SUPPORTED_BOUNDARY_TYPES,
    SUPPORTED_FAULT_TYPES,
    SUPPORTED_FORMATION_KINDS,
)
from project_schema import SCHEMA_VERSION as PROJECT_SCHEMA_VERSION
from project_schema import ProjectValidationError, assert_json_compatible, now_iso, parse_iso_datetime


SCHEMA_NAME = "geology_model"
SCHEMA_VERSION = "1.0"
ALLOWED_TOP_LEVEL_FIELDS = {
    "schema_name",
    "schema_version",
    "geology_model_id",
    "project_id",
    "name",
    "description",
    "created_at",
    "modified_at",
    "spatial_reference",
    "units",
    "boundary",
    "stratigraphy",
    "boreholes",
    "faults",
    "interpolation",
    "derived_artifacts",
    "diagnostics",
    "provenance",
    "extensions",
}


class GeologyModelValidationError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        errors = diagnostics.get("errors", [])
        message = "; ".join(item.get("message", "validation error") for item in errors) or "geology model invalid"
        super().__init__(message)


def generate_geology_model_id():
    return f"geo_{uuid.uuid4().hex[:16]}"


def valid_geology_model_id(value):
    if not isinstance(value, str) or not value.startswith("geo_"):
        return False
    suffix = value[4:]
    return 8 <= len(suffix) <= 32 and all(char in "0123456789abcdef" for char in suffix)


def error(code, path, message):
    return {"code": code, "path": path, "message": message}


def warning(code, path, message):
    return {"code": code, "path": path, "message": message}


def diagnostics(errors=None, warnings=None, summary=None):
    errors = errors or []
    warnings = warnings or []
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": summary or {},
    }


def check_depth(value, depth=0):
    if depth > MAX_JSON_DEPTH:
        raise ProjectValidationError(f"JSON nesting exceeds maximum depth {MAX_JSON_DEPTH}")
    if isinstance(value, dict):
        for item in value.values():
            check_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            check_depth(item, depth + 1)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def stable_hash(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def project_spatial_reference(project):
    crs = project["crs"]
    return {
        "project_crs_authority": crs.get("authority"),
        "project_crs_code": crs.get("code"),
        "axis_order": crs.get("axis_order", "xy"),
    }


def project_geology_units(project):
    units = project["units"]
    return {
        "horizontal_length": units.get("horizontal_length"),
        "vertical_length": units.get("vertical_length"),
    }


def default_provenance(extra=None):
    data = {
        "application": "flopy-project",
        "schema_created_by": "backend.geology_model_schema",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "notes": [],
    }
    if extra:
        data.update(extra)
    return data


def empty_geology_model(project, name="Site geology model"):
    now = now_iso()
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "geology_model_id": generate_geology_model_id(),
        "project_id": project["project_id"],
        "name": name,
        "description": "",
        "created_at": now,
        "modified_at": now,
        "spatial_reference": project_spatial_reference(project),
        "units": project_geology_units(project),
        "boundary": None,
        "stratigraphy": {"formations": []},
        "boreholes": [],
        "faults": [],
        "interpolation": copy.deepcopy(DEFAULT_INTERPOLATION),
        "derived_artifacts": {"mode": "rebuild_from_standardized_inputs", "status": "stale", "input_hash": None},
        "diagnostics": diagnostics(summary=empty_summary()),
        "provenance": default_provenance(),
        "extensions": {},
    }


def empty_summary():
    return {
        "boundary_count": 0,
        "borehole_count": 0,
        "formation_count": 0,
        "fault_count": 0,
        "outside_borehole_count": 0,
        "negative_thickness_count": 0,
        "crossing_interval_count": 0,
    }


def ensure_top_level(payload, project, existing=None):
    model = copy.deepcopy(existing) if existing else empty_geology_model(project)
    payload = copy.deepcopy(payload or {})

    if "schema_version" in payload and payload.get("schema_version") != SCHEMA_VERSION:
        diag = diagnostics([error("SCHEMA_VERSION_UNSUPPORTED", "schema_version", "Unsupported geology model version")])
        raise GeologyModelValidationError(diag)

    unknown = sorted(set(payload.keys()) - ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        diag = diagnostics([error("UNKNOWN_FIELD", key, "Unknown top-level geology model field") for key in unknown])
        raise GeologyModelValidationError(diag)

    for key, value in payload.items():
        if key in {"schema_name", "schema_version", "geology_model_id", "project_id", "created_at"}:
            if key in model and model.get(key) != value and existing:
                diag = diagnostics([error("IMMUTABLE_FIELD", key, f"{key} cannot be changed")])
                raise GeologyModelValidationError(diag)
            if not existing and key in {"geology_model_id", "created_at"}:
                model[key] = value
        elif key != "diagnostics":
            model[key] = value

    model["schema_name"] = SCHEMA_NAME
    model["schema_version"] = SCHEMA_VERSION
    model["project_id"] = project["project_id"]
    model["spatial_reference"] = project_spatial_reference(project)
    model["units"] = project_geology_units(project)
    model["modified_at"] = now_iso()
    model.setdefault("created_at", model["modified_at"])
    model.setdefault("geology_model_id", generate_geology_model_id())
    model.setdefault("description", "")
    model.setdefault("interpolation", copy.deepcopy(DEFAULT_INTERPOLATION))
    model.setdefault("derived_artifacts", {})
    model.setdefault("provenance", default_provenance())
    model.setdefault("extensions", {})
    return model


def preflight_project_context(payload, project, existing=None, allow_incomplete=False):
    errors = []
    if not isinstance(payload, dict):
        return [error("SCHEMA_INVALID", "$", "Geology model payload must be a JSON object")]

    if existing is None and not allow_incomplete:
        required = {"schema_name", "schema_version", "project_id"}
        for field in sorted(required - set(payload.keys())):
            errors.append(error("PROJECT_NOT_FOUND" if field == "project_id" else "SCHEMA_INVALID", field, f"{field} is required"))

    if "schema_name" in payload and payload.get("schema_name") != SCHEMA_NAME:
        errors.append(error("SCHEMA_VERSION_UNSUPPORTED", "schema_name", f"schema_name must be {SCHEMA_NAME}"))
    if "project_id" in payload and payload.get("project_id") != project["project_id"]:
        errors.append(error("PROJECT_NOT_FOUND", "project_id", "geology model project_id must match URL project"))
    if "spatial_reference" in payload and payload.get("spatial_reference") != project_spatial_reference(project):
        errors.append(error("PROJECT_CRS_MISMATCH", "spatial_reference", "Geology CRS must match project CRS"))
    if "units" in payload and payload.get("units") != project_geology_units(project):
        errors.append(error("PROJECT_UNITS_MISMATCH", "units", "Geology units must match project units"))
    return errors


def validate_boundary(boundary, allow_missing=False):
    errors, warnings = [], []
    if boundary in (None, {}, []):
        item = error("BOUNDARY_MISSING", "boundary", "Boundary is required")
        if allow_missing:
            warnings.append({**item, "message": "Boundary is not defined yet"})
        else:
            errors.append(item)
        return None, errors, warnings, 0, None

    if not isinstance(boundary, dict) or boundary.get("type") != "Feature":
        errors.append(error("BOUNDARY_INVALID", "boundary", "Boundary must be a GeoJSON Feature"))
        return None, errors, warnings, 0, None
    if "crs" in boundary:
        errors.append(error("PROJECT_CRS_MISMATCH", "boundary.crs", "Boundary must not override project CRS"))
    geometry = boundary.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") not in SUPPORTED_BOUNDARY_TYPES:
        errors.append(error("BOUNDARY_INVALID", "boundary.geometry", "Boundary must be Polygon or MultiPolygon"))
        return boundary, errors, warnings, 0, None

    try:
        geom = shape(geometry)
    except Exception as exc:
        errors.append(error("BOUNDARY_INVALID", "boundary.geometry", f"Invalid boundary geometry: {exc}"))
        return boundary, errors, warnings, 0, None

    point_count = count_coords(geometry.get("coordinates", []))
    if point_count > MAX_BOUNDARY_POINTS:
        errors.append(error("BOUNDARY_INVALID", "boundary.geometry.coordinates", "Boundary point count exceeds limit"))
    if geom.is_empty:
        errors.append(error("BOUNDARY_INVALID", "boundary.geometry", "Boundary geometry is empty"))
    if geom.area <= 0:
        errors.append(error("BOUNDARY_INVALID", "boundary.geometry", "Boundary area must be greater than zero"))
    if not geom.is_valid:
        errors.append(error("BOUNDARY_SELF_INTERSECTION", "boundary.geometry", "Boundary geometry is not valid"))
    if geometry["type"] == "Polygon":
        validate_polygon_rings(geometry.get("coordinates", []), "boundary.geometry.coordinates", errors)
    else:
        for idx, polygon in enumerate(geometry.get("coordinates", [])):
            validate_polygon_rings(polygon, f"boundary.geometry.coordinates[{idx}]", errors)

    normalized = {
        "type": "Feature",
        "properties": copy.deepcopy(boundary.get("properties") or {}),
        "geometry": copy.deepcopy(geometry),
    }
    return normalized, errors, warnings, 1, geom


def validate_polygon_rings(rings, path, errors):
    if not isinstance(rings, list) or not rings:
        errors.append(error("BOUNDARY_INVALID", path, "Polygon must include at least one ring"))
        return
    for idx, ring in enumerate(rings):
        if not isinstance(ring, list) or len(ring) < 4:
            errors.append(error("BOUNDARY_INVALID", f"{path}[{idx}]", "Ring must contain at least four positions"))
            continue
        if ring[0] != ring[-1]:
            errors.append(error("BOUNDARY_INVALID", f"{path}[{idx}]", "Ring must be closed"))
        for pos_idx, pos in enumerate(ring):
            if not valid_position(pos):
                errors.append(error("BOUNDARY_INVALID", f"{path}[{idx}][{pos_idx}]", "Coordinate must be finite x/y"))


def count_coords(coords):
    if not isinstance(coords, list):
        return 0
    if coords and isinstance(coords[0], (int, float)):
        return 1
    return sum(count_coords(item) for item in coords)


def valid_position(position):
    return (
        isinstance(position, (list, tuple))
        and len(position) >= 2
        and finite_number(position[0])
        and finite_number(position[1])
    )


def fault_positions(geometry):
    coords = geometry.get("coordinates", []) if isinstance(geometry, dict) else []
    if geometry.get("type") == "LineString":
        return coords if isinstance(coords, list) else []
    if geometry.get("type") == "MultiLineString":
        positions = []
        if isinstance(coords, list):
            for line in coords:
                if isinstance(line, list):
                    positions.extend(line)
        return positions
    return []


def validate_formations(stratigraphy):
    errors, warnings = [], []
    formations = (stratigraphy or {}).get("formations", [])
    if not isinstance(formations, list):
        return [], [error("FORMATION_UNKNOWN", "stratigraphy.formations", "Formations must be a list")], warnings
    if len(formations) > MAX_FORMATIONS:
        errors.append(error("FORMATION_UNKNOWN", "stratigraphy.formations", "Formation count exceeds limit"))

    seen_ids, seen_orders = set(), set()
    normalized = []
    for idx, formation in enumerate(formations):
        path = f"stratigraphy.formations[{idx}]"
        fid = formation.get("formation_id") if isinstance(formation, dict) else None
        order = formation.get("order") if isinstance(formation, dict) else None
        if not isinstance(fid, str) or not fid.strip():
            errors.append(error("FORMATION_UNKNOWN", f"{path}.formation_id", "formation_id is required"))
            continue
        if fid in seen_ids:
            errors.append(error("FORMATION_ORDER_CONFLICT", f"{path}.formation_id", "formation_id must be unique"))
        seen_ids.add(fid)
        if not isinstance(order, int) or isinstance(order, bool):
            errors.append(error("FORMATION_ORDER_CONFLICT", f"{path}.order", "formation order must be integer"))
        elif order in seen_orders:
            errors.append(error("FORMATION_ORDER_CONFLICT", f"{path}.order", "formation order must be unique"))
        seen_orders.add(order)
        kind = formation.get("kind", "unknown")
        if kind not in SUPPORTED_FORMATION_KINDS:
            warnings.append(warning("FORMATION_KIND_UNSUPPORTED", f"{path}.kind", "Unsupported kind stored as unknown"))
            kind = "unknown"
        normalized.append(
            {
                "formation_id": fid,
                "name": str(formation.get("name") or fid),
                "order": int(order) if isinstance(order, int) and not isinstance(order, bool) else 0,
                "kind": kind,
                "allow_missing": bool(formation.get("allow_missing", False)),
                "allow_pinchout": bool(formation.get("allow_pinchout", False)),
                "display": copy.deepcopy(formation.get("display") or {"color": "#cccccc"}),
                "source_layer_id": formation.get("source_layer_id", order),
            }
        )
    normalized.sort(key=lambda item: item["order"])
    return normalized, errors, warnings


def validate_boreholes(boreholes, formation_ids, boundary_geom=None, allow_missing=False):
    errors, warnings = [], []
    if not boreholes:
        item = error("BOREHOLE_INTERVAL_EMPTY", "boreholes", "At least one borehole is required")
        if allow_missing:
            warnings.append({**item, "message": "No boreholes defined yet"})
        else:
            errors.append(item)
        return [], errors, warnings, 0, 0, 0
    if not isinstance(boreholes, list):
        return [], [error("BOREHOLE_COORDINATE_INVALID", "boreholes", "Boreholes must be a list")], warnings, 0, 0, 0
    if len(boreholes) > MAX_BOREHOLES:
        errors.append(error("BOREHOLE_COORDINATE_INVALID", "boreholes", "Borehole count exceeds limit"))

    seen, normalized = set(), []
    outside_count = 0
    negative_thickness_count = 0
    overlap_count = 0
    for idx, borehole in enumerate(boreholes):
        path = f"boreholes[{idx}]"
        bid = borehole.get("borehole_id") if isinstance(borehole, dict) else None
        if not isinstance(bid, str) or not bid.strip():
            errors.append(error("BOREHOLE_COORDINATE_INVALID", f"{path}.borehole_id", "borehole_id is required"))
            continue
        if bid in seen:
            errors.append(error("BOREHOLE_ID_DUPLICATE", f"{path}.borehole_id", "borehole_id must be unique"))
        seen.add(bid)
        x, y = borehole.get("x"), borehole.get("y")
        collar = borehole.get("collar_elevation")
        total_depth = borehole.get("total_depth", 0.0)
        if not finite_number(x) or not finite_number(y) or not finite_number(collar):
            errors.append(error("BOREHOLE_COORDINATE_INVALID", path, "x/y/collar_elevation must be finite"))
        if not finite_number(total_depth) or float(total_depth) < 0:
            errors.append(error("BOREHOLE_COORDINATE_INVALID", f"{path}.total_depth", "total_depth must be non-negative"))
        intervals = borehole.get("intervals")
        if not isinstance(intervals, list) or not intervals:
            errors.append(error("BOREHOLE_INTERVAL_EMPTY", f"{path}.intervals", "intervals must not be empty"))
            continue
        if len(intervals) > MAX_INTERVALS_PER_BOREHOLE:
            errors.append(error("BOREHOLE_INTERVAL_EMPTY", f"{path}.intervals", "interval count exceeds limit"))
        mode = borehole.get("interval_mode", "elevation")
        if mode != "elevation":
            errors.append(error("BOREHOLE_INTERVAL_EMPTY", f"{path}.interval_mode", "Only elevation interval mode is supported"))
        normalized_intervals = []
        last_bottom = None
        for int_idx, interval in enumerate(intervals):
            ipath = f"{path}.intervals[{int_idx}]"
            fid = interval.get("formation_id")
            if fid not in formation_ids:
                errors.append(error("FORMATION_UNKNOWN", f"{ipath}.formation_id", "formation_id is not defined"))
            top = interval.get("top_elevation")
            bottom = interval.get("bottom_elevation")
            if not finite_number(top) or not finite_number(bottom):
                errors.append(error("BOREHOLE_COORDINATE_INVALID", ipath, "top/bottom elevation must be finite"))
                continue
            top, bottom = float(top), float(bottom)
            if top <= bottom:
                negative_thickness_count += 1
                errors.append(error("BOREHOLE_NEGATIVE_THICKNESS", ipath, "top_elevation must be above bottom_elevation"))
            if last_bottom is not None and top > last_bottom + 1e-9:
                overlap_count += 1
                errors.append(error("BOREHOLE_INTERVAL_OVERLAP", ipath, "intervals overlap or are out of order"))
            last_bottom = bottom
            normalized_intervals.append(
                {
                    "formation_id": fid,
                    "top_elevation": top,
                    "bottom_elevation": bottom,
                    "lithology": str(interval.get("lithology", "")),
                }
            )
        if boundary_geom is not None and finite_number(x) and finite_number(y):
            point = Point(float(x), float(y))
            if not (boundary_geom.contains(point) or boundary_geom.touches(point)):
                outside_count += 1
                warnings.append(warning("BOREHOLE_OUTSIDE_BOUNDARY", path, "Borehole lies outside project boundary"))
        normalized.append(
            {
                "borehole_id": bid,
                "x": float(x) if finite_number(x) else x,
                "y": float(y) if finite_number(y) else y,
                "collar_elevation": float(collar) if finite_number(collar) else collar,
                "total_depth": float(total_depth) if finite_number(total_depth) else total_depth,
                "interval_mode": "elevation",
                "intervals": normalized_intervals,
                "source_ref": str(borehole.get("source_ref") or "standardized_input"),
            }
        )
    return normalized, errors, warnings, outside_count, negative_thickness_count, overlap_count


def validate_faults(faults):
    errors, warnings = [], []
    if faults is None:
        faults = []
    if not isinstance(faults, list):
        return [], [error("FAULT_GEOMETRY_INVALID", "faults", "Faults must be a list")], warnings
    if len(faults) > MAX_FAULTS:
        errors.append(error("FAULT_GEOMETRY_INVALID", "faults", "Fault count exceeds limit"))

    seen, normalized = set(), []
    for idx, fault in enumerate(faults):
        path = f"faults[{idx}]"
        fid = fault.get("fault_id") if isinstance(fault, dict) else None
        if not isinstance(fid, str) or not fid.strip():
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.fault_id", "fault_id is required"))
            continue
        if fid in seen:
            errors.append(error("FAULT_ID_DUPLICATE", f"{path}.fault_id", "fault_id must be unique"))
        seen.add(fid)
        geometry = fault.get("geometry", {})
        if geometry.get("type") not in SUPPORTED_FAULT_TYPES:
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.geometry", "Fault must be LineString or MultiLineString"))
            continue
        positions = fault_positions(geometry)
        if not positions:
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.geometry.coordinates", "Fault coordinates must not be empty"))
            continue
        invalid_position = next((pos for pos in positions if not valid_position(pos)), None)
        if invalid_position is not None:
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.geometry.coordinates", "Fault coordinates must be finite x/y positions"))
            continue
        if count_coords(geometry.get("coordinates", [])) > MAX_FAULT_POINTS:
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.geometry.coordinates", "Fault point count exceeds limit"))
        try:
            geom = shape(geometry)
        except Exception as exc:
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.geometry", f"Invalid fault geometry: {exc}"))
            continue
        if geom.is_empty or not isinstance(geom, (LineString, MultiLineString)):
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.geometry", "Fault geometry is empty or unsupported"))
        coords = list(geom.coords) if isinstance(geom, LineString) else [c for line in geom.geoms for c in line.coords]
        distinct = {(float(x), float(y)) for x, y, *_ in coords if finite_number(x) and finite_number(y)}
        if len(distinct) < 2:
            errors.append(error("FAULT_GEOMETRY_INVALID", f"{path}.geometry", "Fault must contain at least two distinct points"))
        properties = copy.deepcopy(fault.get("properties") or {})
        properties.setdefault("hydraulic_role", "geologic_partition_only")
        warnings.append(warning("FAULT_NOT_HFB", path, "Fault is used only for geologic interpolation partitioning, not MODFLOW HFB"))
        normalized.append(
            {
                "fault_id": fid,
                "name": str(fault.get("name") or fid),
                "geometry": copy.deepcopy(geometry),
                "properties": properties,
                "source_ref": str(fault.get("source_ref") or "standardized_input"),
            }
        )
    return normalized, errors, warnings


def validate_geology_model(payload, project, existing=None, allow_incomplete=False):
    try:
        check_depth(payload)
        assert_json_compatible(payload)
    except ProjectValidationError as exc:
        raise GeologyModelValidationError(diagnostics([error("JSON_INVALID", "$", str(exc))]))
    preflight_errors = preflight_project_context(payload, project, existing=existing, allow_incomplete=allow_incomplete)
    if not isinstance(payload, dict):
        raise GeologyModelValidationError(diagnostics(preflight_errors))
    model = ensure_top_level(payload, project, existing=existing)

    errors, warnings = list(preflight_errors), []
    try:
        parse_iso_datetime(model["created_at"], "created_at")
        parse_iso_datetime(model["modified_at"], "modified_at")
    except ProjectValidationError as exc:
        errors.append(error("TIME_INVALID", "created_at/modified_at", str(exc)))

    if model.get("schema_name") != SCHEMA_NAME:
        errors.append(error("SCHEMA_VERSION_UNSUPPORTED", "schema_name", f"schema_name must be {SCHEMA_NAME}"))
    if model.get("schema_version") != SCHEMA_VERSION:
        errors.append(error("SCHEMA_VERSION_UNSUPPORTED", "schema_version", "Unsupported schema_version"))
    if not valid_geology_model_id(model.get("geology_model_id")):
        errors.append(error("GEOLOGY_MODEL_ID_INVALID", "geology_model_id", "geology_model_id must be geo_ plus 8-32 lowercase hex characters"))
    if model.get("project_id") != project["project_id"]:
        errors.append(error("PROJECT_NOT_FOUND", "project_id", "geology model project_id must match URL project"))
    if model.get("spatial_reference") != project_spatial_reference(project):
        errors.append(error("PROJECT_CRS_MISMATCH", "spatial_reference", "Geology CRS must match project CRS"))
    if model.get("units") != project_geology_units(project):
        errors.append(error("PROJECT_UNITS_MISMATCH", "units", "Geology units must match project units"))

    boundary, b_errors, b_warnings, boundary_count, boundary_geom = validate_boundary(
        model.get("boundary"), allow_missing=allow_incomplete
    )
    formations, f_errors, f_warnings = validate_formations(model.get("stratigraphy"))
    formation_ids = {item["formation_id"] for item in formations}
    boreholes, bh_errors, bh_warnings, outside_count, neg_count, overlap_count = validate_boreholes(
        model.get("boreholes"), formation_ids, boundary_geom=boundary_geom, allow_missing=allow_incomplete
    )
    faults, fault_errors, fault_warnings = validate_faults(model.get("faults"))

    errors.extend(b_errors + f_errors + bh_errors + fault_errors)
    warnings.extend(b_warnings + f_warnings + bh_warnings + fault_warnings)

    model["boundary"] = boundary
    model["stratigraphy"] = {"formations": formations}
    model["boreholes"] = boreholes
    model["faults"] = faults
    model["interpolation"] = {**copy.deepcopy(DEFAULT_INTERPOLATION), **(model.get("interpolation") or {})}
    model["provenance"] = {**default_provenance(), **(model.get("provenance") or {})}
    model["extensions"] = model.get("extensions") or {}
    model["derived_artifacts"] = model.get("derived_artifacts") or {}
    input_hash = stable_hash(
        {
            "boundary": model["boundary"],
            "formations": model["stratigraphy"]["formations"],
            "boreholes": model["boreholes"],
            "faults": model["faults"],
            "interpolation": model["interpolation"],
        }
    )
    if model["derived_artifacts"].get("input_hash") != input_hash:
        model["derived_artifacts"] = {
            "mode": "rebuild_from_standardized_inputs",
            "status": "stale",
            "input_hash": input_hash,
        }
        warnings.append(warning("DERIVED_ARTIFACT_STALE", "derived_artifacts", "Derived artifacts are stale or absent"))

    summary = empty_summary()
    summary.update(
        {
            "boundary_count": boundary_count,
            "borehole_count": len(boreholes),
            "formation_count": len(formations),
            "fault_count": len(faults),
            "outside_borehole_count": outside_count,
            "negative_thickness_count": neg_count,
            "crossing_interval_count": overlap_count,
        }
    )
    model["diagnostics"] = diagnostics(errors=errors, warnings=warnings, summary=summary)
    return model


def require_valid_geology_model(payload, project, existing=None):
    model = validate_geology_model(payload, project, existing=existing, allow_incomplete=False)
    if not model["diagnostics"]["valid"]:
        raise GeologyModelValidationError(model["diagnostics"])
    return model


def linestring_points_for_engine(fault):
    geom = shape(fault["geometry"])
    if isinstance(geom, LineString):
        coords = list(geom.coords)
    else:
        coords = list(list(geom.geoms)[0].coords)
    return [{"x": float(x), "y": float(y)} for x, y, *_ in coords]


def boundary_coords_for_frontend(boundary):
    if not boundary:
        return None
    geom = shape(boundary["geometry"])
    if isinstance(geom, MultiPolygon):
        geom = list(geom.geoms)[0]
    return [{"x": float(x), "y": float(y)} for x, y, *_ in geom.exterior.coords]


def normalized_to_frontend(model):
    layer_mapping = {
        idx: formation.get("source_layer_id", formation["order"])
        for idx, formation in enumerate(model["stratigraphy"]["formations"])
    }
    boreholes = []
    for bh in model["boreholes"]:
        layers = []
        for interval in bh["intervals"]:
            formation = next(
                (item for item in model["stratigraphy"]["formations"] if item["formation_id"] == interval["formation_id"]),
                None,
            )
            layers.append(
                {
                    "layer_id": formation.get("source_layer_id", formation["order"]) if formation else interval["formation_id"],
                    "layer_idx": model["stratigraphy"]["formations"].index(formation) if formation else 0,
                    "top": interval["top_elevation"],
                    "bottom": interval["bottom_elevation"],
                    "lithology": interval.get("lithology", ""),
                }
            )
        boreholes.append({"name": bh["borehole_id"], "x": bh["x"], "y": bh["y"], "layers": layers})
    return {
        "layers_count": len(model["stratigraphy"]["formations"]),
        "layer_mapping": layer_mapping,
        "boreholes": boreholes,
        "boundary": boundary_coords_for_frontend(model.get("boundary")),
        "faults": [linestring_points_for_engine(fault) for fault in model.get("faults", [])],
    }
