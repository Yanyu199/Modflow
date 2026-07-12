import json
import os
import re
import tempfile
from pathlib import Path

from project_schema import (
    ProjectValidationError,
    build_project_document,
    merge_project_update,
    validate_project_document,
)


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = BACKEND_DIR / "projects"
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")


class ProjectNotFoundError(FileNotFoundError):
    pass


class ProjectConflictError(FileExistsError):
    pass


def validate_project_id(project_id):
    if not isinstance(project_id, str) or not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ProjectValidationError(
            "project_id must be 3-64 characters and contain only letters, numbers, underscore, or hyphen"
        )
    if project_id in {".", "..", "default"}:
        raise ProjectValidationError("project_id is reserved")
    return project_id


class ProjectStore:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root else DEFAULT_PROJECT_ROOT.resolve()

    def ensure_root(self):
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id):
        validate_project_id(project_id)
        path = (self.root / project_id).resolve()
        if self.root != path and self.root not in path.parents:
            raise ProjectValidationError("project_id resolves outside project storage")
        return path

    def project_path(self, project_id):
        return self.project_dir(project_id) / "project.json"

    def exists(self, project_id):
        return self.project_path(project_id).is_file()

    def create(self, payload):
        project = build_project_document(payload)
        validate_project_id(project["project_id"])
        project_dir = self.project_dir(project["project_id"])
        if project_dir.exists():
            raise ProjectConflictError("project already exists")
        project_dir.mkdir(parents=True, exist_ok=False)
        self._atomic_write(self.project_path(project["project_id"]), project)
        return project

    def get(self, project_id):
        path = self.project_path(project_id)
        if not path.exists():
            raise ProjectNotFoundError("project not found")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return validate_project_document(data)

    def update(self, project_id, patch):
        existing = self.get(project_id)
        updated = merge_project_update(existing, patch)
        self._atomic_write(self.project_path(project_id), updated)
        return updated

    def validate(self, payload):
        return validate_project_document(payload)

    def _atomic_write(self, path, data):
        self.ensure_root()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".project-", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
