"""Real MODFLOW 6 scale benchmark through the project RunService/Executor path."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from flow_model_service import FlowModelService
from grid_model_schema import cell_id, generate_grid_model_id
from grid_model_store import GridModelStore
from mf6_executable import resolve_mf6_executable
from project_schema import now_iso
from project_store import ProjectStore
from run_executor import LocalProcessRunExecutor
from run_manifest_schema import TERMINAL_STATUSES
from run_manifest_store import RunManifestStore
from runtime_config import RuntimeConfig


WORKSPACE_ROOT = Path(__file__).resolve().parent / "workspace" / "mf6-scale-benchmarks"


CASES = {
    "small": {"nlay": 1, "nrow": 1, "ncol": 10000},
    "medium": {"nlay": 1, "nrow": 100, "ncol": 1000},
    "large": {"nlay": 1, "nrow": 50, "ncol": 10000},
}


def _project_payload(project_id):
    return {
        "project_id": project_id,
        "name": f"MF6 scale benchmark {project_id}",
        "description": "",
        "crs": {"authority": "EPSG", "code": 32650, "wkt": None, "axis_order": "xy"},
        "units": {"horizontal_length": "m", "vertical_length": "m", "time": "day", "flow": "m3/day"},
        "model_settings": {"model_type": "groundwater_flow", "flow_regime": "steady"},
        "references": {"geology_model_id": None, "grid_model_id": None, "flow_model_id": None},
        "metadata": {"benchmark": "mf6_scale"},
    }


def _create_grid(store, project, case_name, nlay, nrow, ncol):
    delr = np.full(ncol, 100.0)
    delc = np.full(nrow, 100.0)
    top = np.full((nrow, ncol), 10.0)
    botm = np.full((nlay, nrow, ncol), 0.0)
    idomain = np.ones((nlay, nrow, ncol), dtype=np.int32)
    x_centers = (np.arange(ncol, dtype=float)[None, :] + 0.5) * 100.0
    y_centers = (np.arange(nrow, dtype=float)[:, None] + 0.5) * 100.0
    x_centers = np.repeat(x_centers, nrow, axis=0)
    y_centers = np.repeat(y_centers, ncol, axis=1)
    arrays = {
        "delr": delr,
        "delc": delc,
        "top": top,
        "botm": botm,
        "idomain": idomain,
        "x_centers": x_centers,
        "y_centers": y_centers,
    }
    now = now_iso()
    grid_model_id = generate_grid_model_id()
    manifest = {
        "schema_name": "grid_model",
        "schema_version": "1.0",
        "grid_model_id": grid_model_id,
        "project_id": project["project_id"],
        "geology_model_id": None,
        "name": f"MF6 scale {case_name}",
        "created_at": now,
        "modified_at": now,
        "grid_type": "structured_dis",
        "status": "ready",
        "generation": {
            "cell_size": {"x": 100.0, "y": 100.0},
            "minimum_boundary_overlap": 0.0,
            "minimum_thickness": 0.1,
            "index_base": 0,
            "cell_id_format": "<grid_model_id>:L<layer>:R<row>:C<column>",
        },
        "geometry": {
            "nlay": nlay,
            "nrow": nrow,
            "ncol": ncol,
            "origin": {"x": 0.0, "y": 0.0},
            "rotation_degrees": 0.0,
            "delr": {"type": "constant", "value": 100.0, "count": ncol},
            "delc": {"type": "constant", "value": 100.0, "count": nrow},
        },
        "artifacts": {},
        "quality": {"valid": True, "errors": [], "warnings": [], "infos": [], "summary": {"active_cell_count": nlay * nrow * ncol}},
        "provenance": {"application": "flopy-project", "schema_created_by": "mf6_scale_benchmark"},
    }
    saved = GridModelStore(store).save(project, manifest, arrays)
    store.update(project["project_id"], {"references": {**project["references"], "grid_model_id": grid_model_id}})
    return saved


def _flow_payload(project_id, grid_model_id, nrow, ncol, *, include_well=False):
    chd_cells = []
    for row in range(nrow):
        chd_cells.append({"cell_id": cell_id(grid_model_id, 0, row, 0), "head": 10.0})
        chd_cells.append({"cell_id": cell_id(grid_model_id, 0, row, ncol - 1), "head": 9.0})
    return {
        "project_id": project_id,
        "grid_model_id": grid_model_id,
        "simulation": {
            "type": "steady",
            "stress_periods": [{"perlen": 1.0, "nstp": 1, "tsmult": 1.0, "steady": True}],
            "time_units": "DAYS",
        },
        "initial_conditions": {"mode": "default_with_overrides", "default": 9.5, "overrides": []},
        "hydraulic_properties": {
            "icelltype": {"mode": "per_layer", "values": [0]},
            "kx": {"default": 1.0, "overrides": []},
            "ky": {"default": 1.0, "overrides": []},
            "kz": {"default": 1.0, "overrides": []},
        },
        "boundaries": {
            "chd": [{"boundary_id": "left_right_chd", "name": "Left/right CHD", "cells": chd_cells}],
            "wel": (
                [{"well_id": "center_well", "name": "Center pumping well", "cell_id": cell_id(grid_model_id, 0, nrow // 2, ncol // 2), "rate": -100.0}]
                if include_well
                else []
            ),
        },
        "solver": {
            "complexity": "COMPLEX",
            "outer_maximum": 200,
            "inner_maximum": 500,
            "outer_dvclose": 1.0e-8,
            "inner_dvclose": 1.0e-8,
            "linear_acceleration": "CG",
        },
        "output_control": {"save_head": True, "save_budget": True, "print_budget": True, "head_file": "gwf.hds", "budget_file": "gwf.bud"},
    }


def run_case(case_name, shape, *, timeout_seconds=600):
    resolve_mf6_executable()
    workspace = WORKSPACE_ROOT / f"{case_name}-{int(time.time())}"
    store = ProjectStore(workspace / "projects")
    project_id = f"bench_{case_name}_{int(time.time())}"
    project = store.create(_project_payload(project_id))
    nlay, nrow, ncol = shape["nlay"], shape["nrow"], shape["ncol"]
    grid = _create_grid(store, project, case_name, nlay, nrow, ncol)
    project = store.get(project_id)
    flow_service = FlowModelService(store)
    flow = flow_service.create(project_id, grid["grid_model_id"], _flow_payload(project_id, grid["grid_model_id"], nrow, ncol))["flow_model"]
    config = RuntimeConfig(max_grid_cells=max(1_000_000, nlay * nrow * ncol), run_timeout_seconds=timeout_seconds)
    executor = LocalProcessRunExecutor(store, config, auto_start=True, recover_on_start=False)
    enqueue_started = time.perf_counter()
    submitted = executor.submit(project_id, flow["flow_model_id"], idempotency_key=f"mf6-scale-{case_name}")
    run_id = submitted["manifest"]["run_id"]
    run_store = RunManifestStore(store)
    while True:
        manifest = run_store.load(project_id, run_id)
        if manifest["status"] in TERMINAL_STATUSES:
            break
        time.sleep(0.5)
    total_seconds = time.perf_counter() - enqueue_started
    run_dir = run_store.run_dir(project_id, run_id)
    input_dir = run_store.input_dir(project_id, run_id)
    files = {
        "input_bytes": sum(path.stat().st_size for path in input_dir.glob("*") if path.is_file()),
        "head_bytes": (input_dir / "gwf.hds").stat().st_size if (input_dir / "gwf.hds").exists() else 0,
        "budget_bytes": (input_dir / "gwf.bud").stat().st_size if (input_dir / "gwf.bud").exists() else 0,
        "listing_bytes": (input_dir / "gwf.lst").stat().st_size if (input_dir / "gwf.lst").exists() else 0,
    }
    return {
        "case": case_name,
        "run_id": run_id,
        "status": manifest["status"],
        "shape": [nlay, nrow, ncol],
        "active_cells": nlay * nrow * ncol,
        "total_seconds": total_seconds,
        "mf6_run_duration_seconds": (manifest.get("executor") or {}).get("run_duration_seconds"),
        "resource_usage": manifest.get("resource_usage"),
        "files": files,
        "convergence": manifest.get("convergence"),
        "water_budget": manifest.get("water_budget"),
        "run_dir": str(run_dir),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES), action="append")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args()
    selected_cases = args.case or ["small"]
    results = [run_case(case_name, CASES[case_name], timeout_seconds=args.timeout_seconds) for case_name in selected_cases]
    print(json.dumps({"generated_at": now_iso(), "note": "Real MF6 through RunService/LocalProcessRunExecutor.", "results": results}, indent=2))


if __name__ == "__main__":
    main()
