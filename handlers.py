from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from keyboards import get_main_keyboard, get_link_actions_keyboard, get_back_keyboard
from database import save_link, get_links_by_user, get_link_by_id, delete_link, rename_link
from vkcc import shorten_link, get_link_stats
from utils import safe_delete, is_valid_url, format_link_stats
import re

# Роутер для обработчиков
router = Router()

# Состояния FSM
class LinkStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()
    waiting_for_new_title = State()

# Начало работы (/start)
@router.message(F.text == "/start")
async def start_command(message: Message, state: FSMContext):
    await safe_delete(message)
    await message.answer("👋 Привет!\nВыбери действие:", reply_markup=get_main_keyboard())
    await state.clear()

# Обработка команды /cancel
@router.message(F.text == "/cancel")
async def cancel_command(message: Message, state: FSMContext):
    await safe_delete(message)
    await message.answer("🚫 Действие отменено.", reply_markup=get_main_keyboard())
    await state.clear()

# Кнопка "🔗 Сократить ссылку"
@router.message(F.text == "🔗 Сократить ссылку")
async def shorten_link_start(message: Message, state: FSMContext):
    await safe_delete(message)
    await message.answer("📩 Отправьте ссылку для сокращения (или несколько через | с подписью).", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LinkStates.waiting_for_url)

# Обработка введённой ссылки
@router.message(LinkStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    await safe_delete(message)
    urls = message.text.strip().split("\n")
    if len(urls) > 50:
        await message.answer("🚫 Можно добавить максимум 50 ссылок за раз. Отправьте по частям.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    successful_links = []
    failed_links = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        title = None
        if "|" in url:
            url, title = [part.strip() for part in url.split("|", 1)]
        if not is_valid_url(url):
            failed_links.append(f"Строка: '{url}' — это не ссылка.")
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            short_url = await shorten_link(url)
            vk_key = short_url.split("/")[-1]
            if await save_link(message.from_user.id, url, short_url, title, vk_key):
                successful_links.append({"title": title or "Без подписи", "short_url": short_url})
            else:
                failed_links.append(f"Ссылка '{url}' уже добавлена.")
        except Exception as e:
            failed_links.append(f"Ошибка при сокращении '{url}': {str(e)}")

    # Формируем ответ
    response = "✅ Добавлено ссылок: " + str(len(successful_links)) + ".\n\n"
    if successful_links:
        response += "📋 Список:\n"
        for i, link in enumerate(successful_links, 1):
            response += f"{i}. {link['title']}:\n{link['short_url']}\n"
    if failed_links:
        response += "\n⚠️ Ошибки:\n" + "\n".join(failed_links)
    await message.answer(response, reply_markup=get_main_keyboard())

    await state.clear()

# Кнопка "📋 Мои ссылки"
@router.message(F.text == "📋 Мои ссылки")
async def show_links(message: Message):
    await safe_delete(message)
    links = await get_links_by_user(message.from_user.id)
    if not links:
        await message.answer("📭 У вас пока нет ссылок.", reply_markup=get_main_keyboard())
        return
    keyboard = []
    for link in links:
        link_id, title, short_url, created_at = link
        keyboard.append([get_link_actions_keyboard(link_id, title, short_url)])
    keyboard.append([get_back_keyboard()])
    await message.answer("📋 Ваши ссылки:", reply_markup=keyboard)

# Обработка inline-кнопок
@router.callback_query()
async def process_callback(callback: CallbackQuery):
    await safe_delete(callback.message)
    user_id = callback.from_user.id
    action, link_id = callback.data.split("_")
    link = await get_link_by_id(int(link_id), user_id)

    if not link or link[1] != user_id:
        await callback.answer("🚫 Это не ваша ссылка.")
        return

    link_id, _, long_url, short_url, title, vk_key, created_at = link

    if action == "stats":
        try:
            stats = await get_link_stats(vk_key)
            formatted_stats = format_link_stats(stats, short_url)
            await callback.message.answer(formatted_stats, reply_markup=get_back_keyboard())
        except Exception:
            await callback.message.answer("📉 Пока нет статистики по этой ссылке.\nОна появится, как только начнутся переходы.", reply_markup=get_back_keyboard())

    elif action == "rename":
        await callback.message.answer("✏ Введите новое название для ссылки.", reply_markup=ReplyKeyboardRemove())
        await callback.answer()
        await callback.message.bot.set_state(callback.from_user.id, LinkStates.waiting_for_new_title, callback.message.chat.id)
        await callback.message.bot.set_data(callback.from_user.id, {"link_id": link_id})

    elif action == "delete":
        await callback.message.answer(f"❗ Удалить ссылку {short_url}?\n[✅ Да] [❌ Нет]", reply_markup=get_link_actions_keyboard(link_id, title, short_url, delete_confirm=True))
        await callback.answer()

    elif action == "delete_yes":
        if await delete_link(link_id, user_id):
            await callback.message.answer("🗑 Ссылка удалена.", reply_markup=get_main_keyboard())
        else:
            await callback.message.answer("🚫 Ошибка при удалении.", reply_markup=get_main_keyboard())
        await callback.answer()

    elif action == "delete_no":
        await callback.message.answer("❌ Удаление отменено.", reply_markup=get_link_actions_keyboard(link_id, title, short_url))
        await callback.answer()

    elif action == "back":
        await show_links(callback.message)

    await callback.answer()

# Обработка нового названия
@router.message(LinkStates.waiting_for_new_title)
async def process_new_title(message: Message, state: FSMContext):
    await safe_delete(message)
    user_data = await state.get_data()
    link_id = user_data.get("link_id")
    if await rename_link(link_id, message.from_user.id, message.text.strip()):
        await message.answer("✏️ Название обновлено!", reply_markup=get_main_keyboard())
    else:
        await message.answer("🚫 Ошибка при обновлении названия.", reply_markup=get_main_keyboard())
    await state.clear()

# Настройка обработчиков
def setup_handlers(dp):
    dp.include_router(router)
