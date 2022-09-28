from enum import Enum


LANGUAGES = ['en', 'ru']
FLAGS = ['🇬🇧', '🇷🇺']


def validate_welcome_message(message: str, i18n) -> tuple[bool, list[str] | None]:
    errors = []
    if '{user_tag}' not in message:
        errors.append(i18n.t('errors.welcome_message.user_tag'))
    if len(errors) == 0:
        return True, None
    else:
        return False, errors


def validate_language(lang: str, i18n) -> tuple[bool, list[str] | None]:
    errors = []
    if lang not in LANGUAGES:
        errors.append(i18n.t('errors.language.inclusion', languages=', '.join(LANGUAGES)))
    if len(errors) == 0:
        return True, None
    else:
        return False, errors


def dummy_validator(_, _i18n) -> tuple[bool, list[str] | None]:
    return True, None


class Setting(Enum):
    LANGUAGE = 1
    BAN_CHANNELS = 2
    WELCOME_MESSAGE = 3

    @property
    def title(self):
        return self.name.replace('_', ' ').capitalize()

    @property
    def default_value(self):
        match self:
            case self.BAN_CHANNELS:
                return False

    @property
    def from_str(self):
        match self:
            case self.BAN_CHANNELS:
                return lambda v: bool(int(v))
            case _:
                return lambda v: v

    @property
    def variants(self):
        match self:
            case self.LANGUAGE:
                return list(zip(LANGUAGES, FLAGS))
            case self.BAN_CHANNELS:
                return [('1', 'Yes'), ('0', 'No')]

    @property
    def validate(self):
        match self:
            case self.LANGUAGE:
                return validate_language
            case self.WELCOME_MESSAGE:
                return validate_welcome_message
            case _:
                return dummy_validator


class Settings:
    settings = {}

    def __init__(self, database):
        self.db = database

    async def load(self):
        for s in await self.db.select_settings():
            setting = Setting(s['setting_id'])
            chat_id, value = s['chat_id'], setting.from_str(s['value'])
            self.settings[chat_id] = self.settings.get(chat_id, {})
            self.settings[chat_id][setting] = value

    def get(self, chat_id: int, setting: Setting):
        value = self.settings.get(chat_id, {}).get(setting)
        if value is None:
            return setting.default_value
        return value

    async def set(self, chat_id: int, setting: Setting, value: str):
        await self.db.upsert_setting(chat_id, setting.value, value)
        s = self.settings.get(chat_id, {})
        s[setting] = setting.from_str(value)
        self.settings[chat_id] = s
