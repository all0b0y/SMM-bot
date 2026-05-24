from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from smm_bot.agents.schemas import CompanyInput


DEFAULT_PLATFORM = "Instagram Reels"
MIN_DESCRIPTION_CHARS = 30
MAX_IDEAS_COUNT = 50
MAX_SCRIPTS_COUNT = 20


class NormalizedUserRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    telegram_user_id: int | None = None
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None


class NormalizedMessageRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    telegram_chat_id: int | None = None
    telegram_message_id: int | None = None


class NormalizedPipelineInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = "pipeline_input.v1"
    source: str = "telegram_bot"
    raw_text: str
    normalized_text: str
    platform: str = DEFAULT_PLATFORM
    content_goal: str | None = None
    quality_mode: str = "balanced"
    ideas_count: int = 15
    scripts_count: int = 5
    user: NormalizedUserRef = Field(default_factory=NormalizedUserRef)
    message: NormalizedMessageRef = Field(default_factory=NormalizedMessageRef)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> str:
        if value is None:
            return DEFAULT_PLATFORM
        text = str(value).strip()
        return text or DEFAULT_PLATFORM

    @field_validator("quality_mode", mode="before")
    @classmethod
    def normalize_quality_mode(cls, value: object) -> str:
        text = str(value or "balanced").strip()
        return text or "balanced"

    @field_validator("ideas_count", "scripts_count", mode="before")
    @classmethod
    def normalize_positive_count(cls, value: object) -> int:
        try:
            count = int(value)
        except (TypeError, ValueError):
            return 1
        return max(1, count)

    def to_company_input(self) -> CompanyInput:
        return CompanyInput(
            company_description=self.normalized_text,
            platform=self.platform,
            ideas_count=self.ideas_count,
            scripts_count=self.scripts_count,
        )


def normalize_pipeline_input(
    *,
    raw_text: str,
    platform: str | None = None,
    content_goal: str | None = None,
    quality_mode: str = "balanced",
    ideas_count: int = 15,
    scripts_count: int = 5,
    source: str = "telegram_bot",
    telegram_user_id: int | None = None,
    telegram_username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
    telegram_chat_id: int | None = None,
    telegram_message_id: int | None = None,
) -> NormalizedPipelineInput:
    normalized_text = _clean_text(raw_text)
    diagnostics: dict[str, Any] = {
        "raw_chars": len(raw_text or ""),
        "normalized_chars": len(normalized_text),
        "is_too_short": len(normalized_text) < MIN_DESCRIPTION_CHARS,
    }

    normalized_ideas_count = _bounded_count(ideas_count, MAX_IDEAS_COUNT)
    normalized_scripts_count = _bounded_count(scripts_count, MAX_SCRIPTS_COUNT)

    if normalized_ideas_count != ideas_count:
        diagnostics["ideas_count_normalized_from"] = ideas_count
    if normalized_scripts_count != scripts_count:
        diagnostics["scripts_count_normalized_from"] = scripts_count

    return NormalizedPipelineInput(
        source=source,
        raw_text=raw_text or "",
        normalized_text=normalized_text,
        platform=platform,
        content_goal=content_goal,
        quality_mode=quality_mode,
        ideas_count=normalized_ideas_count,
        scripts_count=normalized_scripts_count,
        user=NormalizedUserRef(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        ),
        message=NormalizedMessageRef(
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
        ),
        diagnostics=diagnostics,
    )


def _clean_text(value: str) -> str:
    lines = []
    for line in (value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        cleaned = " ".join(line.split())
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines).strip()


def _bounded_count(value: object, upper_bound: int) -> int:
    try:
        count = int(value or 1)
    except (TypeError, ValueError):
        return 1
    return min(max(1, count), upper_bound)
