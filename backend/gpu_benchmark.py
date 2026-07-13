"""CPU/GPU post-processing benchmark for groundwater result arrays."""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from array_backend import resolve_array_backend
from runtime_config import DEFAULT_RUNTIME_CONFIG


def _operations_numpy(array):
    finite = np.isfinite(array)
    masked = np.where(finite, array, np.nan)
    finite_values = masked[finite]
    min_value = float(finite_values.min())
    max_value = float(finite_values.max())
    thickness = np.maximum(array[1:] - array[:-1], 0.0) if array.size > 1 else array
    normalized = (masked - min_value) / max(max_value - min_value, 1.0e-30)
    color_range = (float(np.nanmin(normalized)), float(np.nanmax(normalized)))
    return {
        "min": min_value,
        "max": max_value,
        "thickness_mean": float(np.nanmean(thickness)),
        "color_range": color_range,
    }


def _operations_cupy(cp, array):
    finite = cp.isfinite(array)
    masked = cp.where(finite, array, cp.nan)
    finite_values = masked[finite]
    min_value = float(cp.asnumpy(finite_values.min()))
    max_value = float(cp.asnumpy(finite_values.max()))
    thickness = cp.maximum(array[1:] - array[:-1], 0.0) if int(array.size) > 1 else array
    normalized = (masked - min_value) / max(max_value - min_value, 1.0e-30)
    color_min = float(cp.asnumpy(cp.nanmin(normalized)))
    color_max = float(cp.asnumpy(cp.nanmax(normalized)))
    thickness_mean = float(cp.asnumpy(cp.nanmean(thickness)))
    return {
        "min": min_value,
        "max": max_value,
        "thickness_mean": thickness_mean,
        "color_range": (color_min, color_max),
    }


def run_case(size_mb):
    bytes_target = int(size_mb * 1024 * 1024)
    count = max(1, bytes_target // 8)
    rng = np.random.default_rng(42)
    source = rng.random(count, dtype=np.float64)
    source[::997] = np.nan

    cpu_start = time.perf_counter()
    cpu_result = _operations_numpy(source)
    cpu_seconds = time.perf_counter() - cpu_start

    backend = resolve_array_backend(prefer_gpu=True)
    gpu = {
        "available": backend.info.name == "cupy",
        "backend": backend.info.name,
        "warnings": backend.info.warnings,
        "used": False,
        "fallback_reason": None,
    }
    threshold = int(DEFAULT_RUNTIME_CONFIG.gpu_min_array_bytes)
    if source.nbytes < threshold:
        gpu["fallback_reason"] = "array_below_gpu_threshold"
        return {
            "size_mb": size_mb,
            "array_bytes": int(source.nbytes),
            "threshold_bytes": threshold,
            "cpu_seconds": cpu_seconds,
            "gpu": gpu,
            "max_abs_error": 0.0,
        }
    if backend.info.name != "cupy":
        gpu["fallback_reason"] = "gpu_unavailable"
        return {
            "size_mb": size_mb,
            "array_bytes": int(source.nbytes),
            "threshold_bytes": threshold,
            "cpu_seconds": cpu_seconds,
            "gpu": gpu,
            "max_abs_error": 0.0,
        }

    cp = backend.cp
    try:
        init_start = time.perf_counter()
        cp.cuda.Device().synchronize()
        init_seconds = time.perf_counter() - init_start
        h2d_start = time.perf_counter()
        gpu_array = cp.asarray(source)
        cp.cuda.Device().synchronize()
        h2d_seconds = time.perf_counter() - h2d_start
        kernel_start = time.perf_counter()
        gpu_result = _operations_cupy(cp, gpu_array)
        cp.cuda.Device().synchronize()
        kernel_seconds = time.perf_counter() - kernel_start
        d2h_start = time.perf_counter()
        gpu_result = dict(gpu_result)
        cp.cuda.Device().synchronize()
        d2h_seconds = time.perf_counter() - d2h_start
        total = init_seconds + h2d_seconds + kernel_seconds + d2h_seconds
        gpu.update({
            "used": total < cpu_seconds,
            "init_seconds": init_seconds,
            "host_to_device_seconds": h2d_seconds,
            "kernel_seconds": kernel_seconds,
            "device_to_host_seconds": d2h_seconds,
            "total_seconds": total,
            "memory_pool_used_bytes": int(cp.get_default_memory_pool().used_bytes()),
        })
        errors = [
            abs(cpu_result["min"] - gpu_result["min"]),
            abs(cpu_result["max"] - gpu_result["max"]),
            abs(cpu_result["thickness_mean"] - gpu_result["thickness_mean"]),
            abs(cpu_result["color_range"][0] - gpu_result["color_range"][0]),
            abs(cpu_result["color_range"][1] - gpu_result["color_range"][1]),
        ]
        return {
            "size_mb": size_mb,
            "array_bytes": int(source.nbytes),
            "threshold_bytes": threshold,
            "cpu_seconds": cpu_seconds,
            "gpu": gpu,
            "max_abs_error": float(max(errors)),
        }
    except Exception as exc:
        gpu.update({"fallback_reason": f"gpu_error_or_oom: {exc}"})
        try:
            cp.get_default_memory_pool().free_all_blocks()
        except Exception:
            pass
        return {
            "size_mb": size_mb,
            "array_bytes": int(source.nbytes),
            "threshold_bytes": threshold,
            "cpu_seconds": cpu_seconds,
            "gpu": gpu,
            "max_abs_error": 0.0,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes-mb", nargs="+", type=int, default=[10, 100])
    args = parser.parse_args()
    print(json.dumps({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": [run_case(size) for size in args.sizes_mb]}, indent=2))


if __name__ == "__main__":
    main()
