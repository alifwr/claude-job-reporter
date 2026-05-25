"""Deliver the generated report: write file, echo to stdout, clipboard."""
from __future__ import annotations

import sys
from pathlib import Path

import pyperclip


def deliver(report: str, out_file: Path, clipboard: bool) -> None:
    """Write the report to file, print to stdout, and copy to clipboard."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report)

    sys.stdout.write(report)
    if not report.endswith("\n"):
        sys.stdout.write("\n")

    if clipboard:
        try:
            pyperclip.copy(report)
        except Exception as e:
            sys.stderr.write(f"warning: clipboard copy failed ({e}); skipped.\n")
