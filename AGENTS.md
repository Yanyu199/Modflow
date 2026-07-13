# AGENTS.md

## Mission

Build a GMS-like groundwater modeling workflow on MODFLOW 6 and FloPy, with Vue and Three.js for interaction and visualization. Numerical correctness and reproducibility come before UI polish.

## Layout

- Backend: `backend/`
- Frontend: `frontend/`
- Documentation: `docs/`

## Commands

- Backend tests: `cd backend && python -m pytest`
- Frontend build: `cd frontend && pnpm run build`

## Rules

- Do not use UI mock data to pretend that an unimplemented FloPy package works.
- Do not silently guess CRS or units. Missing or conflicting CRS/unit context must be rejected or explicitly acknowledged by the user.
- Do not use developer-machine absolute paths in production code or schema data.
- Schema changes must include versioning and compatibility notes.
- Numerical features must have a benchmark or a documented validation path.
- Report test results and known limitations when completing a task.
