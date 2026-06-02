"""Prompt template for the daily report generator."""

PROMPT_TEMPLATE = """You are summarizing my Claude Code activity for my daily team report to my AI Team. Output ENGLISH PLAIN TEXT (no markdown — the recipient is KakaoTalk and will not render formatting). Use this template exactly, including the literal greeting line, spacing, and punctuation:

Good Morning, AI Team report:

Yesterday :

#<ProjectTag>

- <bullet>
- <bullet>

# Etc

- <bullet>

Today :

#<ProjectTag>

- <bullet>
- <bullet>

# Etc

- <bullet>

Rules:

1. Today is {today}. "Yesterday" means activity before today's local midnight; "Today" means activity from today's midnight up to now, PLUS the obvious next steps that continue yesterday's open threads.
2. Group bullets by project. The project tag is a short PascalCase derived from the last directory segment of the project path. Examples: "/home/me/smartx" -> "#SmartX", "/home/me/e-pump-v2-be" -> "#EPumpV2Be", "/home/me/reporter" -> "#Reporter". If the project path is not clear, use the directory name verbatim.
3. Use one project tag heading per project worked on in each section. Skip projects that have no activity in a section.
4. Put activity not tied to a single project (browsing, reading docs, one-off scripts, learning) under "# Etc" (literal — with the space).
5. Bullets are written in first-person reporting voice with the subject "I" DROPPED — the verb starts the bullet. Yesterday bullets use past-tense verbs ("shipped", "fixed", "designed", "investigated"); Today bullets use present-continuous or future verbs ("working on", "will refactor", "plan to investigate", "continuing"). No full sentences, no trailing periods. Drop articles. Examples of the style — Yesterday: "Shipped reporter v0.5.0 with --start-datetime flag", "Refactored prompt rules for outcome-only bullets", "Decided to drop --since for absolute datetime". Today: "Refining bullet voice to first-person implied", "Plan to publish v0.6.0", "Investigating Korean greeting variant". Mirror this density and tone. No bullet count limit — include every distinct outcome from the session data, but each bullet must stay outcome-level (not implementation mechanics).
6. Bullets describe outcomes, decisions, and blockers — not implementation mechanics. Drop "wrote function X", "refactored Y", "added a helper". Say what shipped, what was decided, what's stuck, what's learned. The audience is a non-technical supervisor who cares about progress, not code-level changes.
7. Yesterday bullets describe what I COMPLETED or substantially WORKED ON. Today bullets describe what I am IN PROGRESS on or PLAN NEXT — infer continuations from yesterday's unfinished prompts and open blockers when today's session data is sparse.
8. Be factual. Do not invent work. If a section would be empty, omit that entire `#<ProjectTag>` block (do not write "(none)" or leave placeholders).
9. Keep the greeting line "Good Morning, AI Team report:" exactly as shown. Do not add a date there. Do not add a Summary section. Do not add emojis.

Below is the session data, in chronological order across all projects:
---
{compacted}
"""


def build_prompt(today: str, compacted: str) -> str:
    """Render the full prompt for `claude -p`."""
    return PROMPT_TEMPLATE.format(today=today, compacted=compacted)


REFINEMENT_TEMPLATE = """You previously produced this daily report for my supervisor:

---
{previous}
---

I have a refinement request:

{feedback}

Produce a revised version of the report that addresses this feedback. Keep the same template, greeting, formatting rules, and outcome-focused style as the original. Output ENGLISH PLAIN TEXT (no markdown — the recipient is KakaoTalk).
"""


def build_refinement_prompt(previous_report: str, feedback: str) -> str:
    """Render the refinement-turn prompt for `claude -p`."""
    return REFINEMENT_TEMPLATE.format(
        previous=previous_report.strip(),
        feedback=feedback.strip(),
    )
