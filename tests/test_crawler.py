import json
from pathlib import Path
from reporter.crawler import path_to_slug, discover_session_files


def test_simple_path():
    assert path_to_slug(Path("/home/seratusjuta/reporter")) == "-home-seratusjuta-reporter"


def test_root_path():
    assert path_to_slug(Path("/")) == "-"


def test_path_with_dashes_preserved():
    assert path_to_slug(Path("/home/me/my-proj")) == "-home-me-my-proj"


def _make_session(path: Path, cwd: str, ts: str = "2026-05-25T09:00:00Z") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "type": "user",
        "timestamp": ts,
        "sessionId": "sess-1",
        "cwd": cwd,
        "message": {"content": "hello"},
    })
    path.write_text(line + "\n")
    return path


def test_discover_finds_primary_slug(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    projects_dir = tmp_path / "claude_projects"
    slug_dir = projects_dir / f"-{str(project)[1:].replace('/', '-')}"
    session_file = _make_session(slug_dir / "a.jsonl", cwd=str(project))

    found = discover_session_files([project], projects_dir=projects_dir)
    assert session_file in found


def test_discover_finds_worktree(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    projects_dir = tmp_path / "claude_projects"
    primary = projects_dir / f"-{str(project)[1:].replace('/', '-')}"
    worktree_slug = primary.name + "--claude-worktrees-feat-x"
    session_file = _make_session(
        projects_dir / worktree_slug / "b.jsonl",
        cwd=str(project / "sub"),
    )

    found = discover_session_files([project], projects_dir=projects_dir)
    assert session_file in found


def test_discover_skips_unrelated(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    projects_dir = tmp_path / "claude_projects"
    _make_session(
        projects_dir / "-home-other-thing" / "x.jsonl",
        cwd="/home/other/thing",
    )

    found = discover_session_files([project], projects_dir=projects_dir)
    assert found == []
