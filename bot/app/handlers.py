import html
import logging
from contextlib import suppress
from uuid import UUID

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.api import ApiError, ShopApi

log = logging.getLogger("bot.handlers")
router = Router()
PAGE_SIZE = 5


# Всё «состояние диалога» едет внутри callback_data, FSM не используется:
# любая реплика может обработать любой апдейт.
class CatalogCb(CallbackData, prefix="c"):
    page: int = 0


class ProductCb(CallbackData, prefix="p"):
    id: UUID
    page: int = 0


class AddCb(CallbackData, prefix="a"):
    id: UUID


class RemoveCb(CallbackData, prefix="r"):
    id: UUID


def price(cents: int) -> str:
    return f"{cents // 100:,}".replace(",", " ") + f",{cents % 100:02d} ₽"


def menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Каталог", callback_data=CatalogCb(page=0))
    kb.button(text="Корзина", callback_data="cart")
    kb.adjust(2)
    return kb.as_markup()


async def show(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """Правит сообщение на месте; если это фото-карточка — шлёт новое."""
    message = call.message
    if not isinstance(message, Message):
        return
    if message.photo:
        await message.answer(text, reply_markup=markup)
    else:
        with suppress(TelegramBadRequest):  # «message is not modified»
            await message.edit_text(text, reply_markup=markup)


# --- меню --------------------------------------------------------------------------------
@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Демо-магазин. Выберите товар в каталоге, добавьте в корзину и оформите заказ. "
        "Оплаты нет — это учебный прототип.",
        reply_markup=menu_kb(),
    )


# --- каталог -----------------------------------------------------------------------------
async def render_catalog(api: ShopApi, page: int) -> tuple[str, InlineKeyboardMarkup]:
    data = await api.products(page, PAGE_SIZE)
    items, total = data["items"], data["total"]
    if not items:
        return "Каталог пуст.", menu_kb()

    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(
            text=f"{item['title']} — {price(item['price_cents'])}",
            callback_data=ProductCb(id=item["id"], page=page),
        )
    kb.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="Назад", callback_data=CatalogCb(page=page - 1).pack()))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="Дальше", callback_data=CatalogCb(page=page + 1).pack()))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="Корзина", callback_data="cart"))

    first = page * PAGE_SIZE + 1
    return f"Каталог: товары {first}–{first + len(items) - 1} из {total}", kb.as_markup()


@router.message(Command("catalog"))
async def catalog_command(message: Message, api: ShopApi) -> None:
    text, markup = await render_catalog(api, 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(CatalogCb.filter())
async def catalog_page(call: CallbackQuery, callback_data: CatalogCb, api: ShopApi) -> None:
    text, markup = await render_catalog(api, callback_data.page)
    await show(call, text, markup)
    await call.answer()


# --- карточка товара ---------------------------------------------------------------------
@router.callback_query(ProductCb.filter())
async def product_card(call: CallbackQuery, callback_data: ProductCb, api: ShopApi) -> None:
    if not isinstance(call.message, Message):
        return await call.answer()
    try:
        product = await api.product(callback_data.id)
    except ApiError as exc:
        return await call.answer(exc.detail, show_alert=True)

    caption = (
        f"<b>{html.escape(product['title'])}</b>\n{html.escape(product['description'])}\n\n"
        f"Цена: {price(product['price_cents'])}\nВ наличии: {product['stock']} шт."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="В корзину", callback_data=AddCb(id=product["id"]))
    kb.button(text="К каталогу", callback_data=CatalogCb(page=callback_data.page))
    kb.adjust(1)

    if product["image_url"]:
        photo = BufferedInputFile(await api.fetch_image(product["image_url"]), filename="product.png")
        await call.message.answer_photo(photo, caption=caption, reply_markup=kb.as_markup())
    else:
        await call.message.answer(caption, reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(AddCb.filter())
async def add_to_cart(call: CallbackQuery, callback_data: AddCb, api: ShopApi) -> None:
    try:
        await api.add_to_cart(call.from_user.id, callback_data.id)
    except ApiError as exc:
        return await call.answer(exc.detail, show_alert=True)
    await call.answer("Добавлено в корзину")


# --- корзина -----------------------------------------------------------------------------
async def render_cart(api: ShopApi, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    cart = await api.cart(user_id)
    kb = InlineKeyboardBuilder()
    if not cart["items"]:
        kb.button(text="В каталог", callback_data=CatalogCb(page=0))
        return "Корзина пуста.", kb.as_markup()

    lines = [
        f"• {html.escape(i['product']['title'])} × {i['qty']} — {price(i['subtotal_cents'])}"
        for i in cart["items"]
    ]
    text = "<b>Корзина</b>\n" + "\n".join(lines) + f"\n\n<b>Итого: {price(cart['total_cents'])}</b>"
    for i in cart["items"]:
        kb.button(text=f"Убрать: {i['product']['title'][:28]}", callback_data=RemoveCb(id=i["product"]["id"]))
    kb.button(text="Оформить заказ", callback_data="checkout")
    kb.button(text="В каталог", callback_data=CatalogCb(page=0))
    kb.adjust(1)
    return text, kb.as_markup()


@router.message(Command("cart"))
async def cart_command(message: Message, api: ShopApi) -> None:
    if message.from_user is None:
        return
    text, markup = await render_cart(api, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "cart")
async def cart_view(call: CallbackQuery, api: ShopApi) -> None:
    text, markup = await render_cart(api, call.from_user.id)
    await show(call, text, markup)
    await call.answer()


@router.callback_query(RemoveCb.filter())
async def cart_remove(call: CallbackQuery, callback_data: RemoveCb, api: ShopApi) -> None:
    await api.remove_from_cart(call.from_user.id, callback_data.id)
    text, markup = await render_cart(api, call.from_user.id)
    await show(call, text, markup)
    await call.answer("Убрано")


# --- оформление: телефон приходит кнопкой «поделиться контактом», диалоговых шагов нет ----
@router.callback_query(F.data == "checkout")
async def checkout(call: CallbackQuery) -> None:
    if isinstance(call.message, Message):
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отправить номер и оформить заказ", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await call.message.answer(
            "Нажмите кнопку ниже: номер нужен для связи по заказу. Оплаты нет — это демо.",
            reply_markup=keyboard,
        )
    await call.answer()


@router.message(F.contact)
async def place_order(message: Message, api: ShopApi) -> None:
    user, contact = message.from_user, message.contact
    if user is None or contact is None:
        return
    if contact.user_id != user.id:
        await message.answer("Отправьте, пожалуйста, свой номер.", reply_markup=ReplyKeyboardRemove())
        return
    try:
        order = await api.place_order(
            user.id,
            name=user.full_name,
            phone=contact.phone_number,
            # Повторная доставка того же апдейта (ретрай вебхука, другая реплика) не создаст дубль.
            idempotency_key=f"tg-{message.chat.id}-{message.message_id}",
        )
    except ApiError as exc:
        await message.answer(f"Не удалось оформить заказ: {html.escape(exc.detail)}", reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(
        f"Заказ <code>{order['id'][:8]}</code> оформлен на сумму {price(order['total_cents'])}. "
        "Мы свяжемся с вами по номеру из Telegram.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Что дальше?", reply_markup=menu_kb())


@router.error()
async def on_error(event: ErrorEvent) -> bool:
    log.exception("Ошибка при обработке апдейта", exc_info=event.exception)
    update = event.update
    if update.callback_query is not None:
        await update.callback_query.answer("Сервис временно недоступен", show_alert=True)
    elif update.message is not None:
        await update.message.answer("Сервис временно недоступен, попробуйте позже.")
    return True
