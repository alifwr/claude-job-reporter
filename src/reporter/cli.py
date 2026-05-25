"""Reporter CLI entry point."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from reporter.config import Config, DEFAULT_CONFIG_PATH, load, save
from reporter.crawler import (
    CLAUDE_PROJECTS_DIR,
    discover_session_files,
    iter_events_in_window,
    parse_duration,
    path_to_slug,
)
from reporter.compactor import extract_event, render_session, trim_to_budget
from reporter.reporter import generate_report, ClaudeError
from reporter.output import deliver
from reporter.prompts import build_prompt

COMPACT_CHAR_BUDGET = 200_000  # ~50k tokens

app = typer.Typer(help="Generate daily activity reports from Claude Code sessions.")

_CONFIG_PATH: Path = DEFAULT_CONFIG_PATH


@app.callback()
def _global_options(
    config: Path = typer.Option(
        DEFAULT_CONFIG_PATH, "--config", help="Path to the config file."
    ),
) -> None:
    """Configure the global config path before subcommands run."""
    global _CONFIG_PATH
    _CONFIG_PATH = config


@app.command()
def init() -> None:
    """Create an empty config file at the configured path."""
    if _CONFIG_PATH.exists():
        typer.echo(f"Config already exists: {_CONFIG_PATH}")
        raise typer.Exit(code=0)
    save(Config(), _CONFIG_PATH)
    typer.echo(f"Created {_CONFIG_PATH}")


@app.command()
def add(path: Path) -> None:
    """Register a project directory to watch."""
    if not path.exists() or not path.is_dir():
        typer.echo(f"error: directory not found: {path}", err=True)
        raise typer.Exit(code=1)
    cfg = load(_CONFIG_PATH)
    resolved = path.resolve()
    if resolved in cfg.projects:
        typer.echo(f"already registered: {resolved}")
        return
    cfg.projects.append(resolved)
    save(cfg, _CONFIG_PATH)
    typer.echo(f"added: {resolved}")


@app.command()
def remove(path: Path) -> None:
    """Unregister a project directory."""
    cfg = load(_CONFIG_PATH)
    resolved = path.resolve()
    if resolved not in cfg.projects:
        typer.echo(f"not registered: {resolved}", err=True)
        raise typer.Exit(code=1)
    cfg.projects.remove(resolved)
    save(cfg, _CONFIG_PATH)
    typer.echo(f"removed: {resolved}")


@app.command(name="list")
def list_projects() -> None:
    """List registered project directories."""
    cfg = load(_CONFIG_PATH)
    if not cfg.projects:
        typer.echo("(no projects registered)")
        return
    for p in cfg.projects:
        typer.echo(str(p))


@app.command()
def run(
    since: Optional[str] = typer.Option(None, "--since", help="Time window, e.g. 24h, 3d."),
    out: Optional[Path] = typer.Option(None, "--out", help="Output file path."),
    no_clip: bool = typer.Option(False, "--no-clip", help="Skip clipboard copy."),
    model: Optional[str] = typer.Option(None, "--model", help="Model passed to `claude -p`."),
    claude_binary: Optional[str] = typer.Option(None, "--claude-binary", help="Path to claude CLI."),
) -> None:
    """Crawl sessions, generate report, write file/stdout/clipboard."""
    cfg = load(_CONFIG_PATH)
    since_str = since or cfg.since
    model_name = model or cfg.model
    binary = claude_binary or cfg.claude_binary
    use_clipboard = cfg.clipboard and not no_clip

    today = datetime.now().date().isoformat()
    if out is None:
        out = cfg.out_dir / f"{today}.md"

    projects_dir_env = os.environ.get("REPORTER_PROJECTS_DIR")
    projects_dir = Path(projects_dir_env) if projects_dir_env else CLAUDE_PROJECTS_DIR

    try:
        delta = parse_duration(since_str)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1)
    cutoff = datetime.now(timezone.utc) - delta

    files = discover_session_files(cfg.projects, projects_dir=projects_dir)
    if not files:
        typer.echo(f"No activity in last {since_str} (no session files found).", err=True)
        raise typer.Exit(code=2)

    sessions: dict[str, list[dict]] = {}
    project_for_slug = {path_to_slug(p): p.name for p in cfg.projects}

    for jsonl in files:
        slug_dir_name = jsonl.parent.name
        display = next(
            (name for slug, name in project_for_slug.items() if slug_dir_name.startswith(slug)),
            slug_dir_name,
        )
        for ev in iter_events_in_window(jsonl, cutoff):
            extracted = extract_event(ev)
            if extracted is not None:
                sessions.setdefault(display, []).append(extracted)

    sessions = {k: v for k, v in sessions.items() if v}
    if not sessions:
        typer.echo(f"No activity in last {since_str}.", err=True)
        raise typer.Exit(code=2)

    sessions = trim_to_budget(sessions, COMPACT_CHAR_BUDGET)
    compacted = "\n".join(render_session(slug, evs) for slug, evs in sessions.items())
    prompt = build_prompt(today, compacted)

    try:
        report = generate_report(prompt=prompt, binary=binary, model=model_name)
    except ClaudeError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=3)

    deliver(report, out, clipboard=use_clipboard)
