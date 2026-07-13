# Frontend Architecture

Date: 2026-07-13.

The frontend remains Vue 2. This update establishes the first separation layer
without migrating to Vue 3 or Vuex.

## Directories

```text
frontend/src/
  api/
  stores/
  views/
  features/flowPackages/
  visualization/
```

## API Layer

All component-level HTTP calls now go through `frontend/src/api/` except the API
client itself. The base URL is resolved in this order:

1. `window.__FLOPY_API_BASE_URL__`
2. `window.__FLOPY_CONFIG__.apiBaseUrl`
3. webpack build variable `FLOPY_API_BASE_URL`
4. default `http://localhost:5000`

Set the build variable with PowerShell:

```powershell
$env:FLOPY_API_BASE_URL="http://127.0.0.1:5000"
pnpm run dev
```

## Stores

Lightweight Vue 2 stores now exist for:

- `projectStore`
- `geologyStore`
- `gridStore`
- `flowStore`
- `runStore`

Stores keep IDs, summaries, active model references, loading/error state, and
run polling state. Large arrays should stay in renderer-private caches or typed
array caches, not deep reactive Vue state.

## Flow Package Registry

`features/flowPackages/registry.js` registers:

- enabled: CHD, WEL, RIV
- disabled: GHB, DRN, RCH, EVT

Disabled packages are explicitly not formal backend packages in this update.

## App.vue Status

Before this task `App.vue` had about 1508 lines and handled navigation, project
state, geology migration, grid preview, flow payload construction, run
submission, run history, and result display.

After this task it no longer imports axios directly and delegates HTTP work to
API modules and run polling to `runStore`. It still contains significant
business logic and should be thinned further in a later UI refactor.

## Three.js

`Real3DViewer` already used `InstancedMesh` for grid voxels. This update adds
shared disposal helpers and a removable resize listener. Result slices should be
loaded by layer and cached as typed arrays.

## Bundle And Lazy Loading

Production webpack builds now use production mode, disabled production source
maps, async chunk filenames, and performance warnings. Workflow panels behind
the top page switches are async components so large analysis/flow/geology panels
are split out of the initial chunk where possible.

After a production build:

```bash
cd frontend
pnpm run bundle:report
```

The report includes raw and gzip sizes for initial and async JS chunks and writes
`dist/bundle-report.json`.

Local build on 2026-07-13:

- previous main bundle: about 11.1 MiB raw
- current `main.js`: 1.96 MiB raw, 509,091 bytes gzip
- current async JS total: 4,726,710 bytes raw, 1,405,600 bytes gzip
- largest async vendor chunk: 4.4 MiB raw, 1,372,492 bytes gzip

The initial gzip budget passes. The async vendor chunk still exceeds the current
async budget and should be split further before production use.

## Rendering Benchmark

The viewer exposes a browser-side benchmark:

```js
await vm.$refs.viewer3d.runRenderBenchmark()
```

It renders real `THREE.InstancedMesh` cases for 10k, 50k, 100k, and 200k
instances by default and records draw calls, triangles, first frame, average
FPS, P95 frame time, picking time, color update time, and heap readings where
the browser exposes `performance.memory`.
