from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .prompts import SYSTEM_PROMPT
from .registry import AgentSpec


logger = logging.getLogger(__name__)


T = TypeVar("T", bound=BaseModel)


class AgentLLMClient(Protocol):
    def complete(
        self,
        *,
        agent: AgentSpec,
        user_prompt: str,
        output_schema: type[T],
    ) -> T:
        ...


class LLMValidationError(RuntimeError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise LLMValidationError("LLM response must be a JSON object")
    return parsed


def fallback_output(output_schema: type[T], reason: str) -> T:
    instance = output_schema.model_validate({})
    if hasattr(instance, "warnings"):
        current = list(getattr(instance, "warnings"))
        setattr(instance, "warnings", [*current, reason])
    return instance


class OpenRouterLLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: str | None = None,
        app_name: str | None = None,
        raise_on_failure: bool = False,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_KEY")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", base_url)
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL")
        self.app_name = app_name or os.getenv("OPENROUTER_APP_NAME", "SMM Bot")
        self.raise_on_failure = raise_on_failure
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("OPENROUTER_API_KEY is not configured")
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def complete(
        self,
        *,
        agent: AgentSpec,
        user_prompt: str,
        output_schema: type[T],
    ) -> T:
        errors: list[str] = []
        for model in (agent.primary_model, *agent.fallback_models):
            is_fallback = model != agent.primary_model
            if is_fallback:
                logger.warning("[llm] fallback to %s for agent=%s", model, agent.name)
            else:
                logger.debug("[llm] → %s  agent=%s  prompt_chars=%d", model, agent.name, len(user_prompt))
            t0 = time.monotonic()
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    temperature=agent.temperature,
                    max_tokens=agent.max_output_tokens,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": f"{agent.name}_output",
                            "schema": output_schema.model_json_schema(),
                            "strict": True,
                        },
                    },
                    extra_headers=self._headers(),
                )
                content = response.choices[0].message.content or ""
                result = output_schema.model_validate(extract_json_object(content))
                logger.debug("[llm] ← %s  agent=%s  (%.1fs)", model, agent.name, time.monotonic() - t0)
                return result
            except (ValidationError, json.JSONDecodeError, LLMValidationError) as exc:
                logger.warning("[llm] validation error  model=%s  agent=%s: %s", model, agent.name, exc)
                errors.append(f"{model}: validation failed: {exc}")
            except Exception as exc:
                logger.warning("[llm] request error  model=%s  agent=%s: %s", model, agent.name, exc)
                errors.append(f"{model}: request failed: {exc}")
        error_message = "; ".join(errors) or "LLM call failed"
        logger.error("[llm] all models failed for agent=%s: %s", agent.name, error_message)
        if self.raise_on_failure:
            raise RuntimeError(error_message)
        return fallback_output(output_schema, error_message)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        return headers


class TrackingLLMClient:
    def __init__(self, wrapped: AgentLLMClient) -> None:
        self.wrapped = wrapped
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        agent: AgentSpec,
        user_prompt: str,
        output_schema: type[T],
    ) -> T:
        self.calls.append(
            {
                "agent_name": agent.name,
                "model_id": agent.primary_model,
                "temperature": agent.temperature,
                "prompt_chars": len(user_prompt),
            }
        )
        return self.wrapped.complete(
            agent=agent,
            user_prompt=user_prompt,
            output_schema=output_schema,
        )


FakeResponse = BaseModel | dict[str, Any] | Callable[[AgentSpec, str, type[T]], BaseModel | dict[str, Any]]


class FakeLLMClient:
    def __init__(self, responses: dict[str, FakeResponse] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, str]] = []

    def complete(
        self,
        *,
        agent: AgentSpec,
        user_prompt: str,
        output_schema: type[T],
    ) -> T:
        self.calls.append((agent.name, user_prompt))
        response = self.responses.get(agent.name)
        if response is None:
            return fallback_output(output_schema, f"fake response missing for {agent.name}")
        if callable(response):
            response = response(agent, user_prompt, output_schema)
        if isinstance(response, BaseModel):
            return output_schema.model_validate(response.model_dump())
        return output_schema.model_validate(response)
