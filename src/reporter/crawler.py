"""Crawl Claude Code session JSONL files from registered project directories."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

CLAUDE_PROJECTS_DIR = Path("~/.claude/projects").expanduser()


def path_to_slug(path: Path) -> str:
    """Convert an absolute path to the Claude Code session-directory slug."""
    return str(path).replace("/", "-")


def _read_first_cwd(jsonl: Path) -> str | None:
    """Return the cwd field from the first JSON line, or None on failure."""
    try:
        with jsonl.open("r", encoding="utf-8") as f:
            first = f.readline()
        if not first.strip():
            return None
        return json.loads(first).get("cwd")
    except (OSError, json.JSONDecodeError):
        return None


def discover_session_files(
    projects: Iterable[Path],
    projects_dir: Path = CLAUDE_PROJECTS_DIR,
) -> list[Path]:
    """Find all JSONL session files belonging to the given watched projects.

    Includes the primary slug dir for each project plus any sibling slug dir
    whose name starts with the primary slug (worktrees) AND whose first event's
    cwd resolves inside the watched project.
    """
    if not projects_dir.exists():
        return []

    watched = [p.resolve() for p in projects]
    primary_slugs = {path_to_slug(p): p for p in watched}

    found: list[Path] = []
    for slug_dir in projects_dir.iterdir():
        if not slug_dir.is_dir():
            continue

        # Match primary slug directly.
        if slug_dir.name in primary_slugs:
            found.extend(sorted(slug_dir.glob("*.jsonl")))
            continue

        # Match worktree slug (prefix match + cwd check).
        for primary, project in primary_slugs.items():
            if not slug_dir.name.startswith(primary):
                continue
            for jsonl in sorted(slug_dir.glob("*.jsonl")):
                cwd = _read_first_cwd(jsonl)
                if cwd is None:
                    continue
                try:
                    if Path(cwd).resolve().is_relative_to(project):
                        found.append(jsonl)
                except (OSError, ValueError):
                    pass

    return found
