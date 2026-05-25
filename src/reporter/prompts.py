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
5. Bullets are short technical fragments: noun phrase + verb, no full sentences, no trailing periods. Drop articles. Examples of the style: "Attack graph map engine architecture, skeleton, data format, and scenario", "UI refinement on korea/english flag translation", "wire LLM report generator". Mirror this density and tone.
6. Yesterday bullets describe what was COMPLETED or substantially WORKED ON. Today bullets describe what is IN PROGRESS or PLANNED NEXT — infer continuations from yesterday's unfinished prompts and open blockers when today's session data is sparse.
7. Be factual. Do not invent work. If a section would be empty, omit that entire `#<ProjectTag>` block (do not write "(none)" or leave placeholders).
8. Keep the greeting line "Good Morning, AI Team report:" exactly as shown. Do not add a date there. Do not add a Summary section. Do not add emojis.

Below is the session data, in chronological order across all projects:
---
{compacted}
"""


def build_prompt(today: str, compacted: str) -> str:
    """Render the full prompt for `claude -p`."""
    return PROMPT_TEMPLATE.format(today=today, compacted=compacted)
