import os
import shutil
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
PRIMARY_ENV_VAR = "FLOPY_MF6_EXE"
COMPAT_ENV_VAR = "MF6_EXE_PATH"


@dataclass(frozen=True)
class CheckedExecutableSource:
    source: str
    candidate: str
    status: str


@dataclass(frozen=True)
class ExecutableResolution:
    path: str
    source: str
    checked: tuple


class ExecutableResolutionError(RuntimeError):
    def __init__(self, message, checked):
        self.checked = tuple(checked)
        details = "\n".join(
            f"- {item.source}: {item.candidate} [{item.status}]"
            for item in self.checked
        )
        super().__init__(f"{message}\nChecked sources:\n{details}")


def _normalize_path(path_value, repo_root):
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _is_executable_file(path):
    if not path.is_file():
        return False, "not a file"
    if os.name == "nt":
        executable_suffixes = {".exe", ".bat", ".cmd", ".com"}
        if path.suffix.lower() in executable_suffixes:
            return True, "ok"
    if os.access(str(path), os.X_OK):
        return True, "ok"
    return False, "not executable"


def _check_file_candidate(source, path, checked):
    ok, status = _is_executable_file(path)
    checked.append(CheckedExecutableSource(source, str(path), status))
    if ok:
        return ExecutableResolution(str(path), source, tuple(checked))
    return None


def resolve_mf6_executable(env=None, repo_root=None):
    """
    Resolve the MODFLOW 6 executable in a portable order:
    1. FLOPY_MF6_EXE
    2. MF6_EXE_PATH
    3. repository-relative candidates
    4. system PATH
    """
    env = env if env is not None else os.environ
    repo_root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    checked = []

    for env_name in (PRIMARY_ENV_VAR, COMPAT_ENV_VAR):
        value = env.get(env_name)
        if value:
            candidate = _normalize_path(value, repo_root)
            result = _check_file_candidate(f"env:{env_name}", candidate, checked)
            if result:
                return result
        else:
            checked.append(CheckedExecutableSource(f"env:{env_name}", "<unset>", "not set"))

    repo_candidates = [
        repo_root / "mf6.6.3_win64" / "bin" / ("mf6.exe" if os.name == "nt" else "mf6"),
        repo_root / "backend" / "bin" / ("mf6.exe" if os.name == "nt" else "mf6"),
        repo_root / "bin" / ("mf6.exe" if os.name == "nt" else "mf6"),
    ]
    for candidate in repo_candidates:
        result = _check_file_candidate("repo-relative", candidate.resolve(), checked)
        if result:
            return result

    path_candidate = shutil.which("mf6", path=env.get("PATH", ""))
    if path_candidate:
        candidate = Path(path_candidate).resolve()
        result = _check_file_candidate("PATH:mf6", candidate, checked)
        if result:
            return result
    else:
        checked.append(CheckedExecutableSource("PATH:mf6", "mf6", "not found"))

    raise ExecutableResolutionError("Unable to locate a usable MODFLOW 6 executable.", checked)
