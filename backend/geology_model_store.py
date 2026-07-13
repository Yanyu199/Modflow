import json
import os
import tempfile
from pathlib import Path

from geology_model_schema import SCHEMA_VERSION, GeologyModelValidationError, validate_geology_model
from project_schema import ProjectValidationError
from project_store import ProjectStore, validate_project_id


class GeologyModelNotFoundError(FileNotFoundError):
    pass


def validate_geology_model_id(geology_model_id):
    if not isinstance(geology_model_id, str) or not geology_model_id.startswith("geo_"):
        raise ProjectValidationError("geology_model_id must start with geo_")
    suffix = geology_model_id[4:]
    if len(suffix) < 8 or len(suffix) > 32 or not all(c in "0123456789abcdef" for c in suffix):
        raise ProjectValidationError("geology_model_id contains invalid characters")
    return geology_model_id


class GeologyModelStore:
    def __init__(self, project_store=None):
        self.project_store = project_store or ProjectStore()

    def geology_dir(self, project_id):
        validate_project_id(project_id)
        path = self.project_store.project_dir(project_id) / "geology"
        return path

    def artifacts_dir(self, project_id):
        return self.geology_dir(project_id) / "artifacts"

    def active_path(self, project_id):
        return self.geology_dir(project_id) / "geology_model.json"

    def get_active(self, project):
        path = self.active_path(project["project_id"])
        if not path.exists():
            raise GeologyModelNotFoundError("active geology model not found")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        model = validate_geology_model(data, project, allow_incomplete=True)
        ref_id = project.get("references", {}).get("geology_model_id")
        if ref_id and model.get("geology_model_id") != ref_id:
            raise GeologyModelNotFoundError("active geology model reference mismatch")
        return model

    def save(self, project, geology_model):
        validate_geology_model_id(geology_model["geology_model_id"])
        path = self.active_path(project["project_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir(project["project_id"]).mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, geology_model)
        return geology_model

    def _atomic_write(self, path, data):
        fd, tmp_name = tempfile.mkstemp(prefix=".geology-", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
