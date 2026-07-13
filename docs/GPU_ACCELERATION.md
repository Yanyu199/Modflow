# GPU Acceleration Policy

Date: 2026-07-13.

GPU support is optional. It is not a prerequisite for running MODFLOW 6 and this
project does not implement or claim a CUDA MODFLOW solver.

## Backend

`backend/array_backend.py` provides:

- `NumPyBackend`
- `OptionalCuPyBackend`
- `resolve_array_backend()`

Default behavior is NumPy. If `FLOPY_USE_GPU=true` and CuPy with a CUDA device is
available, the optional CuPy backend may be used for pre/post-processing array
operations. If CuPy or CUDA is unavailable, the code records a warning and
falls back to NumPy.

Allowed GPU scope:

- array masks
- thickness/idomain derived statistics
- result-slice conversion
- color-range statistics
- other pre/post-processing that does not change MF6 solve semantics

Not allowed in this update:

- GPU MF6 solving
- passing GPU arrays into FloPy
- changing numerical checksums or benchmark tolerances

## Frontend

Three.js uses WebGL for rendering. The viewer now records WebGL capabilities and
uses instanced rendering for cells. GPU limitations should reduce display scale
or switch to layer mode; they must not block MODFLOW computation.

## Tests

CPU path tests always run. GPU-specific availability is optional and may fall
back to NumPy with an explicit warning.
