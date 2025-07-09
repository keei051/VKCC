from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сократить ссылку")],
            [KeyboardButton(text="Мои ссылки")],
            [KeyboardButton(text="Главное меню")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )

def get_link_actions_keyboard(link_id: int, title: str, short_url: str, delete_confirm: bool = False) -> InlineKeyboardMarkup:
    if delete_confirm:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Да", callback_data=f"delete_yes_{link_id}")],
                [InlineKeyboardButton(text="Нет", callback_data=f"delete_no_{link_id}")],
                [InlineKeyboardButton(text="К списку", callback_data=f"back_{link_id}")]
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Статистика", callback_data=f"stats_{link_id}")],
            [InlineKeyboardButton(text="Переименовать", callback_data=f"rename_{link_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{link_id}")],
            [InlineKeyboardButton(text="К списку", callback_data=f"back_{link_id}")]
        ]
    )

def get_link_card_keyboard(link_id: int, title: str, long_url: str, short_url: str, created_at: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Переименовать", callback_data=f"rename_{link_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{link_id}")],
            [InlineKeyboardButton(text="К списку", callback_data=f"back_{link_id}")]
        ]
    )

def get_pagination_keyboard(current_page: int, total_pages: int) -> list:
    keyboard = []
    if current_page > 1:
        keyboard.append(InlineKeyboardButton(text="Назад", callback_data=f"page_{current_page-1}"))
    if current_page < total_pages:
        keyboard.append(InlineKeyboardButton(text="Вперёд", callback_data=f"page_{current_page+1}"))
    return keyboard if keyboard else []
