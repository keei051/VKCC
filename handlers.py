from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.markdown import hlink
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime

from keyboards import (
    get_main_inline_keyboard,
    get_restart_keyboard,
    get_link_card_keyboard,
    get_stats_keyboard,
    get_delete_confirm_keyboard,
    get_rename_keyboard,
)
from database import save_link, get_links_by_user, get_link_by_id, delete_link, rename_link
from utils import is_valid_url, safe_delete, format_link_stats
from vkcc import shorten_link, get_link_stats
from config import VK_TOKEN, MAX_LINKS_PER_BATCH
import logging
import math

router = Router()
logger = logging.getLogger(__name__)

class LinkStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()
    waiting_for_mass_title = State()
    waiting_for_new_title = State()

# Универсальная защита редактирования сообщений
async def safe_edit(bot, chat_id, message_id, text, reply_markup=None):
    try:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug(f"Сообщение не изменено, игнорируем: {e}")
            return None
        logger.error(f"Ошибка редактирования сообщения: {e}")
        return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при редактировании сообщения: {e}")
        return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML")

async def process_and_save_link(url: str, title: str, message: Message, state: FSMContext) -> tuple[bool, str]:
    if not VK_TOKEN:
        raise RuntimeError("VK_TOKEN не задан!")
    if len(title) > 100:
        return False, "Слишком длинное название (максимум 100 символов)."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={url}")
        short_url = await shorten_link(url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        vk_key = short_url.split("/")[-1]
        logger.info(f"Попытка сохранить ссылку: user_id={message.from_user.id}, short_url={short_url}, title={title}")
        if await save_link(message.from_user.id, url, short_url, title or "Без названия", vk_key):
            return True, short_url
        else:
            return False, f"Ссылка '{url}' уже существует."
    except Exception as e:
        logger.error(f"Ошибка при сокращении или сохранении ссылки: {e}")
        return False, str(e)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запуск команды /start для user_id={message.from_user.id}")
    user_name = message.from_user.first_name or "пользователь"
    await message.answer(
        f"Привет, {user_name}! Добро пожаловать в vkcc-link-bot — ваш инструмент для работы со ссылками. Выберите действие ниже.",
        reply_markup=get_main_inline_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()

@router.message(F.text.lower().strip() == "сократить ссылку")
async def start_shorten(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Пользователь {message.from_user.id} начал сокращение ссылки")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_shorten")]
    ])
    msg = await message.answer("Введите ссылки (до 50, каждая с новой строки).", reply_markup=keyboard)
    await state.update_data(initial_msg=msg.message_id)
    await state.set_state(LinkStates.waiting_for_url)

@router.callback_query(F.data == "dummy_shorten")
async def dummy_shorten_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not callback.message:
        logger.error("Сообщение для callback отсутствует")
        await callback.bot.send_message(callback.from_user.id, "Ошибка: сообщение недоступно. Попробуйте снова.", parse_mode="HTML")
        return
    await start_shorten(callback.message, state)

@router.callback_query(F.data == "dummy_links")
async def dummy_links_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not callback.message:
        logger.error("Сообщение для callback отсутствует")
        await callback.bot.send_message(callback.from_user.id, "Ошибка: сообщение недоступно. Попробуйте снова.", parse_mode="HTML")
        return
    await show_user_links(callback.message, state)

@router.callback_query(F.data == "cancel_shorten")
async def dummy_restart_handler(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await callback.answer("Вы вернулись в главное меню.")
    if not callback.message:
        logger.error("Сообщение для callback отсутствует")
        await callback.bot.send_message(callback.from_user.id, "Вы вернулись в главное меню.", reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
        await state.clear()
        return
    await cmd_start(callback.message, state)

@router.message(LinkStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    initial_msg_id = data.get("initial_msg")
    try:
        await safe_edit(message.bot, message.chat.id, initial_msg_id, "Проверяю ссылки...")
    except TelegramBadRequest:
        logger.error(f"Сообщение {initial_msg_id} недоступно для редактирования.")
        msg = await message.answer("Проверяю ссылки...")
        await state.update_data(initial_msg=msg.message_id)
        initial_msg_id = msg.message_id
    urls = [line.strip() for line in message.text.split("\n") if line.strip()]

    if not urls:
        await safe_edit(message.bot, message.chat.id, initial_msg_id, "Ошибка: ни одной ссылки.\n\n<b>Что дальше?</b>", get_main_inline_keyboard())
        await state.clear()
        return
    if len(urls) > MAX_LINKS_PER_BATCH:
        await safe_edit(message.bot, message.chat.id, initial_msg_id, f"Лимит: {MAX_LINKS_PER_BATCH} ссылок.\n\n<b>Что дальше?</b>", get_main_inline_keyboard())
        await state.clear()
        return

    processed = []
    for url in urls:
        if "|" in url:
            u, t = map(str.strip, url.split("|", 1))
        else:
            u, t = url.strip(), None
        if not is_valid_url(u):
            await safe_edit(message.bot, message.chat.id, initial_msg_id, f"Ошибка: {u} — невалидная ссылка.\n\n<b>Что дальше?</b>", get_main_inline_keyboard())
            await state.clear()
            return
        processed.append((u, t))

    await state.update_data(urls=processed, initial_msg=initial_msg_id)
    if len(processed) == 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_shorten")]
        ])
        await safe_edit(message.bot, message.chat.id, initial_msg_id, f"Введите описание для {processed[0][0]} (или оставьте пустым).", keyboard)
        await state.set_state(LinkStates.waiting_for_title)
    else:
        await state.set_state(LinkStates.waiting_for_mass_title)
        await process_mass_urls(message, state)

async def process_mass_urls(message: Message, state: FSMContext):
    data = await state.get_data()
    urls = data.get("urls", [])
    initial_msg_id = data.get("initial_msg")
    if not urls:
        await safe_edit(message.bot, message.chat.id, initial_msg_id, "Ошибка: список пуст.\n\n<b>Что дальше?</b>", get_main_inline_keyboard())
        await state.clear()
        return
    current_url, current_title = urls[0]
    await state.update_data(
        current_url=current_url,
        current_title=current_title,
        urls=urls[1:],
        successful_links=data.get("successful_links", []),
        failed_links=data.get("failed_links", [])
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_shorten")]
    ])
    await safe_edit(message.bot, message.chat.id, initial_msg_id, f"Сокращаю: {current_url}", keyboard)

@router.message(LinkStates.waiting_for_title)
async def process_single_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    url, _ = data.get("urls", [(None, None)])[0]
    title = message.text.strip() if message.text else "Без названия"
    initial_msg_id = data.get("initial_msg")
    success, result = await process_and_save_link(url, title, message, state)
    await safe_edit(message.bot, message.chat.id, initial_msg_id, f"Готово ✅\n{result}\n\n<b>Что дальше?</b>", get_restart_keyboard())
    await state.clear()

@router.message(LinkStates.waiting_for_mass_title)
async def process_mass_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    current_url, current_title = data.get("current_url"), data.get("current_title")
    title = message.text.strip() if message.text else current_title or "Без названия"
    initial_msg_id = data.get("initial_msg")

    success, result = await process_and_save_link(current_url, title, message, state)
    if success:
        data.setdefault("successful_links", []).append({"title": title, "short_url": result})
    else:
        data.setdefault("failed_links", []).append(f"{current_url}: {result}")

    await state.update_data(successful_links=data["successful_links"], failed_links=data["failed_links"])

    if data.get("urls"):
        await process_mass_urls(message, state)
    else:
        await finalize_mass_processing(message, state)

async def finalize_mass_processing(message: Message, state: FSMContext):
    data = await state.get_data()
    initial_msg_id = data.get("initial_msg")
    s = data.get("successful_links", [])
    f = data.get("failed_links", [])

    text = f"Готово ✅\nДобавлено: {len(s)}\n"
    for i, link in enumerate(s, 1):
        text += f"{i}. {link['title']} — {hlink(link['short_url'], link['short_url'])}\n"
    if f:
        text += "\nОшибки:\n" + "\n".join(f)
    text += "\n<b>Что дальше?</b>"

    await safe_edit(message.bot, message.chat.id, initial_msg_id, text, get_restart_keyboard())
    await state.clear()

@router.message(F.text.lower().strip() == "мои ссылки")
async def show_user_links(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запрос списка ссылок для user_id={message.from_user.id}")
    links = get_links_by_user(message.from_user.id)  # Убрано await
    if not links:
        await message.answer("У вас пока нет сохранённых ссылок.\n\n<b>Что дальше?</b>", reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
        return
    await state.update_data(links=links, page=1)
    await send_links_page(message, links, 1)

async def send_links_page(message: Message, links, page):
    per_page = 5
    total_pages = math.ceil(len(links) / per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    current_links = links[start:end]

    keyboard = []
    for link in current_links:
        link_id, title, short_url, created_at = link
        created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")
        keyboard.append([InlineKeyboardButton(text=f"📍 {title}", callback_data=f"link_{link_id}")])
    if total_pages > 1:
        keyboard.append(get_pagination_keyboard(page, total_pages)[0])

    text = "<b>📎 Ваши ссылки:</b>"
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("link_"))
async def show_link_card(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
        return
    _, _, long_url, short_url, title, vk_key, created_at = link
    created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")
    stats = await get_link_stats(vk_key, VK_TOKEN)
    views = stats.get("views", 0)

    text = (
        f"📍 {title}\n"
        f"🔗 <a href='{short_url}'>Открыть ссылку</a>\n"
        f"📆 {created_str}\n"
        f"👁 {views} переходов"
    )
    keyboard = get_link_card_keyboard(link_id, title, long_url, short_url, created_at)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.update_data(card_msg_id=callback.message.message_id)

@router.callback_query(F.data.startswith("stats_"))
async def show_stats(callback: CallbackQuery):
    link_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
        return
    _, _, _, short_url, _, vk_key, _ = link
    stats = await get_link_stats(vk_key, VK_TOKEN)
    text = f"Статистика по {short_url}\n" + format_link_stats(stats, short_url)
    keyboard = get_stats_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "back_from_stats")
async def back_from_stats(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("page", 1)
    links = get_links_by_user(callback.from_user.id)  # Убрано await
    await state.update_data(links=links, page=page)
    await send_links_page(callback.message, links, page)

@router.callback_query(F.data.startswith("rename_"))
async def ask_new_title(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    await state.set_state(LinkStates.waiting_for_new_title)
    await state.update_data(rename_link_id=link_id)
    await callback.message.answer("Введите новое название ссылки.", reply_markup=ReplyKeyboardRemove())

@router.message(LinkStates.waiting_for_new_title)
async def set_new_title(message: Message, state: FSMContext):
    await safe_delete(message)
    new_title = message.text.strip()
    data = await state.get_data()
    link_id = data.get("rename_link_id")
    card_msg_id = data.get("card_msg_id")
    user_id = message.from_user.id
    if not new_title or len(new_title) > 100:
        await message.answer("Ошибка: название не может быть пустым или длиннее 100 символов. Попробуйте снова.")
        return
    await message.answer("Обновляю название...")
    if await rename_link(link_id, user_id, new_title):
        link = await get_link_by_id(link_id, user_id)
        if link:
            _, _, long_url, short_url, _, vk_key, created_at = link
            created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")
            stats = await get_link_stats(vk_key, VK_TOKEN)
            views = stats.get("views", 0)
            text = (
                f"📍 {new_title}\n"
                f"🔗 <a href='{short_url}'>Открыть ссылку</a>\n"
                f"📆 {created_str}\n"
                f"👁 {views} переходов\n\n<b>Что дальше?</b>"
            )
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=card_msg_id,
                    text=text,
                    reply_markup=get_link_card_keyboard(link_id, new_title, long_url, short_url, created_at),
                    parse_mode="HTML"
                )
            except TelegramBadRequest as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                await message.answer(text, reply_markup=get_link_card_keyboard(link_id, new_title, long_url, short_url, created_at), parse_mode="HTML")
    else:
        await message.answer("Ошибка: не удалось обновить название.\n\n<b>Что дальше?</b>", reply_markup=get_restart_keyboard())
    await state.clear()

@router.callback_query(F.data.startswith("delete_"))
async def confirm_delete(callback: CallbackQuery):
    parts = callback.data.split("_")
    if parts[1] == "yes":
        link_id = int(parts[2])
        user_id = callback.from_user.id
        await callback.message.answer("Удаляю ссылку...")
        try:
            await callback.message.delete()
            await callback.message.answer("✅ Ссылка удалена.\n\n<b>Что дальше?</b>", reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка удаления сообщения: {e}")
            await callback.message.answer("✅ Ссылка удалена.\n\n<b>Что дальше?</b>", reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
        if not await delete_link(link_id, user_id):
            await callback.answer("Ошибка удаления ссылки", show_alert=True)
    elif parts[1] == "no":
        link_id = int(parts[2])
        user_id = callback.from_user.id
        link = await get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
            return
        _, _, long_url, short_url, title, vk_key, created_at = link
        created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")
        stats = await get_link_stats(vk_key, VK_TOKEN)
        views = stats.get("views", 0)
        text = (
            f"📍 {title}\n"
            f"🔗 <a href='{short_url}'>Открыть ссылку</a>\n"
            f"📆 {created_str}\n"
            f"👁 {views} переходов"
        )
        await callback.message.edit_text(text, reply_markup=get_link_card_keyboard(link_id, title, long_url, short_url, created_at), parse_mode="HTML")
    else:
        link_id = int(parts[1])
        user_id = callback.from_user.id
        link = await get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
            return
        _, _, long_url, short_url, title, vk_key, created_at = link
        created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")
        stats = await get_link_stats(vk_key, VK_TOKEN)
        views = stats.get("views", 0)
        text = (
            f"📍 {title}\n"
            f"🔗 <a href='{short_url}'>Открыть ссылку</a>\n"
            f"📆 {created_str}\n"
            f"👁 {views} переходов"
        )
        await callback.message.edit_text(text, reply_markup=get_delete_confirm_keyboard(link_id, title, short_url), parse_mode="HTML")

def setup_handlers(dp):
    dp.include_router(router)
