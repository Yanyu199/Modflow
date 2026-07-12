import copy
import math
import uuid
from datetime import datetime, timezone

try:
    from pyproj import CRS
except Exception:  # pragma: no cover - pyproj is normally installed with geopandas.
    CRS = None


SCHEMA_NAME = "modflow_project"
SCHEMA_VERSION = "1.0"

ALLOWED_TOP_LEVEL_FIELDS = {
    "schema_name",
    "schema_version",
    "project_id",
    "name",
    "description",
    "created_at",
    "modified_at",
    "crs",
    "units",
    "model_settings",
    "references",
    "metadata",
}
ALLOWED_CRS_FIELDS = {"authority", "code", "wkt", "axis_order"}
ALLOWED_UNIT_FIELDS = {"horizontal_length", "vertical_length", "time", "flow"}
ALLOWED_MODEL_SETTINGS_FIELDS = {"model_type", "flow_regime"}
ALLOWED_REFERENCE_FIELDS = {"geology_model_id", "flow_model_id"}

SUPPORTED_HORIZONTAL_LENGTH_UNITS = {"m"}
SUPPORTED_VERTICAL_LENGTH_UNITS = {"m"}
SUPPORTED_TIME_UNITS = {"day"}
SUPPORTED_FLOW_UNITS = {"m3/day"}
SUPPORTED_MODEL_TYPES = {"groundwater_flow"}
SUPPORTED_FLOW_REGIMES = {"steady"}


class ProjectValidationError(ValueError):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [str(errors)]
        super().__init__("; ".join(self.errors))


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def generate_project_id():
    return f"prj_{uuid.uuid4().hex[:16]}"


def parse_iso_datetime(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ProjectValidationError(f"{field} must be a timezone-aware ISO-8601 datetime")
    raw = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise ProjectValidationError(f"{field} must be a valid ISO-8601 datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProjectValidationError(f"{field} must include timezone information")
    return parsed


def assert_json_compatible(value, path="$"):
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProjectValidationError(f"{path} must not contain NaN or Infinity")
        return
    if isinstance(value, list):
        for idx, item in enumerate(value):
            assert_json_compatible(item, f"{path}[{idx}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProjectValidationError(f"{path} contains a non-string JSON object key")
            assert_json_compatible(item, f"{path}.{key}")
        return
    raise ProjectValidationError(f"{path} contains non-JSON value of type {type(value).__name__}")


def reject_unknown_fields(data, allowed, path):
    unknown = sorted(set(data.keys()) - allowed)
    if unknown:
        raise ProjectValidationError(f"{path} contains unsupported fields: {', '.join(unknown)}")


def validate_crs(crs):
    if not isinstance(crs, dict):
        raise ProjectValidationError("crs must be an object")
    reject_unknown_fields(crs, ALLOWED_CRS_FIELDS, "crs")

    axis_order = crs.get("axis_order")
    if axis_order != "xy":
        raise ProjectValidationError("crs.axis_order must be 'xy'")

    authority = crs.get("authority")
    code = crs.get("code")
    wkt = crs.get("wkt")

    if not authority and not wkt:
        raise ProjectValidationError("crs must include EPSG authority/code or wkt")
    if authority and authority.upper() != "EPSG":
        raise ProjectValidationError("crs.authority currently supports only EPSG")
    if authority:
        if not isinstance(code, int) or isinstance(code, bool) or code <= 0:
            raise ProjectValidationError("crs.code must be a positive EPSG integer")
    elif code is not None:
        raise ProjectValidationError("crs.code requires crs.authority")

    if wkt is not None and (not isinstance(wkt, str) or not wkt.strip()):
        raise ProjectValidationError("crs.wkt must be a non-empty string when provided")

    if CRS is None:
        if code == 4326:
            raise ProjectValidationError("geographic CRS EPSG:4326 is not supported for MODFLOW grid generation")
        return

    epsg_crs = None
    wkt_crs = None
    try:
        if authority:
            epsg_crs = CRS.from_epsg(code)
        if wkt:
            wkt_crs = CRS.from_wkt(wkt)
    except Exception as exc:
        raise ProjectValidationError(f"crs is not valid: {exc}")

    for candidate, label in ((epsg_crs, "EPSG CRS"), (wkt_crs, "WKT CRS")):
        if candidate is not None and candidate.is_geographic:
            raise ProjectValidationError(f"{label} is geographic; projected coordinates are required")

    if epsg_crs is not None and wkt_crs is not None:
        wkt_epsg = wkt_crs.to_epsg()
        if wkt_epsg is not None and wkt_epsg != code:
            raise ProjectValidationError("crs.authority/code conflicts with crs.wkt")


def validate_units(units):
    if not isinstance(units, dict):
        raise ProjectValidationError("units must be an object")
    reject_unknown_fields(units, ALLOWED_UNIT_FIELDS, "units")

    required = {
        "horizontal_length": SUPPORTED_HORIZONTAL_LENGTH_UNITS,
        "vertical_length": SUPPORTED_VERTICAL_LENGTH_UNITS,
        "time": SUPPORTED_TIME_UNITS,
        "flow": SUPPORTED_FLOW_UNITS,
    }
    for key, allowed in required.items():
        value = units.get(key)
        if value not in allowed:
            raise ProjectValidationError(
                f"units.{key} must be one of {', '.join(sorted(allowed))}; no implicit unit conversion is performed"
            )


def validate_model_settings(settings):
    if not isinstance(settings, dict):
        raise ProjectValidationError("model_settings must be an object")
    reject_unknown_fields(settings, ALLOWED_MODEL_SETTINGS_FIELDS, "model_settings")
    if settings.get("model_type") not in SUPPORTED_MODEL_TYPES:
        raise ProjectValidationError("model_settings.model_type must be groundwater_flow")
    if settings.get("flow_regime") not in SUPPORTED_FLOW_REGIMES:
        raise ProjectValidationError("model_settings.flow_regime must be steady")


def validate_references(references):
    if not isinstance(references, dict):
        raise ProjectValidationError("references must be an object")
    reject_unknown_fields(references, ALLOWED_REFERENCE_FIELDS, "references")
    for key in ALLOWED_REFERENCE_FIELDS:
        value = references.get(key)
        if value is not None and not isinstance(value, str):
            raise ProjectValidationError(f"references.{key} must be null or string")


def validate_project_document(project):
    if not isinstance(project, dict):
        raise ProjectValidationError("project must be a JSON object")
    assert_json_compatible(project)
    reject_unknown_fields(project, ALLOWED_TOP_LEVEL_FIELDS, "project")

    required_fields = {
        "schema_name",
        "schema_version",
        "project_id",
        "name",
        "created_at",
        "modified_at",
        "crs",
        "units",
        "model_settings",
        "references",
        "metadata",
    }
    missing = sorted(field for field in required_fields if field not in project)
    if missing:
        raise ProjectValidationError(f"project missing required fields: {', '.join(missing)}")

    if project["schema_name"] != SCHEMA_NAME:
        raise ProjectValidationError(f"schema_name must be {SCHEMA_NAME}")
    if project["schema_version"] != SCHEMA_VERSION:
        raise ProjectValidationError(f"unsupported schema_version: {project['schema_version']}")
    if not isinstance(project["project_id"], str) or not project["project_id"].strip():
        raise ProjectValidationError("project_id must be a non-empty string")
    if not isinstance(project["name"], str) or not project["name"].strip():
        raise ProjectValidationError("name must be a non-empty string")
    if not isinstance(project.get("description", ""), str):
        raise ProjectValidationError("description must be a string")

    parse_iso_datetime(project["created_at"], "created_at")
    parse_iso_datetime(project["modified_at"], "modified_at")
    validate_crs(project["crs"])
    validate_units(project["units"])
    validate_model_settings(project["model_settings"])
    validate_references(project["references"])
    if not isinstance(project["metadata"], dict):
        raise ProjectValidationError("metadata must be an object")

    return copy.deepcopy(project)


def build_project_document(payload, project_id=None):
    payload = copy.deepcopy(payload or {})
    now = now_iso()
    payload.setdefault("schema_name", SCHEMA_NAME)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["project_id"] = project_id or payload.get("project_id") or generate_project_id()
    payload.setdefault("description", "")
    payload.setdefault("created_at", now)
    payload["modified_at"] = payload.get("modified_at") or now
    payload.setdefault("model_settings", {"model_type": "groundwater_flow", "flow_regime": "steady"})
    payload.setdefault("references", {"geology_model_id": None, "flow_model_id": None})
    payload.setdefault("metadata", {})
    return validate_project_document(payload)


def merge_project_update(existing, patch):
    patch = copy.deepcopy(patch or {})
    reject_unknown_fields(patch, ALLOWED_TOP_LEVEL_FIELDS, "project update")
    immutable = {"schema_name", "schema_version", "project_id", "created_at"}
    for field in immutable:
        if field in patch and patch[field] != existing[field]:
            raise ProjectValidationError(f"{field} cannot be changed")

    updated = copy.deepcopy(existing)
    for field in ALLOWED_TOP_LEVEL_FIELDS - immutable:
        if field in patch:
            updated[field] = patch[field]
    updated["modified_at"] = now_iso()
    return validate_project_document(updated)
