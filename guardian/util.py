import math
import random
import asyncio
from functools import partial
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from guardian.log import logger

LANG_EMOJI = {
    'en': '🇬🇧',
    'ru': '🇷🇺'
}


class AttrDict(dict):
    def __init__(self, d: dict):
        for k, v in d.items():
            if isinstance(v, dict):
                d[k] = AttrDict(v)
        super(AttrDict, self).__init__(d)
        self.__dict__ = self


def callback(func, *args):
    return partial(asyncio.ensure_future, func(*args))


def chunks(elements, n):
    for i in range(0, len(elements), n):
        yield elements[i:i + n]


def get_lang(flag_emoji: str):
    for lang, value in LANG_EMOJI.items():
        if value == flag_emoji:
            return lang


def emoji_keyboard(emoji: list, rows: int):
    markup = InlineKeyboardMarkup()
    row_size = math.ceil(len(emoji) / rows)
    for row in chunks(emoji, row_size):
        kb_row = (InlineKeyboardButton(e, callback_data=e) for e in row)
        markup.row(*kb_row)
    return markup


def lang_keyboard(languages: list, row_size: int):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    for row in chunks(languages, row_size):
        emoji = map(lambda lang: LANG_EMOJI.get(lang, lang), row)
        markup.add(*emoji)
    return markup


def get_user_tag(user):
    if user.username:
        return f'@{user.username}'
    else:
        return f'<a href="tg://user?id={user.id}">{user.first_name or user.last_name}</a>'


def log_exception(e: Exception):
    logger.error(f'{e} [{e.__class__.__name__}]')
