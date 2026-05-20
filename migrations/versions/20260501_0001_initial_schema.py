"""Initial MVP schema.

Revision ID: 20260501_0001
Revises:
Create Date: 2026-05-01 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260501_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",
    """
    CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        telegram_user_id BIGINT UNIQUE NOT NULL,
        telegram_username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT NOT NULL DEFAULT 'ru',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE projects (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        project_type TEXT,
        niche TEXT,
        brand_name TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE project_inputs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        input_type TEXT NOT NULL DEFAULT 'company_description',
        raw_text TEXT NOT NULL,
        platform TEXT,
        content_goal TEXT,
        ideas_count INT NOT NULL DEFAULT 30,
        scripts_count INT NOT NULL DEFAULT 10,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE pipeline_runs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        project_input_id UUID REFERENCES project_inputs(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        quality_mode TEXT NOT NULL DEFAULT 'balanced',
        current_agent TEXT,
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        total_input_tokens INT NOT NULL DEFAULT 0,
        total_output_tokens INT NOT NULL DEFAULT 0,
        total_estimated_cost NUMERIC(12, 6) NOT NULL DEFAULT 0,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE agent_runs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        agent_name TEXT NOT NULL,
        agent_order INT,
        status TEXT NOT NULL DEFAULT 'pending',
        input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        model_id TEXT,
        temperature NUMERIC(3, 2),
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        latency_ms INT,
        validation_status TEXT NOT NULL DEFAULT 'not_checked',
        validation_error TEXT,
        error_message TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE ideas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        source_agent TEXT NOT NULL,
        external_idea_id TEXT,
        title TEXT NOT NULL,
        target_persona TEXT,
        segment TEXT,
        pain TEXT,
        trigger TEXT,
        content_angle TEXT,
        video_format TEXT,
        funnel_stage TEXT,
        rubric TEXT,
        rough_hook TEXT,
        why_it_can_work TEXT,
        status TEXT NOT NULL DEFAULT 'generated',
        parent_idea_id UUID REFERENCES ideas(id) ON DELETE SET NULL,
        raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE idea_reviews (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
        pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        reviewer_agent TEXT NOT NULL,
        audience_fit INT,
        pain_specificity INT,
        product_fit INT,
        retention_potential INT,
        novelty INT,
        production_simplicity INT,
        safety INT,
        total_score NUMERIC(5, 2),
        decision TEXT NOT NULL,
        main_issue TEXT,
        comment TEXT,
        raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE scripts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
        pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        platform TEXT,
        target_persona TEXT,
        funnel_stage TEXT,
        duration TEXT,
        hook TEXT,
        core_message TEXT,
        cta TEXT,
        caption TEXT,
        shooting_notes TEXT,
        scene_by_scene JSONB NOT NULL DEFAULT '[]'::jsonb,
        props_needed JSONB NOT NULL DEFAULT '[]'::jsonb,
        status TEXT NOT NULL DEFAULT 'draft',
        raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE script_reviews (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        script_id UUID NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
        pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        reviewer_agent TEXT NOT NULL,
        hook_strength INT,
        clarity INT,
        pain_relevance INT,
        structure_score INT,
        no_water INT,
        retention INT,
        feasibility INT,
        brand_fit INT,
        safety INT,
        cta_score INT,
        total_score NUMERIC(5, 2),
        decision TEXT NOT NULL,
        issues JSONB NOT NULL DEFAULT '[]'::jsonb,
        improved_version JSONB NOT NULL DEFAULT '{}'::jsonb,
        comment TEXT,
        raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE final_content_packs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        title TEXT,
        brand_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
        audience_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
        content_strategy_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
        approved_content JSONB NOT NULL DEFAULT '[]'::jsonb,
        rejected_content JSONB NOT NULL DEFAULT '[]'::jsonb,
        publishing_recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
        risk_notes JSONB NOT NULL DEFAULT '[]'::jsonb,
        next_steps_for_human JSONB NOT NULL DEFAULT '[]'::jsonb,
        full_pack_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE model_usage_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
        project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
        agent_name TEXT NOT NULL,
        model_id TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT 'openrouter',
        input_tokens INT NOT NULL DEFAULT 0,
        output_tokens INT NOT NULL DEFAULT 0,
        total_tokens INT GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
        input_cost NUMERIC(12, 6) NOT NULL DEFAULT 0,
        output_cost NUMERIC(12, 6) NOT NULL DEFAULT 0,
        total_cost NUMERIC(12, 6) GENERATED ALWAYS AS (input_cost + output_cost) STORED,
        latency_ms INT,
        status TEXT NOT NULL DEFAULT 'success',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE pipeline_errors (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        pipeline_run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
        agent_run_id UUID REFERENCES agent_runs(id) ON DELETE SET NULL,
        project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
        agent_name TEXT,
        error_type TEXT NOT NULL,
        error_message TEXT NOT NULL,
        raw_response TEXT,
        input_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
        is_recoverable BOOLEAN NOT NULL DEFAULT TRUE,
        retry_count INT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE model_policies (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_name TEXT UNIQUE NOT NULL,
        primary_model TEXT NOT NULL,
        fallback_model TEXT,
        temperature NUMERIC(3, 2) NOT NULL DEFAULT 0.3,
        max_tokens INT,
        quality_mode TEXT NOT NULL DEFAULT 'balanced',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX idx_projects_user_id ON projects(user_id)",
    "CREATE INDEX idx_project_inputs_project_id ON project_inputs(project_id)",
    "CREATE INDEX idx_pipeline_runs_project_id ON pipeline_runs(project_id)",
    "CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status)",
    "CREATE INDEX idx_agent_runs_pipeline_run_id ON agent_runs(pipeline_run_id)",
    "CREATE INDEX idx_agent_runs_agent_name ON agent_runs(agent_name)",
    "CREATE INDEX idx_agent_runs_output_json_gin ON agent_runs USING GIN (output_json)",
    "CREATE INDEX idx_ideas_project_id ON ideas(project_id)",
    "CREATE INDEX idx_ideas_pipeline_run_id ON ideas(pipeline_run_id)",
    "CREATE INDEX idx_ideas_status ON ideas(status)",
    "CREATE INDEX idx_idea_reviews_idea_id ON idea_reviews(idea_id)",
    "CREATE INDEX idx_scripts_idea_id ON scripts(idea_id)",
    "CREATE INDEX idx_scripts_project_id ON scripts(project_id)",
    "CREATE INDEX idx_script_reviews_script_id ON script_reviews(script_id)",
    "CREATE INDEX idx_final_content_packs_pipeline_run_id ON final_content_packs(pipeline_run_id)",
    "CREATE INDEX idx_final_pack_json_gin ON final_content_packs USING GIN (full_pack_json)",
    "CREATE INDEX idx_model_usage_pipeline_run_id ON model_usage_logs(pipeline_run_id)",
    "CREATE INDEX idx_errors_pipeline_run_id ON pipeline_errors(pipeline_run_id)",
]

DROP_TABLES = [
    "model_policies",
    "pipeline_errors",
    "model_usage_logs",
    "final_content_packs",
    "script_reviews",
    "scripts",
    "idea_reviews",
    "ideas",
    "agent_runs",
    "pipeline_runs",
    "project_inputs",
    "projects",
    "users",
]


def upgrade() -> None:
    for statement in CREATE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for table_name in DROP_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
