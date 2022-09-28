import yaml
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, Callable
from contextvars import ContextVar
from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware


class LocaleError(Exception):
    pass


class TranslationPathError(Exception):
    pass


class I18nMiddleware(BaseMiddleware):
    ctx_locale = ContextVar('ctx_chat_locale', default=None)

    def __init__(self, get_lang: Callable[[int], Optional[str]], default: str = 'en'):
        super(I18nMiddleware, self).__init__()
        self.get_lang = get_lang
        self.default = default
        self.translations = self.load_translations()

    @staticmethod
    def load_translations() -> Dict[str, dict]:
        translations = {}
        files = Path(__file__).resolve().parent.parent.joinpath('i18n').glob('*.yaml')
        for f in files:
            with open(f, 'r') as stream:
                translations |= yaml.safe_load(stream)
        return translations

    def t(self, path: str, locale: Optional[str] = None, **kwargs) -> str:
        if locale is None:
            locale = self.ctx_locale.get()
        value = self.translations.get(locale)
        if value is None:
            raise LocaleError(f'Wrong locale or missing translations for locale "{locale}"')
        for p in path.split('.'):
            value = value.get(p)
            if value is None:
                raise TranslationPathError(
                    f'No translation for path "{path}" with locale "{locale}"')
        if len(kwargs) > 0:
            return value.format(**kwargs)
        return value

    def get_chat_locale(self, args: Tuple[Any]) -> str:
        chat: Optional[types.Chat] = types.Chat.get_current()
        chat_id: Optional[int] = chat.id if chat else None

        if chat_id:
            *_, data = args
            lang = self.get_lang(chat_id) or self.default
            data['i18n'] = self
            return lang
        return self.default

    async def trigger(self, action, args):
        if 'update' not in action \
                and 'error' not in action \
                and action.startswith('pre_process'):
            locale = self.get_chat_locale(args)
            self.ctx_locale.set(locale)
            return True
