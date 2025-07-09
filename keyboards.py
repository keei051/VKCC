from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# Главное меню (кнопки снизу)
def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сократить ссылку")],
            [KeyboardButton(text="Мои ссылки")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )


# Инлайн-кнопки под каждой ссылкой в списке (карточка)
def get_link_list_keyboard(link_id: int, title: str, short_url: str) -> list:
    return [
        [InlineKeyboardButton(text="Просмотреть", callback_data=f"view_{link_id}")],
        [InlineKeyboardButton(text="Статистика", callback_data=f"stats_{link_id}")],
        [InlineKeyboardButton(text="Изменить", callback_data=f"rename_{link_id}")],
        [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{link_id}")]
    ]


# Инлайн-кнопки при отображении карточки ссылки
def get_link_card_keyboard(link_id: int, title: str, long_url: str, short_url: str, created_at: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Статистика", callback_data=f"stats_{link_id}")],
            [InlineKeyboardButton(text="Изменить", callback_data=f"rename_{link_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{link_id}")],
            [InlineKeyboardButton(text="Назад", callback_data="back")]
        ]
    )


# Кнопки пагинации (вперёд / назад)
def get_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    if current_page > 1:
        buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"page_{current_page - 1}"))
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"page_{current_page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else InlineKeyboardMarkup()


# Простая инлайн-кнопка «Назад»
def get_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]
    )


# Кнопки действий с отдельной ссылкой (или подтверждение удаления)
def get_link_actions_keyboard(link_id: int, title: str, short_url: str, delete_confirm: bool = False) -> InlineKeyboardMarkup:
    if delete_confirm:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data=f"delete_yes_{link_id}")],
                [InlineKeyboardButton(text="❌ Нет", callback_data=f"delete_no_{link_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=get_link_list_keyboard(link_id, title, short_url)
    )
