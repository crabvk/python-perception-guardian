import aiosqlite


class Database:
    FILE = 'data.db'

    async def select_settings(self):
        query = 'SELECT * FROM settings'
        async with aiosqlite.connect(self.FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                return await cursor.fetchall()

    async def upsert_setting(self, chat_id: int, setting_id: int, setting_value: str):
        query = """
        INSERT INTO settings VALUES (:chat_id, :setting_id, :value)
        ON CONFLICT (chat_id, setting_id) DO UPDATE SET value = :value
        """
        async with aiosqlite.connect(self.FILE) as db:
            await db.execute(query, {'chat_id': chat_id, 'setting_id': setting_id, 'value': setting_value})
            await db.commit()
