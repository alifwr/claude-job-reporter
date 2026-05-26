# claude-job-reporter

Generate daily activity reports from local Claude Code session transcripts.
Crawls registered project directories, filters JSONL events by time window,
and asks the local `claude -p` CLI to produce a plain-text daily report
(formatted for KakaoTalk delivery).

See `docs/superpowers/specs/2026-05-25-reporter-design.md` for the design.

## Install

Run without installing (recommended):

    uvx --from git+https://github.com/alifwr/claude-job-reporter reporter --help

Or install as a persistent tool:

    uv tool install git+https://github.com/alifwr/claude-job-reporter

Local development:

    uv pip install -e .

## Usage

    reporter init                              # create ~/.config/reporter/config.toml
    reporter add /path/to/project              # register a project dir to watch
    reporter list                              # show registered dirs
    reporter run --since 24h                   # generate report for last 24h

Options for `run`:

    --since DURATION       window: 24h, 3d, 90m, 1w (default from config)
    --out FILE             output file (default ~/reports/YYYY-MM-DD.md)
    --no-clip              skip clipboard copy
    --model MODEL          model passed to `claude -p` (default: sonnet)
    --claude-binary PATH   override `claude` binary path

## Requirements

- Python 3.11+
- `claude` CLI on PATH (Claude Code subscription — runs `claude -p` for free)
- Linux/macOS (clipboard via `pyperclip`; falls back gracefully if missing)
