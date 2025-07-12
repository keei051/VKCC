from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from database import get_link_by_id, delete_link, rename_link
from keyboards import main_menu, link_inline_keyboard

router = Router()

class RenameStates(StatesGroup):
    renaming = State()

# 📊 Показ статистики по одной ссылке
@router.callback_query(F.data.startswith("stats:"))
async def show_stats(callback: CallbackQuery):
    try:
        link_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный формат ID", show_alert=True)
        return

    user_id = callback.from_user.id
    link = await get_link_by_id(link_id, user_id)
    if not link:
        await callback.answer("Ссылка не найдена.", show_alert=True)
        return

    _, _, original_url, short_url, title, _, created_at = link
    created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")

    text = (
        f"🔗 <b>{title or 'Без названия'}</b>\n\n"
        f"Исходная: <code>{original_url}</code>\n"
        f"Сокращённая: <code>{short_url}</code>\n"
        f"📆 {created_str}"
    )

    await callback.message.edit_text(text, reply_markup=link_inline_keyboard(link_id), parse_mode="HTML")
    await callback.answer()

# 🗑 Удаление ссылки
@router.callback_query(F.data.startswith("delete:"))
async def delete_link_handler(callback: CallbackQuery):
    try:
        link_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка: неверный ID", show_alert=True)
        return

    user_id = callback.from_user.id
    deleted = await delete_link(link_id, user_id)
    if deleted:
        await callback.message.edit_text("🗑 Ссылка удалена.")
    else:
        await callback.answer("Не удалось удалить.", show_alert=True)

# ✏️ Запрос на переименование
@router.callback_query(F.data.startswith("rename:"))
async def rename_prompt(callback: CallbackQuery, state: FSMContext):
    try:
        link_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return

    await state.update_data(rename_id=link_id)
    await state.set_state(RenameStates.renaming)
    await callback.message.answer("✏️ Введите новое название:")
    await callback.answer()

# ✏️ Обработка нового названия
@router.message(RenameStates.renaming)
async def process_rename(message: Message, state: FSMContext):
    new_title = message.text.strip()
    data = await state.get_data()
    link_id = data.get("rename_id")
    user_id = message.from_user.id

    if not new_title or len(new_title) > 100:
        await message.answer("❌ Название не может быть пустым или длиннее 100 символов.")
        await state.clear()
        return

    if await rename_link(link_id, user_id, new_title):
        link = await get_link_by_id(link_id, user_id)
        if link:
            _, _, original_url, short_url, _, _, created_at = link
            created_str = created_at[:10] if isinstance(created_at, str) else created_at.strftime("%Y-%m-%d")
            text = (
                f"✅ Название обновлено!\n\n"
                f"🔗 <b>{new_title}</b>\n"
                f"Исходная: <code>{original_url}</code>\n"
                f"Сокращённая: <code>{short_url}</code>\n"
                f"📆 {created_str}"
            )
            try:
                await message.answer(text, reply_markup=link_inline_keyboard(link_id), parse_mode="HTML")
            except TelegramBadRequest:
                await message.answer("✅ Название обновлено, но сообщение не удалось отобразить.")
        else:
            await message.answer("⚠️ Ссылка не найдена после переименования.")
    else:
        await message.answer("❌ Не удалось обновить название.")

    await state.clear()
