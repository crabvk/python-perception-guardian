import math
import random
import asyncio
from functools import partial
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from guardian.log import logger


def callback(func, *args):
    return partial(asyncio.ensure_future, func(*args))


def chunks(elements, n):
    for i in range(0, len(elements), n):
        yield elements[i:i + n]


def emoji_keyboard(emoji: list, rows: int):
    keyboard_markup = InlineKeyboardMarkup()
    row_size = math.ceil(len(emoji) / rows)
    for row in chunks(emoji, row_size):
        kb_row = (InlineKeyboardButton(e, callback_data=e) for e in row)
        keyboard_markup.row(*kb_row)
    return keyboard_markup


def get_user_tag(user):
    if user.username:
        return f'@{user.username}'
    else:
        return f'<a href="tg://user?id={user.id}">{user.first_name or user.last_name}</a>'


def log_exception(e: Exception):
    logger.error(f'{e} [{e.__class__.__name__}]')
