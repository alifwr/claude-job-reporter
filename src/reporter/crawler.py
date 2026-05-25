"""Crawl Claude Code session JSONL files from registered project directories."""
from __future__ import annotations

from pathlib import Path

CLAUDE_PROJECTS_DIR = Path("~/.claude/projects").expanduser()


def path_to_slug(path: Path) -> str:
    """Convert an absolute path to the Claude Code session-directory slug."""
    return str(path).replace("/", "-")
