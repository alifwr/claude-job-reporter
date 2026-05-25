from reporter.prompts import build_prompt


def test_build_prompt_includes_compacted():
    out = build_prompt("2026-05-25", "SOME_SESSION_DATA")
    assert "SOME_SESSION_DATA" in out


def test_build_prompt_includes_date():
    out = build_prompt("2026-05-25", "x")
    assert "2026-05-25" in out


def test_build_prompt_mentions_kakaotalk_constraint():
    out = build_prompt("2026-05-25", "x")
    assert "PLAIN TEXT" in out
    assert "no markdown" in out.lower()
