from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional, Tuple


def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Мои ссылки", callback_data="dummy_links")],
        [InlineKeyboardButton(text="➖ Сократить ссылку", callback_data="dummy_shorten")]
    ])


def get_link_card_keyboard(link_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для карточки конкретной ссылки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats_{link_id}")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"rename_{link_id}")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{link_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_links")]
    ])


def get_stats_keyboard(link_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для экрана статистики."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_stats_{link_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_from_stats")]
    ])


def get_delete_confirm_keyboard(link_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_yes_{link_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"delete_no_{link_id}")]
    ])


def get_rename_keyboard(link_id: int) -> InlineKeyboardMarkup:
    """Клавиатура отмены переименования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"rename_cancel_{link_id}")]
    ])


def get_pagination_keyboard(page: int, total_pages: int) -> Tuple[list[InlineKeyboardButton], InlineKeyboardMarkup]:
    """Клавиатура для пагинации списка ссылок."""
    buttons: list[InlineKeyboardButton] = []

    if page > 1:
        buttons.append(InlineKeyboardButton(text=f"◀️ Страница {page - 1}", callback_data=f"page_{page - 1}"))

    buttons.append(InlineKeyboardButton(text=f"📄 {page} из {total_pages}", callback_data="noop"))

    if page < total_pages:
        buttons.append(InlineKeyboardButton(text=f"▶️ Страница {page + 1}", callback_data=f"page_{page + 1}"))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
    return buttons, keyboard
