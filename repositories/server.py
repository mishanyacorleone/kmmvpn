from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Server, Connection


class ServerRepository:
    """Репозиторий для работы с серверами"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        host: str,
        panel_port: int,
        panel_username: str,
        panel_password: str,
        inbound_id: int,
        max_clients: int = 20
    ) -> Server:
        """Добавляет новый сервер"""
        server = Server(
            name=name,
            host=host,
            panel_port=panel_port,
            panel_username=panel_username,
            panel_password=panel_password,
            inbound_id=inbound_id,
            max_clients=max_clients
        )
        self._session.add(server)
        await self._session.commit()
        await self._session.refresh(server)
        return server
    
    async def get_by_id(self, server_id: int) -> Server | None:
        """Возвращает сервер по ID"""
        result = await self._session.execute(
            select(Server).where(Server.id == server_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_active(self) -> list[Server]:
        """Возвращает все активные сервера"""
        result = await self._session.execute(
            select(Server).where(Server.is_active == True).order_by(Server.id)
        )
        
        return list(result.scalars().all())
    
    async def get_available(self) -> list[Server]:
        """
        Возвращает серверы, где есть свободные места.
        
        Считает количество активных подключений и сравнивает с max_clients
        """
        connections_count = (
            select(func.count(Connection.id))
            .where(
                Connection.server_id == Server.id,
                Connection.is_active == True
            )
            .correlate(Server)
            .scalar_subquery()
        )

        result = await self._session.execute(
            select(Server)
            .where(
                Server.is_active == True,
                connections_count < Server.max_clients
            )
            .order_by(connections_count)
        )

        return list(result.scalars().all())
    
    async def get_client_count(self, server_id: int) -> int:
        """Возвращает количество активных подключений на серверы"""
        result = await self._session.execute(
            select(func.count(Connection.id)).where(
                Connection.server_id == server_id,
                Connection.is_active == True
            )
        )

        return result.scalar_one()
    
    async def set_active(self, server_id: int, is_active: bool) -> None:
        """Включает или отключает сервер."""
        server = await self.get_by_id(server_id)
        if server:
            server.is_active = is_active
            await self._session.commit()

    async def delete(self, server_id: int) -> None:
        """Удаляет сервер"""
        server = await self.get_by_id(server_id)
        if server:
            await self._session.delete(server)
            await self._session.commit()
