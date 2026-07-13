"""Optional array compute backend.

The production MODFLOW 6 solve path remains the official MF6 executable. This
module is limited to pre/post-processing array operations where NumPy and an
optional GPU backend can be compared for numerical equivalence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Optional

import numpy as np


@dataclass
class ArrayBackendInfo:
    name: str
    gpu_requested: bool
    gpu_available: bool
    warnings: List[str]


class NumPyBackend:
    name = "numpy"

    def asarray(self, value, dtype=None):
        return np.asarray(value, dtype=dtype)

    def asnumpy(self, value):
        return np.asarray(value)

    def finite_min_max(self, value):
        array = np.asarray(value)
        finite = array[np.isfinite(array)]
        if finite.size == 0:
            return None, None
        return float(finite.min()), float(finite.max())


class OptionalCuPyBackend(NumPyBackend):
    name = "cupy"

    def __init__(self, cupy_module):
        self.cp = cupy_module

    def asarray(self, value, dtype=None):
        return self.cp.asarray(value, dtype=dtype)

    def asnumpy(self, value):
        return self.cp.asnumpy(value)

    def finite_min_max(self, value):
        try:
            array = self.cp.asarray(value)
            finite = array[self.cp.isfinite(array)]
            if int(finite.size) == 0:
                return None, None
            return float(finite.min().get()), float(finite.max().get())
        except Exception:
            if hasattr(self.cp, "get_default_memory_pool"):
                self.cp.get_default_memory_pool().free_all_blocks()
            cpu = np.asarray(self.asnumpy(value))
            finite = cpu[np.isfinite(cpu)]
            if finite.size == 0:
                return None, None
            return float(finite.min()), float(finite.max())


def resolve_array_backend(prefer_gpu: Optional[bool] = None) -> Any:
    requested = (
        str(os.environ.get("FLOPY_USE_GPU", "")).strip().lower() in {"1", "true", "yes", "on"}
        if prefer_gpu is None
        else bool(prefer_gpu)
    )
    warnings: List[str] = []
    if not requested:
        backend = NumPyBackend()
        backend.info = ArrayBackendInfo("numpy", False, False, warnings)
        return backend
    try:
        import cupy as cp  # type: ignore

        count = int(cp.cuda.runtime.getDeviceCount())
        if count <= 0:
            raise RuntimeError("no CUDA devices reported")
        backend = OptionalCuPyBackend(cp)
        backend.info = ArrayBackendInfo("cupy", True, True, warnings)
        return backend
    except Exception as exc:
        warnings.append(f"GPU backend unavailable; falling back to NumPy: {exc}")
        backend = NumPyBackend()
        backend.info = ArrayBackendInfo("numpy", True, False, warnings)
        return backend
