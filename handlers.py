from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.markdown import hlink

from keyboards import (
    get_main_keyboard,
    get_link_list_keyboard,
    get_link_card_keyboard,
    get_stats_keyboard,
    get_delete_confirm_keyboard,
    get_rename_keyboard,
    get_restart_keyboard,
)
from database import save_link, get_links_by_user, get_link_by_id, delete_link, rename_link
from utils import is_valid_url, safe_delete, format_link_stats
from vkcc import shorten_link, get_link_stats
from config import VK_TOKEN, MAX_LINKS_PER_BATCH
import logging
import math
import traceback

router = Router()
logger = logging.getLogger(__name__)

class LinkStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()
    waiting_for_mass_title = State()
    waiting_for_new_title = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запуск команды /start для user_id={message.from_user.id}")
    user_name = message.from_user.first_name or "пользователь"
    await message.answer(
        f"Привет, {user_name}. Это бот vkcc-link-bot. Я умею:\n"
        "- Сократить до 50 ссылок с описанием.\n"
        "- Показать и управлять твоим списком ссылок.",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@router.message(F.text == "Сократить ссылку")
async def start_shorten(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Пользователь {message.from_user.id} начал сокращение ссылки")
    msg = await message.answer("Жду твои ссылки... Введи одну или несколько (до 50) через новые строки. Можно добавить описание через `|`, например: https://site.com | Сайт.", reply_markup=ReplyKeyboardRemove())
    await state.update_data(initial_msg=msg.message_id)
    await state.set_state(LinkStates.waiting_for_url)

@router.message(LinkStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    initial_msg_id = data.get("initial_msg")
    initial_msg = await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=initial_msg_id,
        text="Проверяю твои ссылки..."
    )
    await state.update_data(initial_msg=initial_msg.message_id)
    urls = [line.strip() for line in message.text.split("\n") if line.strip()]
    if len(urls) > MAX_LINKS_PER_BATCH:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg.message_id,
            text=f"Слишком много! Максимум {MAX_LINKS_PER_BATCH} ссылок. Разделите ввод.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    if not urls:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg.message_id,
            text="Ошибка: не указана ни одна ссылка. Попробуй снова.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    processed_urls = []
    for url in urls:
        if "|" in url:
            url_part, title = [part.strip() for part in url.split("|", 1)]
        else:
            url_part, title = url.strip(), None
        if not is_valid_url(url_part):
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=initial_msg.message_id,
                text=f"Ошибка: строка '{url}' не является корректной ссылкой.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return
        if not url_part.startswith(("http://", "https://")):
            url_part = "https://" + url_part
        processed_urls.append((url_part, title))
    
    await state.update_data(urls=processed_urls, initial_msg=initial_msg.message_id)
    if len(processed_urls) == 1:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg.message_id,
            text=f"Жду описание для ссылки '{processed_urls[0][0]}' (или оставь пустым)."
        )
        await state.set_state(LinkStates.waiting_for_title)
    else:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg.message_id,
            text=f"Начинаю сокращать {len(processed_urls)} ссылок..."
        )
        await state.set_state(LinkStates.waiting_for_mass_title)
        await process_mass_urls(message, state)

async def process_mass_urls(message: Message, state: FSMContext):
    data = await state.get_data()
    urls = data.get("urls", [])
    initial_msg_id = data.get("initial_msg")

    if not urls:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg_id,
            text="Ошибка: список ссылок пуст. Попробуй снова.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    current_url, current_title = urls[0]
    await state.update_data(
        current_url=current_url,
        current_title=current_title,
        urls=urls[1:],
        successful_links=data.get("successful_links", []),
        failed_links=data.get("failed_links", []),
        initial_msg=initial_msg_id
    )

    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=initial_msg_id,
        text=f"Сокращаю ссылку '{current_url}'..."
    )
    await state.set_state(LinkStates.waiting_for_mass_title)

@router.message(LinkStates.waiting_for_title)
async def process_single_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    urls = data.get("urls", [])
    initial_msg_id = data.get("initial_msg")
    url, _ = urls[0] if urls else (None, None)
    title = message.text.strip() if message.text else None
    if not is_valid_url(url):
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg_id,
            text="Ошибка: указана неверная ссылка. Попробуй снова.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=initial_msg_id,
        text="Сокращаю твою ссылку..."
    )
    try:
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={url}")
        short_url = await shorten_link(url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg_id,
            text="Сохраняю ссылку..."
        )
        vk_key = short_url.split("/")[-1]
        logger.info(f"Попытка сохранить ссылку: user_id={message.from_user.id}, short_url={short_url}, title={title}")
        if await save_link(message.from_user.id, url, short_url, title or "Без названия", vk_key):
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=initial_msg_id,
                text=f"Готово ✅\nДобавлена 1 ссылка:\n1. {title or 'Без названия'} — {short_url}",
                reply_markup=get_restart_keyboard()
            )
        else:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=initial_msg_id,
                text=f"Ошибка: ссылка '{url}' уже существует.",
                reply_markup=get_restart_keyboard()
            )
    except Exception as e:
        logger.error("‼️ Ошибка при сокращении или сохранении ссылки:")
        logger.error(traceback.format_exc())
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg_id,
            text=f"Ошибка: {str(e)}",
            reply_markup=get_restart_keyboard()
        )
    await state.clear()

@router.message(LinkStates.waiting_for_mass_title)
async def process_mass_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    urls = data.get("urls", [])
    initial_msg_id = data.get("initial_msg")
    current_url, current_title = data.get("current_url"), data.get("current_title")
    title = message.text.strip() if message.text else current_title
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=initial_msg_id,
        text=f"Сокращаю ссылку '{current_url}'..."
    )
    try:
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={current_url}")
        short_url = await shorten_link(current_url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=initial_msg_id,
            text=f"Сохраняю ссылку '{current_url}'..."
        )
        vk_key = short_url.split("/")[-1]
        logger.info(f"Попытка сохранить ссылку: user_id={message.from_user.id}, short_url={short_url}, title={title}")
        if await save_link(message.from_user.id, current_url, short_url, title or "Без названия", vk_key):
            successful_links = data.get("successful_links", [])
            successful_links.append({"title": title or "Без названия", "short_url": short_url})
            await state.update_data(successful_links=successful_links)
        else:
            failed_links = data.get("failed_links", [])
            failed_links.append(f"Ссылка '{current_url}' уже существует.")
            await state.update_data(failed_links=failed_links)
    except Exception as e:
        logger.error("‼️ Ошибка при сокращении или сохранении ссылки:")
        logger.error(traceback.format_exc())
        failed_links = data.get("failed_links", [])
        failed_links.append(f"Ошибка при сокращении '{current_url}': {str(e)}")
        await state.update_data(failed_links=failed_links)

    if urls:
        await process_mass_urls(message, state)
    else:
        await finalize_mass_processing(message, state)

async def finalize_mass_processing(message: Message, state: FSMContext):
    data = await state.get_data()
    initial_msg_id = data.get("initial_msg")
    successful_links = data.get("successful_links", [])
    failed_links = data.get("failed_links", [])
    response = f"Готово ✅\nДобавлено {len(successful_links)} ссылок:\n"
    if successful_links:
        for i, link in enumerate(successful_links, 1):
            response += f"{i}. {link['title']} — {hlink(link['short_url'], link['short_url'])}\n"
    if failed_links:
        response += "\nПроблемы:\n" + "\n".join(failed_links)
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=initial_msg_id,
        text=response,
        reply_markup=get_restart_keyboard()
    )
    await state.clear()

@router.message(F.text == "Мои ссылки")
async def show_user_links(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запрос списка ссылок для user_id={message.from_user.id}")
    links = await get_links_by_user(message.from_user.id)
    if not links:
        await message.answer("У вас пока нет сохранённых ссылок.", reply_markup=get_main_keyboard())
        return
    await state.update_data(links=links, page=1)
    await send_links_page(message, links, 1)

async def send_links_page(message_or_cb, links, page):
    per_page = 5
    total_pages = math.ceil(len(links) / per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    current_links = links[start:end]

    text = "<b>Ваши ссылки:</b>\n"
    for link in current_links:
        text += f"📎 {link[1]}\n🔗 {hlink(link[2], link[2])}\n📅 {link[3][:10]}\n/view_{link[0]}\n\n"

    keyboard = []
    if total_pages > 1:
        keyboard += get_pagination_keyboard(page, total_pages)
    if isinstance(message_or_cb, Message):
        await message_or_cb.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    elif isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await message_or_cb.answer()

@router.message(F.text.regexp(r"/view_\d+"))
async def view_link_from_text(message: Message):
    await safe_delete(message)
    link_id = int(message.text.split("_")[-1])
    user_id = message.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await message.answer("Ошибка: ссылка не найдена.")
        return
    _, _, long_url, short_url, title, _, created_at = link
    text = f"🔗 {hlink(short_url, short_url)}\n📎 {title}\n📅 Создана: {created_at[:10]}\n🔍 Исходник: {long_url}"
    await message.answer(text, reply_markup=get_link_card_keyboard(link_id, title, long_url, short_url, created_at))

@router.callback_query(F.data.startswith("page_"))
async def paginate_links(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[-1])
    data = await state.get_data()
    links = data.get("links", [])
    await state.update_data(page=page)
    await send_links_page(callback, links, page)

@router.callback_query(F.data.startswith("link_"))
async def show_link_card(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
        return
    _, _, long_url, short_url, title, _, created_at = link
    text = f"🔗 {hlink(short_url, short_url)}\n📎 {title}\n📅 Создана: {created_at[:10]}\n🔍 Исходник: {long_url}"
    await callback.message.edit_text(text, reply_markup=get_link_card_keyboard(link_id, title, long_url, short_url, created_at))

@router.callback_query(F.data.startswith("stats_"))
async def show_stats(callback: CallbackQuery):
    link_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
        return
    _, _, _, short_url, _, vk_key, _ = link
    await callback.message.answer("Получаю статистику...")
    try:
        stats = await get_link_stats(vk_key, VK_TOKEN)
        text = f"Статистика по {short_url}\n" + format_link_stats(stats, short_url)
        await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback.message.edit_text(f"Ошибка: не удалось получить статистику ({str(e)})", reply_markup=get_stats_keyboard())

@router.callback_query(F.data == "back_from_stats")
async def back_from_stats(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("page", 1)
    links = await get_links_by_user(callback.from_user.id)
    await state.update_data(links=links, page=page)
    await send_links_page(callback, links, page)

@router.callback_query(F.data.startswith("rename_"))
async def ask_new_title(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[1])
    await state.set_state(LinkStates.waiting_for_new_title)
    await state.update_data(rename_link_id=link_id)
    await callback.message.answer("Жду новое название ссылки...", reply_markup=ReplyKeyboardRemove())

@router.message(LinkStates.waiting_for_new_title)
async def set_new_title(message: Message, state: FSMContext):
    await safe_delete(message)
    new_title = message.text.strip()
    data = await state.get_data()
    link_id = data.get("rename_link_id")
    user_id = message.from_user.id
    if not new_title:
        await message.answer("Ошибка: название не может быть пустым. Попробуй снова.")
        return
    await message.answer("Обновляю название...")
    if await rename_link(link_id, user_id, new_title):
        link = await get_link_by_id(link_id, user_id)
        if link:
            _, _, long_url, short_url, _, _, created_at = link
            text = f"🔗 {hlink(short_url, short_url)}\n📎 {new_title}\n📅 Создана: {created_at[:10]}\n🔍 Исходник: {long_url}"
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id - 1,
                text=text,
                reply_markup=get_restart_keyboard()
            )
    else:
        await message.answer("Ошибка: не удалось обновить название.", reply_markup=get_restart_keyboard())
    await state.clear()

@router.callback_query(F.data.startswith("delete_"))
async def confirm_delete(callback: CallbackQuery):
    parts = callback.data.split("_")
    if parts[1] == "yes":
        link_id = int(parts[2])
        user_id = callback.from_user.id
        await callback.message.answer("Удаляю ссылку...")
        if await delete_link(link_id, user_id):
            await callback.message.delete()
            await callback.answer("✅ Ссылка удалена")
        else:
            await callback.answer("Ошибка удаления", show_alert=True)
    elif parts[1] == "no":
        link_id = int(parts[2])
        user_id = callback.from_user.id
        link = await get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
            return
        _, _, long_url, short_url, title, _, created_at = link
        await callback.message.edit_reply_markup(reply_markup=get_link_card_keyboard(link_id, title, long_url, short_url, created_at))
    else:
        link_id = int(parts[1])
        user_id = callback.from_user.id
        link = await get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("Ошибка: ссылка не найдена", show_alert=True)
            return
        _, _, _, short_url, title, _, _ = link
        await callback.message.edit_reply_markup(reply_markup=get_delete_confirm_keyboard(link_id, title, short_url))

def setup_handlers(dp):
    dp.include_router(router)
