"""Flow model validation, compilation, and execution services."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import flopy
import numpy as np

from flow_model_schema import (
    FlowModelNotFoundError,
    FlowModelValidationError,
    add_diagnostic,
    compute_definition_hash,
    default_output_control,
    default_simulation,
    default_solver,
    empty_diagnostics,
    has_errors,
    normalize_ids,
    summarize_diagnostics,
    validate_static_structure,
)
from flow_model_store import FlowModelStore
from grid_model_schema import parse_cell_id
from grid_model_store import GridArtifactError, GridModelStore
from mf6_executable import resolve_mf6_executable
from post_process import process_results
from project_store import ProjectStore, ProjectNotFoundError
from run_workspace import cleanup_run_workspace, create_run_workspace


class FlowModelService:
    def __init__(self, project_store=None, grid_store=None, flow_store=None):
        self.project_store = project_store or ProjectStore()
        self.grid_store = grid_store or GridModelStore(self.project_store)
        self.flow_store = flow_store or FlowModelStore(self.project_store)

    def validate_payload(self, project_id: str, grid_model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        project, grid_manifest, arrays = self._load_project_grid(project_id, grid_model_id)
        document = self.flow_store.build_for_project(project, grid_model_id, payload)
        document = self._normalize_document(document, grid_manifest)
        diagnostics, materialized = self._check_document(project, grid_manifest, arrays, document)
        checked = self._finish_document(document, diagnostics, materialized)
        return {"flow_model": checked, "checker": self._checker_response(diagnostics, materialized)}

    def create(self, project_id: str, grid_model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        project, grid_manifest, arrays = self._load_project_grid(project_id, grid_model_id)
        document = self.flow_store.build_for_project(project, grid_model_id, payload)
        document = self._normalize_document(document, grid_manifest)
        diagnostics, materialized = self._check_document(project, grid_manifest, arrays, document)
        checked = self._finish_document(document, diagnostics, materialized)
        if has_errors(diagnostics):
            raise FlowModelValidationError("flow model checker found blocking errors", diagnostics)
        saved = self.flow_store.save(project, checked)
        return {"flow_model": saved, "checker": self._checker_response(diagnostics, materialized)}

    def update(self, project_id: str, flow_model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        existing = self.flow_store.get_active(project)
        if existing["flow_model_id"] != flow_model_id:
            raise FlowModelNotFoundError("flow_model_id is not the active flow model")
        grid_model_id = payload.get("grid_model_id") or existing["grid_model_id"]
        project, grid_manifest, arrays = self._load_project_grid(project_id, grid_model_id)
        document = self.flow_store.build_for_project(project, grid_model_id, payload, existing=existing)
        document["flow_model_id"] = existing["flow_model_id"]
        document["created_at"] = existing.get("created_at")
        document = self._normalize_document(document, grid_manifest)
        diagnostics, materialized = self._check_document(project, grid_manifest, arrays, document)
        checked = self._finish_document(document, diagnostics, materialized)
        if has_errors(diagnostics):
            raise FlowModelValidationError("flow model checker found blocking errors", diagnostics)
        saved = self.flow_store.save(project, checked)
        return {"flow_model": saved, "checker": self._checker_response(diagnostics, materialized)}

    def get_active(self, project_id: str) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        flow_model = self.flow_store.get_active(project)
        return {"flow_model": flow_model}

    def check(self, project_id: str, flow_model_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        if payload is not None:
            grid_model_id = payload.get("grid_model_id") or project.get("references", {}).get("grid_model_id")
            if not grid_model_id:
                raise FlowModelValidationError(
                    "grid_model_id is required",
                    empty_diagnostics(),
                )
            project, grid_manifest, arrays = self._load_project_grid(project_id, grid_model_id)
            document = self.flow_store.build_for_project(project, grid_model_id, payload)
        else:
            document = self.flow_store.get_active(project)
            if flow_model_id and document.get("flow_model_id") != flow_model_id:
                raise FlowModelNotFoundError("flow_model_id is not the active flow model")
            project, grid_manifest, arrays = self._load_project_grid(project_id, document["grid_model_id"])
        document = self._normalize_document(document, grid_manifest)
        diagnostics, materialized = self._check_document(project, grid_manifest, arrays, document)
        checked = self._finish_document(document, diagnostics, materialized)
        return {"flow_model": checked, "checker": self._checker_response(diagnostics, materialized)}

    def package_preview(self, project_id: str, flow_model_id: str) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        flow_model = self.flow_store.get_active(project)
        if flow_model.get("flow_model_id") != flow_model_id:
            raise FlowModelNotFoundError("flow_model_id is not the active flow model")
        project, grid_manifest, arrays = self._load_project_grid(project_id, flow_model["grid_model_id"])
        diagnostics, materialized = self._check_document(project, grid_manifest, arrays, flow_model)
        if has_errors(diagnostics):
            raise FlowModelValidationError("flow model checker found blocking errors", diagnostics)
        return {"package_preview": self._package_summary(flow_model, materialized), "checker": self._checker_response(diagnostics, materialized)}

    def mark_active_stale(self, project_id: str, reason: str):
        project = self.project_store.get(project_id)
        return self.flow_store.mark_active_stale(project, reason)

    def compile_to_simulation(
        self,
        project_id: str,
        flow_model_id: str,
        workspace: str,
        *,
        mf6_executable: Optional[str] = None,
    ) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        flow_model = self.flow_store.get_active(project)
        if flow_model["flow_model_id"] != flow_model_id:
            raise FlowModelNotFoundError("flow_model_id is not the active flow model")
        project, grid_manifest, arrays = self._load_project_grid(project_id, flow_model["grid_model_id"])
        diagnostics, materialized = self._check_document(project, grid_manifest, arrays, flow_model)
        if has_errors(diagnostics):
            raise FlowModelValidationError("flow model checker found blocking errors", diagnostics)
        sim, gwf = self._build_flopy_simulation(
            flow_model,
            grid_manifest,
            arrays,
            materialized,
            workspace,
            mf6_executable=mf6_executable,
        )
        return {
            "simulation": sim,
            "gwf": gwf,
            "flow_model": flow_model,
            "grid_manifest": grid_manifest,
            "grid_arrays": arrays,
            "materialized": materialized,
            "checker": self._checker_response(diagnostics, materialized),
        }

    def run(self, project_id: str, flow_model_id: str, *, keep_run_dir: Optional[bool] = None) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        flow_model = self.flow_store.get_active(project)
        if flow_model["flow_model_id"] != flow_model_id:
            raise FlowModelNotFoundError("flow_model_id is not the active flow model")
        project, grid_manifest, arrays = self._load_project_grid(project_id, flow_model["grid_model_id"])
        if flow_model.get("status") == "stale":
            diagnostics = empty_diagnostics()
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_MODEL_STALE",
                "Flow model is stale because its grid or upstream model changed. Re-check and save it before running.",
                "status",
            )
            raise FlowModelValidationError("flow model is stale", diagnostics)
        diagnostics, materialized = self._check_document(project, grid_manifest, arrays, flow_model)
        if has_errors(diagnostics):
            raise FlowModelValidationError("flow model checker found blocking errors", diagnostics)

        run_id, work_dir = create_run_workspace(prefix=f"flow-{flow_model_id}")
        success = False
        retained = True
        try:
            compiled = self.compile_to_simulation(project_id, flow_model_id, work_dir)
            sim = compiled["simulation"]
            sim.write_simulation()
            success, buff = sim.run_simulation(silent=True)
            if not success:
                raise RuntimeError("MODFLOW 6 run failed: " + "\n".join(buff[-20:]))
            grid_info = self._grid_info(grid_manifest, arrays)
            points = process_results(
                work_dir,
                grid_info["nlay"],
                grid_info["nrow"],
                grid_info["ncol"],
                grid_info["idomain"],
                grid_info["top"],
                grid_info["botm"],
                grid_info,
            )
            result = {
                "points": points,
                "pathlines": [],
                "logs": "MODFLOW 6 run completed through flow_model_v1.",
            }
            result.update(
                {
                    "success": True,
                    "run_id": run_id,
                    "work_dir": work_dir,
                    "retained": True,
                    "flow_model_id": flow_model_id,
                    "grid_model_id": grid_manifest["grid_model_id"],
                    "checker": self._checker_response(diagnostics, materialized),
                    "package_preview": self._package_summary(flow_model, materialized),
                    "mf6_stdout": buff,
                }
            )
            success = True
            return result
        finally:
            retained = cleanup_run_workspace(work_dir, success=success, keep_success=keep_run_dir)
            if "result" in locals():
                result["retained"] = retained

    def _load_project_grid(self, project_id: str, grid_model_id: str):
        project = self.project_store.get(project_id)
        grid_ref = project.get("references", {}).get("grid_model_id")
        if grid_ref and grid_ref != grid_model_id:
            diagnostics = empty_diagnostics()
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_GRID_REFERENCE_MISMATCH",
                "grid_model_id does not match the active project grid.",
                "grid_model_id",
            )
            raise FlowModelValidationError("grid_model_id mismatch", diagnostics)
        manifest = self.grid_store.get_active(project)
        if manifest.get("grid_model_id") != grid_model_id:
            diagnostics = empty_diagnostics()
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_GRID_REFERENCE_MISMATCH",
                "grid_model_id does not match the stored grid model.",
                "grid_model_id",
            )
            raise FlowModelValidationError("grid_model_id mismatch", diagnostics)
        arrays = self.grid_store.load_arrays(project, manifest)
        return project, manifest, arrays

    def _normalize_document(self, document: Dict[str, Any], grid_manifest: Dict[str, Any]) -> Dict[str, Any]:
        normalized = copy.deepcopy(document)
        normalized.setdefault("simulation", default_simulation())
        normalized.setdefault("solver", default_solver())
        normalized.setdefault("output_control", default_output_control())
        normalized.setdefault("boundaries", {"chd": [], "wel": []})
        normalized["simulation"] = {**default_simulation(), **(normalized.get("simulation") or {})}
        normalized["solver"] = {**default_solver(), **(normalized.get("solver") or {})}
        normalized["output_control"] = {**default_output_control(), **(normalized.get("output_control") or {})}
        normalized["boundaries"] = {
            "chd": list((normalized.get("boundaries") or {}).get("chd") or []),
            "wel": list((normalized.get("boundaries") or {}).get("wel") or []),
        }
        normalized = normalize_ids(normalized)
        return normalized

    def _finish_document(self, document: Dict[str, Any], diagnostics: Dict[str, Any], materialized: Dict[str, Any]) -> Dict[str, Any]:
        checked = copy.deepcopy(document)
        checked["diagnostics"] = {
            **diagnostics,
            "summary": summarize_diagnostics(diagnostics),
        }
        checked.setdefault("provenance", {})
        checked["provenance"]["definition_sha256"] = compute_definition_hash(checked)
        checked["provenance"]["package_summary"] = self._package_summary(checked, materialized)
        checked["status"] = "invalid" if has_errors(diagnostics) else "ready"
        return checked

    def _check_document(self, project: Dict[str, Any], grid_manifest: Dict[str, Any], arrays: Dict[str, np.ndarray], document: Dict[str, Any]):
        diagnostics = validate_static_structure(document)
        materialized: Dict[str, Any] = {"package_names": ["TDIS", "IMS", "GWF", "DIS", "IC", "NPF", "CHD", "WEL", "OC"]}
        if has_errors(diagnostics):
            return diagnostics, materialized

        geometry = grid_manifest.get("geometry") or {}
        shape = (int(geometry["nlay"]), int(geometry["nrow"]), int(geometry["ncol"]))
        idomain = np.asarray(arrays["idomain"])
        grid_status = grid_manifest.get("status")
        if grid_status != "ready":
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_GRID_STALE" if grid_status == "stale" else "FLOW_GRID_NOT_READY",
                "Flow model requires a ready active grid model.",
                "grid.status",
                {"status": grid_status},
            )
        grid_quality = grid_manifest.get("quality") or {}
        if grid_quality.get("errors"):
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_GRID_QUALITY_ERROR",
                "Grid quality contains blocking errors.",
                "grid.quality.errors",
                {"count": len(grid_quality.get("errors") or [])},
            )
        if not np.any(idomain > 0):
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_GRID_NO_ACTIVE_CELLS",
                "Grid must contain at least one active cell.",
                "grid.idomain",
            )

        self._check_simulation_units(project, document, diagnostics)
        strt = self._materialize_initial(document, arrays, shape, diagnostics)
        kx, ky, kz = self._materialize_k(document, arrays, shape, diagnostics)
        icelltype = self._materialize_icelltype(document, shape, diagnostics)
        chd_spd = self._materialize_chd(document, arrays, shape, idomain, diagnostics)
        wel_spd = self._materialize_wel(document, arrays, shape, idomain, diagnostics)
        chd_cells = {tuple(cellid) for cellid, _head in chd_spd}
        for cellid, rate in wel_spd:
            if tuple(cellid) in chd_cells:
                add_diagnostic(
                    diagnostics,
                    "error",
                    "FLOW_WEL_CHD_CONFLICT",
                    "A WEL cell cannot also be a CHD cell in flow_model_v1.",
                    "boundaries.wel",
                    {"cell": list(cellid), "rate": rate},
                )

        materialized.update(
            {
                "shape": shape,
                "strt": strt,
                "kx": kx,
                "ky": ky,
                "kz": kz,
                "icelltype": icelltype,
                "chd_spd": chd_spd,
                "wel_spd": wel_spd,
                "counts": {
                    "chd_cells": len(chd_spd),
                    "wel_cells": len(wel_spd),
                    "k_overrides": self._count_k_overrides(document),
                    "initial_overrides": len((document.get("initial_conditions") or {}).get("overrides") or []),
                },
            }
        )
        if not chd_spd:
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_CHD_REQUIRED",
                "At least one CHD boundary cell is required for the first steady-flow model.",
                "boundaries.chd",
            )
        return diagnostics, materialized

    def _check_simulation_units(self, project: Dict[str, Any], document: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        units = project.get("units") or {}
        if units.get("horizontal_length") != "m" or units.get("vertical_length") != "m" or units.get("time") != "day":
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_UNITS_UNSUPPORTED",
                "flow_model_v1 requires project units m/m/day.",
                "project.units",
            )

    def _materialize_initial(self, document, arrays, shape, diagnostics):
        initial = document.get("initial_conditions") or {}
        mode = initial.get("mode")
        top = np.asarray(arrays["top"], dtype=float)
        botm = np.asarray(arrays["botm"], dtype=float)
        idomain = np.asarray(arrays["idomain"])
        strt = np.zeros(shape, dtype=float)
        if mode == "per_layer":
            values = initial.get("values")
            if not isinstance(values, list) or len(values) != shape[0]:
                add_diagnostic(
                    diagnostics,
                    "error",
                    "FLOW_INITIAL_PER_LAYER_INVALID",
                    "initial_conditions.values length must equal nlay.",
                    "initial_conditions.values",
                )
                return strt
            for layer, value in enumerate(values):
                if self._is_finite_number(value):
                    strt[layer, :, :] = float(value)
                else:
                    add_diagnostic(diagnostics, "error", "FLOW_INITIAL_INVALID", "Initial head must be finite.", f"initial_conditions.values[{layer}]")
        elif mode == "default_with_overrides":
            default = initial.get("default")
            if self._is_finite_number(default):
                strt[:, :, :] = float(default)
            else:
                add_diagnostic(diagnostics, "error", "FLOW_INITIAL_INVALID", "initial_conditions.default must be finite.", "initial_conditions.default")
            seen = set()
            for idx, override in enumerate(initial.get("overrides") or []):
                cell = self._parse_cell(
                    override.get("cell_id") if isinstance(override, dict) else None,
                    document["grid_model_id"],
                    shape,
                    diagnostics,
                    f"initial_conditions.overrides[{idx}].cell_id",
                )
                head = override.get("head") if isinstance(override, dict) else None
                if cell is not None and idomain[cell] <= 0:
                    add_diagnostic(
                        diagnostics,
                        "error",
                        "FLOW_CELL_INACTIVE",
                        "Initial head override cell must be active.",
                        f"initial_conditions.overrides[{idx}].cell_id",
                    )
                    continue
                if cell is not None and cell in seen:
                    add_diagnostic(
                        diagnostics,
                        "error",
                        "FLOW_INITIAL_DUPLICATE_OVERRIDE",
                        "Duplicate initial head override for the same cell.",
                        f"initial_conditions.overrides[{idx}].cell_id",
                    )
                    continue
                if cell is not None:
                    seen.add(cell)
                if cell is not None and self._is_finite_number(head):
                    strt[cell] = float(head)
                elif cell is not None:
                    add_diagnostic(diagnostics, "error", "FLOW_INITIAL_INVALID", "Initial head override must be finite.", f"initial_conditions.overrides[{idx}].head")
        else:
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_INITIAL_MODE_INVALID",
                "initial_conditions.mode must be default_with_overrides or per_layer.",
                "initial_conditions.mode",
            )
        for layer in range(shape[0]):
            active = idomain[layer] > 0
            cell_top = top if layer == 0 else botm[layer - 1]
            cell_bottom = botm[layer]
            outside = active & ((strt[layer] > cell_top) | (strt[layer] < cell_bottom))
            if np.any(outside):
                add_diagnostic(
                    diagnostics,
                    "warning",
                    "FLOW_INITIAL_HEAD_OUTSIDE_CELL",
                    "Some initial heads are outside their cell top/bottom elevations.",
                    "initial_conditions",
                    {"count": int(np.count_nonzero(outside)), "layer": layer},
                )
        return strt

    def _materialize_k(self, document, arrays, shape, diagnostics):
        hydraulic = document.get("hydraulic_properties") or {}
        idomain = np.asarray(arrays["idomain"])
        result = []
        seen = {axis: set() for axis in ("kx", "ky", "kz")}
        for axis in ("kx", "ky", "kz"):
            spec = hydraulic.get(axis) or {}
            default = spec.get("default")
            values = np.ones(shape, dtype=float)
            if self._is_finite_number(default) and float(default) > 0:
                values[:, :, :] = float(default)
            else:
                add_diagnostic(diagnostics, "error", "FLOW_K_INVALID", f"{axis}.default must be positive finite.", f"hydraulic_properties.{axis}.default")
            for idx, override in enumerate(spec.get("overrides") or []):
                cell = self._parse_cell(
                    override.get("cell_id") if isinstance(override, dict) else None,
                    document["grid_model_id"],
                    shape,
                    diagnostics,
                    f"hydraulic_properties.{axis}.overrides[{idx}].cell_id",
                )
                value = override.get("value") if isinstance(override, dict) else None
                if cell is None:
                    continue
                if idomain[cell] <= 0:
                    add_diagnostic(
                        diagnostics,
                        "error",
                        "FLOW_CELL_INACTIVE",
                        f"{axis} override cell must be active.",
                        f"hydraulic_properties.{axis}.overrides[{idx}].cell_id",
                    )
                    continue
                if cell in seen[axis]:
                    add_diagnostic(
                        diagnostics,
                        "error",
                        "FLOW_K_DUPLICATE_OVERRIDE",
                        f"Duplicate {axis} override for the same cell.",
                        f"hydraulic_properties.{axis}.overrides[{idx}].cell_id",
                    )
                    continue
                seen[axis].add(cell)
                if self._is_finite_number(value) and float(value) > 0:
                    values[cell] = float(value)
                else:
                    add_diagnostic(diagnostics, "error", "FLOW_K_INVALID", f"{axis} override must be positive finite.", f"hydraulic_properties.{axis}.overrides[{idx}].value")
            result.append(values)
        return tuple(result)

    def _materialize_icelltype(self, document, shape, diagnostics):
        icelltype_spec = (document.get("hydraulic_properties") or {}).get("icelltype") or {}
        values = icelltype_spec.get("values")
        icelltype = np.zeros(shape, dtype=int)
        if not isinstance(values, list) or len(values) != shape[0]:
            add_diagnostic(
                diagnostics,
                "error",
                "FLOW_ICELLTYPE_VALUES_INVALID",
                "icelltype.values length must equal nlay.",
                "hydraulic_properties.icelltype.values",
            )
            return icelltype
        for layer, value in enumerate(values):
            if value in (0, 1):
                icelltype[layer, :, :] = int(value)
            else:
                add_diagnostic(
                    diagnostics,
                    "error",
                    "FLOW_ICELLTYPE_VALUES_INVALID",
                    "icelltype values must be 0 or 1.",
                    f"hydraulic_properties.icelltype.values[{layer}]",
                )
        return icelltype

    def _materialize_chd(self, document, arrays, shape, idomain, diagnostics):
        chd_spd = []
        seen = {}
        for boundary_idx, boundary in enumerate((document.get("boundaries") or {}).get("chd") or []):
            for cell_idx, cell_spec in enumerate(boundary.get("cells") or []):
                path = f"boundaries.chd[{boundary_idx}].cells[{cell_idx}]"
                cell = self._parse_cell(cell_spec.get("cell_id"), document["grid_model_id"], shape, diagnostics, f"{path}.cell_id")
                if cell is None:
                    continue
                if idomain[cell] <= 0:
                    add_diagnostic(diagnostics, "error", "FLOW_CELL_INACTIVE", "CHD cell must be active.", f"{path}.cell_id")
                    continue
                head = cell_spec.get("head")
                if not self._is_finite_number(head):
                    add_diagnostic(diagnostics, "error", "FLOW_CHD_HEAD_INVALID", "CHD head must be finite.", f"{path}.head")
                    continue
                head = float(head)
                if cell in seen and not math.isclose(seen[cell], head, rel_tol=0.0, abs_tol=1.0e-12):
                    add_diagnostic(diagnostics, "error", "FLOW_CHD_DUPLICATE_CELL", "Duplicate CHD cell has conflicting head values.", f"{path}.cell_id")
                    continue
                seen[cell] = head
                self._warn_head_bounds(head, cell, arrays, diagnostics, path, "FLOW_CHD_HEAD_OUTSIDE_CELL")
        return [(cell, head) for cell, head in sorted(seen.items())]

    def _materialize_wel(self, document, arrays, shape, idomain, diagnostics):
        wel_spd = []
        seen_counts = {}
        for idx, well in enumerate((document.get("boundaries") or {}).get("wel") or []):
            path = f"boundaries.wel[{idx}]"
            cell = self._parse_cell(well.get("cell_id"), document["grid_model_id"], shape, diagnostics, f"{path}.cell_id")
            if cell is None:
                continue
            if idomain[cell] <= 0:
                add_diagnostic(diagnostics, "error", "FLOW_CELL_INACTIVE", "WEL cell must be active.", f"{path}.cell_id")
                continue
            rate = well.get("rate")
            if not self._is_finite_number(rate):
                add_diagnostic(diagnostics, "error", "FLOW_WEL_RATE_INVALID", "WEL rate must be finite.", f"{path}.rate")
                continue
            seen_counts[cell] = seen_counts.get(cell, 0) + 1
            wel_spd.append((cell, float(rate)))
        duplicate_cells = sum(1 for count in seen_counts.values() if count > 1)
        if duplicate_cells:
            add_diagnostic(
                diagnostics,
                "warning",
                "FLOW_WEL_DUPLICATE_CELL",
                "Multiple WEL entries share the same cell and will be passed as separate stresses.",
                "boundaries.wel",
                {"duplicate_cell_count": duplicate_cells},
            )
        return wel_spd

    def _warn_head_bounds(self, head, cell, arrays, diagnostics, path, code):
        layer, row, column = cell
        top = np.asarray(arrays["top"], dtype=float)
        botm = np.asarray(arrays["botm"], dtype=float)
        cell_top = top[row, column] if layer == 0 else botm[layer - 1, row, column]
        cell_bottom = botm[layer, row, column]
        if head > cell_top or head < cell_bottom:
            add_diagnostic(
                diagnostics,
                "warning",
                code,
                "Head is outside the selected cell top/bottom elevations.",
                path,
                {"cell_top": float(cell_top), "cell_bottom": float(cell_bottom), "head": float(head)},
            )

    def _parse_cell(self, cell_id, grid_model_id, shape, diagnostics, path):
        try:
            parsed = parse_cell_id(cell_id, expected_grid_model_id=grid_model_id, shape=shape)
            return (parsed["layer"], parsed["row"], parsed["column"])
        except Exception as exc:
            add_diagnostic(diagnostics, "error", "FLOW_CELL_ID_INVALID", str(exc), path)
            return None

    def _count_k_overrides(self, document):
        hydraulic = document.get("hydraulic_properties") or {}
        return sum(len((hydraulic.get(axis) or {}).get("overrides") or []) for axis in ("kx", "ky", "kz"))

    def _package_summary(self, flow_model, materialized):
        counts = materialized.get("counts") or {}
        return {
            "packages": list(materialized.get("package_names") or []),
            "stress_periods": 1,
            "steady": True,
            "initial_condition": (flow_model.get("initial_conditions") or {}).get("mode"),
            "npf": {
                "k_axes": ["kx", "ky", "kz"],
                "icelltype": (flow_model.get("hydraulic_properties") or {}).get("icelltype", {}),
                "override_count": counts.get("k_overrides", 0),
            },
            "chd_cell_count": counts.get("chd_cells", 0),
            "wel_cell_count": counts.get("wel_cells", 0),
            "output_files": {
                "head": (flow_model.get("output_control") or {}).get("head_file", "gwf.hds"),
                "budget": (flow_model.get("output_control") or {}).get("budget_file", "gwf.bud"),
                "listing": "gwf.lst",
            },
        }

    def _checker_response(self, diagnostics, materialized):
        return {
            "runnable": not has_errors(diagnostics),
            "diagnostics": diagnostics,
            "summary": {
                **summarize_diagnostics(diagnostics),
                **(materialized.get("counts") or {}),
                "packages": list(materialized.get("package_names") or []),
            },
        }

    def _build_flopy_simulation(self, flow_model, grid_manifest, arrays, materialized, workspace, *, mf6_executable=None):
        exe = mf6_executable or resolve_mf6_executable().path
        workspace = str(Path(workspace).resolve())
        sim = flopy.mf6.MFSimulation(
            sim_name="sim",
            version="mf6",
            exe_name=exe,
            sim_ws=workspace,
        )
        period = flow_model["simulation"]["stress_periods"][0]
        flopy.mf6.ModflowTdis(
            sim,
            time_units=flow_model["simulation"].get("time_units", "DAYS"),
            nper=1,
            perioddata=[(float(period.get("perlen", 1.0)), int(period.get("nstp", 1)), float(period.get("tsmult", 1.0)))],
        )
        solver = flow_model.get("solver") or {}
        flopy.mf6.ModflowIms(
            sim,
            complexity=solver.get("complexity", "COMPLEX"),
            outer_maximum=int(solver.get("outer_maximum", 100)),
            inner_maximum=int(solver.get("inner_maximum", 100)),
            outer_dvclose=float(solver.get("outer_dvclose", 1.0e-8)),
            inner_dvclose=float(solver.get("inner_dvclose", 1.0e-8)),
            linear_acceleration=solver.get("linear_acceleration", "BICGSTAB"),
        )
        gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf", save_flows=True)
        geometry = grid_manifest["geometry"]
        flopy.mf6.ModflowGwfdis(
            gwf,
            nlay=int(geometry["nlay"]),
            nrow=int(geometry["nrow"]),
            ncol=int(geometry["ncol"]),
            delr=np.asarray(arrays["delr"], dtype=float),
            delc=np.asarray(arrays["delc"], dtype=float),
            top=np.asarray(arrays["top"], dtype=float),
            botm=np.asarray(arrays["botm"], dtype=float),
            idomain=np.asarray(arrays["idomain"], dtype=int),
            xorigin=float(geometry.get("origin", {}).get("x", 0.0)),
            yorigin=float(geometry.get("origin", {}).get("y", 0.0)),
            angrot=float(geometry.get("rotation_degrees", 0.0)),
        )
        flopy.mf6.ModflowGwfic(gwf, strt=materialized["strt"])
        flopy.mf6.ModflowGwfnpf(
            gwf,
            save_specific_discharge=True,
            icelltype=materialized["icelltype"],
            k=materialized["kx"],
            k22=materialized["ky"],
            k33=materialized["kz"],
        )
        chd_data = [(cellid, head) for cellid, head in materialized["chd_spd"]]
        flopy.mf6.ModflowGwfchd(gwf, stress_period_data={0: chd_data}, save_flows=True)
        wel_data = [(cellid, rate) for cellid, rate in materialized["wel_spd"]]
        flopy.mf6.ModflowGwfwel(gwf, stress_period_data={0: wel_data}, save_flows=True)
        oc = flow_model.get("output_control") or {}
        flopy.mf6.ModflowGwfoc(
            gwf,
            head_filerecord=oc.get("head_file", "gwf.hds"),
            budget_filerecord=oc.get("budget_file", "gwf.bud"),
            saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")],
            printrecord=[("BUDGET", "ALL")] if oc.get("print_budget", True) else None,
        )
        return sim, gwf

    def _grid_info(self, manifest, arrays):
        geometry = manifest["geometry"]
        nlay = int(geometry["nlay"])
        nrow = int(geometry["nrow"])
        ncol = int(geometry["ncol"])
        top = np.asarray(arrays["top"], dtype=float)
        botm = np.asarray(arrays["botm"], dtype=float)
        layer_tops = [top if layer == 0 else botm[layer - 1] for layer in range(nlay)]
        return {
            "grid_model_id": manifest["grid_model_id"],
            "nlay": nlay,
            "nrow": nrow,
            "ncol": ncol,
            "origin_x": float(geometry.get("origin", {}).get("x", 0.0)),
            "origin_y": float(geometry.get("origin", {}).get("y", 0.0)),
            "delr": np.asarray(arrays["delr"], dtype=float),
            "delc": np.asarray(arrays["delc"], dtype=float),
            "top": layer_tops,
            "botm": botm,
            "idomain": np.asarray(arrays["idomain"], dtype=int),
            "x_centers": np.asarray(arrays["x_centers"], dtype=float) if "x_centers" in arrays else None,
            "y_centers": np.asarray(arrays["y_centers"], dtype=float) if "y_centers" in arrays else None,
        }

    @staticmethod
    def _is_finite_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
