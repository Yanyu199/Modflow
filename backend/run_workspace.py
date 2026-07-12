import os
import re
import shutil
import uuid
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE_ROOT = BACKEND_DIR / "workspace"
KEEP_SUCCESS_ENV_VAR = "FLOPY_KEEP_SUCCESSFUL_RUNS"


def sanitize_run_label(label):
    label = str(label or "run")
    label = re.sub(r"[^A-Za-z0-9_.-]+", "-", label)
    label = label.strip(".-")
    return label[:40] or "run"


def new_run_id(prefix="run"):
    return f"{sanitize_run_label(prefix)}-{uuid.uuid4().hex[:12]}"


def create_run_workspace(prefix="run", workspace_root=None):
    root = Path(workspace_root).resolve() if workspace_root else DEFAULT_WORKSPACE_ROOT
    root.mkdir(parents=True, exist_ok=True)

    for _ in range(20):
        run_id = new_run_id(prefix)
        work_dir = root / run_id
        try:
            work_dir.mkdir(parents=False, exist_ok=False)
            return run_id, str(work_dir)
        except FileExistsError:
            continue
    raise RuntimeError(f"Unable to create a unique run workspace under {root}")


def should_keep_successful_runs(env=None):
    env = env if env is not None else os.environ
    value = env.get(KEEP_SUCCESS_ENV_VAR, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def cleanup_run_workspace(work_dir, success, keep_success=None):
    path = Path(work_dir)
    if not path.exists():
        return False
    if not success:
        return True
    if keep_success is None:
        keep_success = should_keep_successful_runs()
    if keep_success:
        return True
    shutil.rmtree(str(path))
    return False
