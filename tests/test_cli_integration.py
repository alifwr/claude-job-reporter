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
