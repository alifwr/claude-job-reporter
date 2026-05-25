"""Reporter CLI entry point."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from reporter.config import Config, DEFAULT_CONFIG_PATH, load, save

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
