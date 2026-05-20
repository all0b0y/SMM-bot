from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from smm_bot.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: object) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def list(self, statement: Select[tuple[ModelT]] | None = None) -> Sequence[ModelT]:
        result = await self.session.scalars(statement or select(self.model))
        return result.all()

