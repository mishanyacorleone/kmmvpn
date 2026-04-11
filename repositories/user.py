from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import User


class UserRepository:
    """Репозиторий для работы с пользователями."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, telegram_id: int, username: str | None) -> tuple[User, bool]:
        """
        Возвращает пользователя или создаёт нового.

        Returns:
            tuple[User, bool]: пользователь и флаг is_created
        """
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Обновляем username если изменился
            if user.username != username:
                user.username = username
                await self._session.commit()
            return user, False
        
        user = User(telegram_id=telegram_id, username=username)
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user, True
    
    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Возвращает пользователя по telegram_id"""
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: int) -> User | None:
        """Возвращает пользователя по внутреннему ID"""
        result = await self._session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_active(self) -> list[User]:
        """Возвращает всех активных пользователей (для рассылки)"""
        result = await self._session.execute(
            select(User).where(User.is_active == True)
        )
        return list(result.scalars().all())
    
    async def has_active_subscription(self, telegram_id: int) -> bool:
        """Проверяет наличие активной подписки."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user or not user.subscription_expires_at:
            return False
        return user.subscription_expires_at > datetime.now(timezone.utc)
    
    async def extend_subscription(self, telegram_id: int, days: int) -> User:
        """
        Продлевает подписку на указанное количество дней.

        Если подписка уже истекла - отсчёт идёт от сегодня.
        Если подписка активна - дни добавляются к текущей дате истечения.
        """
        from datetime import timedelta

        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            raise ValueError(f"Пользователь {telegram_id} не найден")
        
        now = datetime.now(timezone.utc)
        base_date = (
            user.subscription_expires_at
            if user.subscription_expires_at and user.subscription_expires_at > now
            else now
        )

        user.subscription_expires_at = base_date + timedelta(days=days)
        await self._session.commit()
        await self._session.refresh(user)
        return user
    
    async def count_active(self) -> int:
        """Возвращает количество активных пользователей"""
        result = await self._session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        return result.scalar_one()
    
    async def count_with_subscription(self) -> int:
        """Возвращает количество пользователей с активной подпиской"""
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            select(func.count(User.id)).where(
                User.is_active == True,
                User.subscription_expires_at > now
            )
        )
        return result.scalar_one()
    