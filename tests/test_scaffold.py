import pytest

from work_journal.scaffold import scaffold, validate_vars


def test_validate_vars_passes():
    validate_vars({"sprint_name": "x"}, ["sprint_name"])


def test_validate_vars_missing():
    with pytest.raises(SystemExit):
        validate_vars({}, ["sprint_name"])


def test_scaffold_creates_subdirs(tmp_path):
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": ["a", "b", "c"],
        "files": {},
        "required_vars": [],
    }
    result = scaffold(template, "test-dir", {}, base_override=tmp_path)
    assert result.exists()
    assert (result / "a").is_dir()
    assert (result / "b").is_dir()
    assert (result / "c").is_dir()


def test_scaffold_writes_files_with_substitution(tmp_path):
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": [],
        "files": {
            "config.yaml": 'name: "{sprint_name}"\n',
        },
        "required_vars": ["sprint_name"],
    }
    result = scaffold(template, "my-sprint", {"sprint_name": "Sprint-One"}, base_override=tmp_path)
    content = (result / "config.yaml").read_text()
    assert 'name: "Sprint-One"' in content


def test_scaffold_errors_if_dir_exists(tmp_path):
    (tmp_path / "existing").mkdir()
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": [],
        "files": {},
        "required_vars": [],
    }
    with pytest.raises(SystemExit):
        scaffold(template, "existing", {}, base_override=tmp_path)


def test_scaffold_naming_with_vars(tmp_path):
    template = {
        "base_dir": str(tmp_path),
        "naming": "{name}",
        "subdirs": [],
        "files": {},
        "required_vars": [],
    }
    result = scaffold(template, "2026-Q1", {}, base_override=tmp_path)
    assert result.name == "2026-Q1"
