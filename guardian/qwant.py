
import aiohttp
import random
from guardian.log import logger

PARAMS = {
    'count': 10,
    't': 'images',
    'safesearch': 1,
    'locale': 'en_US',
    'offset': 0,
    'device': 'desktop'
}
HEADERS = {
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0',
    'accept': 'application/json'
}


async def get_image_url(query: str) -> str | None:
    logger.info(f'Searching Qwant images with query: {query}')
    params = PARAMS | {'q': query}
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.qwant.com/v3/search/images', params=params, headers=HEADERS) as response:
            data = await response.json()
            items = data.get('data').get('result').get('items')
            return random.choice(items).get('thumbnail')
