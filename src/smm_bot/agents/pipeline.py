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

CONTEXT_PARALLEL_AGENTS = (
    "context_auditor",
    "positioning",
)

MIN_QUALITY_IDEAS = 5
MIN_IDEA_WEIGHTED_SCORE = 4.0
MAX_IDEA_QUALITY_ITERATIONS = 3


class PipelineExecutor:
    def __init__(
        self,
        llm_client: AgentLLMClient,
        *,
        registry: dict[AgentName, AgentSpec] | None = None,
        graph: tuple[AgentName, ...] = MVP_GRAPH,
        on_agent_start: Callable[[str], None] | None = None,
        on_agent_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.registry = registry or MVP_AGENT_REGISTRY
        self.graph = graph
        self.on_agent_start = on_agent_start
        self.on_agent_event = on_agent_event

    def run(self, pipeline_input: CompanyInput | dict[str, Any]) -> PipelineResult:
        input_model = (
            pipeline_input
            if isinstance(pipeline_input, CompanyInput)
            else CompanyInput.model_validate(pipeline_input)
        )
        context: dict[str, Any] = {"input": input_model}
        self._emit_pipeline_event("pipeline_input", input=input_model)

        generators_ran = False
        context_parallel_ran = False
        for agent_name in self.graph:
            if agent_name in CONTEXT_PARALLEL_AGENTS:
                if not context_parallel_ran:
                    self._run_agents_parallel(CONTEXT_PARALLEL_AGENTS, context)
                    context_parallel_ran = True
                continue
            if agent_name in IDEA_GENERATORS:
                if not generators_ran:
                    self._run_idea_generators_parallel(context)
                    generators_ran = True
                continue
            self._run_agent(agent_name, context)
            if agent_name == "idea_improver":
                self._ensure_minimum_quality_ideas(context)
            # After script_critic: apply improved_version and filter by score
            if agent_name == "script_critic":
                self._apply_script_improvements(context)
            if agent_name == "blind_script_checker":
                self._apply_blind_script_check(context)

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
            self._emit_agent_event(
                "agent_request",
                name,
                model_id=agent.primary_model,
                temperature=agent.temperature,
                prompt_values=prompt_values,
                user_prompt=user_prompt,
            )
            try:
                output = self.llm_client.complete(
                    agent=agent,
                    user_prompt=user_prompt,
                    output_schema=agent.output_schema,
                )
            except Exception as exc:
                self._emit_agent_event(
                    "agent_error",
                    name,
                    model_id=agent.primary_model,
                    elapsed_seconds=time.monotonic() - t0,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                raise
            elapsed = time.monotonic() - t0
            logger.info("[agent] ✓ %s  (%.1fs)", name, elapsed)
            self._emit_agent_event(
                "agent_response",
                name,
                model_id=agent.primary_model,
                elapsed_seconds=elapsed,
                output=output,
            )
            return name, output

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(generators)) as pool:
            futures = {pool.submit(_call, n): n for n in generators}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    _, output = future.result()
                    self._ensure_idea_contract(output.ideas, name)
                    all_ideas = context.setdefault("all_ideas_json", {"ideas": []})
                    all_ideas["ideas"].extend(idea.model_dump() for idea in output.ideas)
                    context[name] = output
                    self._store_aliases(name, output, context)
                except Exception as exc:
                    logger.error("[pipeline] generator %s failed: %s", name, exc)

    def _run_agents_parallel(
        self,
        agent_names: tuple[AgentName, ...],
        context: dict[str, Any],
    ) -> None:
        agents = [name for name in self.graph if name in agent_names]
        if not agents:
            return

        logger.info("[pipeline] running %d agents in parallel: %s", len(agents), ", ".join(agents))

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as pool:
            futures = {pool.submit(self._complete_agent, name, context): name for name in agents}
            results: dict[AgentName, BaseModel] = {}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as exc:
                    logger.error("[pipeline] parallel agent %s failed: %s", name, exc)
                    raise

        # Keep downstream context deterministic even when API calls finish in a different order.
        for name in agents:
            context[name] = results[name]
            self._store_aliases(name, results[name], context)

    def _run_idea_generator(self, agent_name: AgentName, context: dict[str, Any]) -> None:
        output = self._run_agent(agent_name, context)
        self._ensure_idea_contract(output.ideas, agent_name)
        all_ideas = context.setdefault("all_ideas_json", {"ideas": []})
        all_ideas["ideas"].extend(idea.model_dump() for idea in output.ideas)

    def _run_agent(self, agent_name: AgentName, context: dict[str, Any]) -> BaseModel:
        output = self._complete_agent(agent_name, context)
        context[agent_name] = output
        self._store_aliases(agent_name, output, context)
        return output

    def _complete_agent(self, agent_name: AgentName, context: dict[str, Any]) -> BaseModel:
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
        self._emit_agent_event(
            "agent_request",
            agent_name,
            model_id=agent.primary_model,
            temperature=agent.temperature,
            prompt_values=prompt_values,
            user_prompt=user_prompt,
        )
        try:
            output = self.llm_client.complete(
                agent=agent,
                user_prompt=user_prompt,
                output_schema=agent.output_schema,
            )
        except Exception as exc:
            self._emit_agent_event(
                "agent_error",
                agent_name,
                model_id=agent.primary_model,
                elapsed_seconds=time.monotonic() - t0,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            raise

        elapsed = time.monotonic() - t0
        logger.info("[agent] ✓ %s  (%.1fs)", agent_name, elapsed)
        self._emit_agent_event(
            "agent_response",
            agent_name,
            model_id=agent.primary_model,
            elapsed_seconds=elapsed,
            output=output,
        )

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
            "context_audit_json": context.get("context_audit_json", {}),
            "reference_video_patterns_json": context.get("reference_video_patterns_json", {}),
            "topic_angles_json": context.get("topic_angles_json", {}),
            "hooks_json": context.get("hooks_json", {}),
            "retention_map_json": context.get("retention_map_json", {}),
            "blind_script_check_json": context.get("blind_script_check_json", {}),
            "all_ideas_json": (
                self._condensed_ideas_for_dedup(context)
                if agent_name == "deduplication"
                else context.get("all_ideas_json", {"ideas": []})
            ),
            "unique_ideas_json": self._safe_unique_ideas(context),
            "evaluated_ideas_json": context.get("evaluated_ideas_json", {}),
            "final_approved_ideas_json": (
                self._top_approved_ideas(context)
                if agent_name in {
                    "reference_video_researcher",
                    "topic_angle_generator",
                    "hook_generator",
                    "script_writer",
                }
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
            "context_auditor": "context_audit_json",
            "positioning": "positioning_json",
            "content_strategy": "content_strategy_json",
            "rubricator": "rubricator_json",
            "deduplication": "unique_ideas_json",
            "idea_critic": "evaluated_ideas_json",
            "idea_improver": "improved_ideas_json",
            "scripts": "scripts_json",
            "script_writer": "scripts_json",
            "script_critic": "script_reviews_json",
            "reference_video_researcher": "reference_video_patterns_json",
            "topic_angle_generator": "topic_angles_json",
            "hook_generator": "hooks_json",
            "retention_optimizer": "retention_map_json",
            "blind_script_checker": "blind_script_check_json",
        }
        alias = aliases.get(agent_name)
        if alias:
            context[alias] = output

    def _ensure_idea_contract(self, ideas: list[ContentIdea], source_agent: AgentName) -> None:
        for index, idea in enumerate(ideas, start=1):
            if not idea.source_agent:
                idea.source_agent = source_agent
            if not idea.idea_id:
                idea.idea_id = f"{source_agent}_{index:03d}"
            if not idea.idea_title:
                idea.idea_title = idea.content_angle or idea.rough_hook or f"Идея {index}"

    def _emit_pipeline_event(self, event_type: str, **payload: Any) -> None:
        if self.on_agent_event is None:
            return
        try:
            self.on_agent_event({"event_type": event_type, **payload})
        except Exception:
            logger.debug("[pipeline] trace event skipped", exc_info=True)

    def _emit_agent_event(self, event_type: str, agent_name: AgentName, **payload: Any) -> None:
        self._emit_pipeline_event(event_type, agent_name=agent_name, **payload)

    def _approved_ideas(self, context: dict[str, Any]) -> dict[str, Any]:
        quality_loop_approved = context.get("quality_loop_approved_ideas_json", {})
        if quality_loop_approved.get("ideas"):
            return quality_loop_approved

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

        fallback_ideas = self._fallback_approved_ideas(context)
        if fallback_ideas:
            logger.warning(
                "[pipeline] all idea gates empty — fallback to %d normalized unique ideas",
                len(fallback_ideas),
            )
            return {"ideas": fallback_ideas}

        return {"ideas": []}

    def _ensure_minimum_quality_ideas(self, context: dict[str, Any]) -> None:
        target = self._quality_loop_target(context)
        if target <= 0:
            return

        approved = self._quality_approved_ideas(context)
        if len(approved) >= target:
            context["quality_loop_approved_ideas_json"] = {"ideas": approved[:target]}
            return

        for iteration in range(1, MAX_IDEA_QUALITY_ITERATIONS + 1):
            candidates = self._quality_loop_candidates(context, target)
            if not candidates:
                break

            logger.warning(
                "[pipeline] idea quality loop %d/%d: approved=%d target=%d candidates=%d",
                iteration,
                MAX_IDEA_QUALITY_ITERATIONS,
                len(approved),
                target,
                len(candidates),
            )
            self._emit_pipeline_event(
                "idea_quality_iteration",
                iteration=iteration,
                approved_count=len(approved),
                target_count=target,
                candidate_count=len(candidates),
                min_score=MIN_IDEA_WEIGHTED_SCORE,
            )

            context["quality_loop_candidates_json"] = {"ideas_to_improve": candidates}
            self._run_agent("idea_improver", context)

            improved = self._improved_ideas_as_content(context)
            if not improved:
                logger.warning("[pipeline] idea quality loop %d: improver returned no usable ideas", iteration)
                continue

            all_ideas = context.setdefault("all_ideas_json", {"ideas": []})
            existing_by_id = {
                item.get("idea_id"): idx
                for idx, item in enumerate(all_ideas.get("ideas", []))
                if item.get("idea_id")
            }
            for idea in improved:
                existing_index = existing_by_id.get(idea["idea_id"])
                if existing_index is None:
                    all_ideas["ideas"].append(idea)
                else:
                    all_ideas["ideas"][existing_index] = {**all_ideas["ideas"][existing_index], **idea}

            context["quality_loop_unique_ideas_json"] = {
                "unique_ideas": [
                    {
                        "idea_id": idea["idea_id"],
                        "idea_title": idea["idea_title"],
                        "source_agent": idea.get("source_agent", "idea_improver"),
                        "reason_kept": "Quality loop improved candidate",
                    }
                    for idea in improved
                ]
            }
            self._run_agent("idea_critic", context)
            self._run_agent("garbage_filter", context)

            approved = self._quality_approved_ideas(context)
            if len(approved) >= target:
                context["quality_loop_approved_ideas_json"] = {"ideas": approved[:target]}
                self._emit_pipeline_event(
                    "idea_quality_target_reached",
                    iteration=iteration,
                    approved_count=len(approved),
                    target_count=target,
                    min_score=MIN_IDEA_WEIGHTED_SCORE,
                )
                return

        fallback = self._fallback_approved_ideas(context)[:target]
        if fallback:
            logger.warning(
                "[pipeline] idea quality loop exhausted — using %d fallback ideas after %d iterations",
                len(fallback),
                MAX_IDEA_QUALITY_ITERATIONS,
            )
            context["quality_loop_approved_ideas_json"] = {"ideas": fallback}

    def _quality_loop_target(self, context: dict[str, Any]) -> int:
        available = len(context.get("all_ideas_json", {}).get("ideas", []))
        scripts_count = context["input"].scripts_count
        return min(MIN_QUALITY_IDEAS, scripts_count, available)

    def _quality_approved_ideas(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        by_id = self._ideas_by_id(context)
        critic = context.get("idea_critic")
        scores = {item.idea_id: item for item in critic.evaluated_ideas} if critic is not None else {}
        approved: list[dict[str, Any]] = []

        garbage = context.get("garbage_filter")
        if garbage is not None:
            for item in garbage.passed:
                review = scores.get(item.idea_id)
                if review is not None and review.weighted_score < MIN_IDEA_WEIGHTED_SCORE:
                    continue
                base = by_id.get(item.idea_id, {"idea_id": item.idea_id, "idea_title": item.idea_title})
                approved.append({**base, "reason_passed": item.reason_passed or "Passed quality gates"})

        for idea in self._improved_ideas_as_content(context):
            if idea["idea_id"] not in {item.get("idea_id") for item in approved}:
                approved.append({**idea, "reason_passed": "Improved to target quality"})

        approved.sort(
            key=lambda item: scores.get(item.get("idea_id", ""), None).weighted_score
            if scores.get(item.get("idea_id", ""), None)
            else 0,
            reverse=True,
        )
        return approved

    def _quality_loop_candidates(self, context: dict[str, Any], target: int) -> list[dict[str, Any]]:
        already_approved = {item.get("idea_id") for item in self._quality_approved_ideas(context)}
        by_id = self._ideas_by_id(context)
        candidates: list[dict[str, Any]] = []

        critic = context.get("idea_critic")
        if critic is not None and critic.evaluated_ideas:
            reviewed = sorted(
                critic.evaluated_ideas,
                key=lambda item: item.weighted_score,
                reverse=True,
            )
            for item in reviewed:
                if item.idea_id in already_approved:
                    continue
                base = by_id.get(item.idea_id, {"idea_id": item.idea_id, "idea_title": item.idea_title})
                candidates.append(
                    {
                        **base,
                        "original_issue": item.main_issue or item.critic_comment or "Needs stronger fit",
                        "recommendation": item.recommendation,
                        "weighted_score": item.weighted_score,
                    }
                )

        if not candidates:
            source = self._safe_unique_ideas(context).get("unique_ideas", [])
            source = source or context.get("all_ideas_json", {}).get("ideas", [])
            for raw in source:
                idea = ContentIdea.model_validate(raw)
                if idea.idea_id in already_approved:
                    continue
                candidates.append(
                    {
                        **idea.model_dump(),
                        "original_issue": "Needs quality pass because critic/filter returned too few usable ideas",
                    }
                )

        return candidates[:target]

    def _improved_ideas_as_content(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        improver = context.get("idea_improver")
        if improver is None:
            return []

        improved: list[dict[str, Any]] = []
        for index, item in enumerate(improver.improved_ideas, start=1):
            if not item.quality_check:
                continue
            idea_id = item.idea_id or f"improved_{index:03d}"
            improved.append(
                {
                    "idea_id": idea_id,
                    "idea_title": item.idea_title or f"Улучшенная идея {index}",
                    "source_agent": "idea_improver",
                    "target_persona": item.target_persona,
                    "pain": item.pain,
                    "content_angle": item.content_angle,
                    "video_format": item.video_format,
                    "funnel_stage": item.funnel_stage,
                    "rough_hook": item.rough_hook,
                    "why_it_can_work": item.why_now_it_works,
                }
            )
        return improved

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

    def _apply_blind_script_check(self, context: dict[str, Any]) -> None:
        """Filter polished scripts by a blind semantic fit check."""
        checker = context.get("blind_script_checker")
        scripts_output = context.get("script_writer")
        if checker is None or scripts_output is None:
            return

        reviews = list(getattr(checker, "script_reviews", []) or [])
        if not reviews:
            logger.warning("[pipeline] blind script checker returned no reviews — keeping critic output")
            self._emit_pipeline_event(
                "blind_script_check_empty",
                script_count=len(scripts_output.scripts),
            )
            return

        reviews_by_id = {review.script_id: review for review in reviews if review.script_id}
        passed: list[VideoScript] = []
        rejected: list[dict[str, Any]] = []

        for script in scripts_output.scripts:
            review = reviews_by_id.get(script.script_id)
            if review is None:
                rejected.append(
                    {
                        "script_id": script.script_id,
                        "idea_id": script.idea_id,
                        "reason": "blind_script_checker did not review this script",
                    }
                )
                continue

            if review.is_semantically_aligned or review.similarity_score >= 70:
                passed.append(script)
                continue

            rejected.append(
                {
                    "script_id": script.script_id,
                    "idea_id": script.idea_id,
                    "score": review.similarity_score,
                    "inferred_project_type": review.inferred_project_type,
                    "inferred_product_or_service": review.inferred_product_or_service,
                    "mismatch_notes": review.mismatch_notes,
                    "required_fixes": review.required_fixes,
                }
            )
            logger.info(
                "[pipeline] script %s rejected by blind semantic check (similarity=%d)",
                script.script_id,
                review.similarity_score,
            )

        passed.sort(
            key=lambda script: reviews_by_id.get(script.script_id).similarity_score
            if reviews_by_id.get(script.script_id)
            else 0,
            reverse=True,
        )

        scripts_output.scripts = passed
        context["polished_scripts_json"] = {"scripts": [s.model_dump() for s in passed]}
        context["blind_script_rejections_json"] = {"rejected_scripts": rejected}

        if not passed:
            context["blind_script_check_failed_all"] = True
            logger.warning(
                "[pipeline] blind script checker rejected all scripts; final pack will not rescue from ideas"
            )

        self._emit_pipeline_event(
            "blind_script_check_applied",
            passed_count=len(passed),
            rejected_count=len(rejected),
            rejected_scripts=rejected,
        )

    def _rescue_final_pack(
        self, context: dict[str, Any], final_output: FinalContentPackOutput
    ) -> FinalContentPackOutput:
        """Build approved_content from script_writer output when final_content_pack returned empty."""
        if context.get("blind_script_check_failed_all"):
            logger.warning("[pipeline] rescue skipped: blind semantic check rejected all scripts")
            return final_output

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
        quality_loop_approved = context.get("quality_loop_approved_ideas_json", {})
        if quality_loop_approved.get("ideas"):
            ideas = quality_loop_approved["ideas"][: context["input"].scripts_count]
            logger.info("[pipeline] selected %d quality-loop ideas for downstream scripting", len(ideas))
            return {"ideas": ideas}

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
        logger.info("[pipeline] selected top-%d of %d approved ideas for downstream scripting", len(top), len(ideas))
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
        """Return normalized unique_ideas for critic. Falls back to all_ideas if dedup failed."""
        quality_loop_unique = context.get("quality_loop_unique_ideas_json")
        if quality_loop_unique is not None:
            return quality_loop_unique

        dedup = context.get("deduplication")
        if dedup is not None and dedup.unique_ideas:
            repaired = self._repair_unique_ideas(context)
            if repaired:
                return {"unique_ideas": repaired}
        all_ideas = context.get("all_ideas_json", {"ideas": []})
        if all_ideas.get("ideas"):
            logger.warning(
                "[pipeline] dedup returned 0 unique_ideas despite %d generated — "
                "falling back to all_ideas for idea_critic",
                len(all_ideas["ideas"]),
            )
        return {"unique_ideas": all_ideas.get("ideas", [])}

    def _repair_unique_ideas(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        dedup = context.get("deduplication")
        if dedup is None:
            return []

        all_ideas = context.get("all_ideas_json", {}).get("ideas", [])
        by_id = {idea.get("idea_id", ""): idea for idea in all_ideas if idea.get("idea_id")}
        by_title = {idea.get("idea_title", ""): idea for idea in all_ideas if idea.get("idea_title")}
        repaired: list[dict[str, Any]] = []

        for index, item in enumerate(dedup.unique_ideas, start=1):
            base = by_id.get(item.idea_id) or by_title.get(item.idea_title) or {}
            idea_id = item.idea_id or base.get("idea_id") or f"dedup_{index:03d}"
            idea_title = item.idea_title or base.get("idea_title") or f"Идея {index}"
            source_agent = base.get("source_agent") or item.source_agent or "deduplication"
            repaired.append(
                {
                    **base,
                    "idea_id": idea_id,
                    "idea_title": idea_title,
                    "source_agent": source_agent,
                    "reason_kept": item.reason_kept,
                }
            )

        if any(not item.idea_id for item in dedup.unique_ideas):
            logger.warning("[pipeline] repaired %d dedup ideas with missing idea_id", len(repaired))
        return repaired

    def _fallback_approved_ideas(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        safe_unique = self._safe_unique_ideas(context).get("unique_ideas", [])
        source = safe_unique or context.get("all_ideas_json", {}).get("ideas", [])
        normalized: list[dict[str, Any]] = []

        for index, raw in enumerate(source, start=1):
            idea = ContentIdea.model_validate(raw)
            if not idea.idea_id:
                idea.idea_id = f"fallback_{index:03d}"
            if not idea.idea_title:
                idea.idea_title = idea.content_angle or idea.rough_hook or f"Идея {index}"
            data = idea.model_dump()
            data["reason_passed"] = "Fallback: upstream critic/filter returned empty lists"
            normalized.append(data)

        n = context["input"].scripts_count
        return normalized[:n]

    def _ideas_to_improve(self, context: dict[str, Any]) -> dict[str, Any]:
        """Collect borderline + revise ideas with their specific issues for the improver."""
        quality_loop_candidates = context.get("quality_loop_candidates_json")
        if quality_loop_candidates is not None:
            return quality_loop_candidates

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
        for index, raw in enumerate(raw_ideas, start=1):
            idea = ContentIdea.model_validate(raw)
            if not idea.idea_id:
                idea.idea_id = f"idea_{index:03d}"
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
