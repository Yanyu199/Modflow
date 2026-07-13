"""Run orchestration for persistent flow_model_v1 executions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from flow_model_schema import (
    FlowModelNotFoundError,
    FlowModelValidationError,
    compute_definition_hash,
    has_errors,
)
from flow_model_service import FlowModelService
from geology_model_store import GeologyModelNotFoundError, GeologyModelStore
from grid_model_schema import stable_hash
from mf6_executable import ExecutableResolutionError, resolve_mf6_executable
from post_process import process_results
from project_store import ProjectStore
from run_diagnostics import (
    parse_listing_files,
    read_water_budget,
    register_run_files,
    validate_budget_file,
    validate_head_file,
)
from run_manifest_schema import (
    ERROR_BY_STATUS,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_WARNINGS,
    STATUS_COMPILING,
    STATUS_FAILED_BUDGET,
    STATUS_FAILED_COMPILE,
    STATUS_FAILED_CONVERGENCE,
    STATUS_FAILED_EXECUTABLE,
    STATUS_FAILED_EXECUTION,
    STATUS_FAILED_INPUT_WRITE,
    STATUS_FAILED_OUTPUTS,
    STATUS_FAILED_POSTPROCESSING,
    STATUS_FAILED_VALIDATION,
    STATUS_POSTPROCESSING,
    STATUS_RUNNING,
    STATUS_VALIDATING,
    STATUS_WRITING_INPUT,
    run_summary,
)
from run_manifest_store import RunManifestNotFoundError, RunManifestStore


class RunFailure(RuntimeError):
    def __init__(self, status: str, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []


class RunService:
    def __init__(self, project_store=None, flow_service=None, run_store=None, geology_store=None):
        self.project_store = project_store or ProjectStore()
        self.flow_service = flow_service or FlowModelService(self.project_store)
        self.run_store = run_store or RunManifestStore(self.project_store)
        self.geology_store = geology_store or GeologyModelStore(self.project_store)

    def run(self, project_id: str, flow_model_id: str, *, keep_artifacts: Optional[bool] = None) -> Dict[str, Any]:
        project = self.project_store.get(project_id)
        manifest = self.run_store.create(project, flow_model_id)
        run_id = manifest["run_id"]
        run_root = self.run_store.run_dir(project_id, run_id)
        input_dir = self.run_store.input_dir(project_id, run_id)
        logs_dir = self.run_store.logs_dir(project_id, run_id)
        points = []
        pathlines = []
        mf6_stdout = []
        if keep_artifacts is not None:
            manifest["retention"]["artifacts_retained"] = bool(keep_artifacts)
            manifest = self.run_store.save(manifest)
        try:
            manifest = self.run_store.transition(manifest, STATUS_VALIDATING)
            project = self.project_store.get(project_id)
            flow_model = self.flow_service.flow_store.get_active(project)
            if flow_model.get("flow_model_id") != flow_model_id:
                raise RunFailure(
                    STATUS_FAILED_VALIDATION,
                    "RUN_FLOW_MODEL_NOT_FOUND",
                    "flow_model_id is not the active flow model for this project.",
                )
            if flow_model.get("status") == "stale":
                raise RunFailure(
                    STATUS_FAILED_VALIDATION,
                    "RUN_FLOW_MODEL_STALE",
                    "Flow model is stale because its grid or upstream model changed.",
                )
            project, grid_manifest, arrays = self.flow_service._load_project_grid(project_id, flow_model["grid_model_id"])
            checker_payload = self.flow_service.check(project_id, flow_model_id)
            checker = checker_payload["checker"]
            package_preview = self.flow_service.package_preview(project_id, flow_model_id)["package_preview"] if checker.get("runnable") else None
            manifest = self._update_manifest(
                manifest,
                checker=checker,
                package_preview=package_preview,
                model_snapshot=self._model_snapshot(project, grid_manifest, flow_model),
                model=self._model_summary(grid_manifest, flow_model, package_preview),
            )
            if has_errors(checker.get("diagnostics") or {}):
                raise RunFailure(
                    STATUS_FAILED_VALIDATION,
                    "RUN_MODEL_CHECK_FAILED",
                    "Flow Model Checker found blocking errors.",
                    checker.get("diagnostics", {}).get("errors", []),
                )

            try:
                resolution = resolve_mf6_executable()
            except ExecutableResolutionError as exc:
                raise RunFailure(
                    STATUS_FAILED_EXECUTABLE,
                    "RUN_MF6_NOT_FOUND",
                    "MODFLOW 6 executable could not be resolved.",
                    [{"source": item.source, "candidate": item.candidate, "status": item.status} for item in exc.checked],
                )
            manifest = self._update_manifest(
                manifest,
                mf6={
                    **manifest["mf6"],
                    "executable_source": resolution.source,
                    "version": self._mf6_version(resolution.path),
                },
            )

            manifest = self.run_store.transition(manifest, STATUS_COMPILING)
            try:
                compiled = self.flow_service.compile_to_simulation(
                    project_id,
                    flow_model_id,
                    str(input_dir),
                    mf6_executable=resolution.path,
                )
            except FlowModelValidationError as exc:
                raise RunFailure(
                    STATUS_FAILED_COMPILE,
                    "RUN_PACKAGE_COMPILE_FAILED",
                    "Flow package compilation failed.",
                    exc.diagnostics.get("errors", []),
                )
            compiled_flow_hash = self._flow_checksum(compiled["flow_model"])
            if compiled_flow_hash != manifest["model_snapshot"]["flow_checksum"]:
                raise RunFailure(
                    STATUS_FAILED_COMPILE,
                    "RUN_SNAPSHOT_MISMATCH",
                    "Compiled flow model does not match the run snapshot.",
                )

            manifest = self.run_store.transition(manifest, STATUS_WRITING_INPUT)
            try:
                compiled["simulation"].write_simulation()
            except Exception as exc:
                raise RunFailure(STATUS_FAILED_INPUT_WRITE, "RUN_INPUT_WRITE_FAILED", str(exc))

            manifest = self.run_store.transition(manifest, STATUS_RUNNING)
            execution = self._execute_mf6(resolution.path, input_dir, logs_dir)
            mf6_stdout = execution["stdout_lines"]
            manifest = self._update_manifest(
                manifest,
                mf6={
                    **manifest["mf6"],
                    "return_code": execution["return_code"],
                    "stdout": "logs/mf6_stdout.txt",
                    "stderr": "logs/mf6_stderr.txt",
                },
            )
            if execution["return_code"] != 0:
                raise RunFailure(
                    STATUS_FAILED_EXECUTION,
                    "RUN_MF6_NONZERO_EXIT",
                    "MODFLOW 6 exited with a nonzero return code.",
                    {"return_code": execution["return_code"]},
                )

            manifest = self.run_store.transition(manifest, STATUS_POSTPROCESSING)
            package_names = list((manifest.get("model") or {}).get("packages") or [])
            logical_files = self._logical_output_files(package_names)
            outputs = register_run_files(run_root, logical_files)
            convergence = parse_listing_files(run_root, ["input/mfsim.lst", "input/gwf.lst"])
            manifest = self._update_manifest(
                manifest,
                outputs=outputs,
                convergence=convergence,
                mf6={**manifest["mf6"], "normal_termination": convergence.get("normal_termination")},
            )
            if convergence.get("state") != "converged":
                raise RunFailure(
                    STATUS_FAILED_CONVERGENCE,
                    "RUN_SOLVER_NOT_CONVERGED",
                    "MODFLOW 6 did not provide converged normal termination evidence.",
                    convergence,
                )

            head_ok, head_error = validate_head_file(input_dir / "gwf.hds")
            budget_ok, budget_error = validate_budget_file(input_dir / "gwf.bud")
            if not head_ok or not budget_ok:
                details = []
                if not head_ok:
                    details.append({"code": "RUN_HEAD_READ_FAILED", "message": head_error})
                if not budget_ok:
                    details.append({"code": "RUN_BUDGET_READ_FAILED", "message": budget_error})
                raise RunFailure(STATUS_FAILED_OUTPUTS, "RUN_OUTPUT_MISSING", "Required output files are missing or unreadable.", details)

            units = project.get("units") or {}
            water_budget, package_budget = read_water_budget(
                input_dir / "gwf.bud",
                input_dir / "gwf.lst",
                package_names=self._budget_package_names(package_names),
                time_unit=units.get("time", "day"),
                flow_unit=units.get("flow", "m3/day"),
            )
            manifest = self._update_manifest(manifest, water_budget=water_budget, package_budget=package_budget)
            if water_budget.get("state") != "available" or water_budget.get("within_tolerance") is not True:
                raise RunFailure(
                    STATUS_FAILED_BUDGET,
                    "RUN_BUDGET_OUT_OF_TOLERANCE",
                    "Water budget is unavailable or outside tolerance.",
                    water_budget,
                )

            try:
                grid_info = self.flow_service._grid_info(grid_manifest, arrays)
                points = process_results(
                    str(input_dir),
                    grid_info["nlay"],
                    grid_info["nrow"],
                    grid_info["ncol"],
                    grid_info["idomain"],
                    grid_info["top"],
                    grid_info["botm"],
                    grid_info,
                )
            except Exception as exc:
                raise RunFailure(STATUS_FAILED_POSTPROCESSING, "RUN_POSTPROCESSING_FAILED", str(exc))

            final_status = STATUS_COMPLETED_WITH_WARNINGS if self._has_nonblocking_warnings(manifest) else STATUS_COMPLETED
            manifest = self.run_store.transition(manifest, final_status)
            return self._result(True, manifest, points, pathlines, mf6_stdout)
        except RunFailure as exc:
            manifest = self._fail(manifest, exc.status, exc.code, exc.message, exc.details)
            return self._result(False, manifest, points, pathlines, mf6_stdout)
        except FlowModelNotFoundError as exc:
            manifest = self._fail(manifest, STATUS_FAILED_VALIDATION, "RUN_FLOW_MODEL_NOT_FOUND", str(exc))
            return self._result(False, manifest, points, pathlines, mf6_stdout)
        except FlowModelValidationError as exc:
            manifest = self._fail(
                manifest,
                STATUS_FAILED_VALIDATION,
                "RUN_MODEL_CHECK_FAILED",
                str(exc),
                exc.diagnostics.get("errors", []),
            )
            return self._result(False, manifest, points, pathlines, mf6_stdout)
        except Exception as exc:
            status = self._failure_status_for_stage(manifest.get("status"))
            code = ERROR_BY_STATUS.get(status, "RUN_POSTPROCESSING_FAILED")
            manifest = self._fail(manifest, status, code, str(exc))
            return self._result(False, manifest, points, pathlines, mf6_stdout)

    def list_runs(self, project_id: str, *, limit: int = 20, status: Optional[str] = None):
        self.project_store.get(project_id)
        return self.run_store.list(project_id, limit=limit, status=status)

    def get_run(self, project_id: str, run_id: str):
        self.project_store.get(project_id)
        return self.run_store.load(project_id, run_id)

    def get_summary(self, project_id: str, run_id: str):
        return run_summary(self.get_run(project_id, run_id))

    def _model_snapshot(self, project, grid_manifest, flow_model):
        geology_checksum = None
        geology_id = project.get("references", {}).get("geology_model_id")
        if geology_id:
            try:
                geology_checksum = stable_hash(self.geology_store.get_active(project))
            except GeologyModelNotFoundError:
                geology_checksum = None
        return {
            "project_checksum": stable_hash(project),
            "geology_checksum": geology_checksum,
            "grid_checksum": stable_hash(grid_manifest),
            "grid_arrays_checksum": (grid_manifest.get("artifacts") or {}).get("arrays_sha256"),
            "flow_checksum": self._flow_checksum(flow_model),
        }

    def _flow_checksum(self, flow_model):
        return (flow_model.get("provenance") or {}).get("definition_sha256") or compute_definition_hash(flow_model)

    def _model_summary(self, grid_manifest, flow_model, package_preview):
        geometry = grid_manifest.get("geometry") or {}
        return {
            "simulation_name": "sim",
            "gwf_model_name": "gwf",
            "nlay": geometry.get("nlay"),
            "nrow": geometry.get("nrow"),
            "ncol": geometry.get("ncol"),
            "nper": 1,
            "packages": list((package_preview or {}).get("packages") or []),
        }

    def _update_manifest(self, manifest, **fields):
        updated = dict(manifest)
        updated.update(fields)
        return self.run_store.save(updated)

    def _fail(self, manifest, status, code, message, details=None):
        if manifest.get("status") != status:
            manifest = self.run_store.transition(manifest, status)
        manifest["error"] = {"code": code, "message": message, "details": details or []}
        manifest.setdefault("warnings", [])
        return self.run_store.save(manifest)

    def _result(self, success, manifest, points, pathlines, mf6_stdout):
        summary = run_summary(manifest)
        diagnostic_outputs = [
            item["name"]
            for item in (manifest.get("outputs") or {}).values()
            if item.get("exists") and item.get("name", "").endswith((".lst", ".txt"))
        ]
        return {
            "success": bool(success),
            "run_id": manifest["run_id"],
            "status": manifest["status"],
            "run": summary,
            "manifest": manifest,
            "points": points,
            "pathlines": pathlines,
            "logs": self._logs_for_response(manifest, mf6_stdout),
            "diagnostic_outputs": diagnostic_outputs,
            "flow_model_id": manifest.get("flow_model_id"),
            "grid_model_id": manifest.get("grid_model_id"),
            "checker": manifest.get("checker"),
            "package_preview": manifest.get("package_preview"),
        }

    def _execute_mf6(self, executable, input_dir: Path, logs_dir: Path):
        try:
            completed = subprocess.run(
                [str(executable)],
                cwd=str(input_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise RunFailure(STATUS_FAILED_EXECUTABLE, "RUN_MF6_START_FAILED", str(exc))
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        (logs_dir / "mf6_stdout.txt").write_text(stdout, encoding="utf-8")
        (logs_dir / "mf6_stderr.txt").write_text(stderr, encoding="utf-8")
        return {
            "return_code": int(completed.returncode),
            "stdout_lines": stdout.splitlines(),
            "stderr_lines": stderr.splitlines(),
        }

    def _mf6_version(self, executable):
        try:
            completed = subprocess.run(
                [str(executable), "-v"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
        except Exception:
            return None
        text = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
        if not text:
            return None
        first_line = text.splitlines()[0].strip()
        return first_line[:120]

    def _logical_output_files(self, package_names=None):
        package_names = set(package_names or [])
        files = {
            "simulation_listing": "input/mfsim.lst",
            "model_listing": "input/gwf.lst",
            "head": "input/gwf.hds",
            "budget": "input/gwf.bud",
            "simulation_name_file": "input/mfsim.nam",
            "model_name_file": "input/gwf.nam",
            "dis": "input/gwf.dis",
            "npf": "input/gwf.npf",
            "chd": "input/gwf.chd",
            "ims": "input/sim.ims",
            "stdout": "logs/mf6_stdout.txt",
            "stderr": "logs/mf6_stderr.txt",
        }
        if "WEL" in package_names:
            files["wel"] = "input/gwf.wel"
        if "RIV" in package_names:
            files["riv"] = "input/gwf.riv"
        return files

    def _budget_package_names(self, package_names):
        supported = ("CHD", "WEL", "RIV")
        present = set(package_names or [])
        return tuple(name for name in supported if name in present)

    def _has_nonblocking_warnings(self, manifest):
        checker = manifest.get("checker") or {}
        diagnostics = checker.get("diagnostics") or {}
        return bool(
            manifest.get("warnings")
            or diagnostics.get("warnings")
            or (manifest.get("convergence") or {}).get("warnings")
            or (manifest.get("package_budget") or {}).get("warnings")
        )

    def _failure_status_for_stage(self, status):
        return {
            STATUS_VALIDATING: STATUS_FAILED_VALIDATION,
            STATUS_COMPILING: STATUS_FAILED_COMPILE,
            STATUS_WRITING_INPUT: STATUS_FAILED_INPUT_WRITE,
            STATUS_RUNNING: STATUS_FAILED_EXECUTION,
            STATUS_POSTPROCESSING: STATUS_FAILED_POSTPROCESSING,
        }.get(status, STATUS_FAILED_POSTPROCESSING)

    def _logs_for_response(self, manifest, mf6_stdout):
        lines = [
            f"Run {manifest['run_id']} status: {manifest['status']}",
            f"MF6 normal termination: {(manifest.get('mf6') or {}).get('normal_termination')}",
            f"Convergence: {(manifest.get('convergence') or {}).get('state')}",
        ]
        budget = manifest.get("water_budget") or {}
        if budget.get("state") != "not_checked":
            lines.append(
                "Water budget: in={0}, out={1}, discrepancy={2}".format(
                    budget.get("total_in"),
                    budget.get("total_out"),
                    budget.get("percent_discrepancy"),
                )
            )
        if manifest.get("error"):
            lines.append(f"{manifest['error']['code']}: {manifest['error']['message']}")
        if mf6_stdout:
            lines.append("--- MF6 stdout tail ---")
            lines.extend(mf6_stdout[-20:])
        return "\n".join(lines)
