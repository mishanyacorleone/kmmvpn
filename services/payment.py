import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.database import Payment
from repositories.user import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class PaymentCreateResult:
    """Результат создания платежа."""
    payment_id: str
    confirmation_url: str   # Ссылка куда отправить пользователя для оплаты


class AbstractPaymentProvider(ABC):
    """Интерфейс платёжного провайдера"""

    @abstractmethod
    async def create_payment(
        self,
        amount_rub: int,
        telegram_id: int,
        description: str
    ) -> PaymentCreateResult:
        """Создаёт платёж и возвращает ссылку для оплаты"""
        ...

    @abstractmethod
    async def check_payment(self, payment_id: str) -> bool:
        """Проверяет статус платежа. Возвращает True - если оплачен"""
        ...


class StubPaymentProvider(AbstractPaymentProvider):
    """
    Заглушка для тестирования без реальной оплаты.
    
    Любой платёж считается успешным сразу.
    """

    async def create_payment(
        self,
        amount_rub: int,
        telegram_id: int,
        description: str
    ) -> PaymentCreateResult:
        stub_id = f"stub_{telegram_id}_{amount_rub}"
        logger.info("STUB: создан тестовый платёж %s", stub_id)
        return PaymentCreateResult(
            payment_id=stub_id,
            # Глубокая ссылка обратно в бота - имитирует редирект после оплаты.
            confirmation_url=f"https://t.me/{settings.bot_username}?start=payment_{stub_id}"
        )
    
    async def check_payment(self, payment_id) -> bool:
        logger.info("STUB: платёж %s считается успешным", payment_id)
        return True
    

class YookassaPaymentProvider(AbstractPaymentProvider):
    """Провайдер оплаты через ЮКассу"""

    async def create_payment(
        self,
        amount_rub: int,
        telegram_id: int,
        description: str
    ) -> PaymentCreateResult:
        from yookassa import Configuration, Payment as YKPayment

        Configuration.account_id = settings.yukassa_shop_id
        Configuration.secret_key = settings.yukassa_secret_key.get_secret_value()

        payment = YKPayment.create({
            "amount": {
                "value": str(amount_rub),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "redirect_url": f"https://t.me/{settings.bot_username}"
            },
            "capture": True,
            "description": description,
            "metadata": {
                "telegram_id": str(telegram_id)
            }
        })

        return PaymentCreateResult(
            payment_id=payment.id,
            confirmation_url=payment.confirmation.confirmation_url,
        )
    
    async def check_payment(self, payment_id: str) -> bool:
        from yookassa import Configuration, Payment as YKPayment

        Configuration.account_id = settings.yukassa_shop_id
        Configuration.secret_key = settings.yukassa_secret_key.get_secret_value()

        payment = YKPayment.find_one(payment_id)
        return payment.status == "succeeded"
    

class PaymentService:
    """Сервис оплаты - оркестрирует провайдера и репозитории"""

    def __init__(self, session: AsyncSession, provider: AbstractPaymentProvider) -> None:
        self._session = session
        self._provider = provider
        self._users = UserRepository(session)

    async def initiate_payment(self, telegram_id: int) -> PaymentCreateResult:
        """
        Создаёт платёж и сохраняет его в БД.
        
        Returns:
            PaymentCreateResult с ссылкой для оплаты
        """
        result = await self._provider.create_payment(
            amount_rub=settings.subscription_price_rub,
            telegram_id=telegram_id,
            description=f"Подписка на сервис на {settings.subscription_duration_days} дней"
        )

        payment = Payment(
            user_id=(await self._users.get_by_telegram_id(telegram_id)).id,
            yukassa_payment_id=result.payment_id,
            amount_rub=settings.subscription_price_rub,
            status="pending"
        )
        self._session.add(payment)
        await self._session.commit()

        return result
    
    async def confirm_payment(self, payment_id: str) -> bool:
        """
        Проверяет оплату и продлевает подписку если успешно.

        Returns:
            True, если платёж подтверждён и подписка продлена
        """
        from sqlalchemy import select

        result = await self._session.execute(
            select(Payment).where(Payment.yukassa_payment_id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment or payment.status != "pending":
            return False
        
        is_paid = await self._provider.check_payment(payment_id)
        if not is_paid:
            return False
        
        payment.status = "succeeded"
        await self._session.commit()

        user = await self._users.get_by_id(payment.user_id)
        if user:
            await self._users.extend_subscription(
                telegram_id=user.telegram_id,
                days=settings.subscription_duration_days
            )

        return True
    

def get_payment_provider() -> AbstractPaymentProvider:
    """
    Фабрика провайдера оплаты.

    Переключается через USE_STUB_PAYMENTS в .env
    Чтобы включить ЮКассу - USE_STUB_PAYMENTS=false
    """
    if settings.use_stub_payments:
        return StubPaymentProvider()
    return YookassaPaymentProvider()
