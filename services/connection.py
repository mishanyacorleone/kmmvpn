from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.connection import ConnectionRepository
from repositories.server import ServerRepository
from repositories.user import UserRepository
from services.server_manager import server_manager


@dataclass
class NewConnectionResult:
    """Результат создания подключения"""

    connection_id: int
    server_name: str
    vless_link: str


class ConnectionService:
    """Сервис для управления подключениями пользователей"""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._connections = ConnectionRepository(session)
        self._servers = ServerRepository(session)
        self._users = UserRepository(session)

    async def create_connection(
        self, telegram_id: int, server_id: int | None = None
    ) -> NewConnectionResult:
        """
        Создает новое подключение для пользователя.

        Если server_id не указан - выбирает наименее загруженный сервер.
        
        Raises:
            ValueError: если нет доступных серверов или нет активной подписки.
        """
        user = await self._users.get_by_telegram_id(telegram_id)
        if not user:
            raise ValueError("Пользователь не найден")
        
        has_subscription = await self._users.has_active_subscription(telegram_id)
        if not has_subscription:
            raise ValueError("Нет активной подписки")
        
        if server_id:
            server = await self._servers.get_by_id(server_id)
            if not server or not server.is_active:
                raise ValueError("Сервер не доступен")
        else:
            available_servers = await self._servers.get_available()
            if not available_servers:
                raise ValueError("Нет доступных серверов")
            server = available_servers[0]

        client = server_manager.get_client(server)
        try:
            client_info = await client.add_client(
                inbound_id=server.inbound_id,
                server_host=server.host,
                server_port=server.panel_port,
                remark=str(telegram_id)
            )
        except Exception as exc:
            raise RuntimeError(f"Ошибка создания клиента в x-ui: {exc}") from exc
        
        connection = await self._connections.create(
            user_id=user.id,
            server_id=server.id,
            xui_client_uuid=client_info.client_uuid
        )

        return NewConnectionResult(
            connection_id=connection.id,
            server_name=server.name,
            vless_link=client_info.vless_link
        )
    
    async def delete_connection(self, connection_id: int, telegram_id: int) -> None:
        """
        Удаляет подключение пользователя.

        Сначала удаляет клиента из x-ui, потом деактивирует в БД.

        Raises:
            ValueError: если подключение не найдено или не принадлежит пользователю.
        """
        connection = await self._connections.get_by_id(connection_id)
        if not connection:
            raise ValueError("Подключение не найдено")
        
        user = await self._users.get_by_telegram_id(telegram_id)
        if not user or connection.user_id != user.id:
            raise ValueError("Подключение не принадлежит пользователю")
        
        server = connection.server
        client = server_manager.get_client(server)

        try:
            await client.remove_client(
                inbound_id=server.inbound_id,
                client_uuid=connection.xui_client_uuid
            )
        except Exception as exc:
            # Логируем, но не останавливаем - клиент мог уже не существовать в x-ui
            import logging
            logging.getLogger(__name__).warning(
                "Не удалось удалить клиента из x-ui %s: %s",
                connection.xui_client_uuid,
                exc
            )

        await self._connections.deactivate(connection_id)

    async def deactivate_all_connections(self, telegram_id: int) -> None:
        """
        Деактивирует все подключения пользователя.

        Используется при истечении подписки.
        """
        user = await self._users.get_by_telegram_id(telegram_id)
        if not user:
            return
        
        connections = await self._connections.deactivate_all_for_user(user.id)

        for connection in connections:
            server = connection.server
            client = server_manager.get_client(server)
            try:
                await client.remove_client(
                    inbound_id=server.inbound_id,
                    client_uuid=connection.xui_client_uuid
                )
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Не удалось удалить клиента из x-ui %s: %s",
                    connection.xui_client_uuid,
                    exc
                )
        