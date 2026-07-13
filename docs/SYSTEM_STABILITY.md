# System Stability Closure

Date: 2026-07-13.

This update closes the immediate stability risks before adding more MODFLOW
packages. It does not add GHB, DRN, RCH, EVT, STO, transient flow, MODPATH, or a
GPU MODFLOW solver.

## Main Changes

- Formal run creation is asynchronous: `POST /projects/<project_id>/runs`
  returns `202` with `run_id`, `poll_url`, and `cancel_url`.
- MODFLOW 6 runs in a local worker process, not in the Flask request thread.
- Run manifests support `queued`, `starting`, `cancel_requested`, `cancelled`,
  `timed_out`, and `interrupted`.
- Resource preflight estimates cell count, active cells, head size, budget size,
  scale class, and configured limits before starting a run.
- Head results are exposed through slice APIs rather than full 3D JSON payloads.
- Frontend API calls are centralized in `frontend/src/api/`.
- Frontend domain state has lightweight Vue 2 stores under `frontend/src/stores/`.
- Three.js resource cleanup now disposes scene objects, geometry, materials,
  renderer resources, animation frames, and event listeners.

## Configured Runtime Limits

Environment variables and defaults:

| Variable | Default | Purpose |
|---|---:|---|
| `FLOPY_MAX_CONCURRENT_RUNS` | 1 | Max local worker runs at once |
| `FLOPY_MAX_RUNS_PER_PROJECT` | 1 | Max active local runs per project |
| `FLOPY_RUN_TIMEOUT_SECONDS` | 3600 | MF6 subprocess timeout |
| `FLOPY_MAX_GRID_CELLS` | 1000000 | Preflight grid-cell hard limit |
| `FLOPY_MAX_RESULT_CACHE_BYTES` | 268435456 | Backend result-slice cache |
| `FLOPY_MAX_RESULT_RESPONSE_BYTES` | 8388608 | Preferred max result response |
| `FLOPY_MAX_RENDER_CELLS` | 200000 | Frontend render guidance |
| `FLOPY_MAX_PROCESS_MEMORY_BYTES` | 2147483648 | Preflight process memory estimate |
| `FLOPY_RESULT_JSON_CELL_LIMIT` | 50000 | Max cells for JSON result slices |

## Scale Classes

| Class | Cell Count | Default Behavior |
|---|---:|---|
| `small` | <= 100,000 | async run, one visible layer, full layer display allowed |
| `medium` | <= 500,000 | async run, layer-slice display |
| `large` | <= 1,000,000 | async run, layer slices and downsampling guidance |
| `too_large` | > 1,000,000 | rejected by default run preflight |

## Known Limits

- The legacy `/run-model?allow_legacy_flow_model=true` path still exists and is
  not the target scalable workflow.
- Result viewer currently loads the default head layer slice after completion;
  multi-layer/time UI controls are still a follow-up.
- Resource checks are preflight estimates, not OS-level cgroup limits.
- GPU is optional and limited to array pre/post-processing abstraction.
