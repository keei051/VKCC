import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hlink
from aiogram.exceptions import TelegramBadRequest

from keyboards import (
    get_main_inline_keyboard,
    get_link_card_keyboard,
    get_stats_keyboard,
    get_delete_confirm_keyboard,
    get_rename_keyboard,
)
from database import (
    save_link,
    get_links_by_user,
    get_link_by_id,
    get_link_by_original_url,
    delete_link,
    rename_link,
    check_duplicate_link,
)
from utils import is_valid_url, format_date, format_link_stats
from vkcc import shorten_link, get_link_stats
from config import VK_TOKEN, MAX_LINKS_PER_BATCH

router = Router()
logger = logging.getLogger(__name__)

class LinkStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()
    waiting_for_mass_title = State()
    waiting_for_new_title = State()

class ThrottlingMiddleware:
    """Ограничивает частоту текстовых команд."""
    def __init__(self, rate_limit_seconds: int = 2):
        self.rate_limit = rate_limit_seconds
        self.last_requests = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        current_time = datetime.now()
        last_request = self.last_requests.get(user_id)

        if last_request and (current_time - last_request).total_seconds() < self.rate_limit:
            await event.answer(
                "❌ Слишком много запросов! Подождите пару секунд.\n\n<b>Что дальше?</b>",
                reply_markup=get_main_inline_keyboard(),
                parse_mode="HTML"
            )
            return
        self.last_requests[user_id] = current_time
        return await handler(event, data)

# Применяем middleware только к текстовым сообщениям
router.message.middleware(ThrottlingMiddleware())

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
            logger.debug(f"Сообщение не изменено: {e}")
            return None
        logger.error(f"Ошибка редактирования сообщения: {e}")
        return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при редактировании: {e}")
        return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML")

async def safe_delete(message: Message):
    try:
        await message.delete()
    except TelegramBadRequest as e:
        logger.debug(f"Не удалось удалить сообщение {message.message_id}: {e}")

async def cleanup_old_messages(bot, chat_id, message_id):
    """Удаляет сообщения старше 5 минут."""
    try:
        message = await bot.get_message(chat_id, message_id)
        if message.date < datetime.now() - timedelta(minutes=5):
            await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        logger.debug(f"Сообщение {message_id} уже удалено или недоступно")

async def process_and_save_link(url: str, title: str, message: Message, state: FSMContext) -> tuple[bool, str, str | None]:
    if not VK_TOKEN:
        return False, "❌ Ошибка: VK_TOKEN не задан.\n\n<b>Что дальше?</b>", None
    if len(title) > 100:
        return False, "❌ Ошибка: Название слишком длинное (максимум 100 символов).\n\n<b>Что дальше?</b>", None
    if not is_valid_url(url):
        return False, f"❌ Ошибка: '{url}' — невалидная ссылка.\n\n<b>Что дальше?</b>", None
    try:
        if check_duplicate_link(message.from_user.id, url):
            return False, f"❌ Ошибка: Ссылка '{url}' уже существует.\n\n<b>Что дальше?</b>", None
        
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={url}")
        short_url = await shorten_link(url, VK_TOKEN)
        if not short_url:
            return False, "❌ Ошибка: Не удалось сократить ссылку (VK API не вернул short_url).\n\n<b>Что дальше?</b>", None
        logger.info(f"Ссылка сокращена: {short_url}")
        vk_key = short_url.split("/")[-1]
        logger.info(f"Попытка сохранить ссылку: user_id={message.from_user.id}, short_url={short_url}, title={title}")
        if save_link(message.from_user.id, url, short_url, title or "Без названия", vk_key):
            return True, f"✅ Ссылка сохранена: {hlink(title or 'Ссылка', short_url)}\n\n<b>Что дальше?</b>", short_url
        return False, f"❌ Ошибка: Не удалось сохранить ссылку '{url}'.\n\n<b>Что дальше?</b>", None
    except Exception as e:
        logger.error(f"Ошибка при сокращении или сохранении ссылки: {e}")
        return False, f"❌ Ошибка: {str(e)}.\n\n<b>Что дальше?</b>", None

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

@router.callback_query(F.data == "shorten_link")
async def shorten_link_handler(callback: CallbackQuery, state: FSMContext):
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
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    await start_shorten(callback.message, state)

@router.callback_query(F.data == "show_links")
async def show_links_handler(callback: CallbackQuery, state: FSMContext):
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
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    await show_user_links(callback.message, state)

@router.callback_query(F.data == "cancel_shorten")
async def cancel_shorten_handler(callback: CallbackQuery, state: FSMContext):
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
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    await cmd_start(callback.message, state)

@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()

@router.message(F.text)
async def handle_unknown_message(message: Message):
    logger.debug(f"Необработанное сообщение от user_id={message.from_user.id}: {message.text}")
    await safe_delete(message)
    await message.answer(
        "❌ Неизвестная команда или сообщение. Используйте /start, /help или кнопки ниже.\n\n<b>Что дальше?</b>",
        reply_markup=get_main_inline_keyboard(),
        parse_mode="HTML"
    )

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
    failed = []
    for url in urls:
        if "|" in url:
            u, t = map(str.strip, url.split("|", 1))
            if len(t) > 100:
                failed.append(f"❌ Ошибка: Название для {u} слишком длинное (максимум 100 символов).")
                continue
        else:
            u, t = url.strip(), None
        if not is_valid_url(u):
            failed.append(f"❌ Ошибка: {u} — невалидная ссылка.")
            continue
        processed.append((u, t))

    if failed:
        await state.update_data(failed_links=failed)
    if not processed:
        text = "❌ Ошибка: Ни одной валидной ссылки.\n" + "\n".join(failed) + "\n\n<b>Что дальше?</b>"
        await safe_edit(message.bot, message.chat.id, initial_msg_id, text, get_main_inline_keyboard())
        await state.clear()
        return

    await state.update_data(urls=processed, initial_msg=initial_msg_id, successful_links=[])
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
        await finalize_mass_processing(message, state)
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
    success, result, short_url = await process_and_save_link(url, title, message, state)
    link = get_link_by_original_url(message.from_user.id, url)
    link_id = link[0] if link else None
    keyboard = get_main_inline_keyboard()
    if success and short_url and link_id:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="📋 Скопировать", callback_data=f"copy:{short_url}"),
            InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename:{link_id}")
        ])
    await safe_edit(message.bot, message.chat.id, initial_msg_id, result, keyboard)
    await state.clear()

@router.message(LinkStates.waiting_for_mass_title)
async def process_mass_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    current_url, current_title = data.get("current_url"), data.get("current_title")
    title = message.text.strip() if message.text else current_title or "Без названия"
    initial_msg_id = data.get("initial_msg")
    success, result, short_url = await process_and_save_link(current_url, title, message, state)
    link = get_link_by_original_url(message.from_user.id, current_url)
    link_id = link[0] if link else None

    if len(title) > 100:
        data.setdefault("failed_links", []).append(
            f"❌ Ошибка: Название для {current_url} слишком длинное (максимум 100 символов)."
        )
    else:
        if success and link_id:
            data.setdefault("successful_links", []).append({"title": title, "short_url": short_url, "link_id": link_id})
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
    partial_success = len(s) > 0

    text = f"{'✅' if partial_success else '❌'} Готово! Добавлено: {len(s)}\n"
    for i, link in enumerate(s, 1):
        text += f"{i}. {link['title']} — {hlink(link['title'], link['short_url'])}\n"
    if f:
        text += "\n❌ Ошибки:\n" + "\n".join(f)
    text += "\n<b>Что дальше?</b>"

    keyboard = get_main_inline_keyboard()
    if partial_success:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="📋 Скопировать все", callback_data="copy_all"),
            InlineKeyboardButton(text="✏️ Переименовать", callback_data="rename_mass")
        ])
    await safe_edit(message.bot, message.chat.id, initial_msg_id, text, keyboard)
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
    total_pages = max(1, len(links) // per_page + (1 if len(links) % per_page else 0))
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    current_links = links[start:end]

    keyboard = []
    for link in current_links:
        link_id, title, short_url, created_at = link
        created_str = format_date(created_at)
        keyboard.append([InlineKeyboardButton(text=f"📍 {title}", callback_data=f"link:{link_id}")])
    if total_pages > page:
        keyboard.append([InlineKeyboardButton(text="📄 Далее", callback_data=f"page:{page+1}")])
    if page > 1:
        keyboard.append([InlineKeyboardButton(text="◄ Назад", callback_data=f"page:{page-1}")])

    text = f"<b>📎 Ваши ссылки (страница {page} из {total_pages}):</b>"
    data = await state.get_data()
    last_msg_id = data.get("last_msg_id")
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except TelegramBadRequest:
            logger.debug(f"Не удалось удалить сообщение {last_msg_id}, возможно, оно уже удалено")

    new_msg = await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await state.update_data(links=links, page=page, last_msg_id=new_msg.message_id)

@router.callback_query(F.data.startswith("page:"))
async def handle_pagination(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный номер страницы", show_alert=True)
        return
    data = await state.get_data()
    links = data.get("links", get_links_by_user(callback.from_user.id))
    await send_links_page(callback.message, links, page, state)
    await callback.answer()

@router.callback_query(F.data == "back_to_links")
async def back_to_links(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    data = await state.get_data()
    links = get_links_by_user(callback.from_user.id)
    page = data.get("page", 1)
    await send_links_page(callback.message, links, page, state)
    await callback.answer()

@router.callback_query(F.data.startswith("link:"))
async def show_link_card(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    try:
        link_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный ID ссылки", show_alert=True)
        return
    user_id = callback.from_user.id
    link = get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("❌ Ошибка: Ссылка не найдена", show_alert=True)
        await callback.message.edit_text(
            "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    _, _, long_url, short_url, title, vk_key, created_at = link
    created_str = format_date(created_at)
    stats = await get_link_stats(vk_key, VK_TOKEN)
    views = stats.get("views", 0)

    text = (
        f"📍 {title}\n"
        f"🔗 <a href='{short_url}'>Короткая ссылка</a>\n"
        f"🌐 <a href='{long_url}'>Исходная ссылка</a>\n"
        f"📆 {created_str}\n"
        f"👁 {views} переходов"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_link_card_keyboard(link_id),
        parse_mode="HTML"
    )
    await state.update_data(card_msg_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("stats:"))
async def show_stats(callback: CallbackQuery):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    try:
        link_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный ID ссылки", show_alert=True)
        return
    user_id = callback.from_user.id
    link = get_link_by_id(link_id, user_id)
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
    text = f"📊 Статистика по {hlink(short_url, short_url)}\n{format_link_stats(stats, short_url)}"
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_from_stats")
async def back_from_stats(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    data = await state.get_data()
    links = get_links_by_user(callback.from_user.id)
    page = data.get("page", 1)
    await send_links_page(callback.message, links, page, state)
    await callback.answer()

@router.callback_query(F.data.startswith("rename:"))
async def ask_new_title(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    try:
        link_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный ID ссылки", show_alert=True)
        return
    await state.set_state(LinkStates.waiting_for_new_title)
    await state.update_data(rename_link_id=link_id)
    await callback.message.answer("✏️ Введите новое название ссылки:", reply_markup=get_rename_keyboard(link_id))
    await callback.answer()

@router.callback_query(F.data.startswith("copy:"))
async def copy_link(callback: CallbackQuery):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    short_url = callback.data.split(":", 1)[1]
    await callback.message.answer(
        f"🔗 Ваша ссылка: {hlink(short_url, short_url)}\n\nСкопируйте её вручную.\n\n<b>Что дальше?</b>",
        reply_markup=get_main_inline_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rename_single:"))
async def rename_single_link(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    try:
        link_id = int(callback.data.split(":", 2)[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный ID ссылки", show_alert=True)
        await callback.message.edit_text(
            "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    await state.set_state(LinkStates.waiting_for_new_title)
    await state.update_data(rename_link_id=link_id)
    await callback.message.answer("✏️ Введите новое название ссылки:", reply_markup=get_rename_keyboard(link_id))
    await callback.answer()

@router.callback_query(F.data == "copy_all")
async def copy_all_links(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    data = await state.get_data()
    successful_links = data.get("successful_links", [])
    if not successful_links:
        await callback.message.edit_text(
            "❌ Ошибка: Нет ссылок для копирования.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    text = "📋 Скопируйте ссылки:\n"
    for i, link in enumerate(successful_links, 1):
        text += f"{i}. {link['title']} — {link['short_url']}\n"
    text += "\n<b>Что дальше?</b>"
    await callback.message.edit_text(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "rename_mass")
async def rename_mass_links(callback: CallbackQuery, state: FSMContext):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    data = await state.get_data()
    successful_links = data.get("successful_links", [])
    if not successful_links:
        await callback.message.edit_text(
            "❌ Ошибка: Нет ссылок для переименования.\n\n<b>Что дальше?</b>",
            reply_markup=get_main_inline_keyboard(),
            parse_mode="HTML"
        )
        return
    await state.set_state(LinkStates.waiting_for_mass_title)
    await state.update_data(
        urls=[(link["short_url"], link["title"], link["link_id"]) for link in successful_links],
        current_url=successful_links[0]["short_url"],
        current_title=successful_links[0]["title"],
        successful_links=[],
        failed_links=data.get("failed_links", [])
    )
    await callback.message.answer(
        f"✏️ Введите новое название для {successful_links[0]['short_url']} (или оставьте пустым).",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_shorten")]
        ])
    )
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
    if rename_link(link_id, user_id, new_title):
        link = get_link_by_id(link_id, user_id)
        if link:
            _, _, long_url, short_url, _, vk_key, created_at = link
            created_str = format_date(created_at)
            stats = await get_link_stats(vk_key, VK_TOKEN)
            views = stats.get("views", 0)
            text = (
                f"✅ Название обновлено!\n"
                f"📍 {new_title}\n"
                f"🔗 <a href='{short_url}'>Короткая ссылка</a>\n"
                f"🌐 <a href='{long_url}'>Исходная ссылка</a>\n"
                f"📆 {created_str}\n"
                f"👁 {views} переходов\n\n<b>Что дальше?</b>"
            )
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=card_msg_id,
                    text=text,
                    reply_markup=get_link_card_keyboard(link_id),
                    parse_mode="HTML"
                )
            except TelegramBadRequest as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                await message.answer(
                    text,
                    reply_markup=get_link_card_keyboard(link_id),
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

@router.callback_query(F.data.startswith("delete:"))
async def confirm_delete(callback: CallbackQuery):
    await cleanup_old_messages(callback.bot, callback.message.chat.id, callback.message.message_id)
    parts = callback.data.split(":")
    try:
        action = parts[1]
        link_id = int(parts[2]) if len(parts) > 2 else int(parts[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный ID ссылки", show_alert=True)
        return
    user_id = callback.from_user.id

    if action == "yes":
        await callback.message.answer("Удаляю ссылку...")
        if delete_link(link_id, user_id):
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
    elif action == "no":
        link = get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("❌ Ошибка: Ссылка не найдена", show_alert=True)
            await callback.message.edit_text(
                "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
                reply_markup=get_main_inline_keyboard(),
                parse_mode="HTML"
            )
            return
        _, _, long_url, short_url, title, vk_key, created_at = link
        created_str = format_date(created_at)
        stats = await get_link_stats(vk_key, VK_TOKEN)
        views = stats.get("views", 0)
        text = (
            f"📍 {title}\n"
            f"🔗 <a href='{short_url}'>Короткая ссылка</a>\n"
            f"🌐 <a href='{long_url}'>Исходная ссылка</a>\n"
            f"📆 {created_str}\n"
            f"👁 {views} переходов"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_link_card_keyboard(link_id),
            parse_mode="HTML"
        )
    else:
        link = get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("❌ Ошибка: Ссылка не найдена", show_alert=True)
            await callback.message.edit_text(
                "❌ Ошибка: Ссылка не найдена.\n\n<b>Что дальше?</b>",
                reply_markup=get_main_inline_keyboard(),
                parse_mode="HTML"
            )
            return
        _, _, long_url, short_url, title, vk_key, created_at = link
        created_str = format_date(created_at)
        stats = await get_link_stats(vk_key, VK_TOKEN)
        views = stats.get("views", 0)
        text = (
            f"📍 {title}\n"
            f"🔗 <a href='{short_url}'>Короткая ссылка</a>\n"
            f"🌐 <a href='{long_url}'>Исходная ссылка</a>\n"
            f"📆 {created_str}\n"
            f"👁 {views} переходов\n\n<b>Подтвердите удаление:</b>"
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_delete_confirm_keyboard(link_id),
            parse_mode="HTML"
        )
    await callback.answer()

def setup_handlers(dp):
    dp.include_router(router)
