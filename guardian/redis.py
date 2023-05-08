import redis.asyncio as redis
import time
from guardian import log


class Redis:
    def __init__(self, url: str):
        pool = redis.ConnectionPool.from_url(url, max_connections=16, decode_responses=True)
        self.redis = redis.Redis(connection_pool=pool)

    async def ignore(self, chat_id: int, user_id: int, duration: int):
        key = f'{chat_id}:{user_id}'
        epoch = time.time() + duration
        log.logger.info(f'Ignore {key} until {epoch}')
        await self.redis.zadd('ignore', {key: epoch})

    async def is_ignored(self, chat_id: int, user_id: int):
        key = f'{chat_id}:{user_id}'
        epoch = await self.redis.zscore('ignore', key)
        if epoch == None:
            return False
        return time.time() < epoch

    async def close(self):
        return await self.redis.close()
