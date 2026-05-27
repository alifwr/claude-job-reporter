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
