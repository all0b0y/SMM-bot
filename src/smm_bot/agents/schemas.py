from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Confidence = Literal["low", "medium", "high"]
Priority = Literal["low", "medium", "high"]
FunnelStage = Literal["awareness", "trust", "conversion", "retention"]
Decision = Literal["approve", "revise", "reject"]


class AgentModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AgentOutput(AgentModel):
    warnings: list[str] = Field(default_factory=list)


class Assumption(AgentModel):
    assumption: str = ""
    confidence: Confidence = "low"
    why: str = ""


class CompanyInput(AgentModel):
    company_description: str
    platform: str = "Instagram Reels"
    ideas_count: int = 15
    scripts_count: int = 5


class Brief(AgentModel):
    project_type: str = ""
    niche: str = ""
    company_or_brand_name: str = ""
    product_or_service: str = ""
    geo: str = ""
    platforms: list[str] = Field(default_factory=list)
    content_goal: list[str] = Field(default_factory=list)
    business_goal: list[str] = Field(default_factory=list)
    target_audience_raw: str = ""
    usp_raw: str = ""
    positioning_raw: str = ""
    tone_of_voice_raw: str = ""
    brand_values: list[str] = Field(default_factory=list)
    product_features: list[str] = Field(default_factory=list)
    product_benefits: list[str] = Field(default_factory=list)
    competitors_raw: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    available_assets: list[str] = Field(default_factory=list)
    important_facts: list[str] = Field(default_factory=list)


class BriefOutput(AgentOutput):
    brief: Brief = Field(default_factory=Brief)
    missing_data: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class AudienceSubsegment(AgentModel):
    subsegment_id: str = ""
    name: str = ""
    description: str = ""
    why_relevant: str = ""
    main_need: str = ""
    purchase_power: Priority = "medium"
    content_priority: Priority = "medium"
    awareness_level: Literal[
        "unaware",
        "problem-aware",
        "solution-aware",
        "product-aware",
        "ready-to-buy",
    ] = "problem-aware"
    best_content_formats: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class AudienceSegment(AgentModel):
    segment_id: str = ""
    segment_name: str = ""
    description: str = ""
    subsegments: list[AudienceSubsegment] = Field(default_factory=list)


class ExcludedSegment(AgentModel):
    segment: str = ""
    reason: str = ""


class AudienceSegmentationOutput(AgentOutput):
    audience_segments: list[AudienceSegment] = Field(default_factory=list)
    excluded_segments: list[ExcludedSegment] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)


class Persona(AgentModel):
    persona_id: str = ""
    name: str = ""
    age: int = 0
    gender: str = ""
    geo_type: str = ""
    segment_id: str = ""
    subsegment_id: str = ""
    family_status: str = ""
    income_level: str = ""
    life_context: str = ""
    main_need: str = ""
    main_pain: str = ""
    hidden_pain: str = ""
    desire: str = ""
    objection: str = ""
    triggers: list[str] = Field(default_factory=list)
    proof_needed: list[str] = Field(default_factory=list)
    repelling_factors: list[str] = Field(default_factory=list)
    content_topics: list[str] = Field(default_factory=list)
    best_video_formats: list[str] = Field(default_factory=list)
    buying_readiness: Priority = "medium"


class PersonaPriority(AgentModel):
    persona_id: str = ""
    priority: Priority = "medium"
    reason: str = ""


class PersonasOutput(AgentOutput):
    personas: list[Persona] = Field(default_factory=list)
    persona_prioritization: list[PersonaPriority] = Field(default_factory=list)


class ContentOpportunity(AgentModel):
    opportunity_id: str = ""
    pain_or_trigger: str = ""
    content_angle: str = ""
    why_it_matters: str = ""
    possible_video_formats: list[str] = Field(default_factory=list)
    funnel_stage: FunnelStage = "awareness"


class PersonaPainTrigger(AgentModel):
    persona_id: str = ""
    explicit_pains: list[str] = Field(default_factory=list)
    hidden_pains: list[str] = Field(default_factory=list)
    desires: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    content_opportunities: list[ContentOpportunity] = Field(default_factory=list)


class PainTriggerOutput(AgentOutput):
    pain_trigger_map: list[PersonaPainTrigger] = Field(default_factory=list)
    universal_pains_to_avoid: list[str] = Field(default_factory=list)
    high_potential_angles: list[str] = Field(default_factory=list)


class Positioning(AgentModel):
    short_positioning: str = ""
    expanded_positioning: str = ""
    usp: str = ""
    brand_promise: str = ""
    key_differentiators: list[str] = Field(default_factory=list)
    emotional_benefits: list[str] = Field(default_factory=list)
    functional_benefits: list[str] = Field(default_factory=list)
    proof_points_needed: list[str] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    tone_boundaries: list[str] = Field(default_factory=list)


class PainToProductMap(AgentModel):
    pain: str = ""
    product_connection: str = ""
    safe_message: str = ""
    risky_message_to_avoid: str = ""


class PositioningOutput(AgentOutput):
    positioning: Positioning = Field(default_factory=Positioning)
    pain_to_product_map: list[PainToProductMap] = Field(default_factory=list)


class ContentPillar(AgentModel):
    pillar_id: str = ""
    name: str = ""
    purpose: str = ""
    target_personas: list[str] = Field(default_factory=list)
    example_topics: list[str] = Field(default_factory=list)
    best_formats: list[str] = Field(default_factory=list)
    funnel_stage: FunnelStage = "awareness"


class FunnelDistribution(AgentModel):
    awareness: str = ""
    trust: str = ""
    conversion: str = ""
    retention: str = ""


class ContentStrategy(AgentModel):
    main_content_goal: str = ""
    secondary_goals: list[str] = Field(default_factory=list)
    content_pillars: list[ContentPillar] = Field(default_factory=list)
    funnel_distribution: FunnelDistribution = Field(default_factory=FunnelDistribution)
    core_messages: list[str] = Field(default_factory=list)
    topics_to_use: list[str] = Field(default_factory=list)
    topics_to_avoid: list[str] = Field(default_factory=list)
    video_strategy_notes: list[str] = Field(default_factory=list)
    kpi: list[str] = Field(default_factory=list)


class ContentStrategyOutput(AgentOutput):
    content_strategy: ContentStrategy = Field(default_factory=ContentStrategy)


class Rubric(AgentModel):
    rubric_id: str = ""
    content_type: str = ""
    rubric_name: str = ""
    purpose: str = ""
    target_personas: list[str] = Field(default_factory=list)
    pains_addressed: list[str] = Field(default_factory=list)
    video_formats: list[str] = Field(default_factory=list)
    topic_examples: list[str] = Field(default_factory=list)
    cta_types: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class RecommendedMonthlyMix(AgentModel):
    reels_or_short_videos: str = ""
    stories: str = ""
    posts: str = ""
    live_or_long_format: str = ""


class RubricatorOutput(AgentOutput):
    rubricator: list[Rubric] = Field(default_factory=list)
    recommended_monthly_mix: RecommendedMonthlyMix = Field(default_factory=RecommendedMonthlyMix)


class ContentIdea(AgentModel):
    idea_id: str = ""
    idea_title: str = ""

    @field_validator("idea_id", mode="before")
    @classmethod
    def coerce_idea_id(cls, v: Any) -> str:
        return str(v) if v is not None else ""
    source_agent: str = ""
    target_persona: str = ""
    pain: str = ""
    hidden_pain: str = ""
    pain_or_desire: str = ""
    pain_or_trigger: str = ""
    main_trigger: str = ""
    content_angle: str = ""
    video_format: str = ""
    funnel_stage: FunnelStage = "awareness"
    rubric_id: str = ""
    rough_hook: str = ""
    why_it_can_work: str = ""
    viewer_next_step: str = ""
    suggested_cta_type: str = ""
    shooting_complexity: Priority = "medium"
    risk_notes: list[str] = Field(default_factory=list)


class IdeasOutput(AgentOutput):
    ideas: list[ContentIdea] = Field(default_factory=list)
    funnel_balance_comment: str = ""


class UniqueIdea(AgentModel):
    idea_id: str = ""
    idea_title: str = ""
    source_agent: str = ""
    reason_kept: str = ""


class DuplicateGroup(AgentModel):
    group_id: str = ""
    kept_idea_id: str = ""
    removed_idea_ids: list[str] = Field(default_factory=list)
    duplicate_reason: str = ""


class DeduplicationOutput(AgentOutput):
    unique_ideas: list[UniqueIdea] = Field(default_factory=list)
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    removed_count: int = 0
    kept_count: int = 0


class IdeaScores(AgentModel):
    audience_fit: int = Field(default=0, ge=0, le=5)
    pain_specificity: int = Field(default=0, ge=0, le=5)
    product_fit: int = Field(default=0, ge=0, le=5)
    retention_potential: int = Field(default=0, ge=0, le=5)
    novelty: int = Field(default=0, ge=0, le=5)
    production_simplicity: int = Field(default=0, ge=0, le=5)
    safety: int = Field(default=0, ge=0, le=5)


class EvaluatedIdea(AgentModel):
    idea_id: str = ""
    idea_title: str = ""
    scores: IdeaScores = Field(default_factory=IdeaScores)
    weighted_score: float = 0
    decision: Decision = "reject"
    critic_comment: str = ""
    main_issue: str = ""
    recommendation: str = ""


class CriticSummary(AgentModel):
    approved_count: int = 0
    revise_count: int = 0
    rejected_count: int = 0


class IdeaCriticOutput(AgentOutput):
    evaluated_ideas: list[EvaluatedIdea] = Field(default_factory=list)
    summary: CriticSummary = Field(default_factory=CriticSummary)


class PassedIdea(AgentModel):
    idea_id: str = ""
    idea_title: str = ""
    reason_passed: str = ""


class GarbageRejectedIdea(AgentModel):
    idea_id: str = ""
    idea_title: str = ""
    garbage_reasons: list[str] = Field(default_factory=list)
    short_explanation: str = ""


class BorderlineIdea(AgentModel):
    idea_id: str = ""
    idea_title: str = ""
    problem: str = ""
    can_be_improved: bool = False


class GarbageFilterOutput(AgentOutput):
    passed: list[PassedIdea] = Field(default_factory=list)
    garbage_rejected: list[GarbageRejectedIdea] = Field(default_factory=list)
    borderline: list[BorderlineIdea] = Field(default_factory=list)


class ImprovedIdea(AgentModel):
    idea_id: str = ""
    idea_title: str = ""
    original_issue: str = ""
    improvement_made: str = ""
    target_persona: str = ""
    pain: str = ""
    content_angle: str = ""
    video_format: str = ""
    funnel_stage: FunnelStage = "awareness"
    rough_hook: str = ""
    why_now_it_works: str = ""
    quality_check: bool = False


class IdeaImprovementOutput(AgentOutput):
    improved_ideas: list[ImprovedIdea] = Field(default_factory=list)
    skipped_idea_ids: list[str] = Field(default_factory=list)


class ScriptScene(AgentModel):
    time: str = ""
    visual: str = ""
    voiceover: str = ""
    text_on_screen: str = ""


class VideoScript(AgentModel):
    script_id: str = ""
    idea_id: str = ""

    @field_validator("script_id", "idea_id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""
    title: str = ""
    target_persona: str = ""
    funnel_stage: FunnelStage = "awareness"
    duration: str = ""
    hook: str = ""
    core_message: str = ""
    scene_by_scene: list[ScriptScene] = Field(default_factory=list)
    cta: str = ""
    caption: str = ""
    shooting_notes: str = ""
    props_needed: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class ScriptsOutput(AgentOutput):
    scripts: list[VideoScript] = Field(default_factory=list)


class ScriptScores(AgentModel):
    hook_strength: int = Field(default=0, ge=0, le=10)
    clarity: int = Field(default=0, ge=0, le=10)
    pain_relevance: int = Field(default=0, ge=0, le=10)
    structure: int = Field(default=0, ge=0, le=10)
    no_water: int = Field(default=0, ge=0, le=10)
    retention: int = Field(default=0, ge=0, le=10)
    feasibility: int = Field(default=0, ge=0, le=10)
    brand_fit: int = Field(default=0, ge=0, le=10)
    safety: int = Field(default=0, ge=0, le=10)


class ImprovedScriptVersion(AgentModel):
    hook: str = ""
    scene_by_scene: list[ScriptScene] = Field(default_factory=list)
    cta: str = ""


class ScriptReview(AgentModel):
    script_id: str = ""
    idea_id: str = ""

    @field_validator("script_id", "idea_id", mode="before")
    @classmethod
    def coerce_ids(cls, v: Any) -> str:
        return str(v) if v is not None else ""
    scores: ScriptScores = Field(default_factory=ScriptScores)
    total_score: float = 0
    decision: Decision = "reject"
    issues: list[str] = Field(default_factory=list)
    editor_comment: str = ""
    improved_version: ImprovedScriptVersion = Field(default_factory=ImprovedScriptVersion)


class ScriptCriticOutput(AgentOutput):
    script_reviews: list[ScriptReview] = Field(default_factory=list)


class ScriptRefinerOutput(AgentOutput):
    refined_script: VideoScript = Field(default_factory=VideoScript)
    changes_made: list[str] = Field(default_factory=list)


class FinalBrandSummary(AgentModel):
    niche: str = ""
    positioning: str = ""
    usp: str = ""
    tone_of_voice: str = ""


class FinalAudienceSummary(AgentModel):
    priority_segments: list[str] = Field(default_factory=list)
    priority_personas: list[str] = Field(default_factory=list)
    main_pains: list[str] = Field(default_factory=list)
    main_triggers: list[str] = Field(default_factory=list)


class FinalStrategySummary(AgentModel):
    content_pillars: list[str] = Field(default_factory=list)
    recommended_funnel_distribution: dict[str, Any] = Field(default_factory=dict)
    rubrics: list[str] = Field(default_factory=list)


class ApprovedContentScript(AgentModel):
    platform: str = ""
    duration: str = ""
    hook: str = ""
    scene_by_scene: list[ScriptScene] = Field(default_factory=list)
    cta: str = ""
    caption: str = ""
    shooting_notes: str = ""


class ApprovedContent(AgentModel):
    content_id: str = ""
    idea_id: str = ""
    title: str = ""
    target_persona: str = ""
    pain: str = ""
    trigger: str = ""
    funnel_stage: FunnelStage = "awareness"
    rubric: str = ""
    why_approved: str = ""
    quality_score: float = 0
    script: ApprovedContentScript = Field(default_factory=ApprovedContentScript)


class RejectedContent(AgentModel):
    idea_id: str = ""
    idea_title: str = ""
    reason: str = ""


class FinalContentPack(AgentModel):
    brand_summary: FinalBrandSummary = Field(default_factory=FinalBrandSummary)
    audience_summary: FinalAudienceSummary = Field(default_factory=FinalAudienceSummary)
    content_strategy_summary: FinalStrategySummary = Field(default_factory=FinalStrategySummary)
    approved_content: list[ApprovedContent] = Field(default_factory=list)
    rejected_content: list[RejectedContent] = Field(default_factory=list)
    publishing_recommendations: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    next_steps_for_human: list[str] = Field(default_factory=list)


class FinalContentPackOutput(AgentOutput):
    final_content_pack: FinalContentPack = Field(default_factory=FinalContentPack)


class PipelineResult(AgentModel):
    outputs: dict[str, Any] = Field(default_factory=dict)
    final_content_pack: FinalContentPackOutput = Field(default_factory=FinalContentPackOutput)
