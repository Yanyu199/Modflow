import json
import os
import tempfile

import numpy as np

from grid_model_schema import (
    MAX_ARTIFACT_BYTES,
    GridModelNotFoundError,
    array_checksum,
    file_checksum,
    validate_grid_manifest,
    validate_grid_model_id,
)
from project_store import ProjectStore, validate_project_id


class GridArtifactError(ValueError):
    pass


class GridModelStore:
    def __init__(self, project_store=None):
        self.project_store = project_store or ProjectStore()

    def grid_dir(self, project_id):
        validate_project_id(project_id)
        return self.project_store.project_dir(project_id) / "grid"

    def artifacts_dir(self, project_id):
        return self.grid_dir(project_id) / "artifacts"

    def manifest_path(self, project_id):
        return self.grid_dir(project_id) / "grid_model.json"

    def artifact_path(self, project_id, relative_path="artifacts/grid_arrays.npz"):
        if relative_path != "artifacts/grid_arrays.npz":
            raise GridArtifactError("unsupported grid artifact path")
        return self.grid_dir(project_id) / relative_path

    def get_active(self, project):
        manifest = self.load_manifest(project)
        ref_id = project.get("references", {}).get("grid_model_id")
        if ref_id and manifest.get("grid_model_id") != ref_id:
            raise GridModelNotFoundError("active grid model reference mismatch")
        return manifest

    def load_manifest(self, project):
        path = self.manifest_path(project["project_id"])
        if not path.exists():
            raise GridModelNotFoundError("active grid model not found")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return validate_grid_manifest(data, project)

    def load_arrays(self, project, manifest=None):
        manifest = manifest or self.get_active(project)
        artifact = manifest.get("artifacts", {})
        relative_path = artifact.get("arrays_path", "artifacts/grid_arrays.npz")
        path = self.artifact_path(project["project_id"], relative_path)
        if not path.exists():
            raise GridArtifactError("grid array artifact is missing")
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise GridArtifactError("grid array artifact exceeds size limit")
        expected_file_checksum = artifact.get("file_sha256")
        if expected_file_checksum and file_checksum(path) != expected_file_checksum:
            raise GridArtifactError("grid array artifact file checksum mismatch")
        with np.load(path, allow_pickle=False) as data:
            arrays = {name: data[name] for name in data.files}
        expected_checksum = artifact.get("arrays_sha256")
        if expected_checksum and array_checksum(arrays) != expected_checksum:
            raise GridArtifactError("grid array checksum mismatch")
        return arrays

    def save(self, project, manifest, arrays):
        validate_grid_model_id(manifest["grid_model_id"])
        grid_dir = self.grid_dir(project["project_id"])
        artifacts_dir = self.artifacts_dir(project["project_id"])
        grid_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = self.artifact_path(project["project_id"])
        fd, tmp_name = tempfile.mkstemp(prefix=".grid-arrays-", suffix=".npz", dir=str(artifacts_dir))
        os.close(fd)
        try:
            np.savez_compressed(tmp_name, **arrays)
            saved_tmp = tmp_name if tmp_name.endswith(".npz") else f"{tmp_name}.npz"
            if os.path.getsize(saved_tmp) > MAX_ARTIFACT_BYTES:
                raise GridArtifactError("grid array artifact exceeds size limit")
            os.replace(saved_tmp, artifact_path)
        finally:
            for candidate in (tmp_name, f"{tmp_name}.npz"):
                if os.path.exists(candidate):
                    os.remove(candidate)

        manifest = dict(manifest)
        manifest["artifacts"] = {
            **(manifest.get("artifacts") or {}),
            "arrays_path": "artifacts/grid_arrays.npz",
            "arrays_sha256": array_checksum(arrays),
            "file_sha256": file_checksum(artifact_path),
            "byte_size": artifact_path.stat().st_size,
        }
        self._atomic_write(self.manifest_path(project["project_id"]), manifest)
        return manifest

    def mark_active_stale(self, project, reason, geology_checksum=None):
        try:
            manifest = self.load_manifest(project)
        except GridModelNotFoundError:
            return None
        manifest["status"] = "stale"
        manifest.setdefault("quality", {}).setdefault("stale_reasons", [])
        manifest["quality"]["stale_reasons"].append(reason)
        if geology_checksum:
            manifest.setdefault("provenance", {})["current_geology_checksum"] = geology_checksum
        self._atomic_write(self.manifest_path(project["project_id"]), manifest)
        return manifest

    def _atomic_write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".grid-", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

