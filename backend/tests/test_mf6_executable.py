import os
from pathlib import Path

import pytest

from mf6_executable import ExecutableResolutionError, resolve_mf6_executable


def test_explicit_env_path_is_resolved(tmp_path):
    fake_mf6 = tmp_path / ("mf6.exe" if os.name == "nt" else "mf6")
    fake_mf6.write_text("fake executable", encoding="utf-8")
    fake_mf6.chmod(0o755)

    result = resolve_mf6_executable(
        env={"FLOPY_MF6_EXE": str(fake_mf6)},
        repo_root=tmp_path,
    )

    assert result.path == str(fake_mf6.resolve())
    assert result.source == "env:FLOPY_MF6_EXE"


def test_invalid_env_path_reports_checked_sources(tmp_path):
    bad_path = tmp_path / "missing-mf6.exe"

    with pytest.raises(ExecutableResolutionError) as exc_info:
        resolve_mf6_executable(
            env={"FLOPY_MF6_EXE": str(bad_path)},
            repo_root=tmp_path,
        )

    message = str(exc_info.value)
    assert "Unable to locate a usable MODFLOW 6 executable" in message
    assert "env:FLOPY_MF6_EXE" in message
    assert str(bad_path) in message
    assert "PATH:mf6" in message


def test_resolver_does_not_check_developer_absolute_mf6_paths(tmp_path):
    with pytest.raises(ExecutableResolutionError) as exc_info:
        resolve_mf6_executable(env={}, repo_root=tmp_path)

    checked = "\n".join(item.candidate for item in exc_info.value.checked)
    assert "G:\\workspace" not in checked
    assert "D:\\workspace" not in checked
