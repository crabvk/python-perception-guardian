from typing import Union
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher.filters import BoundFilter


class UsernameFilter(BoundFilter):
    key = 'username'

    def __init__(self, username: str):
        self.username = username

    async def check(self, obj: Union[Message, CallbackQuery]):
        return obj.from_user.username == self.username
