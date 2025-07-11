from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Мои ссылки", callback_data="dummy_links")],
        [InlineKeyboardButton(text="➖ Сократить ссылку", callback_data="dummy_shorten")]
    ])


def get_link_card_keyboard(link_id: int, title: str, long_url: str, short_url: str, created_at) -> InlineKeyboardMarkup:
    """Клавиатура для карточки ссылки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats_{link_id}")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_{link_id}")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{link_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_links")]
    ])


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для экрана статистики."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_from_stats")]
    ])


def get_delete_confirm_keyboard(link_id: int, title: str, short_url: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения удаления ссылки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_yes_{link_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"delete_no_{link_id}")]
    ])


def get_rename_keyboard(link_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для экрана переименования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rename")]
    ])


def get_pagination_keyboard(page: int, total_pages: int) -> tuple[list, InlineKeyboardMarkup]:
    """Клавиатура для пагинации списка ссылок."""
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text=f"◀️ Страница {page - 1}", callback_data=f"page_{page - 1}"))
    buttons.append(InlineKeyboardButton(text=f"📄 {page} из {total_pages}", callback_data="noop"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text=f"Страница {page + 1} ▶️", callback_data=f"page_{page + 1}"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None
    return buttons, keyboard


def get_back_to_links_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата к списку ссылок."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_links")]
    ])
