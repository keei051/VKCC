from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сократить ссылку")],
            [KeyboardButton(text="Мои ссылки")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )

def get_link_list_keyboard(links) -> list:
    keyboard = []
    for link in links:
        link_id, title, _, _ = link
        keyboard.append([InlineKeyboardButton(text=f"📍 {title}", callback_data=f"link_{link_id}")])
    return keyboard

def get_link_card_keyboard(link_id: int, title: str, long_url: str, short_url: str, created_at: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats_{link_id}")],
            [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_{link_id}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{link_id}")]
        ]
    )

def get_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_from_stats")]
        ]
    )

def get_delete_confirm_keyboard(link_id: int, title: str, short_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data=f"delete_yes_{link_id}")],
            [InlineKeyboardButton(text="❌ Нет", callback_data=f"delete_no_{link_id}")]
        ]
    )

def get_rename_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )

def get_pagination_keyboard(page: int, total_pages: int) -> list:
    keyboard = []
    if total_pages > 1:
        if page > 1:
            keyboard.append([InlineKeyboardButton(text="◀️ Предыдущая", callback_data=f"page_{page-1}")])
        if page < total_pages:
            keyboard.append([InlineKeyboardButton(text="Следующая ▶️", callback_data=f"page_{page+1}")])
    return keyboard

def get_restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Старт заново", callback_data="restart")]
        ]
    )
