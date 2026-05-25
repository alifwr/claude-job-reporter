from pathlib import Path
import textwrap
import pytest
from reporter.config import Config, DEFAULTS, load, save


def test_load_minimal_config(tmp_path: Path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(textwrap.dedent("""
        projects = ["/tmp/proj-a"]
    """).lstrip())

    cfg = load(cfg_path)
    assert cfg.projects == [Path("/tmp/proj-a")]
    assert cfg.since == DEFAULTS["since"]
    assert cfg.model == DEFAULTS["model"]
    assert cfg.clipboard == DEFAULTS["clipboard"]


def test_load_expands_tilde(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", "/home/testuser")
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('projects = ["~/proj"]\n[defaults]\nout_dir = "~/out"\n')

    cfg = load(cfg_path)
    assert cfg.projects == [Path("/home/testuser/proj")]
    assert cfg.out_dir == Path("/home/testuser/out")


def test_load_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "nope.toml")


def test_save_round_trip(tmp_path: Path):
    cfg_path = tmp_path / "config.toml"
    cfg = Config(
        projects=[Path("/a"), Path("/b")],
        since="3d",
        model="opus",
        out_dir=Path("/tmp/out"),
        clipboard=False,
        claude_binary="claude",
    )
    save(cfg, cfg_path)
    loaded = load(cfg_path)
    assert loaded == cfg
