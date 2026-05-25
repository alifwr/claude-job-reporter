"""Prompt template for the daily report generator."""

PROMPT_TEMPLATE = """You are summarizing my Claude Code activity for a daily report to my professor.
Output ENGLISH PLAIN TEXT (no markdown — the recipient is KakaoTalk and will not render formatting).
Use this template exactly:

📋 Daily Report — {today}

Summary: <2-3 sentences>

🛠 Projects worked on
• <name> — <what + why>

✅ Completed
• ...

⏳ In progress / blockers
• ...

➡ Next steps
• ...

Be concise, factual, and use a professor-appropriate tone. Group by project. Infer the "why" from prompts. If blockers are unclear, omit that section.

Below is the session data:
---
{compacted}
"""


def build_prompt(today: str, compacted: str) -> str:
    """Render the full prompt for `claude -p`."""
    return PROMPT_TEMPLATE.format(today=today, compacted=compacted)
