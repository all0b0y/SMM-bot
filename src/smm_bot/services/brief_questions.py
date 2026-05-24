from __future__ import annotations

from smm_bot.agents.schemas import BriefOutput


def format_brief_questions(brief: BriefOutput, max_questions: int = 10) -> str:
    questions: list[str] = []
    seen: set[str] = set()

    def add_question(text: str) -> None:
        cleaned = text.strip().strip("?.! ")
        if not cleaned:
            return
        key = cleaned.casefold()
        if key in seen or len(questions) >= max_questions:
            return
        seen.add(key)
        questions.append(f"{len(questions) + 1}. {cleaned}?")

    for item in brief.missing_data:
        add_question(item)

    for assumption in brief.assumptions:
        if assumption.confidence != "low":
            continue
        assumption_text = assumption.assumption.strip()
        if assumption_text:
            add_question(f"Уточните: {assumption_text}")

    return "\n".join(questions)
