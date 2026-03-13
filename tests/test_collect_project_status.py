"""Tests for collect_project_status.py."""

from work_journal.collect_project_status import resolve_run_dir


def test_resolve_run_dir_first_run(tmp_path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    result = resolve_run_dir(project_dir, "2026-03-10")
    assert result == project_dir / "2026-03-10"


def test_resolve_run_dir_second_run(tmp_path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / "2026-03-10").mkdir()
    result = resolve_run_dir(project_dir, "2026-03-10")
    assert result == project_dir / "2026-03-10-2"


def test_resolve_run_dir_third_run(tmp_path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / "2026-03-10").mkdir()
    (project_dir / "2026-03-10-2").mkdir()
    result = resolve_run_dir(project_dir, "2026-03-10")
    assert result == project_dir / "2026-03-10-3"
