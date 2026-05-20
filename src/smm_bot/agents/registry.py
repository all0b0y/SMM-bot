from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TypeAlias

from .schemas import (
    AudienceSegmentationOutput,
    BriefOutput,
    ContentStrategyOutput,
    DeduplicationOutput,
    FinalContentPackOutput,
    GarbageFilterOutput,
    IdeaCriticOutput,
    IdeaImprovementOutput,
    IdeasOutput,
    PainTriggerOutput,
    PersonasOutput,
    PositioningOutput,
    RubricatorOutput,
    ScriptRefinerOutput,
    ScriptsOutput,
    ScriptCriticOutput,
)


AgentName: TypeAlias = str


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    title: str
    output_schema: type
    primary_model: str
    fallback_models: tuple[str, ...]
    temperature: float
    max_output_tokens: int = 8000


MVP_AGENT_REGISTRY: dict[AgentName, AgentSpec] = {
    "brief": AgentSpec(
        name="brief",
        title="Brief Agent",
        output_schema=BriefOutput,
        primary_model="qwen/qwen3.6-flash",
        fallback_models=("deepseek/deepseek-chat",),
        temperature=0.1,
    ),
    "audience_segmentation": AgentSpec(
        name="audience_segmentation",
        title="Audience Segmentation Agent",
        output_schema=AudienceSegmentationOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",),
        temperature=0.3,
    ),
    "persona_builder": AgentSpec(
        name="persona_builder",
        title="Persona Builder Agent",
        output_schema=PersonasOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.5,
    ),
    "pain_trigger": AgentSpec(
        name="pain_trigger",
        title="Pain & Trigger Agent",
        output_schema=PainTriggerOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.3,
    ),
    "positioning": AgentSpec(
        name="positioning",
        title="Positioning Agent",
        output_schema=PositioningOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.25,
    ),
    "content_strategy": AgentSpec(
        name="content_strategy",
        title="Content Strategy Agent",
        output_schema=ContentStrategyOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.3,
    ),
    "rubricator": AgentSpec(
        name="rubricator",
        title="Rubricator Agent",
        output_schema=RubricatorOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.45,
    ),
    "pain_based_generator": AgentSpec(
        name="pain_based_generator",
        title="Pain-Based Idea Generator",
        output_schema=IdeasOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.8,
    ),
    "trigger_based_generator": AgentSpec(
        name="trigger_based_generator",
        title="Trigger-Based Idea Generator",
        output_schema=IdeasOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.8,
    ),
    "funnel_based_generator": AgentSpec(
        name="funnel_based_generator",
        title="Funnel-Based Idea Generator",
        output_schema=IdeasOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",),
        temperature=0.75,
    ),
    "deduplication": AgentSpec(
        name="deduplication",
        title="Deduplication Agent",
        output_schema=DeduplicationOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-flash",),
        temperature=0.1,
    ),
    "idea_critic": AgentSpec(
        name="idea_critic",
        title="Idea Critic Agent",
        output_schema=IdeaCriticOutput,
        primary_model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.1,
    ),
    "garbage_filter": AgentSpec(
        name="garbage_filter",
        title="Garbage Filter Agent",
        output_schema=GarbageFilterOutput,
        primary_model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.05,
    ),
    "idea_improver": AgentSpec(
        name="idea_improver",
        title="Idea Improvement Agent",
        output_schema=IdeaImprovementOutput,
        primary_model="deepseek/deepseek-chat",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.55,
    ),
    "script_writer": AgentSpec(
        name="script_writer",
        title="Script Writer Agent",
        output_schema=ScriptsOutput,
        primary_model="qwen/qwen3.6-plus",
        fallback_models=("deepseek/deepseek-chat",),
        temperature=0.6,
    ),
    "script_critic": AgentSpec(
        name="script_critic",
        title="Script Critic Agent",
        output_schema=ScriptCriticOutput,
        primary_model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.1,
    ),
    "script_refiner": AgentSpec(
        name="script_refiner",
        title="Script Refiner Agent",
        output_schema=ScriptRefinerOutput,
        primary_model="qwen/qwen3.6-plus",
        fallback_models=("deepseek/deepseek-chat",),
        temperature=0.5,
    ),
    "final_content_pack": AgentSpec(
        name="final_content_pack",
        title="Final Content Pack Agent",
        output_schema=FinalContentPackOutput,
        primary_model="qwen/qwen3.6-flash",
        fallback_models=("qwen/qwen3.6-plus",),
        temperature=0.2,
    ),
}


MVP_GRAPH: tuple[AgentName, ...] = (
    "brief",
    "audience_segmentation",
    "persona_builder",
    "pain_trigger",
    "positioning",
    "content_strategy",
    "rubricator",
    "pain_based_generator",
    "trigger_based_generator",
    "funnel_based_generator",
    "deduplication",
    "idea_critic",
    "garbage_filter",
    "idea_improver",
    "script_writer",
    "script_critic",
    "final_content_pack",
)


QUALITY_MODE_OVERRIDES: dict[str, dict[AgentName, dict[str, object]]] = {
    "economy": {
        "brief": {
            "primary_model": "qwen/qwen3.6-flash",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "audience_segmentation": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "persona_builder": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "pain_trigger": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "positioning": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "content_strategy": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "rubricator": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "pain_based_generator": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "trigger_based_generator": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "funnel_based_generator": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "deduplication": {
            "primary_model": "qwen/qwen3.6-flash",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "idea_critic": {
            "primary_model": "qwen/qwen3.6-flash",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "garbage_filter": {
            "primary_model": "qwen/qwen3.6-flash",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "script_writer": {
            "primary_model": "deepseek/deepseek-chat",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "script_critic": {
            "primary_model": "qwen/qwen3.6-flash",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "final_content_pack": {
            "primary_model": "qwen/qwen3.6-flash",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
    },
    "high_quality": {
        "brief": {
            "primary_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "fallback_models": ("qwen/qwen3.6-flash",),
        },
        "audience_segmentation": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "persona_builder": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "pain_trigger": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",),
        },
        "positioning": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",),
        },
        "content_strategy": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",),
        },
        "rubricator": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "pain_based_generator": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "trigger_based_generator": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("deepseek/deepseek-chat",),
        },
        "funnel_based_generator": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",),
        },
        "deduplication": {
            "primary_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "fallback_models": ("qwen/qwen3.6-plus",),
        },
        "idea_critic": {
            "primary_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "fallback_models": ("qwen/qwen3.6-plus",),
        },
        "garbage_filter": {
            "primary_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "fallback_models": ("qwen/qwen3.6-plus",),
        },
        "script_writer": {
            "primary_model": "qwen/qwen3.6-plus",
            "fallback_models": ("qwen/qwen3.6-plus",),
        },
        "script_critic": {
            "primary_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "fallback_models": ("qwen/qwen3.6-plus",),
        },
        "final_content_pack": {
            "primary_model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "fallback_models": ("qwen/qwen3.6-plus",),
        },
    },
}


def registry_for_quality_mode(quality_mode: str) -> dict[AgentName, AgentSpec]:
    if quality_mode == "balanced":
        return dict(MVP_AGENT_REGISTRY)

    overrides = QUALITY_MODE_OVERRIDES.get(quality_mode)
    if overrides is None:
        return dict(MVP_AGENT_REGISTRY)

    registry: dict[AgentName, AgentSpec] = {}
    for agent_name, spec in MVP_AGENT_REGISTRY.items():
        registry[agent_name] = replace(spec, **overrides.get(agent_name, {}))
    return registry
