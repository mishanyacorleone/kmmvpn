from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    # Telegram
    bot_token: SecretStr
    bot_username: str  # username бота без @ — нужен для ссылок после оплаты
    admin_ids: list[int]  # список telegram_id администраторов

    # PostgreSQL
    database_url: str  # postgresql+asyncpg://user:pass@host:port/dbname

    # ЮКасса
    yukassa_shop_id: str = ""
    yukassa_secret_key: SecretStr = SecretStr("")

    # Подписка
    subscription_price_rub: int = 100  # цена в рублях
    subscription_duration_days: int = 30

    # Веб
    base_url: str = "http://localhost:8000"  # меняй при смене домена
    web_port: int = 8000
    xui_server_host: str = ""  # IP сервера x-ui для получения ключей подписки
    xui_sub_port: int = 2096   # порт сервера подписок x-ui

    # Админка
    admin_secret_path: str = "admin"        # секретный путь /admin-{path}/
    admin_jwt_secret: str = "change_me"     # секрет для JWT токенов
    admin_password: str = "change_me"       # пароль от админки
    admin_jwt_ttl_hours: int = 8            # время жизни токена

    # Оплата
    use_stub_payments: bool = True  # True = заглушка для тестов, False = ЮКасса

    # 3x-ui
    xui_session_ttl_seconds: int = 3600  # как долго кешировать сессию

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()