import aiosqlite
from enum import Enum


class Setting(Enum):
    LANGUAGE = 1
    BAN_CHANNELS = 2

    @property
    def title(self):
        return self.name.replace('_', ' ').capitalize()

    @property
    def default_value(self):
        match self:
            case self.LANGUAGE:
                return 'en'
            case self.BAN_CHANNELS:
                return False

    @property
    def variants(self):
        match self:
            case self.LANGUAGE:
                return [('en', '🇬🇧'), ('ru', '🇷🇺')]
            case self.BAN_CHANNELS:
                return [('1', 'Yes'), ('0', 'No')]

    @property
    def convert(self):
        match self:
            case self.BAN_CHANNELS:
                return lambda v: bool(int(v))
            case _:
                return str


class Database:
    FILE = 'data.db'
    settings = {}

    async def load_settings(self):
        query = 'SELECT * FROM settings'
        async with aiosqlite.connect(self.FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                for s in await cursor.fetchall():
                    setting = Setting(s['setting_id'])
                    chat_id, value = s['chat_id'], setting.convert(s['value'])
                    self.settings[chat_id] = self.settings.get(chat_id, {})
                    self.settings[chat_id][setting] = value

    def get_setting(self, chat_id: int, setting: Setting):
        value = self.settings.get(chat_id, {}).get(setting)
        if value == None:
            return setting.default_value
        return value

    async def set_setting(self, chat_id: int, setting: Setting, value: str):
        query = """
        INSERT INTO settings VALUES (:chat_id, :setting_id, :value)
        ON CONFLICT (chat_id, setting_id) DO UPDATE SET value = :value
        """
        async with aiosqlite.connect(self.FILE) as db:
            await db.execute(query, {'chat_id': chat_id, 'setting_id': setting.value, 'value': value})
            await db.commit()
        s = self.settings.get(chat_id, {})
        s[setting] = setting.convert(value)
        self.settings[chat_id] = s
