"""On-demand result slice APIs for persisted MODFLOW 6 run artifacts."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import flopy
import numpy as np

from project_store import ProjectStore
from resource_guard import enforce_result_response_size
from run_manifest_schema import TERMINAL_STATUSES, validate_run_id
from run_manifest_store import RunManifestStore
from runtime_config import DEFAULT_RUNTIME_CONFIG, RuntimeConfig


class ResultServiceError(ValueError):
    def __init__(self, code: str, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


class ResultSliceCache:
    def __init__(self, max_bytes: int):
        self.max_bytes = int(max_bytes)
        self._items = OrderedDict()
        self.current_bytes = 0

    def get(self, key):
        if key not in self._items:
            return None
        value, size = self._items.pop(key)
        self._items[key] = (value, size)
        return value

    def put(self, key, value):
        size = int(getattr(value, "nbytes", 0))
        if size > self.max_bytes:
            return value
        if key in self._items:
            _old, old_size = self._items.pop(key)
            self.current_bytes -= old_size
        while self.current_bytes + size > self.max_bytes and self._items:
            _k, (_v, old_size) = self._items.popitem(last=False)
            self.current_bytes -= old_size
        self._items[key] = (value, size)
        self.current_bytes += size
        return value

    def clear(self):
        self._items.clear()
        self.current_bytes = 0

    def stats(self):
        return {"items": len(self._items), "bytes": self.current_bytes, "max_bytes": self.max_bytes}


class ResultService:
    def __init__(self, project_store=None, run_store=None, config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG):
        self.project_store = project_store or ProjectStore()
        self.run_store = run_store or RunManifestStore(self.project_store)
        self.config = config
        self.cache = ResultSliceCache(config.max_result_cache_bytes)

    def variables(self, project_id: str, run_id: str) -> Dict[str, Any]:
        manifest, _run_root = self._load_completed_run(project_id, run_id)
        outputs = manifest.get("outputs") or {}
        variables = []
        if outputs.get("head", {}).get("exists"):
            variables.append({"name": "head", "unit": self._head_unit(manifest), "dimensions": ["layer", "row", "column"]})
        if outputs.get("budget", {}).get("exists"):
            variables.append({"name": "budget", "unit": (manifest.get("water_budget") or {}).get("flow_unit", "m3/day")})
        return {
            "run_id": run_id,
            "status": manifest.get("status"),
            "variables": variables,
            "cache": self.cache.stats(),
        }

    def budget(self, project_id: str, run_id: str) -> Dict[str, Any]:
        manifest, _run_root = self._load_completed_run(project_id, run_id)
        return {
            "run_id": run_id,
            "water_budget": manifest.get("water_budget"),
            "package_budget": manifest.get("package_budget"),
            "cache": self.cache.stats(),
        }

    def head_slice(
        self,
        project_id: str,
        run_id: str,
        *,
        layer: int = 0,
        time_index: int = -1,
        row_start: int = 0,
        row_end: Optional[int] = None,
        column_start: int = 0,
        column_end: Optional[int] = None,
        fmt: str = "json",
    ) -> Dict[str, Any]:
        manifest, run_root = self._load_completed_run(project_id, run_id)
        model = manifest.get("model") or {}
        nlay, nrow, ncol = int(model.get("nlay") or 0), int(model.get("nrow") or 0), int(model.get("ncol") or 0)
        if not (0 <= layer < nlay):
            raise ResultServiceError("RESULT_LAYER_INVALID", "Requested layer is outside model shape.")
        row_end = nrow if row_end is None else int(row_end)
        column_end = ncol if column_end is None else int(column_end)
        row_start = int(row_start)
        column_start = int(column_start)
        if not (0 <= row_start <= row_end <= nrow and 0 <= column_start <= column_end <= ncol):
            raise ResultServiceError("RESULT_SLICE_INVALID", "Requested row/column range is outside model shape.")
        if fmt not in {"json", "binary"}:
            raise ResultServiceError("RESULT_FORMAT_INVALID", "format must be json or binary.")
        cell_count = (row_end - row_start) * (column_end - column_start)
        enforce_result_response_size(cell_count, 8, fmt, self.config)
        head_file = run_root / "input" / "gwf.hds"
        if not head_file.exists():
            raise ResultServiceError("RESULT_HEAD_MISSING", "Head file is missing.", status=404)
        stat = head_file.stat()
        key = (
            str(head_file),
            stat.st_mtime_ns,
            int(layer),
            int(time_index),
            row_start,
            row_end,
            column_start,
            column_end,
        )
        array = self.cache.get(key)
        if array is None:
            try:
                head = flopy.utils.HeadFile(str(head_file))
                kstpkper_values = head.get_kstpkper()
                if not kstpkper_values:
                    raise ResultServiceError("RESULT_HEAD_EMPTY", "Head file has no time steps.", status=422)
                if time_index < 0:
                    index = len(kstpkper_values) + int(time_index)
                else:
                    index = int(time_index)
                if not (0 <= index < len(kstpkper_values)):
                    raise ResultServiceError("RESULT_TIME_INVALID", "Requested time_index is outside result time steps.")
                data = head.get_data(kstpkper=kstpkper_values[index], mflay=layer)
                array = np.asarray(data[row_start:row_end, column_start:column_end], dtype=np.float64)
                array = np.ascontiguousarray(array)
                self.cache.put(key, array)
            except ResultServiceError:
                raise
            except Exception as exc:
                raise ResultServiceError("RESULT_HEAD_READ_FAILED", str(exc), status=422)
        metadata = {
            "run_id": run_id,
            "variable": "head",
            "shape": [int(array.shape[0]), int(array.shape[1])],
            "dtype": "float64",
            "endianness": "little",
            "unit": self._head_unit(manifest),
            "layer": int(layer),
            "time_index": int(time_index),
            "row_start": row_start,
            "row_end": row_end,
            "column_start": column_start,
            "column_end": column_end,
            "nodata": None,
            "cache": self.cache.stats(),
        }
        if fmt == "binary":
            return {"metadata": metadata, "bytes": array.astype("<f8", copy=False).tobytes(order="C")}
        return {"metadata": metadata, "values": array.tolist()}

    def _load_completed_run(self, project_id: str, run_id: str) -> Tuple[Dict[str, Any], Path]:
        validate_run_id(run_id)
        self.project_store.get(project_id)
        manifest = self.run_store.load(project_id, run_id)
        if manifest.get("status") not in TERMINAL_STATUSES:
            raise ResultServiceError("RESULT_RUN_NOT_TERMINAL", "Run results are available only after the run reaches a terminal state.", status=409)
        if manifest.get("status") not in {"completed", "completed_with_warnings"}:
            raise ResultServiceError("RESULT_RUN_NOT_SUCCESSFUL", "Run did not complete successfully.", status=409)
        return manifest, self.run_store.run_dir(project_id, run_id)

    def _head_unit(self, manifest):
        return ((manifest.get("model") or {}).get("head_unit") or "m")
