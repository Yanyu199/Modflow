"""Repeatable lightweight performance probes for scalable-result plumbing.

This script does not claim to benchmark large MODFLOW 6 solves. It measures the
data-path pieces introduced for scalable execution: resource estimates, array
allocation, layer slicing, and response-size expectations.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
import tracemalloc

import numpy as np

from resource_guard import estimate_grid_resources
from runtime_config import DEFAULT_RUNTIME_CONFIG, scale_classification


CASES = {
    "small": (1, 250, 400),      # 100,000 cells
    "medium": (1, 500, 1000),   # 500,000 cells
    "large": (1, 1000, 1000),   # 1,000,000 cells
}


def manifest_for(nlay, nrow, ncol):
    return {
        "geometry": {"nlay": nlay, "nrow": nrow, "ncol": ncol},
        "quality": {"summary": {"active_cell_count": nlay * nrow * ncol}},
    }


def probe_case(name, shape):
    nlay, nrow, ncol = shape
    tracemalloc.start()
    started = time.perf_counter()
    estimate = estimate_grid_resources(manifest_for(nlay, nrow, ncol), DEFAULT_RUNTIME_CONFIG)
    array_started = time.perf_counter()
    head = np.linspace(10.0, 9.0, nlay * nrow * ncol, dtype=np.float64).reshape((nlay, nrow, ncol))
    slice_started = time.perf_counter()
    layer = np.ascontiguousarray(head[0, :, :])
    binary = layer.astype("<f8", copy=False).tobytes(order="C")
    finished = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "case": name,
        "shape": [nlay, nrow, ncol],
        "cells": nlay * nrow * ncol,
        "scale": scale_classification(nlay * nrow * ncol, nlay * nrow * ncol, nlay),
        "estimate": estimate,
        "timings_seconds": {
            "estimate": array_started - started,
            "allocate_head": slice_started - array_started,
            "slice_and_binary": finished - slice_started,
            "total": finished - started,
        },
        "sizes_bytes": {
            "head_array": int(head.nbytes),
            "layer_array": int(layer.nbytes),
            "binary_response": int(len(binary)),
        },
        "python_memory_bytes": {
            "current": int(current),
            "peak": int(peak),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print compact JSON")
    args = parser.parse_args()
    result = {
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor(),
        },
        "note": "Data-path benchmark only; not a large MF6 solve benchmark.",
        "cases": [probe_case(name, shape) for name, shape in CASES.items()],
    }
    print(json.dumps(result, indent=None if args.json else 2))


if __name__ == "__main__":
    main()
