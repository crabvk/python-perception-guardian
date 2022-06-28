import aiosqlite


class Database:
    FILE = 'data.db'
    DEFAULTS = {
        'lang': 'en'
    }
    settings = {}

    async def load_settings(self):
        query = 'SELECT * FROM settings'
        async with aiosqlite.connect(self.FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                for s in await cursor.fetchall():
                    self.settings[s['chat_id']] = {s['name']: s['value']}

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
        self.settings[chat_id] = {name: value}
