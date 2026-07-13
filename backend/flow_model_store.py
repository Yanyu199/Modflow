"""Persistence for the active flow_model_v1 document."""

from __future__ import annotations

import json
import os
import tempfile

from flow_model_schema import (
    FlowModelNotFoundError,
    FlowModelValidationError,
    STATUS_STALE,
    build_base_document,
    empty_diagnostics,
    validate_flow_model_id,
    validate_static_structure,
)
from project_store import ProjectStore, validate_project_id


class FlowModelStore:
    def __init__(self, project_store=None):
        self.project_store = project_store or ProjectStore()

    def flow_dir(self, project_id):
        validate_project_id(project_id)
        return self.project_store.project_dir(project_id) / "flow"

    def model_path(self, project_id):
        return self.flow_dir(project_id) / "flow_model.json"

    def exists(self, project_id):
        return self.model_path(project_id).is_file()

    def get_active(self, project):
        flow_model = self.load(project)
        ref_id = project.get("references", {}).get("flow_model_id")
        if ref_id and flow_model.get("flow_model_id") != ref_id:
            raise FlowModelNotFoundError("active flow model reference mismatch")
        return flow_model

    def load(self, project):
        path = self.model_path(project["project_id"])
        if not path.exists():
            raise FlowModelNotFoundError("active flow model not found")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        diagnostics = validate_static_structure(data)
        if diagnostics.get("errors"):
            raise FlowModelValidationError("stored flow model is invalid", diagnostics)
        return data

    def save(self, project, document):
        validate_flow_model_id(document["flow_model_id"])
        diagnostics = validate_static_structure(document)
        if diagnostics.get("errors"):
            raise FlowModelValidationError("flow model is invalid", diagnostics)
        self._atomic_write(self.model_path(project["project_id"]), document)
        references = dict(project.get("references") or {})
        references["flow_model_id"] = document["flow_model_id"]
        self.project_store.update(
            project["project_id"],
            {"references": references},
        )
        return document

    def mark_active_stale(self, project, reason):
        try:
            document = self.load(project)
        except FlowModelNotFoundError:
            return None
        document["status"] = STATUS_STALE
        document.setdefault("diagnostics", empty_diagnostics())
        document["diagnostics"].setdefault("warnings", []).append(
            {
                "level": "warning",
                "code": "FLOW_MODEL_STALE",
                "message": reason,
                "path": "status",
            }
        )
        document.setdefault("provenance", {}).setdefault("stale_reasons", []).append(reason)
        self._atomic_write(self.model_path(project["project_id"]), document)
        return document

    def build_for_project(self, project, grid_model_id, payload, existing=None):
        return build_base_document(
            project_id=project["project_id"],
            grid_model_id=grid_model_id,
            payload=payload,
            existing=existing,
        )

    def _atomic_write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".flow-", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
