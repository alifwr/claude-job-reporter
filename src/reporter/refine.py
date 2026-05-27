"""Interactive refine loop for `reporter run`."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from rich.console import Console

from reporter.output import deliver as _real_deliver
from reporter.output import OutputError
from reporter.prompts import build_refinement_prompt as _real_build_refinement_prompt
from reporter.reporter import ClaudeError
from reporter.reporter import generate_report as _real_generate_report


_DEFAULT_CONSOLE = Console(stderr=True)


def _default_input(prompt: str, **kwargs) -> str:
    """Fallback prompt that just calls input()."""
    return input(prompt)


def run_refine_loop(
    initial_report: str,
    *,
    out: Path,
    clipboard: bool,
    binary: str,
    model: str,
    today: str,
    runner: Callable[..., str] = _real_generate_report,
    deliverer: Callable[..., None] = _real_deliver,
    prompt_builder: Callable[[str, str], str] = _real_build_refinement_prompt,
    console: Console | None = None,
    input_fn: Callable[..., str] = _default_input,
) -> None:
    """Run the interactive refine loop.

    Repeatedly asks the user whether they're satisfied with the report, or
    want to refine it via a follow-up prompt. Each refinement turn calls
    `runner` with `prompt_builder(previous_report, feedback)` and writes the
    new report via `deliverer`. The loop exits on 's', 'q', empty input, or
    KeyboardInterrupt.

    All collaborators are injectable for testing.
    """
    cons = console if console is not None else _DEFAULT_CONSOLE
    previous_report = initial_report

    try:
        while True:
            choice = input_fn(
                "Refine? [s]atisfied / [r]efine / [q]uit (default: s): ",
            ).strip().lower()

            if choice in ("", "s", "q"):
                return
            if choice != "r":
                return

            feedback = input_fn("Refinement (one line): ").strip()
            if not feedback:
                continue

            prompt = prompt_builder(previous_report, feedback)
            try:
                new_report = runner(prompt=prompt, binary=binary, model=model)
            except ClaudeError as e:
                cons.print(f"[red]error:[/red] {e}")
                continue

            if not new_report or not new_report.strip():
                cons.print("[yellow]warning:[/yellow] claude returned empty output; keeping previous report")
                continue

            try:
                deliverer(new_report, out, clipboard=clipboard)
            except OutputError as e:
                cons.print(f"[red]error:[/red] {e}")
                continue

            previous_report = new_report

    except KeyboardInterrupt:
        cons.print("[dim]exited refine loop[/dim]")
        return
