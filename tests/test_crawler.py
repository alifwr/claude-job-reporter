import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from reporter.crawler import path_to_slug, discover_session_files, parse_duration, iter_events_in_window


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


def test_parse_duration_hours():
    assert parse_duration("24h") == timedelta(hours=24)


def test_parse_duration_days():
    assert parse_duration("3d") == timedelta(days=3)


def test_parse_duration_minutes():
    assert parse_duration("90m") == timedelta(minutes=90)


def test_parse_duration_weeks():
    assert parse_duration("1w") == timedelta(weeks=1)


def test_parse_duration_invalid():
    with pytest.raises(ValueError):
        parse_duration("banana")


def test_iter_events_in_window(tmp_path: Path):
    jsonl = tmp_path / "s.jsonl"
    old = "2026-05-20T00:00:00Z"
    new = "2026-05-25T12:00:00Z"
    jsonl.write_text(
        f'{{"type":"user","timestamp":"{old}","message":{{"content":"old"}}}}\n'
        f'{{"type":"user","timestamp":"{new}","message":{{"content":"new"}}}}\n'
    )

    cutoff = datetime(2026, 5, 25, 0, 0, 0, tzinfo=timezone.utc)
    events = list(iter_events_in_window(jsonl, cutoff))
    assert len(events) == 1
    assert events[0]["message"]["content"] == "new"


def test_iter_events_skips_corrupt_lines(tmp_path: Path):
    jsonl = tmp_path / "s.jsonl"
    jsonl.write_text(
        '{"type":"user","timestamp":"2026-05-25T12:00:00Z","message":{"content":"ok"}}\n'
        'not-json-this-line\n'
        '{"type":"user","timestamp":"2026-05-25T13:00:00Z","message":{"content":"ok2"}}\n'
    )
    cutoff = datetime(2026, 5, 25, 0, 0, 0, tzinfo=timezone.utc)
    events = list(iter_events_in_window(jsonl, cutoff))
    assert len(events) == 2
