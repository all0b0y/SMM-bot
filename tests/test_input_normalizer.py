from smm_bot.services.input_normalizer import (
    MAX_IDEAS_COUNT,
    MAX_SCRIPTS_COUNT,
    normalize_pipeline_input,
)


def test_normalize_pipeline_input_produces_canonical_company_input() -> None:
    normalized = normalize_pipeline_input(
        raw_text="  Brand   sells skincare.\n\n Audience: busy women.  ",
        platform="  TikTok  ",
        quality_mode="balanced",
        ideas_count=999,
        scripts_count=999,
        telegram_user_id=123,
        telegram_chat_id=456,
    )

    assert normalized.schema_version == "pipeline_input.v1"
    assert normalized.normalized_text == "Brand sells skincare.\nAudience: busy women."
    assert normalized.platform == "TikTok"
    assert normalized.ideas_count == MAX_IDEAS_COUNT
    assert normalized.scripts_count == MAX_SCRIPTS_COUNT
    assert normalized.user.telegram_user_id == 123
    assert normalized.message.telegram_chat_id == 456

    company_input = normalized.to_company_input()

    assert company_input.company_description == normalized.normalized_text
    assert company_input.platform == "TikTok"


def test_normalize_pipeline_input_marks_short_input() -> None:
    normalized = normalize_pipeline_input(raw_text="too short")

    assert normalized.diagnostics["is_too_short"] is True
