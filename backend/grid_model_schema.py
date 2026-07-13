import hashlib
import json
import math
import platform
import re
import sys
import uuid

import numpy as np
import scipy

from project_schema import ProjectValidationError, assert_json_compatible, now_iso, parse_iso_datetime


SCHEMA_NAME = "grid_model"
SCHEMA_VERSION = "1.0"
GRID_TYPE = "structured_dis"

MAX_NLAY = 200
MAX_NROW = 1000
MAX_NCOL = 1000
MAX_TOTAL_CELLS = 1_000_000
MIN_CELL_SIZE = 1.0e-6
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_RENDER_CELLS = 200_000

SUPPORTED_PINCHOUT_POLICIES = {"deactivate"}
SUPPORTED_BOUNDARY_ACTIVATION_RULES = {"cell_intersection"}

GRID_ID_PATTERN = re.compile(r"^grid_[0-9a-f]{16,32}$")
CELL_ID_PATTERN = re.compile(r"^(grid_[0-9a-f]{16,32}):L([0-9]+):R([0-9]+):C([0-9]+)$")

ALLOWED_CONFIG_FIELDS = {
    "grid_type",
    "cell_size",
    "rotation",
    "minimum_thickness",
    "pinchout_policy",
    "boundary_activation_rule",
    "minimum_boundary_overlap",
}

QUALITY_ERROR_CODES = {
    "GRID_ARRAY_SHAPE_INVALID",
    "GRID_NONFINITE_VALUE",
    "GRID_NEGATIVE_THICKNESS",
    "GRID_SURFACE_CROSSING",
    "GRID_NO_ACTIVE_CELLS",
    "GRID_EMPTY_LAYER",
    "GRID_ARTIFACT_STALE",
    "GRID_GEOLOGY_CHECKSUM_MISMATCH",
    "GRID_CELL_ID_INVALID",
}


class GridModelValidationError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        errors = diagnostics.get("errors", [])
        message = "; ".join(item.get("message", "grid validation error") for item in errors) or "grid validation error"
        super().__init__(message)


class GridModelNotFoundError(FileNotFoundError):
    pass


def generate_grid_model_id():
    return f"grid_{uuid.uuid4().hex[:16]}"


def validate_grid_model_id(grid_model_id):
    if not isinstance(grid_model_id, str) or not GRID_ID_PATTERN.fullmatch(grid_model_id):
        raise ProjectValidationError("grid_model_id must be grid_ plus 16-32 lowercase hex characters")
    return grid_model_id


def grid_item(level, code, path, message, **extra):
    item = {"level": level, "code": code, "path": path, "message": message}
    item.update(extra)
    return item


def quality_report(errors=None, warnings=None, infos=None, summary=None):
    errors = errors or []
    warnings = warnings or []
    infos = infos or []
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "summary": summary or {},
    }


def config_error(code, path, message):
    return grid_item("error", code, path, message)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def stable_hash(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def array_checksum(arrays):
    digest = hashlib.sha256()
    for name in sorted(arrays):
        arr = np.asarray(arrays[name])
        digest.update(name.encode("utf-8"))
        digest.update(str(arr.dtype).encode("utf-8"))
        digest.update(json.dumps(arr.shape).encode("ascii"))
        digest.update(np.ascontiguousarray(arr).tobytes())
    return digest.hexdigest()


def file_checksum(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_grid_config(payload=None):
    payload = payload or {}
    cell_size = payload.get("cell_size") or {}
    x_val = payload.get("x_val")
    y_val = payload.get("y_val")
    return {
        "grid_type": payload.get("grid_type", GRID_TYPE),
        "cell_size": {
            "x": cell_size.get("x", x_val if x_val is not None else 100.0),
            "y": cell_size.get("y", y_val if y_val is not None else 100.0),
        },
        "rotation": payload.get("rotation", 0.0),
        "minimum_thickness": payload.get("minimum_thickness", 0.1),
        "pinchout_policy": payload.get("pinchout_policy", "deactivate"),
        "boundary_activation_rule": payload.get("boundary_activation_rule", "cell_intersection"),
        "minimum_boundary_overlap": payload.get("minimum_boundary_overlap", 0.1),
    }


def validate_grid_config(payload, preview_cell_limit=True):
    try:
        assert_json_compatible(payload or {})
    except ProjectValidationError as exc:
        raise GridModelValidationError(quality_report([config_error("GRID_CONFIG_INVALID", "$", str(exc))]))

    raw = default_grid_config(payload)
    unknown = sorted(set((payload or {}).keys()) - (ALLOWED_CONFIG_FIELDS | {"x_mode", "y_mode", "x_val", "y_val", "n_layers", "z_thick"}))
    errors = []
    if unknown:
        errors.append(config_error("GRID_CONFIG_INVALID", "$", f"Unsupported grid config fields: {', '.join(unknown)}"))
    if raw["grid_type"] != GRID_TYPE:
        errors.append(config_error("GRID_CONFIG_INVALID", "grid_type", "Only structured_dis is supported"))
    cell_size = raw.get("cell_size")
    if not isinstance(cell_size, dict):
        errors.append(config_error("GRID_CONFIG_INVALID", "cell_size", "cell_size must be an object"))
    else:
        for axis in ("x", "y"):
            value = cell_size.get(axis)
            if not finite_number(value) or float(value) < MIN_CELL_SIZE:
                errors.append(config_error("GRID_CONFIG_INVALID", f"cell_size.{axis}", "cell size must be finite and positive"))
            else:
                cell_size[axis] = float(value)
    if not finite_number(raw.get("rotation")) or abs(float(raw["rotation"])) > 360.0:
        errors.append(config_error("GRID_CONFIG_INVALID", "rotation", "rotation must be finite degrees within [-360, 360]"))
    else:
        raw["rotation"] = float(raw["rotation"])
    if not finite_number(raw.get("minimum_thickness")) or float(raw["minimum_thickness"]) < 0.0:
        errors.append(config_error("GRID_CONFIG_INVALID", "minimum_thickness", "minimum_thickness must be finite and non-negative"))
    else:
        raw["minimum_thickness"] = float(raw["minimum_thickness"])
    if raw.get("pinchout_policy") not in SUPPORTED_PINCHOUT_POLICIES:
        errors.append(config_error("GRID_CONFIG_INVALID", "pinchout_policy", "Only pinchout_policy=deactivate is supported"))
    if raw.get("boundary_activation_rule") not in SUPPORTED_BOUNDARY_ACTIVATION_RULES:
        errors.append(config_error("GRID_CONFIG_INVALID", "boundary_activation_rule", "Only cell_intersection is supported"))
    overlap = raw.get("minimum_boundary_overlap")
    if not finite_number(overlap) or not (0.0 <= float(overlap) <= 1.0):
        errors.append(config_error("GRID_CONFIG_INVALID", "minimum_boundary_overlap", "minimum_boundary_overlap must be between 0 and 1"))
    else:
        raw["minimum_boundary_overlap"] = float(overlap)
    if errors:
        raise GridModelValidationError(quality_report(errors))
    return raw


def cell_id(grid_model_id, layer, row, column):
    validate_grid_model_id(grid_model_id)
    for name, value in (("layer", layer), ("row", row), ("column", column)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ProjectValidationError(f"{name} must be a non-negative 0-based integer")
    return f"{grid_model_id}:L{layer}:R{row}:C{column}"


def parse_cell_id(value, expected_grid_model_id=None, shape=None):
    if not isinstance(value, str):
        raise ProjectValidationError("cell_id must be a string")
    match = CELL_ID_PATTERN.fullmatch(value)
    if not match:
        raise ProjectValidationError("cell_id is invalid")
    grid_model_id, layer, row, column = match.groups()
    validate_grid_model_id(grid_model_id)
    if expected_grid_model_id and grid_model_id != expected_grid_model_id:
        raise ProjectValidationError("cell_id belongs to a different grid_model_id")
    parsed = {
        "grid_model_id": grid_model_id,
        "layer": int(layer),
        "row": int(row),
        "column": int(column),
    }
    if shape is not None:
        nlay, nrow, ncol = shape
        if parsed["layer"] >= nlay or parsed["row"] >= nrow or parsed["column"] >= ncol:
            raise ProjectValidationError("cell_id index is outside grid bounds")
    return parsed


def validate_grid_manifest(manifest, project):
    if not isinstance(manifest, dict):
        raise GridModelValidationError(quality_report([config_error("GRID_MODEL_INVALID", "$", "Grid manifest must be an object")]))
    assert_json_compatible(manifest)
    errors = []
    if manifest.get("schema_name") != SCHEMA_NAME:
        errors.append(config_error("GRID_MODEL_INVALID", "schema_name", f"schema_name must be {SCHEMA_NAME}"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(config_error("GRID_MODEL_INVALID", "schema_version", "Unsupported grid model version"))
    try:
        validate_grid_model_id(manifest.get("grid_model_id"))
    except Exception as exc:
        errors.append(config_error("GRID_MODEL_INVALID", "grid_model_id", str(exc)))
    if manifest.get("project_id") != project["project_id"]:
        errors.append(config_error("PROJECT_NOT_FOUND", "project_id", "Grid project_id must match project"))
    if manifest.get("grid_type") != GRID_TYPE:
        errors.append(config_error("GRID_MODEL_INVALID", "grid_type", "Only structured_dis is supported"))
    for field in ("created_at", "modified_at"):
        try:
            parse_iso_datetime(manifest.get(field), field)
        except ProjectValidationError as exc:
            errors.append(config_error("GRID_MODEL_INVALID", field, str(exc)))
    geometry = manifest.get("geometry") or {}
    for key in ("nlay", "nrow", "ncol"):
        value = geometry.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            errors.append(config_error("GRID_MODEL_INVALID", f"geometry.{key}", f"{key} must be positive integer"))
    if errors:
        raise GridModelValidationError(quality_report(errors))
    return manifest


def dependency_versions():
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }

