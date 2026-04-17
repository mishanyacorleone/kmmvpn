import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote

import aiohttp

from config import settings


@dataclass
class XUIClientConfig:
    """Конфигурация для подключения к панели 3x-ui."""

    host: str
    port: int
    username: str
    password: str
    panel_path: str  # кастомный base URI из настроек панели, например /ak55PzP0kBhJiILrgp

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}"

    @property
    def api_url(self) -> str:
        """Базовый URL для API запросов."""
        path = self.panel_path.rstrip("/")
        return f"{self.base_url}{path}/panel/api/inbounds"

    @property
    def login_url(self) -> str:
        path = self.panel_path.rstrip("/")
        return f"{self.base_url}{path}/login"


@dataclass
class InboundStats:
    """Статистика inbound — количество клиентов и трафик."""

    inbound_id: int
    total_clients: int
    up_bytes: int
    down_bytes: int


@dataclass
class ClientInfo:
    """Данные созданного клиента в x-ui."""

    client_uuid: str
    inbound_id: int
    vless_link: str


@dataclass
class _SessionCache:
    """Кеш сессии для переиспользования cookie."""

    cookie: str
    expires_at: datetime


class XUIClient:
    """
    HTTP клиент для взаимодействия с панелью 3x-ui.

    Кеширует сессию чтобы не логиниться при каждом запросе.
    Каждый экземпляр — отдельный сервер.
    """

    def __init__(self, config: XUIClientConfig) -> None:
        self._config = config
        self._session_cache: _SessionCache | None = None
        self._lock = asyncio.Lock()

    def _make_connector(self) -> aiohttp.TCPConnector:
        return aiohttp.TCPConnector(ssl=False)

    async def _login(self, http_session: aiohttp.ClientSession) -> str:
        """Логинится в панель и возвращает session cookie."""
        url = self._config.login_url
        payload = {
            "username": self._config.username,
            "password": self._config.password,
        }

        async with http_session.post(url, json=payload) as response:
            response.raise_for_status()
            data = await response.json()

            if not data.get("success"):
                raise ValueError(f"Ошибка авторизации в x-ui: {data.get('msg')}")

            cookies = http_session.cookie_jar.filter_cookies(url)
            session_cookie = cookies.get("3x-ui")

            if not session_cookie:
                raise ValueError("x-ui не вернул session cookie после логина")

            return session_cookie.value

    async def _get_cookie(self, http_session: aiohttp.ClientSession) -> str:
        """Возвращает актуальный cookie, логинится если истёк."""
        async with self._lock:
            now = datetime.utcnow()

            if (
                self._session_cache is not None
                and self._session_cache.expires_at > now
            ):
                return self._session_cache.cookie

            cookie = await self._login(http_session)
            self._session_cache = _SessionCache(
                cookie=cookie,
                expires_at=now + timedelta(seconds=settings.xui_session_ttl_seconds),
            )
            return cookie

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        """Выполняет авторизованный запрос к панели."""
        async with aiohttp.ClientSession(connector=self._make_connector()) as http_session:
            cookie = await self._get_cookie(http_session)
            headers = {"Cookie": f"3x-ui={cookie}"}

            async with http_session.request(
                method, url, headers=headers, **kwargs
            ) as response:
                response.raise_for_status()
                data = await response.json()

                if not data.get("success"):
                    if "login" in data.get("msg", "").lower():
                        self._session_cache = None
                        raise PermissionError("Сессия x-ui истекла, повтори запрос")

                    raise RuntimeError(f"x-ui вернул ошибку: {data.get('msg')}")

                return data

    async def get_inbound_stats(self, inbound_id: int) -> InboundStats:
        """Возвращает статистику inbound — клиенты и трафик."""
        url = f"{self._config.api_url}/get/{inbound_id}"
        data = await self._request("GET", url)
        obj = data["obj"]

        inbound_settings = json.loads(obj.get("settings", "{}"))
        clients = inbound_settings.get("clients", [])

        return InboundStats(
            inbound_id=inbound_id,
            total_clients=len(clients),
            up_bytes=obj.get("up", 0),
            down_bytes=obj.get("down", 0),
        )

    async def get_inbound(self, inbound_id: int) -> dict:
        """Возвращает полные данные inbound."""
        url = f"{self._config.api_url}/get/{inbound_id}"
        data = await self._request("GET", url)
        return data["obj"]

    async def add_client(
        self,
        inbound_id: int,
        server_host: str,
        server_port: int,
        remark: str = "",
    ) -> ClientInfo:
        """
        Создаёт нового клиента в inbound и возвращает vless:// ссылку.

        Args:
            inbound_id: ID inbound в x-ui
            server_host: IP или домен сервера (для формирования ссылки)
            server_port: порт inbound (для формирования ссылки)
            remark: метка клиента (например telegram_id пользователя)
        """
        client_uuid = str(uuid.uuid4())

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [
                    {
                        "id": client_uuid,
                        "email": remark or client_uuid[:8],
                        "enable": True,
                        "expiryTime": 0,
                        "totalGB": 0,
                        "flow": "xtls-rprx-vision",
                        "limitIp": 0,
                        "tgId": "",
                        "subId": "",
                        "comment": "",
                        "reset": 0,
                    }
                ]
            }),
        }

        url = f"{self._config.api_url}/addClient"
        await self._request("POST", url, json=payload)

        inbound_obj = await self.get_inbound(inbound_id)
        vless_link = self._build_vless_link(
            client_uuid=client_uuid,
            server_host=server_host,
            server_port=server_port,
            inbound_obj=inbound_obj,
            remark=remark,
        )

        return ClientInfo(
            client_uuid=client_uuid,
            inbound_id=inbound_id,
            vless_link=vless_link,
        )

    async def remove_client(self, inbound_id: int, client_uuid: str) -> None:
        """Удаляет клиента из inbound."""
        url = f"{self._config.api_url}/{inbound_id}/delClient/{client_uuid}"
        await self._request("POST", url)

    async def toggle_client(
        self, inbound_id: int, client_uuid: str, enable: bool
    ) -> None:
        """Включает или отключает клиента без удаления."""
        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [
                    {
                        "id": client_uuid,
                        "enable": enable,
                    }
                ]
            }),
        }
        url = f"{self._config.api_url}/updateClient/{client_uuid}"
        await self._request("POST", url, json=payload)

    def _build_vless_link(
        self,
        client_uuid: str,
        server_host: str,
        server_port: int,
        inbound_obj: dict,
        remark: str,
    ) -> str:
        """
        Собирает vless:// ссылку из параметров inbound.

        Поддерживает Reality и обычный TLS.
        """
        stream_settings = json.loads(inbound_obj.get("streamSettings", "{}"))
        network = stream_settings.get("network", "tcp")
        security = stream_settings.get("security", "none")

        params: dict[str, str] = {"type": network}

        if security == "reality":
            reality_settings = stream_settings.get("realitySettings", {})
            params["security"] = "reality"
            params["flow"] = "xtls-rprx-vision"
            params["pbk"] = reality_settings.get("publicKey", "")
            params["fp"] = reality_settings.get("fingerprint", "chrome")
            params["sni"] = reality_settings.get("serverNames", [""])[0]
            params["sid"] = reality_settings.get("shortIds", [""])[0]
            params["spx"] = "%2F"

        elif security == "tls":
            tls_settings = stream_settings.get("tlsSettings", {})
            params["security"] = "tls"
            params["sni"] = tls_settings.get("serverName", server_host)
            params["fp"] = "chrome"

        query_string = urlencode(params)
        encoded_remark = quote(remark or "vpn")
        port = inbound_obj.get("port", server_port)

        return f"vless://{client_uuid}@{server_host}:{port}?{query_string}#{encoded_remark}"