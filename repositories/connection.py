from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Connection


class ConnectionRepository:
    """Репозиторий для работы с подключениями пользователей."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        server_id: int,
        xui_client_uuid: str
    ) -> Connection:
        """Создаёт новое подключение"""
        connection = Connection(
            user_id=user_id,
            server_id=server_id,
            xui_client_uuid=xui_client_uuid
        )
        self._session.add(connection)
        await self._session.commit()
        await self._session.refresh(connection)
        return connection
    
    async def get_by_id(self, connection_id: int) -> Connection | None:
        """Возвращает подключение по ID с загрузкой сервера"""
        result = await self._session.execute(
            select(Connection)
            .options(joinedload(Connection.server))
            .where(Connection.id == connection_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_uuid(self, xui_client_uuid: str) -> Connection | None:
        """Возвращает подключение по uuid клиента в x-ui"""
        result = await self._session.execute(
            select(Connection)
            .options(joinedload(Connection.server))
            .where(Connection.xui_client_uuid == xui_client_uuid)
        )
        return result.scalar_one_or_none()
    
    async def get_user_connections(self, user_id: int) -> list[Connection]:
        """Возвращает все активные подключения пользователя с серверами"""
        result = await self._session.execute(
            select(Connection)
            .options(joinedload(Connection.server))
            .where(
                Connection.user_id == user_id,
                Connection.is_active == True
            )
            .order_by(Connection.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_server(self, server_id: int) -> list[Connection]:
        """Возвращает все активные подключения на сервере"""
        result = await self._session.execute(
            select(Connection).where(
                Connection.server_id == server_id,
                Connection.is_active == True
            )
        )
        return list(result.scalars().all())
    
    async def deactivate(self, connection_id: int) -> None:
        """Деактивирует подключение (не удаляет из БД)"""
        connection = await self.get_by_id(connection_id)
        if connection:
            connection.is_active = False
            await self._session.commit()
    
    async def deactivate_all_for_user(self, user_id: int) -> list[Connection]:
        """
        Деактивирует все подключения пользователя.

        Возвращает список деактивированных подключений
        чтобы вызывающий код мог удалить клиентов из x-ui
        """
        connections = await self.get_user_connections(user_id)
        for connection in connections:
            connection.is_active = False
        await self._session.commit()
        return connections
    