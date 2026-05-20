from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any


PIPELINE_STEPS = [
    "Brief Agent",
    "Audience Segmentation Agent",
    "Persona Builder Agent",
    "Pain & Trigger Agent",
    "Positioning Agent",
    "Competitor Insight Agent",
    "Content Strategy Agent",
    "Rubricator Agent",
    "Parallel Idea Generators",
    "Deduplication Agent",
    "Idea Critic Agent",
    "Garbage Filter Agent",
    "Idea Improvement Agent",
    "Second Critic Agent",
    "Script Writer Agent",
    "Script Critic Agent",
    "CTA Critic Agent",
    "Platform Adaptation Agent",
    "Final Content Pack Agent",
]

QUALITY_GATE_STEPS = [
    "Deduplication Agent",
    "Idea Critic Agent",
    "Garbage Filter Agent",
    "Idea Improvement Agent",
    "Second Critic Agent",
]

DEFAULT_INPUT = (
    "Бренд натуральной косметики для занятых женщин 28-40 лет. "
    "Нужны идеи коротких видео для Reels с акцентом на простой уход."
)


@dataclass(frozen=True)
class FakeLLM:
    model: str = "fake/local-deterministic"

    def complete_json(self, agent_name: str, state: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "Brief Agent": self._brief,
            "Audience Segmentation Agent": self._segments,
            "Persona Builder Agent": self._personas,
            "Pain & Trigger Agent": self._pains,
            "Positioning Agent": self._positioning,
            "Content Strategy Agent": self._strategy,
            "Rubricator Agent": self._rubricator,
            "Parallel Idea Generators": self._ideas,
            "Deduplication Agent": self._dedupe,
            "Idea Critic Agent": self._idea_critic,
            "Garbage Filter Agent": self._garbage_filter,
            "Idea Improvement Agent": self._improve_ideas,
            "Second Critic Agent": self._second_critic,
            "Script Writer Agent": self._scripts,
            "Script Critic Agent": self._script_critic,
            "CTA Critic Agent": self._cta_critic,
            "Platform Adaptation Agent": self._platform_adaptation,
            "Final Content Pack Agent": self._final_pack,
        }
        handler = handlers.get(agent_name)
        if handler is None:
            return {"status": "skipped", "reason": "not needed in fake smoke"}
        return handler(state)

    def _brief(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "project_type": "brand",
            "niche": "natural skincare",
            "brand_name": "Demo Beauty",
            "platforms": ["instagram_reels"],
            "goals": ["awareness", "trust", "sales"],
            "tone_of_voice": "clear, helpful, expert",
        }

    def _segments(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "segments": [
                {
                    "name": "busy_professionals",
                    "description": "Women 28-40 who want simple skincare routines",
                }
            ]
        }

    def _personas(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "personas": [
                {
                    "name": "Anna",
                    "age": 34,
                    "segment": "busy_professionals",
                    "pain": "Too many products make skincare feel complicated",
                }
            ]
        }

    def _pains(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "pains": ["Routine takes too long", "Unclear product order"],
            "triggers": ["simple system", "visible routine", "time saving"],
        }

    def _positioning(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "positioning": "Natural skincare as a simple daily system",
            "promise_boundaries": ["no medical claims", "no guaranteed results"],
        }

    def _strategy(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "content_pillars": ["routine clarity", "ingredient education", "before buying"],
            "funnel": ["reach", "trust", "conversion"],
        }

    def _rubricator(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "rubrics": [
                "3-step routine",
                "ingredient myth",
                "common skincare mistake",
            ]
        }

    def _ideas(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "ideas": [
                {
                    "title": "Why your skincare routine feels endless",
                    "pain": "Routine takes too long",
                    "persona": "Anna",
                    "product_fit": "simple daily system",
                },
                {
                    "title": "Buy our cream today",
                    "pain": "",
                    "persona": "",
                    "product_fit": "generic sale",
                },
            ]
        }

    def _dedupe(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"ideas": state["ideas"], "removed_duplicates": []}

    def _idea_critic(self, state: dict[str, Any]) -> dict[str, Any]:
        reviews = []
        for idea in state["ideas"]:
            reviews.append(
                {
                    "title": idea["title"],
                    "decision": "approve" if idea["pain"] else "reject",
                    "score": 8 if idea["pain"] else 2,
                    "main_issue": "" if idea["pain"] else "No concrete pain or persona",
                }
            )
        return {"idea_reviews": reviews}

    def _garbage_filter(self, state: dict[str, Any]) -> dict[str, Any]:
        approved_titles = {
            review["title"]
            for review in state["idea_reviews"]
            if review["decision"] == "approve"
        }
        return {
            "approved_ideas": [
                idea for idea in state["ideas"] if idea["title"] in approved_titles
            ],
            "rejected_ideas": [
                review for review in state["idea_reviews"] if review["decision"] != "approve"
            ],
        }

    def _improve_ideas(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"approved_ideas": state["approved_ideas"], "improved_count": 0}

    def _second_critic(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "approved_ideas": state["approved_ideas"],
            "second_review_status": "passed",
        }

    def _scripts(self, state: dict[str, Any]) -> dict[str, Any]:
        scripts = []
        for idea in state["approved_ideas"]:
            scripts.append(
                {
                    "title": idea["title"],
                    "hook": "If your skincare takes 40 minutes, the problem may be the system.",
                    "core_message": "Show a clear 3-step routine built around one daily habit.",
                    "cta": "Save this routine before your next skincare reset.",
                    "duration": "25-35 sec",
                }
            )
        return {"scripts": scripts}

    def _script_critic(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "script_reviews": [
                {"title": script["title"], "decision": "approve", "score": 8}
                for script in state["scripts"]
            ]
        }

    def _cta_critic(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"cta_review_status": "passed"}

    def _platform_adaptation(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "adapted_scripts": [
                {
                    **script,
                    "platform": "instagram_reels",
                    "caption": "A simple skincare system beats a crowded shelf.",
                }
                for script in state["scripts"]
            ]
        }

    def _final_pack(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "brand_summary": state["brief"],
            "audience_summary": state["segments"],
            "content_strategy_summary": state["strategy"],
            "approved_content": state["adapted_scripts"],
            "rejected_content": state["rejected_ideas"],
            "publishing_recommendations": ["Start with routine clarity videos"],
            "risk_notes": ["Avoid medical and guaranteed-result claims"],
            "next_steps_for_human": ["Validate examples against actual product facts"],
        }


def run_fake_pipeline(raw_input: str = DEFAULT_INPUT) -> dict[str, Any]:
    llm = FakeLLM()
    state: dict[str, Any] = {"raw_input": raw_input, "executed_steps": []}

    for step in PIPELINE_STEPS:
        result = llm.complete_json(step, state)
        state["executed_steps"].append(step)
        if step == "Brief Agent":
            state["brief"] = result
        elif step == "Audience Segmentation Agent":
            state["segments"] = result
        elif step == "Persona Builder Agent":
            state["personas"] = result
        elif step == "Pain & Trigger Agent":
            state["pains_and_triggers"] = result
        elif step == "Positioning Agent":
            state["positioning"] = result
        elif step == "Content Strategy Agent":
            state["strategy"] = result
        elif step == "Rubricator Agent":
            state["rubricator"] = result
        elif step == "Parallel Idea Generators":
            state["ideas"] = result["ideas"]
        elif step == "Deduplication Agent":
            state["ideas"] = result["ideas"]
            state["removed_duplicates"] = result["removed_duplicates"]
        elif step == "Idea Critic Agent":
            state["idea_reviews"] = result["idea_reviews"]
        elif step == "Garbage Filter Agent":
            state["approved_ideas"] = result["approved_ideas"]
            state["rejected_ideas"] = result["rejected_ideas"]
        elif step == "Idea Improvement Agent":
            state["approved_ideas"] = result["approved_ideas"]
        elif step == "Second Critic Agent":
            state["approved_ideas"] = result["approved_ideas"]
            state["second_review_status"] = result["second_review_status"]
        elif step == "Script Writer Agent":
            state["scripts"] = result["scripts"]
        elif step == "Script Critic Agent":
            state["script_reviews"] = result["script_reviews"]
        elif step == "CTA Critic Agent":
            state["cta_review_status"] = result["cta_review_status"]
        elif step == "Platform Adaptation Agent":
            state["adapted_scripts"] = result["adapted_scripts"]
        elif step == "Final Content Pack Agent":
            state["final_content_pack"] = result

    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic MVP pipeline smoke.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Raw project description.")
    args = parser.parse_args()

    state = run_fake_pipeline(args.input)
    print(json.dumps(state["final_content_pack"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
