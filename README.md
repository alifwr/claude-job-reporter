# reporter

Generate daily activity reports from local Claude Code session transcripts.

See `docs/superpowers/specs/2026-05-25-reporter-design.md` for the design.

## Install

    uv pip install -e .

## Usage

    reporter init
    reporter add /path/to/project
    reporter run --since 24h
