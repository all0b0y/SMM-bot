from sqlalchemy import select

from smm_bot.db.models import User
from smm_bot.repositories.base import Repository


class UserRepository(Repository[User]):
    model = User

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        statement = select(User).where(User.telegram_user_id == telegram_user_id)
        return await self.session.scalar(statement)

    async def upsert_telegram_user(
        self,
        *,
        telegram_user_id: int,
        telegram_username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> User:
        user = await self.get_by_telegram_user_id(telegram_user_id)
        if user is None:
            user = User(
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code or "ru",
            )
            return await self.add(user)

        user.telegram_username = telegram_username
        user.first_name = first_name
        user.last_name = last_name
        if language_code is not None:
            user.language_code = language_code
        await self.session.flush()
        return user

