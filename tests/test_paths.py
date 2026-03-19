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


def test_config_dir_exists():
    from work_journal.paths import CONFIG_DIR

    assert CONFIG_DIR.exists()
    assert CONFIG_DIR.name == "config"


def test_shared_config_path_exists():
    from work_journal.paths import SHARED_CONFIG_PATH

    assert SHARED_CONFIG_PATH.exists()
    assert SHARED_CONFIG_PATH.name == "shared.yaml"


def test_templates_dir_exists():
    from work_journal.paths import TEMPLATES_DIR

    assert TEMPLATES_DIR.exists()
    assert TEMPLATES_DIR.name == "templates"


def test_project_configs_dir_exists():
    from work_journal.paths import PROJECT_CONFIGS_DIR

    assert PROJECT_CONFIGS_DIR.exists()


def test_sprint_notes_dir():
    from work_journal.paths import SPRINT_NOTES_DIR

    assert SPRINT_NOTES_DIR.name == "sprint-notes"


def test_progress_briefs_dir():
    from work_journal.paths import PROGRESS_BRIEFS_DIR

    assert PROGRESS_BRIEFS_DIR.name == "progress-briefs"
