from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .schemas import (
    AudienceSegmentationOutput,
    BlindScriptCheckOutput,
    BriefOutput,
    ContextAuditOutput,
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
    ReferenceVideoPatternsOutput,
    HookGeneratorOutput,
    RetentionOptimizerOutput,
    RubricatorOutput,
    ScriptRefinerOutput,
    ScriptsOutput,
    ScriptCriticOutput,
    TopicAnglesOutput,
)


AgentName: TypeAlias = str


OWL_ALPHA = "openrouter/owl-alpha"
DEEPSEEK_FLASH = "deepseek/deepseek-v4-flash"
DEEPSEEK_PRO = "deepseek/deepseek-v4-pro"


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
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.1,
    ),
    "audience_segmentation": AgentSpec(
        name="audience_segmentation",
        title="Audience Segmentation Agent",
        output_schema=AudienceSegmentationOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.3,
    ),
    "persona_builder": AgentSpec(
        name="persona_builder",
        title="Persona Builder Agent",
        output_schema=PersonasOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_PRO,),
        temperature=0.5,
    ),
    "pain_trigger": AgentSpec(
        name="pain_trigger",
        title="Pain & Trigger Agent",
        output_schema=PainTriggerOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_PRO,),
        temperature=0.3,
    ),
    "context_auditor": AgentSpec(
        name="context_auditor",
        title="Context Auditor Agent",
        output_schema=ContextAuditOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.1,
    ),
    "positioning": AgentSpec(
        name="positioning",
        title="Positioning Agent",
        output_schema=PositioningOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_PRO,),
        temperature=0.25,
    ),
    "content_strategy": AgentSpec(
        name="content_strategy",
        title="Content Strategy Agent",
        output_schema=ContentStrategyOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_PRO,),
        temperature=0.3,
    ),
    "rubricator": AgentSpec(
        name="rubricator",
        title="Rubricator Agent",
        output_schema=RubricatorOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_PRO,),
        temperature=0.45,
    ),
    "pain_based_generator": AgentSpec(
        name="pain_based_generator",
        title="Pain-Based Idea Generator",
        output_schema=IdeasOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.8,
    ),
    "trigger_based_generator": AgentSpec(
        name="trigger_based_generator",
        title="Trigger-Based Idea Generator",
        output_schema=IdeasOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.8,
    ),
    "funnel_based_generator": AgentSpec(
        name="funnel_based_generator",
        title="Funnel-Based Idea Generator",
        output_schema=IdeasOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.75,
    ),
    "deduplication": AgentSpec(
        name="deduplication",
        title="Deduplication Agent",
        output_schema=DeduplicationOutput,
        primary_model=DEEPSEEK_FLASH,
        fallback_models=(OWL_ALPHA,),
        temperature=0.1,
    ),
    "idea_critic": AgentSpec(
        name="idea_critic",
        title="Idea Critic Agent",
        output_schema=IdeaCriticOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.1,
    ),
    "garbage_filter": AgentSpec(
        name="garbage_filter",
        title="Garbage Filter Agent",
        output_schema=GarbageFilterOutput,
        primary_model=DEEPSEEK_FLASH,
        fallback_models=(OWL_ALPHA,),
        temperature=0.05,
    ),
    "idea_improver": AgentSpec(
        name="idea_improver",
        title="Idea Improvement Agent",
        output_schema=IdeaImprovementOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.55,
    ),
    "script_writer": AgentSpec(
        name="script_writer",
        title="Script Writer Agent",
        output_schema=ScriptsOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.6,
    ),
    "reference_video_researcher": AgentSpec(
        name="reference_video_researcher",
        title="Reference Video Research Agent",
        output_schema=ReferenceVideoPatternsOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.35,
    ),
    "topic_angle_generator": AgentSpec(
        name="topic_angle_generator",
        title="Topic Angle Agent",
        output_schema=TopicAnglesOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.5,
    ),
    "hook_generator": AgentSpec(
        name="hook_generator",
        title="Hook Generator Agent",
        output_schema=HookGeneratorOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.65,
    ),
    "script_critic": AgentSpec(
        name="script_critic",
        title="Script Critic Agent",
        output_schema=ScriptCriticOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.1,
    ),
    "retention_optimizer": AgentSpec(
        name="retention_optimizer",
        title="Retention Optimizer Agent",
        output_schema=RetentionOptimizerOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.15,
    ),
    "blind_script_checker": AgentSpec(
        name="blind_script_checker",
        title="Blind Script Checker Agent",
        output_schema=BlindScriptCheckOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.1,
    ),
    "script_refiner": AgentSpec(
        name="script_refiner",
        title="Script Refiner Agent",
        output_schema=ScriptRefinerOutput,
        primary_model=DEEPSEEK_PRO,
        fallback_models=(OWL_ALPHA,),
        temperature=0.5,
    ),
    "final_content_pack": AgentSpec(
        name="final_content_pack",
        title="Final Content Pack Agent",
        output_schema=FinalContentPackOutput,
        primary_model=OWL_ALPHA,
        fallback_models=(DEEPSEEK_FLASH,),
        temperature=0.2,
    ),
}


MVP_GRAPH: tuple[AgentName, ...] = (
    "brief",
    "audience_segmentation",
    "persona_builder",
    "pain_trigger",
    "context_auditor",
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
    "reference_video_researcher",
    "topic_angle_generator",
    "hook_generator",
    "script_writer",
    "retention_optimizer",
    "script_critic",
    "blind_script_checker",
    "final_content_pack",
)


QUALITY_MODE_OVERRIDES: dict[str, dict[AgentName, dict[str, object]]] = {}


def registry_for_quality_mode(quality_mode: str) -> dict[AgentName, AgentSpec]:
    # quality_mode remains in DB/input metadata for backwards compatibility,
    # but the product now uses one unified model policy for every run.
    return dict(MVP_AGENT_REGISTRY)
