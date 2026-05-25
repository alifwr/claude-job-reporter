import subprocess
import pytest
from reporter.reporter import generate_report, ClaudeError


def test_generate_report_calls_claude(mocker):
    mock_run = mocker.patch("reporter.reporter.subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="REPORT TEXT", stderr="",
    )

    out = generate_report(prompt="hi", binary="claude", model="sonnet")
    assert out == "REPORT TEXT"

    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "--model" in cmd
    assert "sonnet" in cmd
    assert kwargs["input"] == "hi"


def test_generate_report_raises_on_nonzero_exit(mocker):
    mocker.patch(
        "reporter.reporter.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=2, stdout="", stderr="boom",
        ),
    )
    with pytest.raises(ClaudeError) as ei:
        generate_report(prompt="hi", binary="claude", model="sonnet")
    assert "boom" in str(ei.value)


def test_generate_report_raises_if_binary_missing(mocker):
    mocker.patch(
        "reporter.reporter.subprocess.run",
        side_effect=FileNotFoundError("no claude"),
    )
    with pytest.raises(ClaudeError) as ei:
        generate_report(prompt="hi", binary="claude", model="sonnet")
    assert "not found" in str(ei.value).lower()
