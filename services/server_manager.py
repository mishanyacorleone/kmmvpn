from infrastructure.xui_client import XUIClient, XUIClientConfig, InboundStats
from models.database import Server


class ServerManager:
    """
    Менеджер пула XUIClient.

    Хранит по одному клиенту на сервер и переиспользует сессии.
    Создаётся один раз при старте бота и живёт всё время.
    """

    def __init__(self) -> None:
        self._clients: dict[int, XUIClient] = {}  # server_id -> XUIClient

    def get_client(self, server: Server) -> XUIClient:
        """Возвращает XUIClient для сервера, создаёт если нет."""
        if server.id not in self._clients:
            config = XUIClientConfig(
                host=server.host,
                port=server.panel_port,
                username=server.panel_username,
                password=server.panel_password,
                panel_path=server.panel_path,
            )
            self._clients[server.id] = XUIClient(config)
        return self._clients[server.id]

    def remove_client(self, server_id: int) -> None:
        """Удаляет клиент из пула (при удалении сервера)."""
        self._clients.pop(server_id, None)

    async def get_inbound_stats(self, server: Server) -> InboundStats | None:
        """
        Возвращает статистику inbound сервера.

        Возвращает None если сервер недоступен — не бросает исключение,
        чтобы один упавший сервер не ломал список серверов для пользователя.
        """
        try:
            client = self.get_client(server)
            return await client.get_inbound_stats(server.inbound_id)
        except Exception:
            return None


# Глобальный экземпляр — создаётся один раз при старте
server_manager = ServerManager()
