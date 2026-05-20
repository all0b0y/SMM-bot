import uuid
from collections.abc import Sequence

from sqlalchemy import select

from smm_bot.db.models import Project, ProjectInput
from smm_bot.repositories.base import Repository


class ProjectRepository(Repository[Project]):
    model = Project

    async def list_by_user_id(self, user_id: uuid.UUID) -> Sequence[Project]:
        statement = (
            select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
        )
        return await self.list(statement)

    async def create_project(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        project_type: str | None = None,
        niche: str | None = None,
        brand_name: str | None = None,
    ) -> Project:
        project = Project(
            user_id=user_id,
            title=title,
            project_type=project_type,
            niche=niche,
            brand_name=brand_name,
        )
        return await self.add(project)


class ProjectInputRepository(Repository[ProjectInput]):
    model = ProjectInput

    async def create_input(
        self,
        *,
        project_id: uuid.UUID,
        raw_text: str,
        input_type: str = "company_description",
        platform: str | None = None,
        content_goal: str | None = None,
        ideas_count: int = 30,
        scripts_count: int = 10,
        metadata: dict | None = None,
    ) -> ProjectInput:
        project_input = ProjectInput(
            project_id=project_id,
            input_type=input_type,
            raw_text=raw_text,
            platform=platform,
            content_goal=content_goal,
            ideas_count=ideas_count,
            scripts_count=scripts_count,
            metadata_=metadata or {},
        )
        return await self.add(project_input)
