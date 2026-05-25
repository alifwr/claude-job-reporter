import json
import os
from pathlib import Path
from typer.testing import CliRunner
from reporter.cli import app

runner = CliRunner()


def test_init_creates_config(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    result = runner.invoke(app, ["--config", str(cfg), "init"])
    assert result.exit_code == 0
    assert cfg.exists()
    assert "projects" in cfg.read_text()


def test_add_appends_project(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    runner.invoke(app, ["--config", str(cfg), "init"])
    proj = tmp_path / "myproj"
    proj.mkdir()
    result = runner.invoke(app, ["--config", str(cfg), "add", str(proj)])
    assert result.exit_code == 0
    assert str(proj) in cfg.read_text()


def test_add_rejects_missing_dir(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    runner.invoke(app, ["--config", str(cfg), "init"])
    result = runner.invoke(app, ["--config", str(cfg), "add", "/no/such/dir"])
    assert result.exit_code != 0
    assert "not found" in (result.stdout + result.stderr).lower()


def test_remove_drops_project(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    proj = tmp_path / "myproj"
    proj.mkdir()
    runner.invoke(app, ["--config", str(cfg), "init"])
    runner.invoke(app, ["--config", str(cfg), "add", str(proj)])
    result = runner.invoke(app, ["--config", str(cfg), "remove", str(proj)])
    assert result.exit_code == 0
    assert str(proj) not in cfg.read_text()


def test_list_prints_projects(tmp_path: Path):
    cfg = tmp_path / "config.toml"
    proj = tmp_path / "myproj"
    proj.mkdir()
    runner.invoke(app, ["--config", str(cfg), "init"])
    runner.invoke(app, ["--config", str(cfg), "add", str(proj)])
    result = runner.invoke(app, ["--config", str(cfg), "list"])
    assert result.exit_code == 0
    assert str(proj) in result.stdout


def _write_session(slug_dir: Path, project_path: Path, when: str) -> Path:
    slug_dir.mkdir(parents=True, exist_ok=True)
    f = slug_dir / "s.jsonl"
    f.write_text(json.dumps({
        "type": "user",
        "timestamp": when,
        "sessionId": "sess-1",
        "cwd": str(project_path),
        "message": {"content": "do work"},
    }) + "\n")
    return f


def test_run_end_to_end(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "config.toml"
    proj = tmp_path / "proj"
    proj.mkdir()
    runner.invoke(app, ["--config", str(cfg), "init"])
    runner.invoke(app, ["--config", str(cfg), "add", str(proj)])

    fake_projects = tmp_path / "claude_projects"
    slug_dir = fake_projects / str(proj).replace("/", "-")
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    _write_session(slug_dir, proj, recent)

    monkeypatch.setenv("REPORTER_PROJECTS_DIR", str(fake_projects))
    fake_claude = Path(__file__).parent / "fixtures" / "fake_claude.sh"
    out_file = tmp_path / "report.md"

    result = runner.invoke(app, [
        "--config", str(cfg), "run",
        "--since", "24h",
        "--out", str(out_file),
        "--no-clip",
        "--claude-binary", str(fake_claude),
    ])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert out_file.exists()
    assert "Daily Report" in out_file.read_text()


def test_run_exits_2_when_no_sessions(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "config.toml"
    proj = tmp_path / "proj"
    proj.mkdir()
    runner.invoke(app, ["--config", str(cfg), "init"])
    runner.invoke(app, ["--config", str(cfg), "add", str(proj)])

    monkeypatch.setenv("REPORTER_PROJECTS_DIR", str(tmp_path / "empty_projects"))
    fake_claude = Path(__file__).parent / "fixtures" / "fake_claude.sh"

    result = runner.invoke(app, [
        "--config", str(cfg), "run",
        "--since", "1h",
        "--no-clip",
        "--claude-binary", str(fake_claude),
        "--out", str(tmp_path / "r.md"),
    ])
    assert result.exit_code == 2


def test_run_without_init_exits_1(tmp_path: Path):
    cfg = tmp_path / "missing.toml"
    result = runner.invoke(app, ["--config", str(cfg), "run"])
    assert result.exit_code == 1
    assert "init" in (result.stdout + result.stderr).lower()


def test_list_without_init_exits_1(tmp_path: Path):
    cfg = tmp_path / "missing.toml"
    result = runner.invoke(app, ["--config", str(cfg), "list"])
    assert result.exit_code == 1
