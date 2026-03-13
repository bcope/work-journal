import pytest


def test_resolve_env_vars_simple(monkeypatch):
    monkeypatch.setenv("TEST_VAR", "hello")
    from work_journal.config import resolve_env_vars

    assert resolve_env_vars("${TEST_VAR}") == "hello"


def test_resolve_env_vars_nested_dict(monkeypatch):
    monkeypatch.setenv("A", "1")
    monkeypatch.setenv("B", "2")
    from work_journal.config import resolve_env_vars

    result = resolve_env_vars({"x": "${A}", "y": {"z": "${B}"}})
    assert result == {"x": "1", "y": {"z": "2"}}


def test_resolve_env_vars_list(monkeypatch):
    monkeypatch.setenv("ITEM", "val")
    from work_journal.config import resolve_env_vars

    assert resolve_env_vars(["${ITEM}", "literal"]) == ["val", "literal"]


def test_resolve_env_vars_missing_warns(monkeypatch, capsys):
    monkeypatch.delenv("SURELY_MISSING", raising=False)
    from work_journal.config import resolve_env_vars

    result = resolve_env_vars("${SURELY_MISSING}")
    assert result == "${SURELY_MISSING}"
    assert "SURELY_MISSING" in capsys.readouterr().err


def test_resolve_env_vars_passthrough():
    from work_journal.config import resolve_env_vars

    assert resolve_env_vars(42) == 42
    assert resolve_env_vars(None) is None


def test_load_config_returns_dict():
    from work_journal.config import load_config

    config = load_config()
    assert isinstance(config, dict)
    assert "jira" in config


def test_load_sprint_config(tmp_path):
    from work_journal.config import load_sprint_config

    sprint_yaml = tmp_path / "sprint.yaml"
    sprint_yaml.write_text('sprint_name: "test-sprint"\n')
    result = load_sprint_config(tmp_path)
    assert result["sprint_name"] == "test-sprint"


def test_load_sprint_config_missing(tmp_path):
    from work_journal.config import load_sprint_config

    with pytest.raises(SystemExit):
        load_sprint_config(tmp_path)
