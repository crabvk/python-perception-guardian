import aioredis
import time
from guardian.log import logger


class Redis:
    def __init__(self, url: str):
        pool = aioredis.ConnectionPool.from_url(
            url, max_connections=16, decode_responses=True)
        self.redis = aioredis.Redis(connection_pool=pool)

    @staticmethod
    def _answer_key(chat_id: int, user_id: int, message_id: int):
        return f'answer:{chat_id}:{user_id}:{message_id}'

    async def set_answer(self, chat_id: int, user_id: int, message_id: int, emoji: str, ignore_for: int):
        answer_key = self._answer_key(chat_id, user_id, message_id)
        ignore_key = f'{chat_id}:{user_id}'
        epoch = time.time() + ignore_for
        logger.info(f'Set & Ignore {answer_key} => {emoji}, {epoch}')
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.set(answer_key, emoji).zadd('ignore', {ignore_key: epoch}).execute()

    async def get_answer(self, chat_id: int, user_id: int, message_id: int, delete: bool = False):
        key = self._answer_key(chat_id, user_id, message_id)
        if delete:
            answer = await self.redis.execute_command('GETDEL', key)
        else:
            answer = await self.redis.get(key)
        logger.info(f'Get {key} => {answer}')
        return answer

    async def delete_answer(self, chat_id: int, user_id: int, message_id: int):
        key = self._answer_key(chat_id, user_id, message_id)
        result = await self.redis.delete(key)
        logger.info(f'Delete {key} => {result}')
        return result

    async def is_ignored(self, chat_id: int, user_id: int):
        key = f'{chat_id}:{user_id}'
        epoch = await self.redis.zscore('ignore', key)
        if epoch == None:
            return False
        return time.time() < epoch
