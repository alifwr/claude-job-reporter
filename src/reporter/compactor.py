"""Turn raw JSONL events into compact records suitable for the LLM prompt."""
from __future__ import annotations

from typing import Any

PROMPT_MAX_CHARS = 2000
TOOL_RESULT_MAX_CHARS = 500
TOOL_PARAM_MAX_CHARS = 200


def _truncate(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + " [truncated]"


def _truncate_tool_result(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    return f"{s[:limit]} [truncated {len(s) - limit} chars]"


def _content_text(content: Any) -> str:
    """Reduce a `message.content` value to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
    return ""


def extract_event(ev: dict) -> dict | None:
    """Extract the salient fields of a raw JSONL event.

    Returns a small dict like {ts, kind, ...} or None to drop the event.
    """
    ts = ev.get("timestamp", "")
    kind = ev.get("type")

    if kind == "user":
        content = ev.get("message", {}).get("content")
        # Tool results arrive as user events with a structured content list.
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    body = block.get("content", "")
                    if isinstance(body, list):
                        body = _content_text(body)
                    return {
                        "ts": ts,
                        "kind": "tool_result",
                        "text": _truncate_tool_result(str(body), TOOL_RESULT_MAX_CHARS),
                    }
            return None
        text = str(content) if content is not None else ""
        return {"ts": ts, "kind": "user", "text": _truncate(text, PROMPT_MAX_CHARS)}

    if kind == "assistant":
        content = ev.get("message", {}).get("content", [])
        if not isinstance(content, list):
            return None
        # Prefer tool_use if present; otherwise text.
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return _extract_tool_use(ts, block)
        text = _content_text(content)
        if not text:
            return None
        return {"ts": ts, "kind": "assistant", "text": _truncate(text, PROMPT_MAX_CHARS)}

    return None


def _extract_tool_use(ts: str, block: dict) -> dict:
    name = block.get("name", "?")
    inp = block.get("input", {}) or {}
    out: dict[str, Any] = {"ts": ts, "kind": "tool_use", "name": name}
    if "file_path" in inp:
        out["file_path"] = str(inp["file_path"])
    if "command" in inp:
        out["command"] = _truncate(str(inp["command"]), TOOL_PARAM_MAX_CHARS)
    return out


def _hhmm(ts: str) -> str:
    """Return 'HH:MM' from an ISO timestamp; '??:??' if unparseable."""
    if len(ts) >= 16 and ts[10] == "T":
        return ts[11:16]
    return "??:??"


def render_session(slug: str, events: list[dict]) -> str:
    """Render a per-session compact text block. Returns '' if events is empty."""
    if not events:
        return ""

    start_ts = events[0]["ts"]
    end_ts = events[-1]["ts"]
    lines = [f"=== SESSION: {slug} | {start_ts} — {end_ts} | {len(events)} events ==="]

    files_touched: list[str] = []
    seen_files: set[str] = set()

    for ev in events:
        t = _hhmm(ev["ts"])
        kind = ev["kind"]
        if kind == "user":
            lines.append(f"[{t}] USER: {ev['text']}")
        elif kind == "assistant":
            lines.append(f"[{t}] CLAUDE: {ev['text']}")
        elif kind == "tool_use":
            name = ev["name"]
            if "file_path" in ev:
                lines.append(f"[{t}] TOOL: {name} {ev['file_path']}")
                if ev["file_path"] not in seen_files:
                    seen_files.add(ev["file_path"])
                    files_touched.append(ev["file_path"])
            elif "command" in ev:
                lines.append(f'[{t}] TOOL: {name} "{ev["command"]}"')
            else:
                lines.append(f"[{t}] TOOL: {name}")
        elif kind == "tool_result":
            lines.append(f"[{t}] RESULT: {ev['text']}")

    if files_touched:
        lines.append(f"=== FILES TOUCHED: {', '.join(files_touched)} ===")

    return "\n".join(lines) + "\n"
