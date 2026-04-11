from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    # Telegram
    bot_token: SecretStr
    bot_username: str # username бота без @ нужен для ссылок после оплаты
    admin_ids: list[int] # Список telegram_id админов

    # PostgreSQL
    database_url: str # postgresql+asyncpg://user:pass@host:port/db_name

    # ЮКасса
    yukassa_shop_id: str = ""
    yukassa_secret_key: SecretStr = SecretStr("")

    # Подписка
    subscription_price_rub: int = 100
    subscription_duration_days: int = 30

    # Оплата
    use_stub_payments: bool = True # True = заглушка для теста, False = ЮКасса

    # 3x-ui
    xui_session_ttl_seconds: int = 3600 # Как долго кэшировать сессию

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
