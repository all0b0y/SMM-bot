from smm_bot.agents.schemas import Assumption, BriefOutput
from smm_bot.services.brief_questions import format_brief_questions


def test_format_brief_questions_skips_empty_items_and_duplicates() -> None:
    brief = BriefOutput(
        missing_data=[
            "Целевая аудитория?",
            "",
            "   ",
            "Целевая аудитория",
            "Цель продвижения",
        ],
        assumptions=[
            Assumption(assumption="", confidence="low"),
            Assumption(assumption="   ", confidence="low"),
            Assumption(assumption="география проекта", confidence="low"),
            Assumption(assumption="тон коммуникации", confidence="medium"),
        ],
    )

    assert format_brief_questions(brief, max_questions=10) == (
        "1. Целевая аудитория?\n"
        "2. Цель продвижения?\n"
        "3. Уточните: география проекта?"
    )


def test_format_brief_questions_respects_limit() -> None:
    brief = BriefOutput(missing_data=[f"Вопрос {index}" for index in range(1, 12)])

    questions = format_brief_questions(brief, max_questions=10).splitlines()

    assert len(questions) == 10
    assert questions[-1] == "10. Вопрос 10?"
