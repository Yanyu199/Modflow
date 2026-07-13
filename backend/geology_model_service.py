import copy
import io
from pathlib import Path

import pandas as pd

from geological_builder import GeologicalModeler
from geology_model_schema import (
    GeologyModelValidationError,
    empty_geology_model,
    normalized_to_frontend,
    require_valid_geology_model,
    validate_geology_model,
)
from geology_model_store import GeologyModelNotFoundError, GeologyModelStore
from project_schema import ProjectValidationError


class NamedBytesIO(io.BytesIO):
    def __init__(self, data, filename):
        super().__init__(data)
        self.filename = filename


def dataframe_to_boreholes_and_formations(df, source_ref):
    df = df.copy()
    df.columns = df.columns.str.strip()
    required = {"钻孔名称", "X", "Y", "Z", "分层ID"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"钻孔文件缺少必要列: {', '.join(missing)}")

    if "Top" not in df.columns or "Bottom" not in df.columns:
        if "分层厚度" not in df.columns:
            raise ValueError("钻孔文件必须包含 Top/Bottom 或 分层厚度")
        df = df.sort_values(by=["钻孔名称", "分层ID"])
        df["cum_thick"] = df.groupby("钻孔名称")["分层厚度"].cumsum()
        df["Bottom"] = df["Z"] - df["cum_thick"]
        df["Top"] = df["Bottom"] + df["分层厚度"]

    layer_ids = sorted(df["分层ID"].unique())
    formations = []
    for order, layer_id in enumerate(layer_ids, start=1):
        formations.append(
            {
                "formation_id": f"fm_{int(layer_id)}",
                "name": f"Formation {int(layer_id)}",
                "order": order,
                "kind": "unknown",
                "allow_missing": False,
                "allow_pinchout": False,
                "display": {"color": "#cccccc"},
                "source_layer_id": int(layer_id),
            }
        )

    boreholes = []
    for bh_name, group in df.sort_values(by=["钻孔名称", "分层ID"]).groupby("钻孔名称"):
        intervals = []
        max_top = None
        min_bottom = None
        for _, row in group.iterrows():
            top = float(row["Top"])
            bottom = float(row["Bottom"])
            max_top = top if max_top is None else max(max_top, top)
            min_bottom = bottom if min_bottom is None else min(min_bottom, bottom)
            intervals.append(
                {
                    "formation_id": f"fm_{int(row['分层ID'])}",
                    "top_elevation": top,
                    "bottom_elevation": bottom,
                    "lithology": str(row.get("含水层岩性", "")),
                }
            )
        first = group.iloc[0]
        boreholes.append(
            {
                "borehole_id": str(bh_name),
                "x": float(first["X"]),
                "y": float(first["Y"]),
                "collar_elevation": float(first["Z"]),
                "total_depth": float((max_top or first["Z"]) - (min_bottom or first["Z"])),
                "interval_mode": "elevation",
                "intervals": intervals,
                "source_ref": source_ref,
            }
        )
    return boreholes, formations


def geology_model_to_dataframe(model):
    source_by_formation = {
        formation["formation_id"]: formation.get("source_layer_id", formation["order"])
        for formation in model["stratigraphy"]["formations"]
    }
    rows = []
    for borehole in model["boreholes"]:
        for interval in borehole["intervals"]:
            rows.append(
                {
                    "钻孔名称": borehole["borehole_id"],
                    "X": borehole["x"],
                    "Y": borehole["y"],
                    "Z": borehole["collar_elevation"],
                    "分层ID": source_by_formation[interval["formation_id"]],
                    "Top": interval["top_elevation"],
                    "Bottom": interval["bottom_elevation"],
                    "含水层岩性": interval.get("lithology", ""),
                }
            )
    return pd.DataFrame(rows)


def build_geological_modeler_from_geology_model(model):
    df = geology_model_to_dataframe(model)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    file_obj = NamedBytesIO(csv_bytes, "geology_model_rebuild.csv")
    geo_model = GeologicalModeler(file_obj)
    geo_model.preprocess_data()
    return geo_model


class GeologyModelService:
    def __init__(self, project_store, geology_store=None):
        self.project_store = project_store
        self.geology_store = geology_store or GeologyModelStore(project_store)

    def _project(self, project_id):
        return self.project_store.get(project_id)

    def _references_with_geology(self, project, geology_model_id):
        references = project.get("references", {})
        return {
            "geology_model_id": geology_model_id,
            "grid_model_id": references.get("grid_model_id"),
            "flow_model_id": references.get("flow_model_id"),
        }

    def _mark_grid_stale(self, project_id, reason, geology=None):
        try:
            from grid_model_service import GridModelService

            GridModelService(self.project_store, self.geology_store).mark_stale_for_project(project_id, reason, geology)
        except Exception:
            return None

    def _mark_derived_ready(self, project, model):
        ready = copy.deepcopy(model)
        derived = copy.deepcopy(ready.get("derived_artifacts") or {})
        if derived.get("input_hash"):
            derived["status"] = "ready"
            derived["mode"] = derived.get("mode") or "rebuild_from_standardized_inputs"
            ready["derived_artifacts"] = derived
            return self.geology_store.save(project, ready)
        return model

    def _can_rebuild_cache(self, model):
        formations = (model.get("stratigraphy") or {}).get("formations") or []
        return bool(
            model.get("diagnostics", {}).get("valid")
            and model.get("boreholes")
            and formations
        )

    def active_or_empty(self, project):
        try:
            return self.geology_store.get_active(project)
        except GeologyModelNotFoundError:
            return empty_geology_model(project)

    def validate(self, project_id, payload, allow_incomplete=False):
        project = self._project(project_id)
        return validate_geology_model(payload, project, allow_incomplete=allow_incomplete)

    def create(self, project_id, payload):
        project = self._project(project_id)
        model = require_valid_geology_model(payload, project)
        saved = self.geology_store.save(project, model)
        self.project_store.update(project_id, {"references": self._references_with_geology(project, saved["geology_model_id"])})
        return saved

    def update(self, project_id, geology_model_id, payload):
        project = self._project(project_id)
        existing = self.geology_store.get_active(project)
        if existing["geology_model_id"] != geology_model_id:
            raise GeologyModelNotFoundError("geology model not found for project")
        model = validate_geology_model(payload, project, existing=existing, allow_incomplete=False)
        if not model["diagnostics"]["valid"]:
            raise GeologyModelValidationError(model["diagnostics"])
        saved = self.geology_store.save(project, model)
        if existing.get("derived_artifacts", {}).get("input_hash") != saved.get("derived_artifacts", {}).get("input_hash"):
            self._mark_grid_stale(project_id, "active geology model changed", saved)
        return saved

    def get_active(self, project_id):
        project = self._project(project_id)
        return self.geology_store.get_active(project)

    def rebuild(self, project_id, cache):
        model = self.get_active(project_id)
        if not model["diagnostics"]["valid"]:
            raise GeologyModelValidationError(model["diagnostics"])
        cache[project_id] = build_geological_modeler_from_geology_model(model)
        project = self._project(project_id)
        model = self._mark_derived_ready(project, model)
        return model, normalized_to_frontend(model)

    def ensure_cache(self, project_id, cache):
        if project_id not in cache:
            self.rebuild(project_id, cache)
        return cache[project_id]

    def save_partial(self, project_id, patch, cache=None, rebuild_cache=True):
        project = self._project(project_id)
        existing = self.active_or_empty(project)
        candidate = copy.deepcopy(existing)
        candidate.update(patch)
        model = validate_geology_model(candidate, project, existing=existing, allow_incomplete=True)
        # Component validation errors mean the patch itself is bad; missing global pieces are warnings in partial mode.
        if model["diagnostics"]["errors"]:
            raise GeologyModelValidationError(model["diagnostics"])
        saved = self.geology_store.save(project, model)
        self.project_store.update(project_id, {"references": self._references_with_geology(project, saved["geology_model_id"])})
        if existing.get("derived_artifacts", {}).get("input_hash") != saved.get("derived_artifacts", {}).get("input_hash"):
            self._mark_grid_stale(project_id, "geology inputs changed", saved)
        if cache is not None and rebuild_cache and self._can_rebuild_cache(saved):
            cache[project_id] = build_geological_modeler_from_geology_model(saved)
            saved = self._mark_derived_ready(project, saved)
        return saved

    def update_boreholes_from_upload(self, project_id, file_obj, raw_csv=None, cache=None):
        filename = Path(getattr(file_obj, "filename", "boreholes.csv")).name
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_obj)
        else:
            df = pd.read_csv(file_obj)
        source_ref = f"upload:{filename}"
        boreholes, formations = dataframe_to_boreholes_and_formations(df, source_ref)
        provenance = {"legacy_raw_csv_present": bool(raw_csv), "last_borehole_source": source_ref}
        patch = {"boreholes": boreholes, "stratigraphy": {"formations": formations}, "provenance": provenance}
        return self.save_partial(project_id, patch, cache=cache)

    def update_boundary(self, project_id, boundary_feature, source_metadata=None, cache=None):
        patch = {
            "boundary": boundary_feature,
            "provenance": {"last_boundary_source": source_metadata or {"kind": "unknown"}},
        }
        return self.save_partial(project_id, patch, cache=cache, rebuild_cache=True)

    def update_faults(self, project_id, faults, source_metadata=None, cache=None):
        patch = {
            "faults": faults,
            "provenance": {"last_fault_source": source_metadata or {"kind": "user_declared_project_crs"}},
        }
        return self.save_partial(project_id, patch, cache=cache, rebuild_cache=True)
