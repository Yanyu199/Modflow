# Flow Model Schema

Updated: 2026-07-13

This document describes the first persistent steady-flow model contract implemented by the project. It is intentionally limited to MODFLOW 6 GWF steady flow with structured DIS grids.

## Responsibilities

- Project: identity, CRS, units, and active model references.
- Geology Model: boundary, boreholes, stratigraphy, faults, interpolation inputs, and geology provenance.
- Grid Model: backend-authoritative structured DIS grid, `top`, `botm`, `idomain`, `delr`, `delc`, and stable `cell_id`.
- Flow Model: IC, NPF, CHD, WEL, IMS, OC, checker diagnostics, and package preview.
- Run: one execution of a checked flow model, persisted as `run_manifest_v1` with input/output artifacts, convergence diagnostics, water budget, and package budget.

## Storage

The active flow model is saved at:

```text
backend/projects/<project_id>/flow/flow_model.json
```

The flow model does not copy Grid Model arrays and does not save MODFLOW result files. It references the active Grid Model by `grid_model_id` and uses Grid Store arrays at compile time. Run results are saved under `backend/projects/<project_id>/runs/<run_id>/`.

## Identifier

`flow_model_id` uses:

```text
flow_<16-32 lowercase hex characters>
```

The Project Schema reference is:

```json
{
  "references": {
    "geology_model_id": "geo_...",
    "grid_model_id": "grid_...",
    "flow_model_id": "flow_..."
  }
}
```

Only one active flow model is supported per project in v1.

## Minimal Valid Shape

```json
{
  "schema_name": "flow_model",
  "schema": "flow_model",
  "schema_version": "1.0",
  "flow_model_id": "flow_0123456789abcdef",
  "project_id": "example_project",
  "grid_model_id": "grid_0123456789abcdef",
  "status": "ready",
  "simulation": {
    "type": "steady",
    "stress_periods": [
      {"perlen": 1.0, "nstp": 1, "tsmult": 1.0, "steady": true}
    ],
    "time_units": "DAYS"
  },
  "initial_conditions": {
    "mode": "default_with_overrides",
    "default": 9.5,
    "overrides": []
  },
  "hydraulic_properties": {
    "icelltype": {"mode": "per_layer", "values": [0]},
    "kx": {"default": 1.0, "overrides": []},
    "ky": {"default": 1.0, "overrides": []},
    "kz": {"default": 1.0, "overrides": []}
  },
  "boundaries": {
    "chd": [
      {
        "boundary_id": "left_right_chd",
        "name": "Benchmark CHD",
        "cells": [
          {"cell_id": "grid_0123456789abcdef:L0:R0:C0", "head": 10.0},
          {"cell_id": "grid_0123456789abcdef:L0:R0:C4", "head": 9.0}
        ]
      }
    ],
    "wel": [
      {
        "well_id": "center_well",
        "name": "Center pumping well",
        "cell_id": "grid_0123456789abcdef:L0:R0:C2",
        "rate": -1.0
      }
    ]
  },
  "solver": {
    "complexity": "COMPLEX",
    "outer_maximum": 100,
    "inner_maximum": 100,
    "outer_dvclose": 1e-8,
    "inner_dvclose": 1e-8,
    "linear_acceleration": "BICGSTAB"
  },
  "output_control": {
    "save_head": true,
    "save_budget": true,
    "print_budget": true,
    "head_file": "gwf.hds",
    "budget_file": "gwf.bud"
  }
}
```

## IC

Supported modes:

- `default_with_overrides`: a finite default initial head plus optional `cell_id` overrides.
- `per_layer`: one finite initial head per layer.

Initial heads are materialized into `strt`. The checker warns when active-cell heads are outside cell top/bottom elevations. The code no longer uses the grid top surface as an implicit initial head in the formal Flow Model path.

## NPF

NPF stores explicit `kx`, `ky`, and `kz` definitions. Each axis has a positive finite default and optional positive finite `cell_id` overrides. The UI can still help users enter an isotropic value, but the backend saves and compiles the three axes explicitly.

`icelltype` is defined per layer and currently accepts only:

- `0`: confined.
- `1`: convertible.

The benchmark model uses `icelltype = 0` so the expected heads come from a linear finite-volume calculation.

## CHD

CHD is cell based in v1. Each entry references active Grid Model cells by stable `cell_id`, supports any layer, and stores a finite `head`. At least one CHD cell is required before a steady model can run. Conflicting duplicate CHD heads are rejected.

## WEL

WEL is cell based in v1. Each well references an active `cell_id` and stores a finite `rate`.

Sign convention:

- Negative rate: pumping/extraction.
- Positive rate: injection.

WEL entries are blocked on CHD cells. Multiple WEL entries in one cell are allowed but produce a checker warning.

## Checker

The checker returns stable `error`, `warning`, and `info` diagnostics. A flow model is runnable only when there are no errors.

Implemented blocking checks include:

- Project/grid reference mismatch.
- Unsupported units.
- Invalid schema, ID, status, or unknown fields.
- Invalid IC, K, icelltype, CHD, WEL values.
- Invalid, out-of-bounds, cross-grid, or inactive `cell_id`.
- Missing CHD.
- WEL/CHD cell conflict.
- Stale flow model on run.

Implemented warnings include:

- Initial head outside cell top/bottom.
- CHD head outside cell top/bottom.
- Multiple WEL entries in one cell.

## Package Compiler

The compiler reads Grid Store arrays and creates:

- TDIS
- IMS
- GWF
- DIS
- IC
- NPF
- CHD
- WEL
- OC

The normal `/run-model` path rejects request-body overrides for IC, K, CHD, WEL, RCH, EVT, boundary geometry, `top`, `botm`, and `idomain`. The saved Flow Model is the authority.

## API

Implemented endpoints:

```text
POST /projects/<project_id>/flow-models/validate
POST /projects/<project_id>/flow-models
GET  /projects/<project_id>/flow-models/active
PUT  /projects/<project_id>/flow-models/<flow_model_id>
POST /projects/<project_id>/flow-models/<flow_model_id>/check
GET  /projects/<project_id>/flow-models/<flow_model_id>/package-preview
POST /projects/<project_id>/flow-models/<flow_model_id>/rebuild
POST /projects/<project_id>/runs
GET  /projects/<project_id>/runs
GET  /projects/<project_id>/runs/<run_id>
GET  /projects/<project_id>/runs/<run_id>/summary
```

Normal run request:

```json
{
  "project_id": "example_project",
  "grid_model_id": "grid_0123456789abcdef",
  "flow_model_id": "flow_0123456789abcdef"
}
```

The legacy `/run-model` body remains only behind `allow_legacy_flow_model=true` and returns a deprecation warning. When a formal `flow_model_id` is supplied, `/run-model` delegates to the Run API path and returns a `run_manifest_v1` summary without exposing `work_dir`.

## Benchmark

The formal Flow Model benchmark uses:

- Grid: 1 layer, 1 row, 5 columns.
- `delr = 100 m`, `delc = 100 m`.
- `top = 10 m`, `bottom = 0 m`.
- `Kx = Ky = Kz = 1 m/day`.
- `icelltype = 0`.
- Left CHD: 10 m at `L0:R0:C0`.
- Right CHD: 9 m at `L0:R0:C4`.
- Center WEL: -1 m3/day at `L0:R0:C2`.
- Initial head: 9.5 m.
- Expected heads: `[10.0, 9.7, 9.4, 9.2, 9.0]`.

Expected heads come from the same independent finite-volume calculation used by the original steady-flow benchmark, not from reverse-fitting MF6 output.
