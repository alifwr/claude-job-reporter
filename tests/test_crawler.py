import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from reporter.crawler import (
    path_to_slug,
    discover_session_files,
    iter_events_in_window,
    parse_start_datetime,
)


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


def test_parse_start_datetime_date_only():
    dt = parse_start_datetime("2026-05-28")
    assert dt.year == 2026 and dt.month == 5 and dt.day == 28
    assert dt.hour == 0 and dt.minute == 0
    assert dt.tzinfo is not None  # naive input -> local tz applied


def test_parse_start_datetime_space_separator():
    dt = parse_start_datetime("2026-05-28 09:30")
    assert dt.year == 2026 and dt.hour == 9 and dt.minute == 30
    assert dt.tzinfo is not None


def test_parse_start_datetime_t_separator():
    dt = parse_start_datetime("2026-05-28T09:30:15")
    assert dt.hour == 9 and dt.minute == 30 and dt.second == 15
    assert dt.tzinfo is not None


def test_parse_start_datetime_utc_z_suffix():
    dt = parse_start_datetime("2026-05-28T09:00:00Z")
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 9


def test_parse_start_datetime_explicit_offset():
    dt = parse_start_datetime("2026-05-28T09:00:00+09:00")
    assert dt.utcoffset().total_seconds() == 9 * 3600


def test_parse_start_datetime_invalid_raises():
    with pytest.raises(ValueError) as exc_info:
        parse_start_datetime("banana")
    assert "Invalid start datetime" in str(exc_info.value)


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
