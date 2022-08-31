import aiosqlite

SETTINGS = {
    'language': [('en', '🇬🇧'), ('ru', '🇷🇺')],
    'ban_channels': [('1', 'Yes'), ('0', 'No')]
}


class Database:
    FILE = 'data.db'
    DEFAULTS = {
        'language': 'en',
        'ban_channels': False
    }
    CONVERTS = {
        'ban_channels': lambda v: bool(int(v))
    }
    settings = {}

    async def load_settings(self):
        query = 'SELECT * FROM settings'
        async with aiosqlite.connect(self.FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                for s in await cursor.fetchall():
                    chat_id, name, value = s['chat_id'], s['name'], s['value']
                    convert = self.CONVERTS.get(name, str)
                    self.settings[chat_id] = self.settings.get(chat_id, {})
                    self.settings[chat_id][name] = convert(value)

    def get_setting(self, chat_id: int, name: str):
        value = self.settings.get(chat_id, {}).get(name)
        if value == None:
            return self.DEFAULTS.get(name)
        return value

    async def set_setting(self, chat_id: int, name: str, value: str):
        query = """
        INSERT INTO settings VALUES (:chat_id, :name, :value)
        ON CONFLICT (chat_id, name) DO UPDATE SET value = :value
        """
        async with aiosqlite.connect(self.FILE) as db:
            await db.execute(query, {'chat_id': chat_id, 'name': name, 'value': value})
            await db.commit()
        convert = self.CONVERTS.get(name, str)
        s = self.settings.get(chat_id, {})
        s[name] = convert(value)
        self.settings[chat_id] = s
