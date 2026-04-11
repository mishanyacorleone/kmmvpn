import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.user import payment_keyboard, back_to_menu_keyboard
from repositories.user import UserRepository
from services.payment import PaymentService, get_payment_provider

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "buy_subscription")
async def cb_buy_subscription(callback: CallbackQuery, session: AsyncSession) -> None:
    from config import settings

    user = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    has_sub = await UserRepository(session).has_active_subscription(callback.from_user.id)

    try:
        provider = get_payment_provider()
        service = PaymentService(session, provider)
        result = await service.initiate_payment(telegram_id=callback.from_user.id)

        status_note = ""
        if has_sub:
            status_note = "ℹ️ У тебя уже есть активная подписка — дни добавятся к текущей.\n\n"

        await callback.message.edit_text(
            f"{status_note}"
            f"💳 Оплата подписки\n\n"
            f"Срок: {settings.subscription_duration_days} дней\n"
            f"Сумма: {settings.subscription_price_rub} ₽\n\n"
            "После оплаты нажми «Я оплатил».",
            reply_markup=payment_keyboard(result.confirmation_url),
        )
        await callback.answer()

    except Exception as exc:
        logger.error("Ошибка создания платежа для %d: %s", callback.from_user.id, exc)
        await callback.message.edit_text(
            "😔 Не удалось создать платёж. Попробуй позже.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()


@router.callback_query(F.data == "check_payment")
async def cb_check_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Проверяет последний незакрытый платёж пользователя.

    Ищет последний pending платёж и проверяет его статус.
    """
    from sqlalchemy import select
    from models.database import Payment, User

    user = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    result = await session.execute(
        select(Payment)
        .where(
            Payment.user_id == user.id,
            Payment.status == "pending",
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        await callback.answer(
            "Активный платёж не найден. Создай новый.",
            show_alert=True,
        )
        return

    await callback.answer("⏳ Проверяю оплату...")

    try:
        provider = get_payment_provider()
        service = PaymentService(session, provider)
        is_confirmed = await service.confirm_payment(payment.yukassa_payment_id)

        if is_confirmed:
            user = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
            date_str = user.subscription_expires_at.strftime("%d.%m.%Y")
            await callback.message.edit_text(
                f"✅ Оплата подтверждена!\n\n"
                f"Подписка активна до {date_str}.\n"
                "Теперь можешь создать подключение.",
                reply_markup=back_to_menu_keyboard(),
            )
        else:
            await callback.message.edit_text(
                "❌ Оплата не найдена.\n\n"
                "Попробуй через минуту или создай новый платёж.",
                reply_markup=payment_keyboard("#"),
            )

    except Exception as exc:
        logger.error("Ошибка проверки платежа для %d: %s", callback.from_user.id, exc)
        await callback.message.edit_text(
            "😔 Ошибка проверки платежа. Попробуй позже.",
            reply_markup=back_to_menu_keyboard(),
        )