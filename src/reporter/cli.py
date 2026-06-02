"""Reporter CLI entry point."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from reporter import __version__
from reporter.config import Config, DEFAULT_CONFIG_PATH, load, save
from datetime import timedelta

from reporter.crawler import (
    CLAUDE_PROJECTS_DIR,
    discover_session_files,
    iter_events_in_window,
    parse_start_datetime,
    path_to_slug,
)
from reporter.compactor import extract_event, render_session, trim_to_budget
from reporter.reporter import generate_report, ClaudeError
from reporter.output import deliver, OutputError
from reporter.prompts import build_prompt
from reporter.refine import run_refine_loop

COMPACT_CHAR_BUDGET = 200_000  # ~50k tokens

console = Console()
err_console = Console(stderr=True)

CONFIG_PANEL = "Config commands"
RUN_PANEL = "Run command"

HELP_INTRO = """
Generate daily activity reports from your Claude Code session transcripts.

[bold]Workflow[/bold]
  1. [cyan]reporter init[/cyan]                                  create config file
  2. [cyan]reporter add /path/to/proj[/cyan]                     register a project to watch
  3. [cyan]reporter run -s 2026-05-28[/cyan]                     crawl + summarize via [bold]claude -p[/bold]

[bold]Examples[/bold]
  [dim]$[/dim] reporter run                                  [dim]# last 24h, default output path[/dim]
  [dim]$[/dim] reporter run -s 2026-05-28                    [dim]# since midnight of given date (local tz)[/dim]
  [dim]$[/dim] reporter run -s '2026-05-28 09:00'            [dim]# explicit time[/dim]
  [dim]$[/dim] reporter run -s 2026-05-28T09:00:00Z          [dim]# explicit UTC[/dim]
  [dim]$[/dim] reporter run --out report.md                  [dim]# custom path[/dim]
  [dim]$[/dim] reporter run --no-clip                        [dim]# skip clipboard copy[/dim]

[dim]Config lives at ~/.config/reporter/config.toml unless --config is set.[/dim]
"""

_CONFIG_PATH: Path = DEFAULT_CONFIG_PATH


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"reporter [cyan]v{__version__}[/cyan]")
        raise typer.Exit()


def _load_config_or_exit() -> Config:
    try:
        return load(_CONFIG_PATH)
    except FileNotFoundError:
        err_console.print(
            f"[red]error:[/red] config not found at [cyan]{_CONFIG_PATH}[/cyan]. "
            f"Run [bold cyan]reporter init[/bold cyan] first."
        )
        raise typer.Exit(code=1)


app = typer.Typer(
    help=HELP_INTRO,
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback()
def _global_options(
    config: Path = typer.Option(
        DEFAULT_CONFIG_PATH,
        "--config",
        "-c",
        help="Path to the config file.",
        show_default=True,
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Configure the global config path before subcommands run."""
    global _CONFIG_PATH
    _CONFIG_PATH = config


@app.command(rich_help_panel=CONFIG_PANEL)
def init() -> None:
    """
    Create an empty config file.

    [dim]Writes to ~/.config/reporter/config.toml unless overridden with --config.[/dim]
    """
    if _CONFIG_PATH.exists():
        console.print(f"[yellow]config already exists:[/yellow] [cyan]{_CONFIG_PATH}[/cyan]")
        raise typer.Exit(code=0)
    save(Config(), _CONFIG_PATH)
    console.print(f"[green]✓ created[/green] [cyan]{_CONFIG_PATH}[/cyan]")


@app.command(rich_help_panel=CONFIG_PANEL)
def add(
    path: Path = typer.Argument(..., help="Project directory to watch."),
) -> None:
    """Register a project directory to watch."""
    if not path.exists() or not path.is_dir():
        err_console.print(f"[red]error:[/red] directory not found: [cyan]{path}[/cyan]")
        raise typer.Exit(code=1)
    cfg = _load_config_or_exit()
    resolved = path.resolve()
    if resolved in cfg.projects:
        console.print(f"[yellow]already registered:[/yellow] [cyan]{resolved}[/cyan]")
        return
    cfg.projects.append(resolved)
    save(cfg, _CONFIG_PATH)
    console.print(f"[green]✓ added[/green] [cyan]{resolved}[/cyan]")


@app.command(rich_help_panel=CONFIG_PANEL)
def remove(
    path: Path = typer.Argument(..., help="Project directory to unregister."),
) -> None:
    """Unregister a project directory."""
    cfg = _load_config_or_exit()
    resolved = path.resolve()
    if resolved not in cfg.projects:
        err_console.print(f"[red]error:[/red] not registered: [cyan]{resolved}[/cyan]")
        raise typer.Exit(code=1)
    cfg.projects.remove(resolved)
    save(cfg, _CONFIG_PATH)
    console.print(f"[green]✓ removed[/green] [cyan]{resolved}[/cyan]")


@app.command(name="list", rich_help_panel=CONFIG_PANEL)
def list_projects() -> None:
    """List registered project directories."""
    cfg = _load_config_or_exit()
    if not cfg.projects:
        console.print("[dim](no projects registered)[/dim]")
        return
    # Plain output when stdout is not a TTY so paths aren't truncated when piping.
    if not sys.stdout.isatty():
        for p in cfg.projects:
            print(str(p))
        return
    table = Table(
        title="Watched projects",
        title_style="bold",
        title_justify="left",
        show_header=True,
        header_style="bold cyan",
        box=None,
        pad_edge=False,
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Path", style="white", overflow="fold")
    for i, p in enumerate(cfg.projects, 1):
        table.add_row(str(i), str(p))
    console.print(table)


@app.command(rich_help_panel=RUN_PANEL)
def run(
    start_datetime: Optional[str] = typer.Option(
        None, "--start-datetime", "-s",
        help="Filter cutoff (inclusive). ISO 8601: [cyan]YYYY-MM-DD[/cyan], [cyan]YYYY-MM-DD HH:MM[/cyan], or [cyan]YYYY-MM-DDTHH:MM:SSZ[/cyan]. Naive values use local timezone. Default: 24h ago.",
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", "-o",
        help="Output file path. Default: [cyan]<out_dir>/YYYY-MM-DD.md[/cyan].",
    ),
    no_clip: bool = typer.Option(
        False, "--no-clip",
        help="Skip clipboard copy.",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model passed to [bold]claude -p[/bold] (e.g. [cyan]sonnet[/cyan], [cyan]opus[/cyan], [cyan]haiku[/cyan]).",
    ),
    claude_binary: Optional[str] = typer.Option(
        None, "--claude-binary",
        help="Override path to the [bold]claude[/bold] CLI.",
    ),
    no_interactive: bool = typer.Option(
        False, "--no-interactive",
        help="Skip the post-report refine loop even on an interactive terminal.",
    ),
) -> None:
    """
    Crawl session JSONLs, summarize, write report.

    [dim]The report is written to --out, echoed to stdout, and copied to the
    clipboard unless --no-clip is set. stdout is just the report content
    (status messages go to stderr) so piping works:[/dim]

      [dim]$ reporter run | less[/dim]
    """
    cfg = _load_config_or_exit()
    model_name = model or cfg.model
    binary = claude_binary or cfg.claude_binary
    use_clipboard = cfg.clipboard and not no_clip

    today = datetime.now().date().isoformat()
    if out is None:
        out = cfg.out_dir / f"{today}.md"

    projects_dir_env = os.environ.get("REPORTER_PROJECTS_DIR")
    projects_dir = Path(projects_dir_env) if projects_dir_env else CLAUDE_PROJECTS_DIR

    if start_datetime is None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        cutoff_label = "last 24h"
    else:
        try:
            cutoff = parse_start_datetime(start_datetime)
        except ValueError as e:
            err_console.print(f"[red]error:[/red] {e}")
            raise typer.Exit(code=1)
        cutoff_label = f"since {cutoff.isoformat()}"

    err_console.print(
        f"[dim]window:[/dim] [cyan]{cutoff_label}[/cyan]  "
        f"[dim]model:[/dim] [cyan]{model_name}[/cyan]  "
        f"[dim]projects:[/dim] [cyan]{len(cfg.projects)}[/cyan]"
    )

    files = discover_session_files(cfg.projects, projects_dir=projects_dir)
    if not files:
        err_console.print(
            f"[yellow]No activity {cutoff_label}[/yellow] [dim](no session files found).[/dim]"
        )
        raise typer.Exit(code=2)

    sessions: dict[str, list[dict]] = {}
    project_for_slug = {path_to_slug(p): str(p) for p in cfg.projects}

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
        err_console.print(f"[yellow]No activity {cutoff_label}.[/yellow]")
        raise typer.Exit(code=2)

    total_events = sum(len(v) for v in sessions.values())
    err_console.print(
        f"[dim]sessions:[/dim] [cyan]{len(sessions)}[/cyan]  "
        f"[dim]events:[/dim] [cyan]{total_events}[/cyan]  "
        f"[dim]files:[/dim] [cyan]{len(files)}[/cyan]"
    )

    sessions = trim_to_budget(sessions, COMPACT_CHAR_BUDGET)
    compacted = "\n".join(render_session(slug, evs) for slug, evs in sessions.items())
    prompt = build_prompt(today, compacted)

    try:
        with err_console.status(
            f"[bold green]Generating report[/bold green] [dim]via `{binary} -p --model {model_name}`...[/dim]",
            spinner="dots",
        ):
            report = generate_report(prompt=prompt, binary=binary, model=model_name)
    except ClaudeError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=3)

    try:
        deliver(report, out, clipboard=use_clipboard)
    except OutputError as e:
        err_console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=1)

    err_console.print()
    err_console.print(
        Panel(
            f"[green]✓[/green] report written to [cyan]{out}[/cyan]\n"
            + (
                "[green]✓[/green] copied to clipboard"
                if use_clipboard
                else "[dim]clipboard skipped[/dim]"
            ),
            title="[bold green]done[/bold green]",
            title_align="left",
            border_style="green",
            expand=False,
        )
    )

    if not no_interactive and sys.stdin.isatty():
        run_refine_loop(
            initial_report=report,
            out=out,
            clipboard=use_clipboard,
            binary=binary,
            model=model_name,
            today=today,
        )
