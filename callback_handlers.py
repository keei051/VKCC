from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from database import Database
from keyboards import main_menu, link_inline_keyboard
from utils import send_long_message

router = Router()
db = Database()

# Показ статистики по одной ссылке
@router.callback_query(F.data.startswith("stats:"))
async def show_stats(callback: CallbackQuery):
    link_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    link = db.get_link(link_id, user_id)
    if not link:
        await callback.answer("Ссылка не найдена.", show_alert=True)
        return

    original_url, short_url, title = link
    text = f"🔗 <b>{title or 'Без названия'}</b>\n\n" \
           f"Исходная: <code>{original_url}</code>\n" \
           f"Сокращённая: <code>{short_url}</code>"

    await callback.message.edit_text(text, reply_markup=link_inline_keyboard(link_id), parse_mode="HTML")
    await callback.answer()

# Удаление ссылки
@router.callback_query(F.data.startswith("delete:"))
async def delete_link(callback: CallbackQuery):
    link_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    deleted = db.delete_link(link_id, user_id)
    if deleted:
        await callback.message.edit_text("🗑 Ссылка удалена.")
    else:
        await callback.answer("Не удалось удалить.", show_alert=True)

# Запрос на переименование
@router.callback_query(F.data.startswith("rename:"))
async def rename_prompt(callback: CallbackQuery, state: FSMContext):
    link_id = int(callback.data.split(":")[1])
    await state.update_data(rename_id=link_id)
    await callback.message.answer("✏️ Введите новое название:")
    await state.set_state("renaming")
    await callback.answer()
