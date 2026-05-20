from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from smm_bot.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    language_code: Mapped[str] = mapped_column(Text, server_default=text("'ru'"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)

    projects: Mapped[list[Project]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    project_type: Mapped[str | None] = mapped_column(Text)
    niche: Mapped[str | None] = mapped_column(Text)
    brand_name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"), nullable=False)

    user: Mapped[User] = relationship(back_populates="projects")
    inputs: Mapped[list[ProjectInput]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    pipeline_runs: Mapped[list[PipelineRun]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("idx_projects_user_id", "user_id"),)


class ProjectInput(CreatedAtMixin, Base):
    __tablename__ = "project_inputs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_type: Mapped[str] = mapped_column(
        Text,
        server_default=text("'company_description'"),
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(Text)
    content_goal: Mapped[str | None] = mapped_column(Text)
    ideas_count: Mapped[int] = mapped_column(Integer, server_default=text("30"), nullable=False)
    scripts_count: Mapped[int] = mapped_column(Integer, server_default=text("10"), nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="inputs")
    pipeline_runs: Mapped[list[PipelineRun]] = relationship(back_populates="project_input")

    __table_args__ = (Index("idx_project_inputs_project_id", "project_id"),)


class PipelineRun(TimestampMixin, Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_input_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_inputs.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"), nullable=False)
    quality_mode: Mapped[str] = mapped_column(
        Text, server_default=text("'balanced'"), nullable=False
    )
    current_agent: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_input_tokens: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    total_output_tokens: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    total_estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        server_default=text("0"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="pipeline_runs")
    project_input: Mapped[ProjectInput | None] = relationship(back_populates="pipeline_runs")
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_pipeline_runs_project_id", "project_id"),
        Index("idx_pipeline_runs_status", "status"),
    )


class AgentRun(CreatedAtMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    agent_order: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"), nullable=False)
    input_json: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    output_json: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    model_id: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(
        Text,
        server_default=text("'not_checked'"),
        nullable=False,
    )
    validation_error: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="agent_runs")

    __table_args__ = (
        Index("idx_agent_runs_pipeline_run_id", "pipeline_run_id"),
        Index("idx_agent_runs_agent_name", "agent_name"),
        Index("idx_agent_runs_output_json_gin", "output_json", postgresql_using="gin"),
    )


class Idea(TimestampMixin, Base):
    __tablename__ = "ideas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_agent: Mapped[str] = mapped_column(Text, nullable=False)
    external_idea_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    target_persona: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text)
    pain: Mapped[str | None] = mapped_column(Text)
    trigger: Mapped[str | None] = mapped_column(Text)
    content_angle: Mapped[str | None] = mapped_column(Text)
    video_format: Mapped[str | None] = mapped_column(Text)
    funnel_stage: Mapped[str | None] = mapped_column(Text)
    rubric: Mapped[str | None] = mapped_column(Text)
    rough_hook: Mapped[str | None] = mapped_column(Text)
    why_it_can_work: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'generated'"), nullable=False)
    parent_idea_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ideas.id", ondelete="SET NULL"),
    )
    raw_json: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    parent_idea: Mapped[Idea | None] = relationship(remote_side=[id])
    reviews: Mapped[list[IdeaReview]] = relationship(
        back_populates="idea",
        cascade="all, delete-orphan",
    )
    scripts: Mapped[list[Script]] = relationship(
        back_populates="idea", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_ideas_project_id", "project_id"),
        Index("idx_ideas_pipeline_run_id", "pipeline_run_id"),
        Index("idx_ideas_status", "status"),
    )


class IdeaReview(CreatedAtMixin, Base):
    __tablename__ = "idea_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_agent: Mapped[str] = mapped_column(Text, nullable=False)
    audience_fit: Mapped[int | None] = mapped_column(Integer)
    pain_specificity: Mapped[int | None] = mapped_column(Integer)
    product_fit: Mapped[int | None] = mapped_column(Integer)
    retention_potential: Mapped[int | None] = mapped_column(Integer)
    novelty: Mapped[int | None] = mapped_column(Integer)
    production_simplicity: Mapped[int | None] = mapped_column(Integer)
    safety: Mapped[int | None] = mapped_column(Integer)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    main_issue: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    idea: Mapped[Idea] = relationship(back_populates="reviews")

    __table_args__ = (Index("idx_idea_reviews_idea_id", "idea_id"),)


class Script(TimestampMixin, Base):
    __tablename__ = "scripts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(Text)
    target_persona: Mapped[str | None] = mapped_column(Text)
    funnel_stage: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[str | None] = mapped_column(Text)
    hook: Mapped[str | None] = mapped_column(Text)
    core_message: Mapped[str | None] = mapped_column(Text)
    cta: Mapped[str | None] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    shooting_notes: Mapped[str | None] = mapped_column(Text)
    scene_by_scene: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    props_needed: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"), nullable=False)
    raw_json: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    idea: Mapped[Idea] = relationship(back_populates="scripts")
    reviews: Mapped[list[ScriptReview]] = relationship(
        back_populates="script",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_scripts_idea_id", "idea_id"),
        Index("idx_scripts_project_id", "project_id"),
    )


class ScriptReview(CreatedAtMixin, Base):
    __tablename__ = "script_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    script_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_agent: Mapped[str] = mapped_column(Text, nullable=False)
    hook_strength: Mapped[int | None] = mapped_column(Integer)
    clarity: Mapped[int | None] = mapped_column(Integer)
    pain_relevance: Mapped[int | None] = mapped_column(Integer)
    structure_score: Mapped[int | None] = mapped_column(Integer)
    no_water: Mapped[int | None] = mapped_column(Integer)
    retention: Mapped[int | None] = mapped_column(Integer)
    feasibility: Mapped[int | None] = mapped_column(Integer)
    brand_fit: Mapped[int | None] = mapped_column(Integer)
    safety: Mapped[int | None] = mapped_column(Integer)
    cta_score: Mapped[int | None] = mapped_column(Integer)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    issues: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    improved_version: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    script: Mapped[Script] = relationship(back_populates="reviews")

    __table_args__ = (Index("idx_script_reviews_script_id", "script_id"),)


class FinalContentPack(CreatedAtMixin, Base):
    __tablename__ = "final_content_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(Text)
    brand_summary: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    audience_summary: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    content_strategy_summary: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    approved_content: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    rejected_content: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    publishing_recommendations: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    risk_notes: Mapped[list] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )
    next_steps_for_human: Mapped[list] = mapped_column(
        JSONB,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    full_pack_json: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_final_content_packs_pipeline_run_id", "pipeline_run_id"),
        Index("idx_final_pack_json_gin", "full_pack_json", postgresql_using="gin"),
    )


class ModelUsageLog(CreatedAtMixin, Base):
    __tablename__ = "model_usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, server_default=text("'openrouter'"), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        Computed("input_tokens + output_tokens", persisted=True),
    )
    input_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        server_default=text("0"),
        nullable=False,
    )
    output_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        server_default=text("0"),
        nullable=False,
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        Computed("input_cost + output_cost", persisted=True),
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default=text("'success'"), nullable=False)

    __table_args__ = (Index("idx_model_usage_pipeline_run_id", "pipeline_run_id"),)


class PipelineError(CreatedAtMixin, Base):
    __tablename__ = "pipeline_errors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    agent_name: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text)
    input_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    is_recoverable: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    __table_args__ = (Index("idx_errors_pipeline_run_id", "pipeline_run_id"),)


class ModelPolicy(TimestampMixin, Base):
    __tablename__ = "model_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    agent_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    primary_model: Mapped[str] = mapped_column(Text, nullable=False)
    fallback_model: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        server_default=text("0.3"),
        nullable=False,
    )
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    quality_mode: Mapped[str] = mapped_column(
        Text, server_default=text("'balanced'"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
