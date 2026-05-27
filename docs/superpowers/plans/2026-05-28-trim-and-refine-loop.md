# Trim Report + Interactive Refine Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the daily report prompt to be supervisor-friendly (outcome bullets, max 3 per project) AND add an interactive refine loop so the user can iteratively revise the report after `reporter run` finishes.

**Architecture:** Edit `prompts.py` to add two prompt rules and a new `build_refinement_prompt` function. Add new `refine.py` module that runs the post-`deliver()` interactive loop with full dependency injection for testability. Wire it into `cli.py run` behind a TTY check and `--no-interactive` flag.

**Tech Stack:** Python 3.11+, typer, rich (already in deps), pytest, pytest-mock.

---

## File Structure

```
src/reporter/prompts.py        Edit: tighten template, add build_refinement_prompt + REFINEMENT_TEMPLATE
src/reporter/refine.py         New: run_refine_loop with DI for tests
src/reporter/cli.py            Edit: call run_refine_loop after deliver; add --no-interactive flag
tests/test_prompts.py          Add: 3 tests (2 trim, 1 refinement-builder)
tests/test_refine.py           New: 6 tests for the loop
tests/test_cli_integration.py  Add: 1 test for --no-interactive
pyproject.toml                 Bump version 0.2.0 → 0.3.0 (final task)
src/reporter/__init__.py       Bump __version__ (final task)
```

---

## Task 1: Tighten Report Prompt

**Files:**
- Modify: `src/reporter/prompts.py`
- Modify: `tests/test_prompts.py`

Tighten the `PROMPT_TEMPLATE` Rules block: add the outcome-vs-mechanics rule and the 3-bullets-per-project cap.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_prompts.py`:

```python
def test_build_prompt_caps_three_bullets_per_project():
    out = build_prompt("2026-05-28", "")
    text = out.lower()
    assert "3 bullets" in text or "three bullets" in text


def test_build_prompt_demands_outcomes_not_mechanics():
    out = build_prompt("2026-05-28", "")
    text = out.lower()
    assert "outcome" in text
    assert "decision" in text or "decisions" in text
    # Must explicitly call out mechanics as the wrong style
    assert "mechanic" in text or "mechanics" in text
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd /home/seratusjuta/reporter && source .venv/bin/activate
pytest tests/test_prompts.py -v
```

Expected: both new tests FAIL with AssertionError; existing 7 prompt tests still pass.

- [ ] **Step 3: Edit `src/reporter/prompts.py` PROMPT_TEMPLATE**

Find the existing rule 5 in `PROMPT_TEMPLATE`:

```
5. Bullets are short technical fragments: noun phrase + verb, no full sentences, no trailing periods. Drop articles. Examples of the style: "Attack graph map engine architecture, skeleton, data format, and scenario", "UI refinement on korea/english flag translation", "wire LLM report generator". Mirror this density and tone.
```

Replace with:

```
5. Bullets are short outcome fragments: noun phrase + verb, no full sentences, no trailing periods. Drop articles. Examples of the style: "Attack graph map engine architecture, skeleton, data format, and scenario", "UI refinement on korea/english flag translation", "wire LLM report generator". Mirror this density and tone. Max 3 bullets per `#<ProjectTag>` block — if more activity, merge into higher-level outcome bullets.
```

Then find rule 6:

```
6. Yesterday bullets describe what was COMPLETED or substantially WORKED ON. Today bullets describe what is IN PROGRESS or PLANNED NEXT — infer continuations from yesterday's unfinished prompts and open blockers when today's session data is sparse.
```

Insert a new rule between 5 and 6 (renumbering 6→7, 7→8, 8→9):

```
6. Bullets describe outcomes, decisions, and blockers — not implementation mechanics. Drop "wrote function X", "refactored Y", "added a helper". Say what shipped, what was decided, what's stuck, what's learned. The audience is a non-technical supervisor who cares about progress, not code-level changes.
```

Renumber the existing 6 → 7, 7 → 8, 8 → 9.

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_prompts.py -v
```

Expected: all 9 tests PASS (7 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/reporter/prompts.py tests/test_prompts.py
git commit -m "feat(prompts): tighten bullet rules — outcomes only, max 3 per project"
```

---

## Task 2: build_refinement_prompt

**Files:**
- Modify: `src/reporter/prompts.py`
- Modify: `tests/test_prompts.py`

Add a second prompt template + builder for the refinement turn.

- [ ] **Step 1: Add failing test**

Append to `tests/test_prompts.py`:

```python
from reporter.prompts import build_refinement_prompt


def test_build_refinement_prompt_includes_previous_and_feedback():
    previous = "Good Morning, AI Team report:\n\nYesterday :\n\n#Reporter\n\n- ship v0.2.0"
    feedback = "Use Indonesian for the greeting."

    out = build_refinement_prompt(previous, feedback)

    assert previous.strip() in out
    assert feedback.strip() in out
    # The model must be told to keep the original template/style
    assert "template" in out.lower() or "format" in out.lower()
    assert "plain text" in out.lower()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_prompts.py::test_build_refinement_prompt_includes_previous_and_feedback -v
```

Expected: FAIL with ImportError (`build_refinement_prompt` doesn't exist).

- [ ] **Step 3: Append to `src/reporter/prompts.py`**

```python
REFINEMENT_TEMPLATE = """You previously produced this daily report for my supervisor:

---
{previous}
---

I have a refinement request:

{feedback}

Produce a revised version of the report that addresses this feedback. Keep the same template, greeting, formatting rules, and outcome-focused style as the original. Output ENGLISH PLAIN TEXT (no markdown — the recipient is KakaoTalk).
"""


def build_refinement_prompt(previous_report: str, feedback: str) -> str:
    """Render the refinement-turn prompt for `claude -p`."""
    return REFINEMENT_TEMPLATE.format(
        previous=previous_report.strip(),
        feedback=feedback.strip(),
    )
```

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/test_prompts.py -v
```

Expected: all 10 tests PASS (9 from Task 1 + 1 new).

- [ ] **Step 5: Commit**

```bash
git add src/reporter/prompts.py tests/test_prompts.py
git commit -m "feat(prompts): add build_refinement_prompt for interactive refine turns"
```

---

## Task 3: refine.run_refine_loop (skeleton + satisfied/quit/empty paths)

**Files:**
- Create: `src/reporter/refine.py`
- Create: `tests/test_refine.py`

Build the loop function. First pass: only the exit paths (satisfied / quit / default-empty). No actual refinement call yet.

- [ ] **Step 1: Add failing tests**

Create `tests/test_refine.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from reporter.refine import run_refine_loop


def _make_inputs(*seq):
    """Return a callable that returns the next item in seq on each call."""
    it = iter(seq)

    def fake(prompt, **kwargs):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError(f"input_fn called more times than expected; last prompt: {prompt!r}")

    return fake


def test_loop_exits_on_satisfied(tmp_path: Path):
    runner = MagicMock()
    deliverer = MagicMock()
    run_refine_loop(
        initial_report="REPORT",
        out=tmp_path / "r.md",
        clipboard=False,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=runner,
        deliverer=deliverer,
        input_fn=_make_inputs("s"),
    )
    runner.assert_not_called()
    deliverer.assert_not_called()


def test_loop_exits_on_default_empty(tmp_path: Path):
    runner = MagicMock()
    deliverer = MagicMock()
    run_refine_loop(
        initial_report="REPORT",
        out=tmp_path / "r.md",
        clipboard=False,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=runner,
        deliverer=deliverer,
        input_fn=_make_inputs(""),
    )
    runner.assert_not_called()
    deliverer.assert_not_called()


def test_loop_exits_on_quit(tmp_path: Path):
    runner = MagicMock()
    deliverer = MagicMock()
    run_refine_loop(
        initial_report="REPORT",
        out=tmp_path / "r.md",
        clipboard=False,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=runner,
        deliverer=deliverer,
        input_fn=_make_inputs("q"),
    )
    runner.assert_not_called()
    deliverer.assert_not_called()


def test_loop_keyboard_interrupt_exits_quietly(tmp_path: Path):
    def boom(prompt, **kwargs):
        raise KeyboardInterrupt

    run_refine_loop(
        initial_report="REPORT",
        out=tmp_path / "r.md",
        clipboard=False,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=MagicMock(),
        deliverer=MagicMock(),
        input_fn=boom,
    )  # Must NOT raise
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_refine.py -v
```

Expected: 4 FAILS with ImportError (module doesn't exist).

- [ ] **Step 3: Create `src/reporter/refine.py`**

```python
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
                # Unknown token -> treat as satisfied.
                return

            feedback = input_fn("Refinement (one line): ").strip()
            if not feedback:
                continue

            # Refinement turn — implemented in Task 4.
            return  # pragma: no cover — replaced in Task 4

    except KeyboardInterrupt:
        cons.print("[dim]exited refine loop[/dim]")
        return
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
pytest tests/test_refine.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/reporter/refine.py tests/test_refine.py
git commit -m "feat(refine): scaffold run_refine_loop with exit-only paths"
```

---

## Task 4: refine.run_refine_loop — refinement turn

**Files:**
- Modify: `src/reporter/refine.py`
- Modify: `tests/test_refine.py`

Add the actual refinement call: prompt_builder → runner → deliverer → loop continues with new report as `previous_report`.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_refine.py`:

```python
def test_loop_one_refinement_then_satisfied(tmp_path: Path):
    runner = MagicMock(return_value="REFINED REPORT")
    deliverer = MagicMock()
    captured_prompts = []

    def prompt_builder(prev, fb):
        captured_prompts.append((prev, fb))
        return f"PROMPT:{prev}::{fb}"

    out = tmp_path / "r.md"

    run_refine_loop(
        initial_report="ORIGINAL REPORT",
        out=out,
        clipboard=True,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=runner,
        deliverer=deliverer,
        prompt_builder=prompt_builder,
        input_fn=_make_inputs("r", "make it shorter", "s"),
    )

    assert len(captured_prompts) == 1
    assert captured_prompts[0] == ("ORIGINAL REPORT", "make it shorter")

    runner.assert_called_once()
    kwargs = runner.call_args.kwargs
    assert kwargs["prompt"] == "PROMPT:ORIGINAL REPORT::make it shorter"
    assert kwargs["binary"] == "claude"
    assert kwargs["model"] == "sonnet"

    deliverer.assert_called_once()
    args, kwargs = deliverer.call_args
    assert args[0] == "REFINED REPORT"
    assert args[1] == out
    assert kwargs["clipboard"] is True


def test_loop_two_refinements(tmp_path: Path):
    runner = MagicMock(side_effect=["FIRST_REFINED", "SECOND_REFINED"])
    deliverer = MagicMock()
    captured_prompts = []

    def prompt_builder(prev, fb):
        captured_prompts.append((prev, fb))
        return "_"

    run_refine_loop(
        initial_report="ORIGINAL",
        out=tmp_path / "r.md",
        clipboard=False,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=runner,
        deliverer=deliverer,
        prompt_builder=prompt_builder,
        input_fn=_make_inputs("r", "fix grammar", "r", "shorter", "s"),
    )

    assert captured_prompts == [
        ("ORIGINAL", "fix grammar"),
        ("FIRST_REFINED", "shorter"),
    ]
    assert runner.call_count == 2
    assert deliverer.call_count == 2


def test_loop_handles_claude_error(tmp_path: Path):
    from reporter.reporter import ClaudeError as CE

    runner = MagicMock(side_effect=[CE("boom"), "GOOD_REPORT"])
    deliverer = MagicMock()

    run_refine_loop(
        initial_report="ORIGINAL",
        out=tmp_path / "r.md",
        clipboard=False,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=runner,
        deliverer=deliverer,
        prompt_builder=lambda p, f: "_",
        input_fn=_make_inputs("r", "first try", "r", "second try", "s"),
    )

    # First call raised, second succeeded; deliverer only called for the success.
    assert runner.call_count == 2
    assert deliverer.call_count == 1
    args, _ = deliverer.call_args
    assert args[0] == "GOOD_REPORT"


def test_loop_empty_feedback_skips_claude(tmp_path: Path):
    runner = MagicMock()
    deliverer = MagicMock()

    run_refine_loop(
        initial_report="ORIGINAL",
        out=tmp_path / "r.md",
        clipboard=False,
        binary="claude",
        model="sonnet",
        today="2026-05-28",
        runner=runner,
        deliverer=deliverer,
        prompt_builder=lambda p, f: "_",
        input_fn=_make_inputs("r", "", "s"),
    )

    runner.assert_not_called()
    deliverer.assert_not_called()
```

- [ ] **Step 2: Run tests, verify the first three fail and the empty-feedback one passes**

```bash
pytest tests/test_refine.py -v
```

Expected:
- `test_loop_one_refinement_then_satisfied` FAIL (runner not called yet — loop returns early)
- `test_loop_two_refinements` FAIL (same)
- `test_loop_handles_claude_error` FAIL (same)
- `test_loop_empty_feedback_skips_claude` PASS (already handled in Task 3)
- 4 prior tests still PASS

- [ ] **Step 3: Replace the `return` placeholder in `src/reporter/refine.py`**

Find this block:

```python
            # Refinement turn — implemented in Task 4.
            return  # pragma: no cover — replaced in Task 4
```

Replace with:

```python
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
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
pytest tests/test_refine.py -v
```

Expected: 8 PASS (4 from Task 3 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/reporter/refine.py tests/test_refine.py
git commit -m "feat(refine): implement refinement turn — prompt -> claude -> deliver -> loop"
```

---

## Task 5: Wire refine loop into CLI

**Files:**
- Modify: `src/reporter/cli.py`
- Modify: `tests/test_cli_integration.py`

Add `--no-interactive` flag and call `run_refine_loop` after `deliver()` when stdin is a TTY.

- [ ] **Step 1: Add failing test for --no-interactive**

Append to `tests/test_cli_integration.py`:

```python
def test_run_no_interactive_flag_skips_refine_loop(tmp_path: Path, monkeypatch):
    """--no-interactive should exit immediately after the first report is delivered."""
    cfg = tmp_path / "config.toml"
    proj = tmp_path / "proj"
    proj.mkdir()
    runner.invoke(app, ["--config", str(cfg), "init"])
    runner.invoke(app, ["--config", str(cfg), "add", str(proj)])

    fake_projects = tmp_path / "claude_projects"
    slug_dir = fake_projects / str(proj).replace("/", "-")
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    _write_session(slug_dir, proj, recent)

    monkeypatch.setenv("REPORTER_PROJECTS_DIR", str(fake_projects))
    fake_claude = Path(__file__).parent / "fixtures" / "fake_claude.sh"
    out_file = tmp_path / "report.md"

    result = runner.invoke(app, [
        "--config", str(cfg), "run",
        "--since", "24h",
        "--out", str(out_file),
        "--no-clip",
        "--no-interactive",
        "--claude-binary", str(fake_claude),
    ])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert out_file.exists()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/test_cli_integration.py::test_run_no_interactive_flag_skips_refine_loop -v
```

Expected: FAIL with "no such option `--no-interactive`" or exit code 2.

- [ ] **Step 3: Edit `src/reporter/cli.py`**

Find this block (at the top with the other imports from `reporter.*`):

```python
from reporter.compactor import extract_event, render_session, trim_to_budget
from reporter.reporter import generate_report, ClaudeError
from reporter.output import deliver, OutputError
from reporter.prompts import build_prompt
```

Add a new import line below them:

```python
from reporter.refine import run_refine_loop
```

Also add `sys` to the existing imports at the top of the file (right after `import os`):

```python
import sys
```

Now find the `run` function signature:

```python
@app.command(rich_help_panel=RUN_PANEL)
def run(
    since: Optional[str] = typer.Option(
        None, "--since", "-s",
        help="Time window. Format: [cyan]Nm[/cyan]/[cyan]Nh[/cyan]/[cyan]Nd[/cyan]/[cyan]Nw[/cyan] (e.g. [cyan]24h[/cyan], [cyan]3d[/cyan], [cyan]90m[/cyan]).",
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
) -> None:
```

Add a new option line after `claude_binary`:

```python
    no_interactive: bool = typer.Option(
        False, "--no-interactive",
        help="Skip the post-report refine loop even on an interactive terminal.",
    ),
```

Find the final `try: deliver(...)` block at the end of `run`:

```python
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
```

Add a refine-loop call AFTER the Panel print, at the very end of `run`:

```python

    if not no_interactive and sys.stdin.isatty():
        run_refine_loop(
            initial_report=report,
            out=out,
            clipboard=use_clipboard,
            binary=binary,
            model=model_name,
            today=today,
        )
```

- [ ] **Step 4: Run tests, verify all pass**

```bash
pytest -v
```

Expected: 70 PASS (59 existing + 2 prompt + 8 refine + 1 cli). No regressions.

- [ ] **Step 5: Verify `reporter run --help` shows the new flag**

```bash
source .venv/bin/activate
uv pip install -e . --quiet
reporter run --help
```

Expected: output includes `--no-interactive`.

- [ ] **Step 6: Commit**

```bash
git add src/reporter/cli.py tests/test_cli_integration.py
git commit -m "feat(cli): wire refine loop into run; add --no-interactive flag"
```

---

## Task 6: Bump version, build, publish

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/reporter/__init__.py`

- [ ] **Step 1: Bump version to 0.3.0**

Edit `pyproject.toml`:

```toml
version = "0.3.0"
```

Edit `src/reporter/__init__.py`:

```python
__version__ = "0.3.0"
```

- [ ] **Step 2: Run full suite + verify CLI**

```bash
cd /home/seratusjuta/reporter && source .venv/bin/activate
pytest -v
reporter --version
```

Expected: 70 tests PASS. `reporter --version` prints `reporter v0.3.0`.

- [ ] **Step 3: Build dist**

```bash
rm -rf dist/
uv build
twine check dist/*
```

Expected: PASSED for both wheel and sdist.

- [ ] **Step 4: Commit + push**

```bash
git add pyproject.toml src/reporter/__init__.py
git commit -m "chore: bump version to 0.3.0"
git push
```

- [ ] **Step 5: Publish to PyPI**

The user will provide a fresh PyPI token. Run:

```bash
UV_PUBLISH_TOKEN='<token>' uv publish dist/*
```

Expected: "Publishing 2 files" and successful upload.

- [ ] **Step 6: Verify install from PyPI**

```bash
sleep 15
uvx --refresh --from 'claude-job-reporter==0.3.0' reporter --version
```

Expected: `reporter v0.3.0`.

---

## Self-Review

1. **Spec coverage:**
   - Change 1 (tighten template) → Task 1.
   - `build_refinement_prompt` → Task 2.
   - `refine.py run_refine_loop` exit paths + KeyboardInterrupt → Task 3.
   - Refinement turn + empty-output guard + ClaudeError handling → Task 4.
   - `--no-interactive` flag + TTY check + CLI wire-up → Task 5.
   - Version bump + publish → Task 6.

2. **Placeholder scan:** All code blocks contain concrete content. No "TBD" / "TODO" / "add error handling" placeholders.

3. **Type consistency:**
   - `run_refine_loop` signature matches spec, used identically across Task 3, Task 4, Task 5.
   - `build_refinement_prompt(previous_report, feedback)` signature matches between Task 2 and Task 3's import.
   - `runner` keyword args (`prompt=`, `binary=`, `model=`) match `generate_report` from earlier code.
   - `deliverer(report, out, clipboard=...)` matches existing `deliver` signature.
   - The OutputError test in Task 4 uses positional + kwargs; `deliver(report, out, clipboard=...)` from `output.py` accepts that — confirmed.

All consistent. Plan ready.
