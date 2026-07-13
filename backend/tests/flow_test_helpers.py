import numpy as np

from grid_model_schema import cell_id
from grid_model_store import GridModelStore
from project_schema import now_iso
from project_store import ProjectStore


def create_simple_flow_grid(store: ProjectStore, project, grid_model_id="grid_1111111111111111"):
    top = np.full((1, 5), 10.0)
    botm = np.full((1, 1, 5), 0.0)
    delr = np.full(5, 100.0)
    delc = np.full(1, 100.0)
    idomain = np.ones((1, 1, 5), dtype=np.int32)
    x_centers = np.array([[50.0, 150.0, 250.0, 350.0, 450.0]])
    y_centers = np.array([[50.0, 50.0, 50.0, 50.0, 50.0]])
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
    manifest = {
        "schema_name": "grid_model",
        "schema_version": "1.0",
        "grid_model_id": grid_model_id,
        "project_id": project["project_id"],
        "geology_model_id": project.get("references", {}).get("geology_model_id"),
        "name": "Minimal benchmark grid",
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
            "nlay": 1,
            "nrow": 1,
            "ncol": 5,
            "origin": {"x": 0.0, "y": 0.0},
            "rotation_degrees": 0.0,
            "delr": {"type": "constant", "value": 100.0, "count": 5},
            "delc": {"type": "constant", "value": 100.0, "count": 1},
        },
        "artifacts": {},
        "quality": {"valid": True, "errors": [], "warnings": [], "infos": [], "summary": {"active_cell_count": 5}},
        "provenance": {"application": "flopy-project", "schema_created_by": "test"},
    }
    saved = GridModelStore(store).save(project, manifest, arrays)
    references = dict(project["references"])
    references["grid_model_id"] = grid_model_id
    store.update(project["project_id"], {"references": references})
    return saved, arrays


def steady_flow_payload(project, grid_model_id):
    return {
        "project_id": project["project_id"],
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
            "chd": [
                {
                    "boundary_id": "left_right_chd",
                    "name": "Benchmark CHD",
                    "cells": [
                        {"cell_id": cell_id(grid_model_id, 0, 0, 0), "head": 10.0},
                        {"cell_id": cell_id(grid_model_id, 0, 0, 4), "head": 9.0},
                    ],
                }
            ],
            "wel": [
                {
                    "well_id": "center_well",
                    "name": "Center pumping well",
                    "cell_id": cell_id(grid_model_id, 0, 0, 2),
                    "rate": -1.0,
                }
            ],
        },
        "solver": {
            "complexity": "COMPLEX",
            "outer_maximum": 100,
            "inner_maximum": 100,
            "outer_dvclose": 1.0e-8,
            "inner_dvclose": 1.0e-8,
            "linear_acceleration": "BICGSTAB",
        },
        "output_control": {
            "save_head": True,
            "save_budget": True,
            "print_budget": True,
            "head_file": "gwf.hds",
            "budget_file": "gwf.bud",
        },
    }
