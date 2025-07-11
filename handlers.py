from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.utils.markdown import hlink
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime

from keyboards import (
    get_main_inline_keyboard,
    get_link_card_keyboard,
    get_stats_keyboard,
    get_delete_confirm_keyboard,
    get_rename_keyboard,
)
from database import save_link, get_links_by_user, get_link_by_id, delete_link, rename_link, check_duplicate_link
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
        return False, "❌ Ошибка: VK_TOKEN не задан.\n\n<b>Что дальше?</b>"
    if len(title) > 100:
        return False, "❌ Ошибка: Название слишком длинное (максимум 100 символов).\n\n<b>Что дальше?</b>"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        # Проверка дубликата ссылки
        if check_duplicate_link(message.from_user.id, url):
            return False, f"❌ Ошибка: Ссылка '{url}' уже существует.\n\n<b>Что дальше?</b>"
        
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={url}")
        short_url = await shorten_link(url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        vk_key = short_url.split("/")[-1]
        logger.info(f"Попытка сохранить ссылку: user_id={message.from_user.id}, short_url={short_url}, title={title}")
        if await save_link(message.from_user.id, url, short_url, title or "Без названия", vk_key):
            return True, f"✅ Ссылка сохранена: {hlink(short_url, short_url)}\n\n<b>Что дальше?</b>"
        else:
            return False, f"❌ Ошибка: Не удалось сохранить ссылку '{url}'.\n\n<b>Что дальше?</b>"
    except Exception as e:
        logger.error(f"Ошибка при сокращении или сохранении ссылки: {e}")
        return False, f"❌ Ошибка: {str(e)}.\n\n<b>Что дальше?</b>"

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запуск команды /start для user_id={message.from_user.id}")
    user_name = message.from_user.first_name or "пользователь"
    await message.answer(
        f"Привет, {user_name}! Добро пожаловать в vkcc-link-bot — твой инструмент для сокращения ссылок.\n\n<b>Что дальше?</b>",
        reply_markup=get_main_inline_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()

@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запрос помощи для user_id={message.from_user.id}")
    await message.answer(
        "📚 Помощь по vkcc-link-bot:\n"
        "➖ /start — Начать работу с ботом\n"
        "➖ 'Сократить ссылку' — Сократить одну или до 50 ссылок\n"
        "➖ 'Мои ссылки' — Показать список ваших ссылок\n\n"
        "<b>Что дальше?</b>",
        reply_markup=get_main_inline_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()

@router.message(F.text.lower().strip() == "сократить ссылку")
async def start_shorten(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Пользователь {message.from_user.id} начал сокращение ссылки")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_shorten")]
    ])
    msg = await message.answer(
        "Введите ссылки (до 50, каждая с новой строки, можно с описанием: ссылка | описание).",
        reply_markup=keyboard
    )
    await state.update_data(initial_msg=msg.message_id)
    await state.set_state(LinkStates.waiting_for_url)

@router.callback_query(F.data == "dummy_shorten")
async def dummy_shorten_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not callback.message:
        logger.error("Сообщение для callback отсутствует")
        await callback.bot.send_message(
            callback.from_user.id,
            "❌ Ошибка: Сообщение недоступно.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    await start_shorten(callback.message, state)

@router.callback_query(F.data == "dummy_links")
async def dummy_links_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not callback.message:
        logger.error("Сообщение для callback отсутствует")
        await callback.bot.send_message(
            callback.from_user.id,
            "❌ Ошибка: Сообщение недоступно.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    await show_user_links(callback.message, state)

@router.callback_query(F.data == "cancel_shorten")
async def dummy_restart_handler(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await callback.answer("Вы вернулись в главное меню.")
    if not callback.message:
        logger.error("Сообщение для callback отсутствует")
        await callback.bot.send_message(
            callback.from_user.id,
            "Вы вернулись в главное меню.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
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
        await safe_edit(
            message.bot, message.chat.id, initial_msg_id,
            "❌ Ошибка: Ни одной ссылки.\n\n<b>Что дальше?</b>",
            get_main_inline_keyboard()
        )
        await state.clear()
        return
    if len(urls) > MAX_LINKS_PER_BATCH:
        await safe_edit(
            message.bot, message.chat.id, initial_msg_id,
            f"❌ Ошибка: Лимит — {MAX_LINKS_PER_BATCH} ссылок.\n\n<b>Что дальше?</b>",
            get_main_inline_keyboard()
        )
        await state.clear()
        return

    processed = []
    for url in urls:
        if "|" in url:
            u, t = map(str.strip, url.split("|", 1))
            if len(t) > 100:
                await safe_edit(
                    message.bot, message.chat.id, initial_msg_id,
                    f"❌ Ошибка: Название для {u} слишком длинное (максимум 100 символов).\n\n<b>Что дальше?</b>",
                    get_main_inline_keyboard()
                )
                await state.clear()
                return
        else:
            u, t = url.strip(), None
        if not is_valid_url(u):
            await safe_edit(
                message.bot, message.chat.id, initial_msg_id,
                f"❌ Ошибка: {u} — невалидная ссылка.\n\n<b>Что дальше?</b>",
                get_main_inline_keyboard()
            )
            await state.clear()
            return
        processed.append((u, t))

    await state.update_data(urls=processed, initial_msg=initial_msg_id)
    if len(processed) == 1:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_shorten")]
        ])
        await safe_edit(
            message.bot, message.chat.id, initial_msg_id,
            f"Введите описание для {processed[0][0]} (или оставьте пустым).",
            keyboard
        )
        await state.set_state(LinkStates.waiting_for_title)
    else:
        await state.set_state(LinkStates.waiting_for_mass_title)
        await process_mass_urls(message, state)

async def process_mass_urls(message: Message, state: FSMContext):
    data = await state.get_data()
    urls = data.get("urls", [])
    initial_msg_id = data.get("initial_msg")
    if not urls:
        await safe_edit(
            message.bot, message.chat.id, initial_msg_id,
            "❌ Ошибка: Список пуст.\n\n<b>Что дальше?</b>",
            get_main_inline_keyboard()
        )
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
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_shorten")]
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
    await safe_edit(message.bot, message.chat.id, initial_msg_id, result, get_main_inline_keyboard())
    await state.clear()

@router.message(LinkStates.waiting_for_mass_title)
async def process_mass_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    current_url, current_title = data.get("current_url"), data.get("current_title")
    title = message.text.strip() if message.text else current_title or "Без названия"
    initial_msg_id = data.get("initial_msg")

    if len(title) > 100:
        await safe_edit(
            message.bot, message.chat.id, initial_msg_id,
            f"❌ Ошибка: Название для {current_url} слишком длинное (максимум 100 символов).\n\n<b>Что дальше?</b>",
            get_main_inline_keyboard()
        )
        await state.clear()
        return

    success, result = await process_and_save_link(current_url, title, message, state)
    if success:
        # Извлекаем short_url из result, убирая HTML и "Что дальше?"
        short_url = result.split("✅ Ссылка сохранена: ")[1].split("\n\n<b>Что дальше?</b>")[0].split(">")[1].split("</a")[0]
        data.setdefault("successful_links", []).append({"title": title, "short_url": short_url})
    else:
        data.setdefault("failed_links", []).append(result)

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

    text = f"✅ Готово! Добавлено: {len(s)}\n"
    for i, link in enumerate(s, 1):
        text += f"{i}. {link['title']} — {hlink(link['title'], link['short_url'])}\n"
    if f:
        text += "\n❌ Ошибки:\n" + "\n".join(f)
    text += "\n<b>Что дальше?</b>"

    await safe_edit(message.bot, message.chat.id, initial_msg_id, text, get_main_inline_keyboard())
    await state.clear()

@router.message(F.text.lower().strip() == "мои ссылки")
async def show_user_links(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запрос списка ссылок для user_id={message.from_user.id}")
    links = get_links_by_user(message.from_user.id)
    if not links:
        await message.answer(
            "У вас пока нет сохранённых ссылок.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    await state.update_data(links=links, page=1, last_msg_id=None)
    await send_links_page(message, links, 1, state)

async def send_links_page(message: Message, links, page, state: FSMContext):
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
    if total_pages > page:
        keyboard.append([InlineKeyboardButton(text="📄 Ещё", callback_data=f"page_{page+1}")])
    elif page > 1:
        keyboard.append(get_pagination_keyboard(page, total_pages)[0])

    text = "<b>📎 Ваши ссылки:</b>"
    data = await state.get_data()
    last_msg_id = data.get("last_msg_id")
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except TelegramBadRequest:
            logger.debug(f"Не удалось удалить сообщение {last_msg_id}, возможно, оно уже удалено")

    new_msg = await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await state.update_data(links=links, page=page, last_msg_id=new_msg.message_id)

@router.callback_query(F.data.startswith("page_"))
async def handle_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    data = await state.get_data()
    links = data.get("links", get_links_by_user(callback.from_user.id))
    await send_links_page(callback.message, links, page, state)
    await callback.answer()

@router.callback_query(F.data == "back_to_links")
async def back_to_links(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    links = get_links_by_user(callback.from_user.id)
    page = data.get("page", 1)
    await send_links_page(callback.message, links, page, state)
    await callback.answer()

@router.callback_query(F.data.startswith("link_"))
async def show_link_card(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("❌ Ошибка: Ссылка не найдена", show_alert=True)
        await callback.message.edit_text(
            "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
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
    await callback.message.edit_text(
        text,
        reply_markup=get_link_card_keyboard(link_id, title, long_url, short_url, created_at),
        parse_mode="HTML"
    )
    await state.update_data(card_msg_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("stats_"))
async def show_stats(callback: CallbackQuery):
    link_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("❌ Ошибка: Ссылка не найдена", show_alert=True)
        await callback.message.edit_text(
            "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    _, _, _, short_url, _, vk_key, _ = link
    stats = await get_link_stats(vk_key, VK_TOKEN)
    text = f"📊 Статистика по {hlink(short_url, short_url)}\n" + format_link_stats(stats, short_url)
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_from_stats")
async def back_from_stats(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    links = get_links_by_user(callback.from_user.id)
    page = data.get("page", 1)
    await send_links_page(callback.message, links, page, state)
    await callback.answer()

@router.callback_query(F.data.startswith("rename_"))
async def ask_new_title(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    await state.set_state(LinkStates.waiting_for_new_title)
    await state.update_data(rename_link_id=link_id)
    await callback.message.answer("Введите новое название ссылки.", reply_markup=get_rename_keyboard(link_id))
    await callback.answer()

@router.message(LinkStates.waiting_for_new_title)
async def set_new_title(message: Message, state: FSMContext):
    await safe_delete(message)
    new_title = message.text.strip()
    data = await state.get_data()
    link_id = data.get("rename_link_id")
    card_msg_id = data.get("card_msg_id")
    user_id = message.from_user.id
    if not new_title or len(new_title) > 100:
        await message.answer(
            "❌ Ошибка: Название не может быть пустым или длиннее 100 символов.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        await state.clear()
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
                f"✅ Название обновлено!\n"
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
                await message.answer(
                    text,
                    reply_markup=get_link_card_keyboard(link_id, new_title, long_url, short_url, created_at),
                    parse_mode="HTML"
                )
        else:
            await message.answer(
                "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
                reply_markup=get_main_inline_keyboard(),
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ Ошибка: Не удалось обновить название.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
    await state.clear()

@router.callback_query(F.data.startswith("delete_"))
async def confirm_delete(callback: CallbackQuery):
    parts = callback.data.split("_")
    if parts[1] == "yes":
        link_id = int(parts[2])
        user_id = callback.from_user.id
        await callback.message.answer("Удаляю ссылку...")
        if await delete_link(link_id, user_id):
            try:
                await callback.message.delete()
                await callback.message.answer(
                    "✅ Ссылка удалена.\n\n<b>Что дальше?</b>",
                    reply_markup=get_main_inline_keyboard(),
                    parse_mode="HTML"
                )
            except TelegramBadRequest as e:
                logger.error(f"Ошибка удаления сообщения: {e}")
                await callback.message.answer(
                    "✅ Ссылка удалена.\n\n<b>Что дальше?</b>",
                    reply_markup=get_main_inline_keyboard(),
                    parse_mode="HTML"
                )
        else:
            await callback.message.edit_text(
                "❌ Ошибка: Не удалось удалить ссылку.\n\n<b>Что дальше?</b>",
                reply_markup=get_main_inline_keyboard(),
                parse_mode="HTML"
            )
        await callback.answer()
    elif parts[1] == "no":
        link_id = int(parts[2])
        user_id = callback.from_user.id
        link = await get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("❌ Ошибка: Ссылка не найдена", show_alert=True)
            await callback.message.edit_text(
                "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
                reply_markup=get_main_inline_keyboard(),
                parse_mode="HTML"
            )
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
        await callback.message.edit_text(
            text,
            reply_markup=get_link_card_keyboard(link_id, title, long_url, short_url, created_at),
            parse_mode="HTML"
        )
        await callback.answer()
    else:
        link_id = int(parts[1])
        user_id = callback.from_user.id
        link = await get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("❌ Ошибка: Ссылка не найдена", show_alert=True)
            await callback.message.edit_text(
                "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
                reply_markup=get_main_inline_keyboard(),
                parse_mode="HTML"
            )
            return
        _, _, long_url, short_url, title, vk_key, created_at = link
        created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")
        stats = await get_link_stats(vk_key, VK_TOKEN)
        views = stats.get("views", 0)
        text = (
            f"📍 {title}\n"
            f"🔗 <a href='{short_url}'>Открыть ссылку</a>\n"
            f"📆 {created_str}\n"
            f"👁 {views} переходов\n\n<b>Подтвердите удаление:</b>"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_delete_confirm_keyboard(link_id, title, short_url),
            parse_mode="HTML"
        )
        await callback.answer()

def setup_handlers(dp):
    dp.include_router(router)
