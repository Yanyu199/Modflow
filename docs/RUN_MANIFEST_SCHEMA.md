# Run Manifest Schema

Updated: 2026-07-13

This document describes `run_manifest_v1`, the first persistent run contract for the formal MODFLOW 6 steady-flow path.

## Purpose

A run manifest is the audit record for one model execution. It separates model validation, FloPy package compilation, MODFLOW 6 process execution, convergence diagnostics, water-budget acceptance, package-budget summaries, output-file verification, and post-processing results.

The manifest is stored with the run artifacts so a failed or successful run can be reviewed without depending on Flask process memory.

## Storage

Each run is stored under the owning project:

```text
backend/projects/<project_id>/runs/<run_id>/
  run_manifest.json
  input/
    mfsim.nam
    mfsim.lst
    *.tdis
    *.ims
    *.nam
    *.dis
    *.ic
    *.npf
    *.chd
    *.wel
    *.oc
    *.lst
    *.hds
    *.bud
  output/
  logs/
    mf6_stdout.txt
    mf6_stderr.txt
```

`run_id` has the form:

```text
run_<16-32 lowercase hex characters>
```

The API returns logical relative file paths. It must not expose server absolute paths.

## State Machine

Allowed states:

- `created`
- `validating`
- `compiling`
- `writing_input`
- `running`
- `postprocessing`
- `completed`
- `completed_with_warnings`
- `failed_validation`
- `failed_compile`
- `failed_executable`
- `failed_input_write`
- `failed_execution`
- `failed_convergence`
- `failed_outputs`
- `failed_budget`
- `failed_postprocessing`

Terminal states cannot transition back to running states. Illegal transitions fail before the manifest is overwritten.

Failure statuses map to stable error-code families:

| Status | Error-code family |
|---|---|
| `failed_validation` | `RUN_VALIDATION_FAILED` |
| `failed_compile` | `RUN_COMPILE_FAILED` |
| `failed_executable` | `RUN_EXECUTABLE_FAILED` |
| `failed_input_write` | `RUN_INPUT_WRITE_FAILED` |
| `failed_execution` | `RUN_EXECUTION_FAILED` |
| `failed_convergence` | `RUN_CONVERGENCE_FAILED` |
| `failed_outputs` | `RUN_OUTPUTS_FAILED` |
| `failed_budget` | `RUN_BUDGET_FAILED` |
| `failed_postprocessing` | `RUN_POSTPROCESSING_FAILED` |

Some validation failures use more specific stable codes, for example `RUN_FLOW_MODEL_STALE`.

## Snapshots

The manifest records immutable identifiers and checksums for the inputs used by the run:

```json
{
  "model_snapshot": {
    "project": {
      "project_id": "example_project",
      "schema_version": "1.1",
      "updated_at": "2026-07-13T00:00:00Z"
    },
    "geology": {
      "geology_model_id": "geo_...",
      "definition_sha256": "..."
    },
    "grid": {
      "grid_model_id": "grid_...",
      "definition_sha256": "...",
      "artifact_sha256": "..."
    },
    "flow": {
      "flow_model_id": "flow_...",
      "definition_sha256": "..."
    }
  }
}
```

The service verifies the saved Flow Model checksum again immediately before input writing so a stale or changed definition cannot silently run.

## MF6 Execution

The manifest records:

- executable path source, not only the resolved path;
- MODFLOW 6 version if it can be read;
- command arguments;
- process `return_code`;
- stdout and stderr log names;
- listing-file diagnostics.

Normal termination, convergence, and process success are separate checks:

- process success: `return_code == 0`;
- normal termination: listing files contain a recognized normal termination message;
- convergence: listing files contain no known non-convergence message;
- numerical acceptance: output files and budget checks pass.

## Water Budget

The first budget report is for the last steady stress period and records:

- `kstp`;
- `kper`;
- `totim`;
- `time_units`;
- `total_in`;
- `total_out`;
- `difference`;
- `percent_discrepancy`;
- tolerance used by the test.

The current benchmark tolerance is:

```text
head_abs_tol = 1e-8 m
head_rel_tol = 1e-9
budget_abs_tol = 1e-7 m3/day
percent_discrepancy_tol = 1e-5
```

## Package Budget

The first package budget summary reports CHD and WEL totals from the cell-budget file:

```json
{
  "package_budget": {
    "CHD": {"in": 3.0, "out": 2.0, "net": 1.0},
    "WEL": {"in": 0.0, "out": 1.0, "net": -1.0}
  }
}
```

Positive records are treated as inflow. Negative records are treated as outflow.

## Output Registry

The manifest registers expected outputs and verifies that the important binary/text files exist:

- `mfsim.lst`;
- model listing file such as `gwf.lst`;
- head file such as `gwf.hds`;
- budget file such as `gwf.bud`;
- package inputs such as `.dis`, `.npf`, `.chd`, `.wel`, `.oc`, `.ims`.

Each entry stores a logical path, role, existence, size in bytes, and SHA-256 checksum when available.

## API

Run endpoints:

```text
POST /projects/<project_id>/runs
GET  /projects/<project_id>/runs
GET  /projects/<project_id>/runs/<run_id>
GET  /projects/<project_id>/runs/<run_id>/summary
```

Create request:

```json
{
  "flow_model_id": "flow_0123456789abcdef",
  "keep_artifacts": true
}
```

Successful response:

```json
{
  "success": true,
  "run_id": "run_0123456789abcdef",
  "status": "completed",
  "run": {
    "run_id": "run_0123456789abcdef",
    "status": "completed",
    "mf6": {
      "executable_source": "repo-relative",
      "version": "6.6.3",
      "return_code": 0
    },
    "convergence": {
      "normal_termination": true,
      "converged": true,
      "percent_discrepancy": 0.0
    },
    "water_budget": {
      "total_in": 3.0,
      "total_out": 3.0,
      "difference": 0.0,
      "percent_discrepancy": 0.0
    },
    "package_budget": {
      "CHD": {"in": 3.0, "out": 2.0, "net": 1.0},
      "WEL": {"in": 0.0, "out": 1.0, "net": -1.0}
    },
    "outputs": {
      "head": "input/gwf.hds",
      "budget": "input/gwf.bud",
      "simulation_listing": "input/mfsim.lst",
      "model_listing": "input/gwf.lst"
    }
  }
}
```

Failure response:

```json
{
  "success": false,
  "run_id": "run_0123456789abcdef",
  "status": "failed_validation",
  "error": {
    "code": "RUN_FLOW_MODEL_STALE",
    "message": "Flow Model is stale because the active Grid Model changed."
  },
  "diagnostic_outputs": {
    "manifest": "run_manifest.json",
    "stdout": "logs/mf6_stdout.txt",
    "stderr": "logs/mf6_stderr.txt"
  }
}
```

Failure responses should not include Python tracebacks or server absolute paths.
