# Trim Report + Interactive Refine Loop — Design Spec

**Date:** 2026-05-28
**Author:** seratusjuta
**Status:** Draft for review
**Version:** bumps reporter 0.2.0 → 0.3.0

## Purpose

Two changes to the `reporter` CLI:

1. **Tighten the generated report** so it suits a non-technical supervisor:
   outcomes and decisions, not implementation mechanics; cap of 3 bullets per
   project.
2. **Add an interactive feedback loop** so the user can iteratively refine the
   report by typing follow-up prompts after the first generation, instead of
   re-running the whole pipeline.

## Goals & non-goals

**Goals**
- Reports default to outcome-level signal; supervisor can scan in <30s.
- After `reporter run` finishes on an interactive terminal, prompt the user to
  accept or refine the report. Refinement is a single follow-up text prompt
  that re-invokes `claude -p` with the previous report plus the user's request.
- Loop continues until the user says "satisfied" or quits.
- Each iteration overwrites the same `--out` file and re-copies to clipboard.
- Non-interactive contexts (no TTY, `--no-interactive`, cron) skip the loop
  cleanly — the first report is the final report.

**Non-goals**
- No multi-line editor flow (no `$EDITOR` integration). Single-line prompt
  per refinement turn.
- No history/branching of revisions. The "current" report is always the last
  one written.
- No tokens-cost or rate-limit handling (Claude Code sub absorbs this).
- No diff display between iterations.
- No persistence of refinement history across separate `reporter run`
  invocations.

## Change 1 — Tighten the report

Edit `src/reporter/prompts.py` `PROMPT_TEMPLATE`. Two rule changes inside the
existing Rules block:

- **New rule (appended after rule 5):**
  > Bullets describe outcomes, decisions, and blockers — not implementation
  > mechanics. Drop "wrote function X", "refactored Y", "added a helper".
  > Say what shipped, what was decided, what's stuck, what's learned.

- **Modify rule 5 (bullet style):** add a hard cap. New trailing sentence:
  > Max 3 bullets per `#<ProjectTag>` block. If more activity, merge into
  > higher-level outcome bullets.

No template structure changes. All existing template-shape tests
(`test_build_prompt_has_ai_team_greeting`, etc.) keep passing.

New tests in `tests/test_prompts.py`:
- `test_build_prompt_caps_three_bullets_per_project` — asserts "3 bullets"
  language present.
- `test_build_prompt_demands_outcomes_not_mechanics` — asserts "outcomes",
  "decisions", and a representative mechanics-style example are present.

## Change 2 — Interactive refine loop

### CLI surface

`reporter run` gains one new flag, default off so the loop is implicit:

```
--no-interactive    Skip the refine loop even on an interactive terminal.
                    Default: loop only when stdin is a TTY.
```

Behavior:

1. After a successful `deliver()`, check `sys.stdin.isatty()` AND
   `not no_interactive`. If either fails, return.
2. Enter the loop in `refine.run_refine_loop(report, ctx)` (new module).

### `src/reporter/refine.py` (new)

Single public function:

```python
def run_refine_loop(
    initial_report: str,
    *,
    out: Path,
    clipboard: bool,
    binary: str,
    model: str,
    today: str,
    prompt_builder: Callable[[str, str], str] = build_refinement_prompt,
    runner: Callable[..., str] = generate_report,
    deliverer: Callable[..., None] = deliver,
    console: Console = err_console,
    input_fn: Callable[[str], str] = Prompt.ask,
) -> None:
    ...
```

Loop body each turn:

1. Show a small panel: `[s]atisfied  [r]efine  [q]uit  (default: s)`.
2. Read one keystroke / short string via `input_fn`. Empty input or `s`
   exits cleanly. `q` exits cleanly. `r` continues.
3. Ask: `Refinement (one line): ` via `input_fn`. Empty input → loop again to
   the s/r/q prompt (no claude call).
4. Build `prompt = prompt_builder(previous_report, feedback)`.
5. Show spinner, call `runner(prompt=prompt, binary=binary, model=model)` →
   `new_report`.
6. Call `deliverer(new_report, out, clipboard=clipboard)`.
7. Set `previous_report = new_report`. Loop.

If `ClaudeError` or `OutputError` is raised mid-loop, print the error in red
and offer the prompt again — the user can retry or quit. Don't propagate the
exception (the first report already shipped; the loop is bonus).

`KeyboardInterrupt` (Ctrl-C) exits the loop quietly with a dim message.

The dependency injection (`runner`, `prompt_builder`, `deliverer`, `input_fn`,
`console`) is for testability — tests pass fakes, real CLI passes the real
ones.

### `build_refinement_prompt` (new, in `prompts.py`)

```python
def build_refinement_prompt(previous_report: str, feedback: str) -> str:
    return REFINEMENT_TEMPLATE.format(
        previous=previous_report.strip(),
        feedback=feedback.strip(),
    )
```

Template (full text):

```
You previously produced this daily report for my supervisor:

---
{previous}
---

I have a refinement request:

{feedback}

Produce a revised version of the report that addresses this feedback. Keep
the same template, greeting, formatting rules, and outcome-focused style as
the original. Output ENGLISH PLAIN TEXT (no markdown).
```

### Test plan for refine

New `tests/test_refine.py`:

- `test_loop_exits_on_satisfied` — `input_fn` returns `"s"`. Assert
  `runner` is never called, `deliverer` is never called.
- `test_loop_exits_on_default_empty` — `input_fn` returns `""`. Same as above.
- `test_loop_exits_on_quit` — `input_fn` returns `"q"`.
- `test_loop_one_refinement_then_satisfied` — sequence
  `["r", "make it shorter", "s"]`. Assert `runner` called once with a prompt
  containing both the previous report and the feedback. Assert `deliverer`
  called once with the new report.
- `test_loop_two_refinements` — sequence
  `["r", "fix grammar", "r", "shorter", "s"]`. Assert `runner` called twice,
  second call's prompt contains the FIRST refined report (not the original).
- `test_loop_handles_claude_error` — `runner` raises `ClaudeError` once, then
  succeeds. Sequence `["r", "first try", "r", "second try", "s"]`. Assert no
  exception propagates; loop continues.
- `test_loop_keyboard_interrupt_exits_quietly` — `input_fn` raises
  `KeyboardInterrupt`. Assert no exception propagates from
  `run_refine_loop`.

New test in `tests/test_prompts.py`:

- `test_build_refinement_prompt_includes_previous_and_feedback` — feedback
  string and a verbatim snippet of the previous report both appear in output.

### CLI integration test

Extend `tests/test_cli_integration.py`:

- `test_run_skips_refine_loop_when_not_tty` — uses the existing fake `claude`
  fixture. Asserts the loop doesn't block when `CliRunner` is used (CliRunner
  provides non-TTY stdin by default, so the existing tests already pass; this
  test just makes the contract explicit).
- `test_run_no_interactive_flag_skips_loop` — pass `--no-interactive`,
  confirm exit 0 quickly.

(We can't easily integration-test the actual interactive loop without spawning
a PTY — the unit tests in `test_refine.py` cover behavior; the CLI test only
verifies it's wired in and skippable.)

## Architecture summary

```
┌────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐
│ config │──▶│ crawler │──▶│ compactor│──▶│  claude  │──▶│ output │
└────────┘   └─────────┘   └──────────┘   └────┬─────┘   └───┬────┘
                                               │             │
                                               ▼             ▼
                                          ┌──────────────────────┐
                                          │  refine loop (TTY +  │
                                          │  --interactive)      │
                                          │  • prompt s/r/q      │
                                          │  • one-line feedback │
                                          │  • claude -p again   │
                                          │  • overwrite out     │
                                          └──────────────────────┘
```

The refine module is downstream of `output.deliver()`. Each refinement turn
re-uses `generate_report()` and `deliver()`.

## Error handling

| Failure                                | Behavior                                                     |
|----------------------------------------|--------------------------------------------------------------|
| `ClaudeError` during refinement        | Print error in red, return to s/r/q prompt. First report kept. |
| `OutputError` during refinement        | Print error in red, return to s/r/q prompt. Last good report stays on disk. |
| `KeyboardInterrupt` mid-loop           | Print "[dim]exited refine loop[/dim]", return normally.       |
| Empty feedback string                  | No claude call. Re-prompt s/r/q.                              |
| Non-TTY stdin                          | Skip loop entirely. (Same as `--no-interactive`.)             |

## Edge cases

- User pastes a multi-line feedback string — `Prompt.ask` reads only the
  first line. This is by design (single-line for low friction). If the user
  needs more, they can refine again.
- User types `Y` / `yes` / `no` / other unexpected token at s/r/q — fall
  through to default action (satisfied).
- `claude -p` returns empty output — `deliver` still writes the empty file.
  Treat empty as if it succeeded; user can `q` to abandon and keep the
  pre-empty report... wait — `deliver` already overwrote. Mitigation: keep a
  shadow `previous_report` variable in the loop; if the new report is empty
  or whitespace-only, treat as `ClaudeError` and don't write.

## File changes summary

```
src/reporter/prompts.py        Edit: tighten template, add build_refinement_prompt
src/reporter/refine.py         New: run_refine_loop
src/reporter/cli.py            Edit: call run_refine_loop after deliver
tests/test_prompts.py          Add: 3 new tests
tests/test_refine.py           New: 6 tests
tests/test_cli_integration.py  Add: 1 new test for --no-interactive
pyproject.toml                 Bump version 0.2.0 → 0.3.0
src/reporter/__init__.py       Bump __version__
```

## Out of scope / future work

- Multi-line refinement via `$EDITOR` (could add `--refine-editor` later).
- Show a diff between iterations.
- Persist refinement history (`~/.cache/reporter/`) for "undo last".
- Streaming the model output during refinement instead of waiting + spinner.
