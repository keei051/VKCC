from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from aiogram.filters import CommandStart
from keyboards import get_main_keyboard, get_link_actions_keyboard, get_back_keyboard
from database import save_link, get_links_by_user, get_link_by_id, delete_link, rename_link
from vkcc import shorten_link, get_link_stats
from utils import safe_delete, is_valid_url, format_link_stats
from config import MAX_LINKS_PER_BATCH, VK_TOKEN
import logging
import asyncio
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

class LinkStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()
    waiting_for_mass_title = State()
    waiting_for_new_title = State()

@router.message(CommandStart())
@router.callback_query(F.data.startswith("main_menu"))
async def start_command(message_or_callback: Message | CallbackQuery, state: FSMContext):
    await safe_delete(message_or_callback if isinstance(message_or_callback, Message) else message_or_callback.message)
    user_name = (message_or_callback.from_user.first_name or "пользователь") if isinstance(message_or_callback, Message) else (message_or_callback.message.from_user.first_name or "пользователь")
    await (message_or_callback.answer if isinstance(message_or_callback, Message) else message_or_callback.message.answer)(
        f"Привет, {user_name}. Это профессиональный бот для работы со ссылками."
    )
    await asyncio.sleep(0.5)
    await (message_or_callback.answer if isinstance(message_or_callback, Message) else message_or_callback.message.answer)(
        "Функции:\n"
        "- Сокращение до 50 ссылок с возможностью добавления описания.\n"
        "- Просмотр статистики (переходы, география, демография).\n"
        "- Управление ссылками: переименование и удаление.\n\n"
        "Выберите действие ниже.",
        reply_markup=get_main_keyboard()
    )
    await state.clear()

@router.message(F.text == "/cancel")
async def cancel_command(message: Message, state: FSMContext):
    await safe_delete(message)
    await message.answer("Действие отменено.", reply_markup=get_main_keyboard())
    await state.clear()

@router.message(F.text == "Сократить ссылку")
async def shorten_link_start(message: Message, state: FSMContext):
    await safe_delete(message)
    await message.answer("Введите ссылку для сокращения (или несколько через новые строки).", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LinkStates.waiting_for_url)

@router.message(LinkStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    await safe_delete(message)
    urls = [line.strip() for line in message.text.split("\n") if line.strip()]
    if len(urls) > MAX_LINKS_PER_BATCH:
        await message.answer(f"Максимум {MAX_LINKS_PER_BATCH} ссылок за раз. Разделите ввод.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    if not urls:
        await message.answer("Не указана ни одна ссылка. Повторите попытку.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    await state.update_data(urls=urls)
    if len(urls) == 1:
        await message.answer("Введите описание для ссылки (или оставьте пустым).")
        await state.set_state(LinkStates.waiting_for_title)
    else:
        await state.set_state(LinkStates.waiting_for_mass_title)
        await process_mass_urls(message, state)

async def process_mass_urls(message: Message, state: FSMContext):
    data = await state.get_data()
    urls = data.get("urls", [])
    if not urls:
        await message.answer("Список ссылок пуст. Повторите попытку.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    current_url = urls.pop(0)
    await state.update_data(urls=urls, successful_links=[], failed_links=[])
    if "|" in current_url:
        url_part, _ = [part.strip() for part in current_url.split("|", 1)]
    else:
        url_part = current_url
    if not is_valid_url(url_part):
        failed_links = await state.get_data().get("failed_links", [])
        failed_links.append(f"Строка '{current_url}' не является ссылкой.")
        await state.update_data(failed_links=failed_links)
        if urls:
            await process_mass_urls(message, state)
        else:
            await finalize_mass_processing(message, state)
        return
    if not url_part.startswith(("http://", "https://")):
        url_part = "https://" + url_part
    await message.answer(f"Введите описание для ссылки '{url_part}' (или оставьте пустым).")
    await state.update_data(current_url=url_part)
    await state.set_state(LinkStates.waiting_for_mass_title)

@router.message(LinkStates.waiting_for_title)
async def process_single_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    urls = data.get("urls", [])
    title = message.text.strip() if message.text else None
    url = urls[0] if "|" not in urls[0] else urls[0].split("|")[0].strip()
    if not is_valid_url(url):
        await message.answer("Указана неверная ссылка. Повторите попытку.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={url}")
        short_url = await shorten_link(url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        vk_key = short_url.split("/")[-1]
        if await save_link(message.from_user.id, url, short_url, title, vk_key):
            await message.answer(f"Ссылка успешно добавлена.\n{title or 'Без описания'}:\n{short_url}", reply_markup=get_main_keyboard())
        else:
            await message.answer(f"Ссылка '{url}' уже существует.", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error("‼️ Ошибка при сокращении или сохранении ссылки:")
        logger.error(traceback.format_exc())
        await message.answer(f"Ошибка при сокращении: {str(e)}", reply_markup=get_main_keyboard())
    await state.clear()

@router.message(LinkStates.waiting_for_mass_title)
async def process_mass_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    urls = data.get("urls", [])
    current_url = data.get("current_url")
    title = message.text.strip() if message.text else None
    try:
        logger.info(f"Начинаю обработку ссылки: user_id={message.from_user.id}, url={current_url}")
        short_url = await shorten_link(current_url, VK_TOKEN)
        logger.info(f"Ссылка успешно сокращена: {short_url}")
        vk_key = short_url.split("/")[-1]
        if await save_link(message.from_user.id, current_url, short_url, title, vk_key):
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
            response += f"{i}. {link['title']}:\n{link['short_url']}\n"
    if failed_links:
        response += "\nПроблемы:\n" + "\n".join(failed_links)
    sent_message = await message.answer(response, reply_markup=get_main_keyboard())
    await asyncio.sleep(10)
    await safe_delete(sent_message)
    await state.clear()

@router.message(F.text == "Мои ссылки")
async def show_links(message: Message):
    await safe_delete(message)
    links = await get_links_by_user(message.from_user.id)
    if not links:
        await message.answer("У вас пока нет сохранённых ссылок.", reply_markup=get_main_keyboard())
        return
    keyboard = []
    for link in links:
        link_id, title, short_url, _ = link
        keyboard.append(get_link_actions_keyboard(link_id, title or "Без описания", short_url))
    keyboard.append(get_back_keyboard())
    sent_message = await message.answer("Ваши ссылки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await asyncio.sleep(10)
    await safe_delete(sent_message)

@router.callback_query()
async def process_callback(callback: CallbackQuery):
    await safe_delete(callback.message)
    user_id = callback.from_user.id
    action, link_id = callback.data.split("_")
    link = await get_link_by_id(int(link_id), user_id)

    if not link or link[1] != user_id:
        await callback.answer("Это не ваша ссылка.")
        return

    link_id, _, long_url, short_url, title, vk_key, _ = link

    if action == "stats":
        try:
            stats = await get_link_stats(vk_key, VK_TOKEN)
            formatted_stats = format_link_stats(stats, short_url)
            sent_message = await callback.message.answer(formatted_stats, reply_markup=get_back_keyboard())
            await asyncio.sleep(10)
            await safe_delete(sent_message)
        except Exception as e:
            await callback.message.answer(f"Ошибка получения статистики: {str(e)}. Повторите позже.", reply_markup=get_back_keyboard())

    elif action == "rename":
        await callback.message.answer("Введите новое описание для ссылки.", reply_markup=ReplyKeyboardRemove())
        await callback.answer()
        await callback.message.bot.set_state(callback.from_user.id, LinkStates.waiting_for_new_title, callback.message.chat.id)
        await callback.message.bot.set_data(callback.from_user.id, {"link_id": link_id})

    elif action == "delete":
        sent_message = await callback.message.answer(f"Удалить ссылку {short_url}? [Да] [Нет]", reply_markup=get_link_actions_keyboard(link_id, title or "Без описания", short_url, delete_confirm=True))
        await callback.answer()
        await asyncio.sleep(5)
        await safe_delete(sent_message)

    elif action == "delete_yes":
        if await delete_link(link_id, user_id):
            await callback.message.answer("Ссылка удалена.", reply_markup=get_main_keyboard())
        else:
            await callback.message.answer("Ошибка при удалении.", reply_markup=get_main_keyboard())
        await callback.answer()

    elif action == "delete_no":
        await callback.message.answer("Удаление отменено.", reply_markup=get_link_actions_keyboard(link_id, title or "Без описания", short_url))
        await callback.answer()

    elif action == "back":
        await show_links(callback.message)

    elif action.startswith("main_menu"):
        await start_command(callback, state)

    await callback.answer()

@router.message(LinkStates.waiting_for_new_title)
async def process_new_title(message: Message, state: FSMContext):
    await safe_delete(message)
    data = await state.get_data()
    link_id = data.get("link_id")
    if await rename_link(link_id, message.from_user.id, message.text.strip()):
        await message.answer("Описание обновлено.", reply_markup=get_main_keyboard())
    else:
        await message.answer("Ошибка при обновлении описания.", reply_markup=get_main_keyboard())
    await state.clear()

def setup_handlers(dp):
    dp.include_router(router)
