# Reporter — Design Spec

**Date:** 2026-05-25
**Author:** seratusjuta
**Status:** Draft for review

## Purpose

Generate daily activity reports from local Claude Code session transcripts for
delivery to the user's professor via KakaoTalk (manual copy-paste). The tool
crawls registered project directories, filters session events to a configurable
time window (default last 24 hours), and asks the local `claude` CLI (headless
mode) to produce a plain-text report.

Cost target: zero per-run cost. Uses the user's existing Claude Code
subscription via `claude -p`, not the paid API.

## Goals & non-goals

**Goals**
- One-shot CLI invocation: `reporter run` prints + saves + clipboards a report.
- Persistent config of watched project directories, editable via subcommands.
- Configurable time window (`--since 24h`, `3d`, `90m`, `1w`).
- Plain-text English output formatted for KakaoTalk readability.
- No paid LLM API cost — use `claude -p` subprocess.

**Non-goals**
- No scheduler/daemon. Cron is the user's job if they want automation later.
- No KakaoTalk auto-send (chat-room delivery requires business API; out of scope).
- No multi-user, no cloud sync, no web UI.
- No structured-output JSON schema for the report.

## Architecture

```
┌─────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ config  │──▶│ crawler │──▶│ compactor│──▶│ claude -p│──▶│  output  │
│ .toml   │   │ JSONL   │   │ filter + │   │ subprocess│   │ file +   │
│         │   │ reader  │   │ truncate │   │ headless │   │ stdout + │
└─────────┘   └─────────┘   └──────────┘   └──────────┘   │ clipboard│
                                                          └──────────┘
```

### Components

Each module has one purpose, a clear interface, and is independently testable.

1. **`config.py`** — load/save TOML, validate paths exist, expand `~`.
2. **`crawler.py`** — given watched dirs + time cutoff, yield session events
   from `~/.claude/projects/<slug>/*.jsonl`.
3. **`compactor.py`** — filter noise (large `tool_result` bodies), keep
   prompts/assistant text/tool names/file paths, render compact text per session.
4. **`reporter.py`** — invoke `claude -p` via subprocess, pass compacted text
   via stdin, capture stdout.
5. **`output.py`** — write markdown file, echo to stdout, copy plain-text
   variant to clipboard.
6. **`cli.py`** — entry point with subcommands using `typer`.
7. **`prompts.py`** — the `claude -p` prompt template (kept separate so it's
   easy to tune without code changes).

## Tech stack

- Python 3.11+ (`tomllib` stdlib).
- `pyperclip` for clipboard (cross-platform; falls back gracefully if missing).
- `typer` for CLI ergonomics.
- `pytest` for tests.
- Install via `uv` or `pipx` as a single-user CLI.

## CLI surface

```
reporter init                      Create empty config at default path
reporter add <path>                Register a project dir to watch
reporter remove <path>             Unregister
reporter list                      Show watched dirs
reporter run [opts]                Crawl + generate report

  --since DURATION   Time window (default from config; e.g. 24h, 3d, 90m, 1w)
  --out FILE         Output file (default ~/reports/YYYY-MM-DD.md)
  --no-clip          Skip clipboard copy
  --model MODEL      Passed to `claude -p --model` (default from config)
```

## Config schema

Path: `~/.config/reporter/config.toml`

```toml
projects = [
    "/home/seratusjuta/reporter",
    "/home/seratusjuta/e-pump-v2-be",
]

[defaults]
since = "24h"
model = "sonnet"
out_dir = "~/reports"
clipboard = true

[claude]
binary = "claude"   # auto-detected on PATH if missing
```

`~` is expanded at load time. `reporter add` rejects non-existent paths with a
clear error.

## Data flow

### Step 1 — Map watched dirs to session files

Each watched absolute path is converted to a slug by replacing `/` with `-`,
yielding the directory under `~/.claude/projects/`. The crawler then globs
`*.jsonl` in that slugged directory.

**Worktree handling:** Claude Code sometimes records worktrees under different
slugs (e.g. `-home-...--claude-worktrees-feat-cybench`). To catch them, the
crawler also scans sibling slugs that begin with the same prefix, reads the
first line's `cwd` field, and includes the file if `cwd` resolves inside a
watched dir.

### Step 2 — Time filter

For each candidate JSONL file:
1. Check file mtime; skip immediately if `mtime < cutoff`.
2. Stream line-by-line. Parse each line as JSON. Keep events where
   `timestamp >= cutoff`.

`cutoff = datetime.now(tz=local) - duration`. Event timestamps in JSONL are
ISO-8601 UTC; convert to local time for comparison.

### Step 3 — Event extraction

**Keep:**
- `type == "user"` → `message.content` (the prompt text).
- `type == "assistant"` → text blocks from `message.content` (drop `thinking`
  blocks; keep `tool_use` blocks with name + key params like `file_path` or
  `command` first 200 chars).
- Tool results — keep only outputs under 500 chars; longer ones replaced with
  `[truncated N chars]`.
- File paths from `Read`/`Edit`/`Write`/`MultiEdit` tool_use blocks → collected
  separately for a "files touched" line per session.

**Drop:**
- `meta`, `system`, hook-output events.
- Large `Bash` stdout dumps, full file `Read` contents.
- Image tool results.

### Step 4 — Compact format

Per-session block sent to `claude -p`:

```
=== SESSION: <project-slug> | <start_ts> — <end_ts> | <N events> ===
[09:14] USER: <prompt>
[09:14] CLAUDE: <reply text>
[09:15] TOOL: Edit /path/to/file.py
[09:15] TOOL: Bash "pytest tests/" → ok (truncated)
[09:18] USER: <next prompt>
...
=== FILES TOUCHED: file1.py, file2.ts, ... ===
```

Sessions concatenated in chronological order. Target total ≤ ~50K tokens. If
over, trim oldest events per session with `[N earlier events omitted]` marker.

### Step 5 — Prompt template

```
You are summarizing my Claude Code activity for a daily report to my professor.
Output ENGLISH PLAIN TEXT (no markdown — recipient is KakaoTalk).
Use this template exactly:

📋 Daily Report — <today's date>

Summary: <2-3 sentences>

🛠 Projects worked on
• <name> — <what + why>

✅ Completed
• ...

⏳ In progress / blockers
• ...

➡ Next steps
• ...

Be concise, factual, professor-appropriate tone. Group by project. Infer "why"
from prompts. If blockers are unclear, omit that section.

Below is the session data:
---
<compacted text here>
```

### Step 6 — Output

1. Write the model's stdout to `~/reports/YYYY-MM-DD.md` (overwrites if same
   day). The file extension stays `.md` for editor convenience even though the
   content is plain text.
2. Echo the same content to the terminal stdout.
3. Copy to clipboard via `pyperclip.copy()` unless `--no-clip` or
   `defaults.clipboard = false`.

## Error handling

Validation happens only at system boundaries. Internal calls trust inputs.

| Failure                         | Behavior                                            |
|---------------------------------|-----------------------------------------------------|
| Config missing                  | Hint to run `reporter init`. Exit 1.                |
| Watched dir gone                | Warn, skip, continue.                               |
| JSONL line fails to parse       | Skip line. Count drops; log total at end.           |
| File locked / actively written  | Copy to `/tmp/` first, then parse.                  |
| No sessions in window           | Print "No activity in last X." Exit 2.              |
| `claude` not on PATH            | Print install hint. Exit 3.                         |
| `claude -p` non-zero exit       | Print its stderr. Exit 3.                           |
| Clipboard tool missing          | Warn, skip clipboard. File and stdout still happen. |
| Output dir not writable         | Print path. Exit 1.                                 |

## Edge cases

- **Worktrees** — dedupe by `cwd` of first event so the same project isn't
  reported twice under two slugs.
- **Cross-day sessions** — single JSONL file may straddle the time window;
  per-event filter handles this.
- **Empty session** (after filter) — skip the session entirely.
- **Very long single prompt** (e.g. pasted log) — truncate at 2KB with a
  `[truncated]` marker.
- **Timezones** — cutoff computed in local time; JSONL timestamps treated as
  UTC, converted before comparison and before display.
- **Symlinks** in watched dirs — resolve once at config load via
  `Path.resolve()`.

## Testing strategy

- **Unit tests** (`pytest`) with sample JSONL fixtures in `tests/fixtures/`.
  Each module tested in isolation: config round-trip, slug mapping, time
  filtering, event extraction, truncation rules, compact-format rendering.
- **Integration test** — end-to-end with a fake `claude` binary on `PATH` (a
  shell script that echoes a canned report). Confirms subprocess wiring,
  stdin/stdout handling, file + clipboard output paths.
- **No live LLM in tests.** Real `claude -p` runs only during manual usage.
- **Manual smoke test** after first build — run `reporter run` against the
  user's own `~/.claude/projects/-home-seratusjuta-reporter` directory (this
  brainstorming conversation will be the input data).

## File layout

```
reporter/
├── pyproject.toml
├── README.md
├── src/reporter/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── crawler.py
│   ├── compactor.py
│   ├── reporter.py
│   ├── output.py
│   └── prompts.py
├── tests/
│   ├── fixtures/
│   │   └── sample.jsonl
│   ├── test_config.py
│   ├── test_crawler.py
│   ├── test_compactor.py
│   └── test_cli.py
└── docs/superpowers/specs/
    └── 2026-05-25-reporter-design.md  (this file)
```

## Out of scope (future work)

- Scheduler/cron wrapper.
- KakaoTalk auto-send via Kakao Developers API.
- HTML/PDF export.
- Diff-aware reports (read `git log` from each project for extra signal).
- Multi-language output (Korean variant of the template).
