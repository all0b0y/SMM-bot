from __future__ import annotations

import concurrent.futures
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from .llm import AgentLLMClient
from .prompts import render_prompt
from .registry import MVP_AGENT_REGISTRY, MVP_GRAPH, AgentName, AgentSpec
from .schemas import (
    ApprovedContent,
    ApprovedContentScript,
    CompanyInput,
    ContentIdea,
    FinalContentPackOutput,
    PipelineResult,
    VideoScript,
)


logger = logging.getLogger(__name__)

IDEA_GENERATORS = (
    "pain_based_generator",
    "trigger_based_generator",
    "funnel_based_generator",
)


class PipelineExecutor:
    def __init__(
        self,
        llm_client: AgentLLMClient,
        *,
        registry: dict[AgentName, AgentSpec] | None = None,
        graph: tuple[AgentName, ...] = MVP_GRAPH,
        on_agent_start: Callable[[str], None] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.registry = registry or MVP_AGENT_REGISTRY
        self.graph = graph
        self.on_agent_start = on_agent_start

    def run(self, pipeline_input: CompanyInput | dict[str, Any]) -> PipelineResult:
        input_model = (
            pipeline_input
            if isinstance(pipeline_input, CompanyInput)
            else CompanyInput.model_validate(pipeline_input)
        )
        context: dict[str, Any] = {"input": input_model}

        generators_ran = False
        for agent_name in self.graph:
            if agent_name in IDEA_GENERATORS:
                if not generators_ran:
                    self._run_idea_generators_parallel(context)
                    generators_ran = True
                continue
            self._run_agent(agent_name, context)
            # After script_critic: apply improved_version and filter by score
            if agent_name == "script_critic":
                self._apply_script_improvements(context)

        final_output = context.get("final_content_pack")
        if not isinstance(final_output, FinalContentPackOutput):
            final_output = FinalContentPackOutput()

        if not final_output.final_content_pack.approved_content:
            final_output = self._rescue_final_pack(context, final_output)

        return PipelineResult(outputs=_serializable_outputs(context), final_content_pack=final_output)

    def _run_idea_generators_parallel(self, context: dict[str, Any]) -> None:
        generators = [n for n in self.graph if n in IDEA_GENERATORS]
        logger.info("[pipeline] running %d idea generators in parallel", len(generators))

        def _call(name: AgentName) -> tuple[AgentName, BaseModel]:
            agent = self.registry[name]
            if self.on_agent_start is not None:
                try:
                    self.on_agent_start(name)
                except Exception:
                    pass
            logger.info("[agent] ▶ %s  model=%s", name, agent.primary_model)
            t0 = time.monotonic()
            prompt_values = self._prompt_values(name, context)
            user_prompt = render_prompt(name, prompt_values)
            output = self.llm_client.complete(agent=agent, user_prompt=user_prompt, output_schema=agent.output_schema)
            logger.info("[agent] ✓ %s  (%.1fs)", name, time.monotonic() - t0)
            return name, output

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(generators)) as pool:
            futures = {pool.submit(_call, n): n for n in generators}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    _, output = future.result()
                    for idea in output.ideas:
                        if not idea.source_agent:
                            idea.source_agent = name
                    all_ideas = context.setdefault("all_ideas_json", {"ideas": []})
                    all_ideas["ideas"].extend(idea.model_dump() for idea in output.ideas)
                    context[name] = output
                    self._store_aliases(name, output, context)
                except Exception as exc:
                    logger.error("[pipeline] generator %s failed: %s", name, exc)

    def _run_idea_generator(self, agent_name: AgentName, context: dict[str, Any]) -> None:
        output = self._run_agent(agent_name, context)
        for idea in output.ideas:
            if not idea.source_agent:
                idea.source_agent = agent_name
        all_ideas = context.setdefault("all_ideas_json", {"ideas": []})
        all_ideas["ideas"].extend(idea.model_dump() for idea in output.ideas)

    def _run_agent(self, agent_name: AgentName, context: dict[str, Any]) -> BaseModel:
        if self.on_agent_start is not None:
            try:
                self.on_agent_start(agent_name)
            except Exception:
                pass  # never let progress updates crash the pipeline

        agent = self.registry[agent_name]
        logger.info("[agent] ▶ %s  model=%s", agent_name, agent.primary_model)
        t0 = time.monotonic()

        prompt_values = self._prompt_values(agent_name, context)
        user_prompt = render_prompt(agent_name, prompt_values)
        output = self.llm_client.complete(
            agent=agent,
            user_prompt=user_prompt,
            output_schema=agent.output_schema,
        )

        elapsed = time.monotonic() - t0
        logger.info("[agent] ✓ %s  (%.1fs)", agent_name, elapsed)

        context[agent_name] = output
        self._store_aliases(agent_name, output, context)
        return output

    def _prompt_values(self, agent_name: AgentName, context: dict[str, Any]) -> dict[str, Any]:
        input_model: CompanyInput = context["input"]
        values: dict[str, Any] = {
            "company_description": input_model.company_description,
            "platform": input_model.platform,
            "ideas_count": input_model.ideas_count,
            "scripts_count": input_model.scripts_count,
            "brief_json": context.get("brief_json", {}),
            "audience_segments_json": context.get("audience_segments_json", {}),
            "personas_json": context.get("personas_json", {}),
            "pain_trigger_map_json": context.get("pain_trigger_map_json", {}),
            "positioning_json": context.get("positioning_json", {}),
            "content_strategy_json": context.get("content_strategy_json", {}),
            "rubricator_json": context.get("rubricator_json", {}),
            "all_ideas_json": (
                self._condensed_ideas_for_dedup(context)
                if agent_name == "deduplication"
                else context.get("all_ideas_json", {"ideas": []})
            ),
            "unique_ideas_json": self._safe_unique_ideas(context),
            "evaluated_ideas_json": context.get("evaluated_ideas_json", {}),
            "final_approved_ideas_json": (
                self._top_approved_ideas(context)
                if agent_name == "script_writer"
                else self._approved_ideas(context)
            ),
            "rejected_ideas_json": self._rejected_ideas(context),
            "scripts_json": (
                context.get("polished_scripts_json")
                or context.get("scripts_json", {})
            ),
            "script_reviews_json": context.get("script_reviews_json", {}),
            "tone_of_voice": self._tone_of_voice(context),
            "ideas_to_improve_json": self._ideas_to_improve(context),
            "improved_ideas_json": context.get("improved_ideas_json", {}),
        }
        return values

    def _store_aliases(self, agent_name: AgentName, output: BaseModel, context: dict[str, Any]) -> None:
        aliases = {
            "brief": "brief_json",
            "audience_segmentation": "audience_segments_json",
            "persona_builder": "personas_json",
            "pain_trigger": "pain_trigger_map_json",
            "positioning": "positioning_json",
            "content_strategy": "content_strategy_json",
            "rubricator": "rubricator_json",
            "deduplication": "unique_ideas_json",
            "idea_critic": "evaluated_ideas_json",
            "idea_improver": "improved_ideas_json",
            "scripts": "scripts_json",
            "script_writer": "scripts_json",
            "script_critic": "script_reviews_json",
        }
        alias = aliases.get(agent_name)
        if alias:
            context[alias] = output

    def _approved_ideas(self, context: dict[str, Any]) -> dict[str, Any]:
        by_id = self._ideas_by_id(context)
        approved: list[dict[str, Any]] = []

        # Primary: garbage_filter passed ideas (original strong ideas)
        garbage = context.get("garbage_filter")
        if garbage is not None and garbage.passed:
            passed_ids = {item.idea_id for item in garbage.passed}
            approved.extend(
                by_id.get(item.idea_id, {"idea_id": item.idea_id, "idea_title": item.idea_title})
                | {"reason_passed": item.reason_passed}
                for item in garbage.passed
                if item.idea_id in passed_ids
            )

        # Secondary: improved ideas that passed the improver's own quality check
        improver = context.get("idea_improver")
        if improver is not None:
            already_approved_ids = {i["idea_id"] for i in approved}
            for item in improver.improved_ideas:
                if item.quality_check and item.idea_id not in already_approved_ids:
                    approved.append({
                        "idea_id": item.idea_id,
                        "idea_title": item.idea_title,
                        "target_persona": item.target_persona,
                        "pain": item.pain,
                        "content_angle": item.content_angle,
                        "video_format": item.video_format,
                        "funnel_stage": item.funnel_stage,
                        "rough_hook": item.rough_hook,
                        "reason_passed": f"Improved: {item.improvement_made}",
                    })

        if approved:
            logger.info("[pipeline] approved ideas: %d (primary=%d, improved=%d)",
                        len(approved),
                        len(garbage.passed) if garbage else 0,
                        len([i for i in (improver.improved_ideas if improver else []) if i.quality_check]))
            return {"ideas": approved}

        # Last resort: critic's "revise" decisions — at minimum not outright rejected
        critic = context.get("idea_critic")
        if critic is not None:
            revise_ideas = sorted(
                [i for i in critic.evaluated_ideas if i.decision == "revise"],
                key=lambda i: i.weighted_score,
                reverse=True,
            )
            if revise_ideas:
                logger.warning(
                    "[pipeline] all filters empty — last resort: %d 'revise' ideas from critic",
                    len(revise_ideas),
                )
                return {
                    "ideas": [
                        {
                            "idea_id": i.idea_id,
                            "idea_title": i.idea_title,
                            "reason_passed": f"Last resort (revise, score={i.weighted_score:.1f}): {i.recommendation}",
                        }
                        for i in revise_ideas
                    ]
                }

        return {"ideas": []}

    def _rejected_ideas(self, context: dict[str, Any]) -> dict[str, Any]:
        rejected: list[dict[str, Any]] = []
        critic = context.get("idea_critic")
        if critic is not None:
            rejected.extend(
                {
                    "idea_id": idea.idea_id,
                    "idea_title": idea.idea_title,
                    "reason": idea.critic_comment or idea.main_issue,
                }
                for idea in critic.evaluated_ideas
                if idea.decision == "reject"
            )
        garbage = context.get("garbage_filter")
        if garbage is not None:
            rejected.extend(
                {
                    "idea_id": idea.idea_id,
                    "idea_title": idea.idea_title,
                    "reason": idea.short_explanation,
                }
                for idea in garbage.garbage_rejected
            )
        return {"ideas": rejected}

    def _apply_script_improvements(self, context: dict[str, Any]) -> None:
        """Apply script_critic's improved_version to revise scripts and filter by score ≥ 75."""
        critic = context.get("script_critic")
        scripts_output = context.get("script_writer")
        if critic is None or scripts_output is None:
            return

        MIN_SCORE = 75.0
        reviews_by_id = {r.script_id: r for r in critic.script_reviews}
        polished: list[VideoScript] = []

        for script in scripts_output.scripts:
            review = reviews_by_id.get(script.script_id)
            if review is None:
                polished.append(script)
                continue

            score = review.total_score
            decision = review.decision

            if decision == "reject":
                logger.info("[pipeline] script %s rejected by critic (score=%.0f)", script.script_id, score)
                continue

            if decision == "revise" and review.improved_version:
                iv = review.improved_version
                updated_fields: dict[str, Any] = {}
                if iv.hook:
                    updated_fields["hook"] = iv.hook
                if iv.scene_by_scene:
                    updated_fields["scene_by_scene"] = iv.scene_by_scene
                if iv.cta:
                    updated_fields["cta"] = iv.cta
                script = script.model_copy(update=updated_fields)
                logger.info("[pipeline] script %s improved by critic (score=%.0f)", script.script_id, score)

            polished.append(script)

        # Sort by score descending, keep top with score ≥ 75 but always at least 3
        scored = [(s, reviews_by_id.get(s.script_id, None)) for s in polished]
        scored.sort(key=lambda t: t[1].total_score if t[1] else 0, reverse=True)

        above_threshold = [s for s, r in scored if r and r.total_score >= MIN_SCORE]
        final_scripts = above_threshold if len(above_threshold) >= 3 else [s for s, _ in scored[:3]]

        logger.info(
            "[pipeline] scripts after critic: total=%d  ≥75%%=%d  final=%d",
            len(scripts_output.scripts), len(above_threshold), len(final_scripts),
        )

        scripts_output.scripts = final_scripts
        context["polished_scripts_json"] = {"scripts": [s.model_dump() for s in final_scripts]}

    def _rescue_final_pack(
        self, context: dict[str, Any], final_output: FinalContentPackOutput
    ) -> FinalContentPackOutput:
        """Build approved_content from script_writer output when final_content_pack returned empty."""
        script_writer = context.get("script_writer")
        if script_writer is None or not script_writer.scripts:
            # No scripts at all — try to surface raw approved ideas as stubs
            approved = self._approved_ideas(context)
            ideas = approved.get("ideas", [])[:3]
            if not ideas:
                return final_output
            logger.warning("[pipeline] rescue: no scripts, returning %d idea stubs", len(ideas))
            stub_items = [
                ApprovedContent(
                    idea_id=i.get("idea_id", ""),
                    title=i.get("idea_title", "Идея"),
                    target_persona=i.get("target_persona", ""),
                    pain=i.get("pain", ""),
                    why_approved=i.get("reason_passed", "Прошла фильтрацию"),
                    quality_score=2.5,
                )
                for i in ideas
            ]
            final_output.final_content_pack.approved_content = stub_items
            return final_output

        platform = context["input"].platform
        approved_ideas = self._approved_ideas(context)
        ideas_by_id = {i.get("idea_id", ""): i for i in approved_ideas.get("ideas", [])}

        items: list[ApprovedContent] = []
        for script in script_writer.scripts:
            idea = ideas_by_id.get(script.idea_id, {})
            items.append(
                ApprovedContent(
                    content_id=script.script_id or script.idea_id,
                    idea_id=script.idea_id,
                    title=script.title or idea.get("idea_title", "Сценарий"),
                    target_persona=script.target_persona or idea.get("target_persona", ""),
                    pain=idea.get("pain", ""),
                    trigger=idea.get("main_trigger", ""),
                    funnel_stage=script.funnel_stage,
                    rubric=idea.get("rubric_id", ""),
                    why_approved="Rescue: script passed script_writer stage",
                    quality_score=3.0,
                    script=ApprovedContentScript(
                        platform=platform,
                        duration=script.duration,
                        hook=script.hook,
                        scene_by_scene=script.scene_by_scene,
                        cta=script.cta,
                        caption=script.caption,
                        shooting_notes=script.shooting_notes,
                    ),
                )
            )

        logger.warning(
            "[pipeline] rescue: final_content_pack was empty, built %d items from script_writer", len(items)
        )
        final_output.final_content_pack.approved_content = items
        return final_output

    def _top_approved_ideas(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return top-N approved ideas sorted by critic score for script_writer."""
        approved = self._approved_ideas(context)
        ideas = approved.get("ideas", [])
        if not ideas:
            return approved

        n = context["input"].scripts_count
        critic = context.get("idea_critic")
        if critic is not None:
            scores = {i.idea_id: i.weighted_score for i in critic.evaluated_ideas}
            ideas = sorted(ideas, key=lambda i: scores.get(i.get("idea_id", ""), 0), reverse=True)

        top = ideas[:n]
        logger.info("[pipeline] script_writer receives top-%d of %d approved ideas", len(top), len(ideas))
        return {"ideas": top}

    def _condensed_ideas_for_dedup(self, context: dict[str, Any]) -> dict[str, Any]:
        """Send only the fields needed for duplicate detection — avoids overloading small models."""
        raw_ideas = context.get("all_ideas_json", {}).get("ideas", [])
        condensed = []
        for raw in raw_ideas:
            idea = ContentIdea.model_validate(raw)
            condensed.append({
                "idea_id": idea.idea_id,
                "idea_title": idea.idea_title,
                "target_persona": idea.target_persona,
                "content_angle": idea.content_angle,
                "pain_or_desire": idea.pain_or_desire or idea.pain,
                "rough_hook": idea.rough_hook,
            })
        logger.debug("[pipeline] dedup input condensed: %d ideas → %d fields each", len(condensed), 6)
        return {"ideas": condensed}

    def _safe_unique_ideas(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return unique_ideas for critic. Falls back to all_ideas if dedup returned empty."""
        dedup = context.get("deduplication")
        if dedup is not None and dedup.unique_ideas:
            return context.get("unique_ideas_json", {})
        all_ideas = context.get("all_ideas_json", {"ideas": []})
        if all_ideas.get("ideas"):
            logger.warning(
                "[pipeline] dedup returned 0 unique_ideas despite %d generated — "
                "falling back to all_ideas for idea_critic",
                len(all_ideas["ideas"]),
            )
        return {"unique_ideas": all_ideas.get("ideas", [])}

    def _ideas_to_improve(self, context: dict[str, Any]) -> dict[str, Any]:
        """Collect borderline + revise ideas with their specific issues for the improver."""
        by_id = self._ideas_by_id(context)
        candidates: list[dict[str, Any]] = []

        # Borderline ideas from garbage_filter (nearly passed but had fixable issues)
        garbage = context.get("garbage_filter")
        if garbage is not None:
            for item in garbage.borderline:
                base = by_id.get(item.idea_id, {"idea_id": item.idea_id, "idea_title": item.idea_title})
                candidates.append({**base, "original_issue": item.problem, "can_be_improved": item.can_be_improved})

        # Revise decisions from idea_critic (not outright rejected, just needs work)
        critic = context.get("idea_critic")
        already_ids = {c["idea_id"] for c in candidates}
        if critic is not None:
            for item in critic.evaluated_ideas:
                if item.decision == "revise" and item.idea_id not in already_ids:
                    base = by_id.get(item.idea_id, {"idea_id": item.idea_id, "idea_title": item.idea_title})
                    candidates.append({
                        **base,
                        "original_issue": item.main_issue or item.critic_comment,
                        "recommendation": item.recommendation,
                        "weighted_score": item.weighted_score,
                    })

        return {"ideas_to_improve": candidates}

    def _ideas_by_id(self, context: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw_ideas = context.get("all_ideas_json", {}).get("ideas", [])
        ideas: dict[str, dict[str, Any]] = {}
        for raw in raw_ideas:
            idea = ContentIdea.model_validate(raw)
            ideas[idea.idea_id] = idea.model_dump()
        return ideas

    def _tone_of_voice(self, context: dict[str, Any]) -> str:
        brief_output = context.get("brief")
        if brief_output is None:
            return ""
        return brief_output.brief.tone_of_voice_raw


def _serializable_outputs(context: dict[str, Any]) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for key, value in context.items():
        if key == "input":
            continue
        if isinstance(value, BaseModel):
            outputs[key] = value.model_dump()
        else:
            outputs[key] = value
    return outputs
