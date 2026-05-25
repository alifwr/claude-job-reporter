from reporter.compactor import extract_event, TOOL_RESULT_MAX_CHARS, PROMPT_MAX_CHARS


def test_extract_user_prompt():
    ev = {
        "type": "user",
        "timestamp": "2026-05-25T09:00:00Z",
        "message": {"content": "fix the bug"},
    }
    out = extract_event(ev)
    assert out == {"ts": "2026-05-25T09:00:00Z", "kind": "user", "text": "fix the bug"}


def test_extract_long_user_prompt_truncated():
    ev = {
        "type": "user",
        "timestamp": "2026-05-25T09:00:00Z",
        "message": {"content": "x" * (PROMPT_MAX_CHARS + 100)},
    }
    out = extract_event(ev)
    assert out["text"].endswith("[truncated]")
    assert len(out["text"]) <= PROMPT_MAX_CHARS + len(" [truncated]")


def test_extract_assistant_text():
    ev = {
        "type": "assistant",
        "timestamp": "2026-05-25T09:00:05Z",
        "message": {"content": [{"type": "text", "text": "doing X"}]},
    }
    out = extract_event(ev)
    assert out == {"ts": "2026-05-25T09:00:05Z", "kind": "assistant", "text": "doing X"}


def test_extract_assistant_drops_thinking():
    ev = {
        "type": "assistant",
        "timestamp": "2026-05-25T09:00:05Z",
        "message": {"content": [
            {"type": "thinking", "thinking": "internal stuff"},
            {"type": "text", "text": "public reply"},
        ]},
    }
    out = extract_event(ev)
    assert out["text"] == "public reply"


def test_extract_tool_use_edit():
    ev = {
        "type": "assistant",
        "timestamp": "2026-05-25T09:00:10Z",
        "message": {"content": [
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": "/a/b/c.py", "old_string": "x", "new_string": "y"}},
        ]},
    }
    out = extract_event(ev)
    assert out["kind"] == "tool_use"
    assert out["name"] == "Edit"
    assert out["file_path"] == "/a/b/c.py"


def test_extract_tool_use_bash():
    ev = {
        "type": "assistant",
        "timestamp": "2026-05-25T09:00:10Z",
        "message": {"content": [
            {"type": "tool_use", "name": "Bash",
             "input": {"command": "pytest tests/"}},
        ]},
    }
    out = extract_event(ev)
    assert out["kind"] == "tool_use"
    assert out["name"] == "Bash"
    assert out["command"] == "pytest tests/"


def test_extract_tool_result_short():
    ev = {
        "type": "user",
        "timestamp": "2026-05-25T09:00:11Z",
        "message": {"content": [
            {"type": "tool_result", "content": "ok"},
        ]},
    }
    out = extract_event(ev)
    assert out == {"ts": "2026-05-25T09:00:11Z", "kind": "tool_result", "text": "ok"}


def test_extract_tool_result_long_truncated():
    ev = {
        "type": "user",
        "timestamp": "2026-05-25T09:00:11Z",
        "message": {"content": [
            {"type": "tool_result", "content": "x" * (TOOL_RESULT_MAX_CHARS + 50)},
        ]},
    }
    out = extract_event(ev)
    assert "[truncated" in out["text"]


def test_extract_meta_dropped():
    ev = {"type": "meta", "timestamp": "2026-05-25T09:00:00Z"}
    assert extract_event(ev) is None
