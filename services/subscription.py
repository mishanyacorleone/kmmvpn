import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.connection import ConnectionRepository
from repositories.user import UserRepository
from services.server_manager import server_manager

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Сервис управления подписками.

    При продлении подписки синхронизирует expiryTime
    всех активных подключений пользователя в x-ui.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._connections = ConnectionRepository(session)

    async def extend_and_sync(self, telegram_id: int, days: int) -> datetime:
        """
        Продлевает подписку и обновляет expiryTime во всех подключениях в x-ui.

        Args:
            telegram_id: Telegram ID пользователя
            days: количество дней на которое продлевается подписка

        Returns:
            Новая дата истечения подписки
        """
        user = await self._users.extend_subscription(
            telegram_id=telegram_id,
            days=days,
        )

        new_expires_at = user.subscription_expires_at
        connections = await self._connections.get_user_connections(user.id)

        if not connections:
            return new_expires_at

        expiry_ms = int(new_expires_at.timestamp() * 1000)

        for connection in connections:
            server = connection.server
            client = server_manager.get_client(server)

            try:
                await client.update_client_expiry(
                    inbound_id=server.inbound_id,
                    client_uuid=connection.xui_client_uuid,
                    expiry_ms=expiry_ms,
                )
                logger.info(
                    "Обновлён expiryTime для клиента %s до %s",
                    connection.xui_client_uuid,
                    new_expires_at,
                )
            except Exception as exc:
                logger.warning(
                    "Не удалось обновить expiryTime для клиента %s: %s",
                    connection.xui_client_uuid,
                    exc,
                )

        return new_expires_at