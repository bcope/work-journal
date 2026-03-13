def test_repo_root_contains_pyproject():
    from work_journal.paths import REPO_ROOT

    assert (REPO_ROOT / "pyproject.toml").exists()


def test_repo_root_is_absolute():
    from work_journal.paths import REPO_ROOT

    assert REPO_ROOT.is_absolute()


def test_src_dir_exists():
    from work_journal.paths import SRC_DIR

    assert SRC_DIR.exists()
    assert SRC_DIR.name == "work_journal"


def test_config_path_exists():
    from work_journal.paths import CONFIG_PATH

    assert CONFIG_PATH.exists()
    assert CONFIG_PATH.name == "config.yaml"


def test_sprint_notes_dir():
    from work_journal.paths import SPRINT_NOTES_DIR

    assert SPRINT_NOTES_DIR.name == "sprint-notes"


def test_progress_briefs_dir():
    from work_journal.paths import PROGRESS_BRIEFS_DIR

    assert PROGRESS_BRIEFS_DIR.name == "progress-briefs"
