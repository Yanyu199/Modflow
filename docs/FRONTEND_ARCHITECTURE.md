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
