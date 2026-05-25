"""Invoke the local `claude` CLI in headless mode to generate the report."""
from __future__ import annotations

import subprocess


class ClaudeError(RuntimeError):
    """Raised when `claude -p` fails or is not installed."""


def generate_report(prompt: str, binary: str, model: str, timeout: int = 300) -> str:
    """Run `claude -p --model MODEL`, send prompt on stdin, return stdout."""
    cmd = [binary, "-p", "--model", model]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ClaudeError(
            f"`{binary}` not found on PATH. Install Claude Code or set [claude].binary in config."
        )
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"`{binary} -p` timed out after {timeout}s")

    if result.returncode != 0:
        raise ClaudeError(
            f"`{binary} -p` exited with code {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout
