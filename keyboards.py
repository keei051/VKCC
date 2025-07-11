from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню
def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Мои ссылки", callback_data="show_links")],
        [InlineKeyboardButton(text="➖ Сократить ссылку", callback_data="shorten_link")]
    ])

# Кнопки действий над ссылкой
def get_link_card_keyboard(link_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats:{link_id}")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename:{link_id}")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete:{link_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_links")]
    ])

# Кнопка "Назад" из статистики
def get_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_from_stats")]
    ])

# Подтверждение удаления
def get_delete_confirm_keyboard(link_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_yes_{link_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"delete_no_{link_id}")]
    ])

# Отмена переименования
def get_rename_keyboard(link_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rename")]
    ])

# Пагинация (листалка по страницам ссылок)
def get_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []

    if page > 1:
        buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page_{page - 1}"))

    buttons.append(InlineKeyboardButton(text=f"📄 {page} из {total_pages}", callback_data="noop"))

    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="▶️ Далее", callback_data=f"page_{page + 1}"))

    return InlineKeyboardMarkup(inline_keyboard=[buttons])

