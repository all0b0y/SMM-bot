import uuid

from sqlalchemy import select

from smm_bot.db.models import AgentRun, PipelineRun
from smm_bot.repositories.base import Repository


class PipelineRunRepository(Repository[PipelineRun]):
    model = PipelineRun

    async def get_latest_for_project(self, project_id: uuid.UUID) -> PipelineRun | None:
        statement = (
            select(PipelineRun)
            .where(PipelineRun.project_id == project_id)
            .order_by(PipelineRun.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def create_run(
        self,
        *,
        project_id: uuid.UUID,
        project_input_id: uuid.UUID | None = None,
        quality_mode: str = "balanced",
    ) -> PipelineRun:
        run = PipelineRun(
            project_id=project_id,
            project_input_id=project_input_id,
            quality_mode=quality_mode,
        )
        return await self.add(run)


class AgentRunRepository(Repository[AgentRun]):
    model = AgentRun

    async def create_agent_run(
        self,
        *,
        pipeline_run_id: uuid.UUID,
        project_id: uuid.UUID,
        agent_name: str,
        agent_order: int | None = None,
        input_json: dict | None = None,
        model_id: str | None = None,
    ) -> AgentRun:
        run = AgentRun(
            pipeline_run_id=pipeline_run_id,
            project_id=project_id,
            agent_name=agent_name,
            agent_order=agent_order,
            input_json=input_json or {},
            model_id=model_id,
        )
        return await self.add(run)
