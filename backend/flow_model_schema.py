"""Schema and validation helpers for persistent steady-flow models."""

from __future__ import annotations

import copy
import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


SCHEMA_NAME = "flow_model"
SCHEMA_VERSION = "1.0"
FLOW_MODEL_ID_PREFIX = "flow"
FLOW_MODEL_ID_PATTERN = re.compile(r"^flow_[0-9a-f]{16,32}$")

STATUS_DRAFT = "draft"
STATUS_READY = "ready"
STATUS_STALE = "stale"
STATUS_INVALID = "invalid"
ALLOWED_STATUS = {STATUS_DRAFT, STATUS_READY, STATUS_STALE, STATUS_INVALID}

ALLOWED_TOP_LEVEL_FIELDS = {
    "schema",
    "schema_name",
    "schema_version",
    "flow_model_id",
    "project_id",
    "grid_model_id",
    "status",
    "simulation",
    "initial_conditions",
    "hydraulic_properties",
    "boundaries",
    "solver",
    "output_control",
    "diagnostics",
    "provenance",
    "created_at",
    "updated_at",
}

ALLOWED_SIMULATION_FIELDS = {"type", "stress_periods", "time_units"}
ALLOWED_INITIAL_FIELDS = {"mode", "default", "values", "overrides"}
ALLOWED_HYDRAULIC_FIELDS = {"icelltype", "kx", "ky", "kz"}
ALLOWED_K_FIELDS = {"default", "overrides"}
ALLOWED_ICELLTYPE_FIELDS = {"mode", "values"}
ALLOWED_BOUNDARIES_FIELDS = {"chd", "wel"}
ALLOWED_SOLVER_FIELDS = {
    "complexity",
    "outer_maximum",
    "inner_maximum",
    "outer_dvclose",
    "inner_dvclose",
    "linear_acceleration",
}
ALLOWED_OC_FIELDS = {"save_head", "save_budget", "print_budget", "head_file", "budget_file"}


class FlowModelValidationError(ValueError):
    """Raised when a flow model payload cannot be accepted."""

    def __init__(self, message: str, diagnostics: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.diagnostics = diagnostics or empty_diagnostics()


class FlowModelNotFoundError(FileNotFoundError):
    """Raised when a requested flow model is missing."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def generate_flow_model_id() -> str:
    return f"{FLOW_MODEL_ID_PREFIX}_{uuid.uuid4().hex[:16]}"


def validate_flow_model_id(flow_model_id: str) -> str:
    if not isinstance(flow_model_id, str) or not FLOW_MODEL_ID_PATTERN.match(flow_model_id):
        raise FlowModelValidationError(
            "Invalid flow_model_id",
            diagnostics=diagnostics_with_error(
                "FLOW_MODEL_ID_INVALID",
                "flow_model_id must match flow_[0-9a-f]{16,32}.",
                "flow_model_id",
            ),
        )
    return flow_model_id


def empty_diagnostics() -> Dict[str, Any]:
    return {"errors": [], "warnings": [], "infos": []}


def diagnostic(
    level: str,
    code: str,
    message: str,
    path: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = path
    if details:
        item["details"] = details
    return item


def add_diagnostic(
    diagnostics: Dict[str, Any],
    level: str,
    code: str,
    message: str,
    path: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    key = {"error": "errors", "warning": "warnings", "info": "infos"}[level]
    diagnostics.setdefault(key, []).append(diagnostic(level, code, message, path, details))


def diagnostics_with_error(code: str, message: str, path: Optional[str] = None) -> Dict[str, Any]:
    diagnostics = empty_diagnostics()
    add_diagnostic(diagnostics, "error", code, message, path)
    return diagnostics


def has_errors(diagnostics: Dict[str, Any]) -> bool:
    return bool(diagnostics.get("errors"))


def summarize_diagnostics(diagnostics: Dict[str, Any]) -> Dict[str, int]:
    return {
        "errors": len(diagnostics.get("errors", [])),
        "warnings": len(diagnostics.get("warnings", [])),
        "infos": len(diagnostics.get("infos", [])),
    }


def default_simulation() -> Dict[str, Any]:
    return {
        "type": "steady",
        "stress_periods": [{"perlen": 1.0, "nstp": 1, "tsmult": 1.0, "steady": True}],
        "time_units": "DAYS",
    }


def default_solver() -> Dict[str, Any]:
    return {
        "complexity": "COMPLEX",
        "outer_maximum": 100,
        "inner_maximum": 100,
        "outer_dvclose": 1.0e-8,
        "inner_dvclose": 1.0e-8,
        "linear_acceleration": "BICGSTAB",
    }


def default_output_control() -> Dict[str, Any]:
    return {
        "save_head": True,
        "save_budget": True,
        "print_budget": True,
        "head_file": "gwf.hds",
        "budget_file": "gwf.bud",
    }


def build_base_document(
    *,
    project_id: str,
    grid_model_id: str,
    payload: Dict[str, Any],
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge a request payload with stable defaults and metadata."""

    if not isinstance(payload, dict):
        raise FlowModelValidationError(
            "Flow model payload must be an object.",
            diagnostics=diagnostics_with_error("FLOW_PAYLOAD_INVALID", "Flow model payload must be an object."),
        )

    document = copy.deepcopy(existing) if existing else {}
    now = utc_now_iso()
    document.update(copy.deepcopy(payload))
    document["schema"] = SCHEMA_NAME
    document["schema_name"] = SCHEMA_NAME
    document["schema_version"] = SCHEMA_VERSION
    document["project_id"] = project_id
    document["grid_model_id"] = grid_model_id
    document["flow_model_id"] = document.get("flow_model_id") or generate_flow_model_id()
    document["created_at"] = document.get("created_at") or now
    document["updated_at"] = now
    document.setdefault("status", STATUS_DRAFT)
    document.setdefault("simulation", default_simulation())
    document.setdefault("solver", default_solver())
    document.setdefault("output_control", default_output_control())
    document.setdefault("boundaries", {"chd": [], "wel": []})
    document.setdefault("diagnostics", empty_diagnostics())
    document.setdefault("provenance", {})
    document["provenance"].setdefault("created_by", "flow_model_v1")
    document["provenance"].setdefault("source", "user_input")
    document["provenance"].setdefault("schema_version", SCHEMA_VERSION)
    return document


def reject_unknown_fields(
    mapping: Dict[str, Any],
    allowed: Iterable[str],
    diagnostics: Dict[str, Any],
    path: str,
    code: str,
) -> None:
    if not isinstance(mapping, dict):
        add_diagnostic(diagnostics, "error", code, f"{path or 'value'} must be an object.", path)
        return
    allowed_set = set(allowed)
    for key in sorted(mapping.keys()):
        if key not in allowed_set:
            add_diagnostic(
                diagnostics,
                "error",
                code,
                f"Unknown field '{key}' is not allowed.",
                f"{path}.{key}" if path else key,
            )


def require_object(value: Any, diagnostics: Dict[str, Any], path: str, code: str) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        add_diagnostic(diagnostics, "error", code, f"{path} must be an object.", path)
        return None
    return value


def finite_float(value: Any, diagnostics: Dict[str, Any], path: str, code: str, *, positive: bool = False) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        add_diagnostic(diagnostics, "error", code, f"{path} must be a finite number.", path)
        return None
    if number != number or number in (float("inf"), float("-inf")):
        add_diagnostic(diagnostics, "error", code, f"{path} must be a finite number.", path)
        return None
    if positive and number <= 0:
        add_diagnostic(diagnostics, "error", code, f"{path} must be greater than zero.", path)
        return None
    return number


def int_value(value: Any, diagnostics: Dict[str, Any], path: str, code: str) -> Optional[int]:
    if isinstance(value, bool):
        add_diagnostic(diagnostics, "error", code, f"{path} must be an integer.", path)
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        add_diagnostic(diagnostics, "error", code, f"{path} must be an integer.", path)
        return None
    if str(value).strip() not in {str(number), f"{number}.0"} and not isinstance(value, int):
        add_diagnostic(diagnostics, "error", code, f"{path} must be an integer.", path)
        return None
    return number


def normalize_cell_ref(item: Any, diagnostics: Dict[str, Any], path: str) -> Optional[str]:
    if isinstance(item, str):
        cell_id = item
    elif isinstance(item, dict):
        cell_id = item.get("cell_id")
    else:
        add_diagnostic(diagnostics, "error", "FLOW_CELL_REF_INVALID", "Cell reference must be an object or cell_id.", path)
        return None
    if not isinstance(cell_id, str) or not cell_id.strip():
        add_diagnostic(diagnostics, "error", "FLOW_CELL_ID_REQUIRED", "cell_id is required.", f"{path}.cell_id")
        return None
    return cell_id.strip()


def compute_definition_hash(document: Dict[str, Any]) -> str:
    import json

    comparable = {
        key: value
        for key, value in document.items()
        if key not in {"diagnostics", "created_at", "updated_at", "status"}
    }
    raw = json.dumps(comparable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_static_structure(document: Dict[str, Any]) -> Dict[str, Any]:
    """Validate fields that do not require grid arrays."""

    diagnostics = empty_diagnostics()
    reject_unknown_fields(document, ALLOWED_TOP_LEVEL_FIELDS, diagnostics, "", "FLOW_UNKNOWN_FIELD")

    schema_value = document.get("schema_name", document.get("schema"))
    if schema_value != SCHEMA_NAME:
        add_diagnostic(diagnostics, "error", "FLOW_SCHEMA_INVALID", "schema_name must be flow_model.", "schema_name")
    if document.get("schema") and document.get("schema_name") and document["schema"] != document["schema_name"]:
        add_diagnostic(diagnostics, "error", "FLOW_SCHEMA_INVALID", "schema and schema_name must match.", "schema")
    if document.get("schema_version") != SCHEMA_VERSION:
        add_diagnostic(
            diagnostics,
            "error",
            "FLOW_SCHEMA_VERSION_INVALID",
            f"schema_version must be {SCHEMA_VERSION}.",
            "schema_version",
        )
    try:
        validate_flow_model_id(document.get("flow_model_id"))
    except FlowModelValidationError as exc:
        diagnostics["errors"].extend(exc.diagnostics.get("errors", []))

    if document.get("status") not in ALLOWED_STATUS:
        add_diagnostic(diagnostics, "error", "FLOW_STATUS_INVALID", "status is invalid.", "status")

    simulation = require_object(document.get("simulation"), diagnostics, "simulation", "FLOW_SIMULATION_INVALID")
    if simulation is not None:
        reject_unknown_fields(simulation, ALLOWED_SIMULATION_FIELDS, diagnostics, "simulation", "FLOW_UNKNOWN_FIELD")
        if simulation.get("type") != "steady":
            add_diagnostic(diagnostics, "error", "FLOW_ONLY_STEADY_SUPPORTED", "Only steady flow is supported in v1.", "simulation.type")
        if str(simulation.get("time_units", "")).upper() not in {"DAYS"}:
            add_diagnostic(diagnostics, "error", "FLOW_TIME_UNITS_INVALID", "time_units must be DAYS in v1.", "simulation.time_units")
        periods = simulation.get("stress_periods")
        if not isinstance(periods, list) or len(periods) != 1:
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_STRESS_PERIOD_INVALID",
                "Exactly one steady stress period is required in v1.",
                "simulation.stress_periods",
            )
        elif isinstance(periods[0], dict):
            period = periods[0]
            finite_float(period.get("perlen", 1.0), diagnostics, "simulation.stress_periods[0].perlen", "FLOW_PERIOD_INVALID", positive=True)
            steps = int_value(period.get("nstp", 1), diagnostics, "simulation.stress_periods[0].nstp", "FLOW_PERIOD_INVALID")
            finite_float(period.get("tsmult", 1.0), diagnostics, "simulation.stress_periods[0].tsmult", "FLOW_PERIOD_INVALID", positive=True)
            if steps is not None and steps < 1:
                add_diagnostic(diagnostics, "error", "FLOW_PERIOD_INVALID", "nstp must be at least 1.", "simulation.stress_periods[0].nstp")
            if period.get("steady") is not True:
                add_diagnostic(diagnostics, "error", "FLOW_STEADY_REQUIRED", "stress period must be steady.", "simulation.stress_periods[0].steady")
        else:
            add_diagnostic(diagnostics, "error", "FLOW_STRESS_PERIOD_INVALID", "Stress period must be an object.", "simulation.stress_periods[0]")

    initial = require_object(document.get("initial_conditions"), diagnostics, "initial_conditions", "FLOW_INITIAL_INVALID")
    if initial is not None:
        reject_unknown_fields(initial, ALLOWED_INITIAL_FIELDS, diagnostics, "initial_conditions", "FLOW_UNKNOWN_FIELD")
        if initial.get("mode") not in {"default_with_overrides", "per_layer"}:
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_INITIAL_MODE_INVALID",
                "initial_conditions.mode must be default_with_overrides or per_layer.",
                "initial_conditions.mode",
            )

    hydraulic = require_object(document.get("hydraulic_properties"), diagnostics, "hydraulic_properties", "FLOW_HYDRAULIC_INVALID")
    if hydraulic is not None:
        reject_unknown_fields(hydraulic, ALLOWED_HYDRAULIC_FIELDS, diagnostics, "hydraulic_properties", "FLOW_UNKNOWN_FIELD")
        for axis in ("kx", "ky", "kz"):
            spec = require_object(hydraulic.get(axis), diagnostics, f"hydraulic_properties.{axis}", "FLOW_K_INVALID")
            if spec is None:
                continue
            reject_unknown_fields(spec, ALLOWED_K_FIELDS, diagnostics, f"hydraulic_properties.{axis}", "FLOW_UNKNOWN_FIELD")
            finite_float(spec.get("default"), diagnostics, f"hydraulic_properties.{axis}.default", "FLOW_K_INVALID", positive=True)
            overrides = spec.get("overrides", [])
            if overrides is None:
                overrides = []
            if not isinstance(overrides, list):
                add_diagnostic(diagnostics, "error", "FLOW_K_OVERRIDES_INVALID", "K overrides must be a list.", f"hydraulic_properties.{axis}.overrides")
            else:
                for idx, override in enumerate(overrides):
                    if not isinstance(override, dict):
                        add_diagnostic(diagnostics, "error", "FLOW_K_OVERRIDE_INVALID", "K override must be an object.", f"hydraulic_properties.{axis}.overrides[{idx}]")
                        continue
                    normalize_cell_ref(override, diagnostics, f"hydraulic_properties.{axis}.overrides[{idx}]")
                    finite_float(
                        override.get("value"),
                        diagnostics,
                        f"hydraulic_properties.{axis}.overrides[{idx}].value",
                        "FLOW_K_INVALID",
                        positive=True,
                    )
        icelltype = require_object(hydraulic.get("icelltype"), diagnostics, "hydraulic_properties.icelltype", "FLOW_ICELLTYPE_INVALID")
        if icelltype is not None:
            reject_unknown_fields(icelltype, ALLOWED_ICELLTYPE_FIELDS, diagnostics, "hydraulic_properties.icelltype", "FLOW_UNKNOWN_FIELD")
            if icelltype.get("mode") != "per_layer":
                add_diagnostic(
                    diagnostics,
                    "error",
                    "FLOW_ICELLTYPE_MODE_INVALID",
                    "icelltype.mode must be per_layer.",
                    "hydraulic_properties.icelltype.mode",
                )
            values = icelltype.get("values")
            if not isinstance(values, list) or not values:
                add_diagnostic(
                    diagnostics,
                    "error",
                    "FLOW_ICELLTYPE_VALUES_INVALID",
                    "icelltype.values must be a non-empty list.",
                    "hydraulic_properties.icelltype.values",
                )
            elif any(value not in (0, 1) for value in values):
                add_diagnostic(
                    diagnostics,
                    "error",
                    "FLOW_ICELLTYPE_VALUES_INVALID",
                    "icelltype values must be 0 or 1.",
                    "hydraulic_properties.icelltype.values",
                )

    boundaries = require_object(document.get("boundaries"), diagnostics, "boundaries", "FLOW_BOUNDARIES_INVALID")
    if boundaries is not None:
        reject_unknown_fields(boundaries, ALLOWED_BOUNDARIES_FIELDS, diagnostics, "boundaries", "FLOW_UNKNOWN_FIELD")
        chd = boundaries.get("chd", [])
        wel = boundaries.get("wel", [])
        if not isinstance(chd, list):
            add_diagnostic(diagnostics, "error", "FLOW_CHD_INVALID", "boundaries.chd must be a list.", "boundaries.chd")
        else:
            for boundary_idx, boundary in enumerate(chd):
                if not isinstance(boundary, dict):
                    add_diagnostic(diagnostics, "error", "FLOW_CHD_INVALID", "CHD boundary must be an object.", f"boundaries.chd[{boundary_idx}]")
                    continue
                cells = boundary.get("cells")
                if not isinstance(cells, list) or not cells:
                    add_diagnostic(diagnostics, "error", "FLOW_CHD_CELLS_REQUIRED", "CHD boundary must contain at least one cell.", f"boundaries.chd[{boundary_idx}].cells")
                    continue
                for cell_idx, cell in enumerate(cells):
                    if not isinstance(cell, dict):
                        add_diagnostic(diagnostics, "error", "FLOW_CHD_CELL_INVALID", "CHD cell must be an object.", f"boundaries.chd[{boundary_idx}].cells[{cell_idx}]")
                        continue
                    normalize_cell_ref(cell, diagnostics, f"boundaries.chd[{boundary_idx}].cells[{cell_idx}]")
                    finite_float(cell.get("head"), diagnostics, f"boundaries.chd[{boundary_idx}].cells[{cell_idx}].head", "FLOW_CHD_HEAD_INVALID")
        if not isinstance(wel, list):
            add_diagnostic(diagnostics, "error", "FLOW_WEL_INVALID", "boundaries.wel must be a list.", "boundaries.wel")
        else:
            for well_idx, well in enumerate(wel):
                if not isinstance(well, dict):
                    add_diagnostic(diagnostics, "error", "FLOW_WEL_INVALID", "WEL entry must be an object.", f"boundaries.wel[{well_idx}]")
                    continue
                normalize_cell_ref(well, diagnostics, f"boundaries.wel[{well_idx}]")
                finite_float(well.get("rate"), diagnostics, f"boundaries.wel[{well_idx}].rate", "FLOW_WEL_RATE_INVALID")

    solver = require_object(document.get("solver"), diagnostics, "solver", "FLOW_SOLVER_INVALID")
    if solver is not None:
        reject_unknown_fields(solver, ALLOWED_SOLVER_FIELDS, diagnostics, "solver", "FLOW_UNKNOWN_FIELD")
        for key in ("outer_maximum", "inner_maximum"):
            value = int_value(solver.get(key), diagnostics, f"solver.{key}", "FLOW_SOLVER_INVALID")
            if value is not None and value < 1:
                add_diagnostic(diagnostics, "error", "FLOW_SOLVER_INVALID", f"{key} must be at least 1.", f"solver.{key}")
        finite_float(solver.get("outer_dvclose"), diagnostics, "solver.outer_dvclose", "FLOW_SOLVER_INVALID", positive=True)
        finite_float(solver.get("inner_dvclose"), diagnostics, "solver.inner_dvclose", "FLOW_SOLVER_INVALID", positive=True)

    oc = require_object(document.get("output_control"), diagnostics, "output_control", "FLOW_OUTPUT_INVALID")
    if oc is not None:
        reject_unknown_fields(oc, ALLOWED_OC_FIELDS, diagnostics, "output_control", "FLOW_UNKNOWN_FIELD")

    return diagnostics


def normalize_ids(document: Dict[str, Any]) -> Dict[str, Any]:
    """Fill optional stable entry identifiers without changing numerical meaning."""

    normalized = copy.deepcopy(document)
    for idx, boundary in enumerate(normalized.get("boundaries", {}).get("chd", []) or []):
        if isinstance(boundary, dict):
            boundary.setdefault("boundary_id", f"chd_{idx + 1:03d}")
            boundary.setdefault("name", boundary["boundary_id"])
    for idx, well in enumerate(normalized.get("boundaries", {}).get("wel", []) or []):
        if isinstance(well, dict):
            well.setdefault("well_id", f"wel_{idx + 1:03d}")
            well.setdefault("name", well["well_id"])
    return normalized
