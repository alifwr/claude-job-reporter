from reporter.prompts import build_prompt, build_refinement_prompt


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


def test_build_prompt_has_ai_team_greeting():
    out = build_prompt("2026-05-25", "x")
    assert "Good Morning, AI Team report:" in out


def test_build_prompt_has_yesterday_and_today_sections():
    out = build_prompt("2026-05-25", "x")
    assert "Yesterday :" in out
    assert "Today :" in out


def test_build_prompt_explains_pascalcase_tag_rule():
    out = build_prompt("2026-05-25", "x")
    assert "PascalCase" in out
    assert "#SmartX" in out


def test_build_prompt_mentions_etc_bucket():
    out = build_prompt("2026-05-25", "x")
    assert "# Etc" in out


def test_build_prompt_caps_three_bullets_per_project():
    out = build_prompt("2026-05-28", "")
    text = out.lower()
    assert "3 bullets" in text or "three bullets" in text


def test_build_prompt_demands_outcomes_not_mechanics():
    out = build_prompt("2026-05-28", "")
    text = out.lower()
    assert "outcome" in text
    assert "decision" in text or "decisions" in text
    assert "mechanic" in text or "mechanics" in text


def test_build_refinement_prompt_includes_previous_and_feedback():
    previous = "Good Morning, AI Team report:\n\nYesterday :\n\n#Reporter\n\n- ship v0.2.0"
    feedback = "Use Indonesian for the greeting."

    out = build_refinement_prompt(previous, feedback)

    assert previous.strip() in out
    assert feedback.strip() in out
    assert "template" in out.lower() or "format" in out.lower()
    assert "plain text" in out.lower()
