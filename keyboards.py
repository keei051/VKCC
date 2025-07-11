from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# Главное меню (внизу, как обычная клавиатура)
def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сократить ссылку")],
            [KeyboardButton(text="Мои ссылки")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )

# Главное меню (inline-вариант, для edit_message_text)
def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сократить ссылку", callback_data="dummy_shorten")],
            [InlineKeyboardButton(text="Мои ссылки", callback_data="dummy_links")]
        ]
    )

# Список ссылок (каждая — кнопка)
def get_link_list_keyboard(links) -> list:
    keyboard = []
    for link in links:
        link_id, title, _, _ = link
        keyboard.append([InlineKeyboardButton(text=f"📍 {title}", callback_data=f"link_{link_id}")])
    return keyboard

# Кнопки управления одной ссылкой
def get_link_card_keyboard(link_id: int, title: str, long_url: str, short_url: str, created_at: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats_{link_id}")],
            [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_{link_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{link_id}")]
        ]
    )

# Кнопка "Назад" после статистики
def get_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_from_stats")]
        ]
    )

# Подтверждение удаления
def get_delete_confirm_keyboard(link_id: int, title: str, short_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data=f"delete_yes_{link_id}")],
            [InlineKeyboardButton(text="❌ Нет", callback_data=f"delete_no_{link_id}")]
        ]
    )

# Кнопка назад при переименовании
def get_rename_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )

# Постраничная навигация
def get_pagination_keyboard(page: int, total_pages: int) -> list:
    keyboard = []
    if total_pages > 1:
        row = []
        if page > 1:
            row.append(InlineKeyboardButton(text="◀️ Предыдущая", callback_data=f"page_{page-1}"))
        if page < total_pages:
            row.append(InlineKeyboardButton(text="Следующая ▶️", callback_data=f"page_{page+1}"))
        keyboard.append(row)
    return keyboard

# Кнопка "Старт заново"
def get_restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Старт заново", callback_data="restart")]
        ]
    )
