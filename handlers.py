from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.markdown import hlink
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup

from keyboards import (
    get_main_keyboard,
    get_link_list_keyboard,
    get_link_card_keyboard,
    get_link_actions_keyboard,
    get_back_keyboard,
    get_pagination_keyboard,
)
from database import (
    save_link,
    get_links_by_user,
    get_link_by_id,
    delete_link,
    rename_link,
)
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
    waiting_for_page = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Запуск команды /start для user_id={message.from_user.id}")
    user_name = message.from_user.first_name or "пользователь"
    await message.answer(
        f"Привет, {user_name}. Это профессиональный бот для работы со ссылками.",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@router.message(F.text == "Сократить ссылку")
async def start_shorten(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Пользователь {message.from_user.id} начал сокращение ссылки")
    await message.answer("Отправь мне ссылку для сокращения (или несколько через новые строки, до 50). Для описания используйте формат: https://site.com | Описание.", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LinkStates.waiting_for_url)

@router.message(LinkStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    await safe_delete(message)
    logger.info(f"Получен ввод для сокращения от user_id={message.from_user.id}: {message.text}")
    urls = [line.strip() for line in message.text.split("\n") if line.strip()]
    if len(urls) > MAX_LINKS_PER_BATCH:
        await message.answer(f"Максимум {MAX_LINKS_PER_BATCH} ссылок за раз. Разделите ввод.")
        await state.clear()
        return
    if not urls:
        await message.answer("Не указана ни одна ссылка. Повторите попытку.")
        await state.clear()
        return

    processed_urls = []
    for url in urls:
        if "|" in url:
            url_part, title = [part.strip() for part in url.split("|", 1)]
        else:
            url_part, title = url.strip(), None
        if not is_valid_url(url_part):
            await message.answer(f"Строка '{url}' не является корректной ссылкой.")
            await state.clear()
            return
        if not url_part.startswith(("http://", "https://")):
            url_part = "https://" + url_part
        processed_urls.append((url_part, title))
    
    await state.update_data(urls=processed_urls)
    if len(processed_urls) == 1:
        await message.answer(f"Введите описание для ссылки '{processed_urls[0][0]}' (или оставьте пустым).")
        await state.set_state(LinkStates.waiting_for_title)
    else:
        await state.set_state(LinkStates.waiting_for_mass_title)
        await process_mass_urls(message, state)

async def process_mass_urls(message: Message, state: FSMContext):
    data = await state.get_data()
    urls = data.get("urls", [])

    if not urls:
        await message.answer("Список ссылок пуст. Повторите попытку.")
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

    logger.info(f"Обрабатывается ссылка: user_id={message.from_user.id}, url={current_url}")
    await message.answer(f"Введите описание для ссылки '{current_url}' (или оставьте пустым).")
    await state.set_state(LinkStates.waiting_for_mass_title)

@router.message(LinkStates.waiting_for_title)
async def process_single_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    urls = data.get("urls", [])
    url, _ = urls[0] if urls else (None, None)
    title = message.text.strip() if message.text else None
    if not is_valid_url(url):
        await message.answer("Указана неверная ссылка. Повторите попытку.")
        await state.clear()
        return
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={url}")
        short_url = await shorten_link(url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        vk_key = short_url.split("/")[-1]
        logger.info(f"Попытка сохранить ссылку: user_id={message.from_user.id}, short_url={short_url}, title={title}")
        if await save_link(message.from_user.id, url, short_url, title or "Поиск", vk_key):
            await message.answer(f"Ссылка успешно сокращена: {short_url}", reply_markup=get_main_keyboard())
        else:
            await message.answer(f"Ссылка '{url}' уже существует.", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error("‼️ Ошибка при сокращении или сохранении ссылки:")
        logger.error(traceback.format_exc())
        await message.answer(f"Ошибка: {str(e)}", reply_markup=get_main_keyboard())
    await state.clear()

@router.message(LinkStates.waiting_for_mass_title)
async def process_mass_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    urls = data.get("urls", [])
    current_url, current_title = data.get("current_url"), data.get("current_title")
    title = message.text.strip() if message.text else current_title
    try:
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={current_url}")
        short_url = await shorten_link(current_url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        vk_key = short_url.split("/")[-1]
        logger.info(f"Попытка сохранить ссылку: user_id={message.from_user.id}, short_url={short_url}, title={title}")
        if await save_link(message.from_user.id, current_url, short_url, title or "Поиск", vk_key):
            successful_links = data.get("successful_links", [])
            successful_links.append({"title": title or "Без описания", "short_url": short_url})
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
    await safe_delete(message)
    data = await state.get_data()
    successful_links = data.get("successful_links", [])
    failed_links = data.get("failed_links", [])
    response = f"Добавлено ссылок: {len(successful_links)}.\n\n"
    if successful_links:
        response += "Список ссылок:\n"
        for i, link in enumerate(successful_links, 1):
            response += f"{i}. {link['title']}:\n{hlink(link['short_url'], link['short_url'])}\n"
    if failed_links:
        response += "\nПроблемы:\n" + "\n".join(failed_links)
    await message.answer(response, reply_markup=get_main_keyboard())
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
        text += f"• <b>{link[1]}</b> — {hlink(link[2], link[2])}\n"
        text += f"<i>Создана:</i> {link[3][:10]}\n"
        text += f"/view_{link[0]}\n\n"

    keyboard = get_pagination_keyboard(page, total_pages)
    if isinstance(message_or_cb, Message):
        await message_or_cb.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    elif isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await message_or_cb.answer()

@router.message(F.text.regexp(r"/view_\d+"))
async def view_link_from_text(message: Message):
    link_id = int(message.text.split("_")[-1])
    user_id = message.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await message.answer("Ссылка не найдена")
        return
    _, _, long_url, short_url, title, _, created_at = link
    text = f"<b>{title}</b>\n\n{hlink('Открыть ссылку', short_url)}\n\n"
    text += f"<i>Создана:</i> {created_at[:10]}\n<i>Исходная ссылка:</i> {long_url}"
    await message.answer(text, reply_markup=get_link_card_keyboard(link_id, title, long_url, short_url, created_at))

@router.callback_query(F.data.startswith("page_"))
async def paginate_links(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[-1])
    data = await state.get_data()
    links = data.get("links", [])
    await state.update_data(page=page)
    await send_links_page(callback, links, page)

@router.callback_query(F.data.startswith("stats_"))
async def show_stats(callback: CallbackQuery):
    link_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("Ссылка не найдена", show_alert=True)
        return
    _, _, _, short_url, _, vk_key, _ = link
    try:
        stats = await get_link_stats(vk_key, VK_TOKEN)
        text = format_link_stats(stats, short_url)
        await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    except Exception as e:
        await callback.message.answer(f"Ошибка при получении статистики: {str(e)}")

@router.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    links = data.get("links", [])
    page = data.get("page", 1)
    await send_links_page(callback, links, page)

@router.callback_query(F.data.startswith("delete_"))
async def confirm_delete(callback: CallbackQuery):
    parts = callback.data.split("_")
    if parts[1] == "yes":
        link_id = int(parts[-1])
        user_id = callback.from_user.id
        if await delete_link(link_id, user_id):
            await callback.message.delete()
            await callback.answer("Ссылка удалена")
        else:
            await callback.answer("Ошибка удаления", show_alert=True)
    elif parts[1] == "no":
        await callback.message.edit_reply_markup(reply_markup=get_back_keyboard())
    else:
        link_id = int(parts[-1])
        user_id = callback.from_user.id
        link = await get_link_by_id(link_id, user_id)
        if not link:
            await callback.answer("Ссылка не найдена", show_alert=True)
            return
        _, _, _, short_url, title, _, _ = link
        await callback.message.edit_reply_markup(reply_markup=get_link_actions_keyboard(link_id, title, short_url, delete_confirm=True))

@router.callback_query(F.data.startswith("rename_"))
async def ask_new_title(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split("_")[-1])
    await state.set_state(LinkStates.waiting_for_new_title)
    await state.update_data(rename_link_id=link_id)
    await callback.message.answer("Введите новое название ссылки")

@router.message(LinkStates.waiting_for_new_title)
async def set_new_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    data = await state.get_data()
    link_id = data.get("rename_link_id")
    user_id = message.from_user.id
    if not new_title:
        await message.answer("Название не может быть пустым")
        return
    if await rename_link(link_id, user_id, new_title):
        await message.answer("Название обновлено", reply_markup=get_main_keyboard())
    else:
        await message.answer("Ошибка обновления названия")
    await state.clear()

def setup_handlers(dp):
    dp.include_router(router)
def setup_handlers(dp):
    dp.include_router(router)
