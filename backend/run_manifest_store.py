"""Persistence for immutable model run manifests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from project_store import ProjectStore, validate_project_id
from run_manifest_schema import (
    RunManifestValidationError,
    build_run_manifest,
    generate_run_id,
    run_summary,
    transition_manifest,
    validate_manifest,
    validate_run_id,
)


class RunManifestNotFoundError(FileNotFoundError):
    pass


class RunManifestStore:
    def __init__(self, project_store=None):
        self.project_store = project_store or ProjectStore()

    def runs_dir(self, project_id: str) -> Path:
        validate_project_id(project_id)
        return self.project_store.project_dir(project_id) / "runs"

    def run_dir(self, project_id: str, run_id: str) -> Path:
        validate_run_id(run_id)
        path = (self.runs_dir(project_id) / run_id).resolve()
        root = self.runs_dir(project_id).resolve()
        if root != path and root not in path.parents:
            raise RunManifestValidationError("run_id resolves outside run storage")
        return path

    def input_dir(self, project_id: str, run_id: str) -> Path:
        return self.run_dir(project_id, run_id) / "input"

    def output_dir(self, project_id: str, run_id: str) -> Path:
        return self.run_dir(project_id, run_id) / "output"

    def logs_dir(self, project_id: str, run_id: str) -> Path:
        return self.run_dir(project_id, run_id) / "logs"

    def manifest_path(self, project_id: str, run_id: str) -> Path:
        return self.run_dir(project_id, run_id) / "run_manifest.json"

    def create(self, project: Dict[str, Any], flow_model_id: str) -> Dict[str, Any]:
        run_root = self.runs_dir(project["project_id"])
        run_root.mkdir(parents=True, exist_ok=True)
        for _ in range(20):
            run_id = generate_run_id()
            run_dir = self.run_dir(project["project_id"], run_id)
            try:
                run_dir.mkdir(parents=False, exist_ok=False)
                self.input_dir(project["project_id"], run_id).mkdir()
                self.output_dir(project["project_id"], run_id).mkdir()
                self.logs_dir(project["project_id"], run_id).mkdir()
                manifest = build_run_manifest(project, run_id, flow_model_id)
                self.save(manifest)
                return manifest
            except FileExistsError:
                continue
        raise RuntimeError(f"Unable to create a unique run under project {project['project_id']}")

    def load(self, project_id: str, run_id: str) -> Dict[str, Any]:
        path = self.manifest_path(project_id, run_id)
        if not path.exists():
            raise RunManifestNotFoundError("run manifest not found")
        with path.open("r", encoding="utf-8") as f:
            return validate_manifest(json.load(f))

    def save(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        manifest = validate_manifest(manifest)
        path = self.manifest_path(manifest["project_id"], manifest["run_id"])
        self._atomic_write(path, manifest)
        return manifest

    def update(self, manifest: Dict[str, Any], updater: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        updated = updater(dict(manifest))
        return self.save(updated)

    def transition(self, manifest: Dict[str, Any], next_status: str) -> Dict[str, Any]:
        return self.save(transition_manifest(manifest, next_status))

    def list(self, project_id: str, *, limit: int = 20, status: Optional[str] = None) -> List[Dict[str, Any]]:
        run_root = self.runs_dir(project_id)
        if not run_root.exists():
            return []
        manifests = []
        for path in run_root.glob("run_*/run_manifest.json"):
            try:
                manifest = validate_manifest(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            if status and manifest.get("status") != status:
                continue
            manifests.append(manifest)
        manifests.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return [run_summary(item) for item in manifests[: max(1, min(int(limit), 100))]]

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".run-manifest-", suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
