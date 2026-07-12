from pathlib import Path

from run_workspace import cleanup_run_workspace, create_run_workspace


def test_two_runs_get_distinct_workspaces(tmp_path):
    run_id_1, work_dir_1 = create_run_workspace(prefix="unit-test", workspace_root=tmp_path)
    run_id_2, work_dir_2 = create_run_workspace(prefix="unit-test", workspace_root=tmp_path)

    assert run_id_1 != run_id_2
    assert work_dir_1 != work_dir_2
    assert Path(work_dir_1).is_dir()
    assert Path(work_dir_2).is_dir()


def test_failed_run_workspace_is_kept(tmp_path):
    _, work_dir = create_run_workspace(prefix="failed-run", workspace_root=tmp_path)
    marker = Path(work_dir) / "gwf.lst"
    marker.write_text("diagnostic", encoding="utf-8")

    kept = cleanup_run_workspace(work_dir, success=False)

    assert kept is True
    assert marker.exists()


def test_successful_run_workspace_can_be_removed(tmp_path):
    _, work_dir = create_run_workspace(prefix="success-run", workspace_root=tmp_path)
    marker = Path(work_dir) / "gwf.lst"
    marker.write_text("diagnostic", encoding="utf-8")

    kept = cleanup_run_workspace(work_dir, success=True, keep_success=False)

    assert kept is False
    assert not Path(work_dir).exists()
