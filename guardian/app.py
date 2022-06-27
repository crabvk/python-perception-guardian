import asyncio
import random
import typing
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ChatType, ContentType, Message
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils.executor import start_webhook
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.exceptions import TelegramAPIError
from guardian import qwant, qna
from guardian.log import logger
from guardian.redis import Redis
from guardian.util import emoji_keyboard, get_user_tag, callback, log_exception
from guardian.config import Config

PERMISSIVE_ATTRIBUTES = {
    'can_send_messages': True,
    'can_send_media_messages': True,
    'can_send_other_messages': True,
    'can_add_web_page_previews': True
}


class App:
    def __init__(self, config: Config):
        self.bot = Bot(token=config.telegram.token, parse_mode=types.ParseMode.HTML)
        self.dp = Dispatcher(self.bot)
        self.dp.middleware.setup(LoggingMiddleware(logger))
        self.redis = Redis(config.redis.url)
        self.config = config
        self.dp.register_message_handler(self.handle_new_chat_member,
                                         chat_type=[ChatType.GROUP, ChatType.SUPERGROUP],
                                         content_types=ContentType.NEW_CHAT_MEMBERS)

        self.dp.register_message_handler(self.handle_left_chat_member,
                                         chat_type=[ChatType.GROUP, ChatType.SUPERGROUP],
                                         content_types=ContentType.LEFT_CHAT_MEMBER)

        self.dp.register_callback_query_handler(self.handle_inline_kb_answer)

    # TODO: can fail if another admin deletes the message
    async def send_message(self, chat_id: int, text: str, expire: int | float):
        msg = await self.bot.send_message(chat_id, text)
        cb = callback(self.bot.delete_message, chat_id, msg.message_id)
        asyncio.get_running_loop().call_later(expire, cb)

    async def after_question_timeout(self, chat_id: int, user_id: int, message_id: int, user_tag: str):
        deleted = await self.redis.delete_answer(chat_id, user_id, message_id)
        if deleted:
            text = f'{user_tag} Time is over.\nYou can try to join the group again after 5 minutes.'
            await self.bot.delete_message(chat_id, message_id)
            await self.send_message(chat_id, text, self.config.guardian.message_expire)

    async def handle_new_chat_member(self, message: Message):
        new_member = message.new_chat_members[0]
        if new_member.is_bot:
            bot = await message.bot.me
            if new_member.id == bot.id:
                await message.answer(
                    'Great! Now make me an <b>admin</b>, so I can restrict newcomers until they pass the captcha 😉')
                return
            logger.info('New member is a bot, skipping captcha.')
            return

        # Always restrict new member as soon as possible
        restricted, _ = await asyncio.gather(
            message.chat.restrict(new_member.id, can_send_messages=False),
            message.delete(),
            return_exceptions=True
        )

        # Doesn't make sense to show captcha if restriction didn't work
        if issubclass(type(restricted), TelegramAPIError):
            logger.error(restricted)
            await message.answer(restricted)
            return

        # Don't show captcha for ignored users
        chat_user = (message.chat.id, new_member.id)
        if await self.redis.is_ignored(*chat_user):
            logger.info(f'Ignoring {chat_user[0]}:{chat_user[1]}')
            return

        comb = qna.pick(6)
        # TODO: handle request errors from Qwant.com
        url = await qwant.get_image_url(comb.query_phrase)

        keyboard_markup = emoji_keyboard(comb.emoji, rows=2)
        user_tag = get_user_tag(new_member)
        caption = f'{user_tag} Choose what is shown in the picture. You have {self.config.guardian.captcha_expire} seconds.'

        # TODO: handle errors with sending photo and writing to redis
        msg = await self.bot.send_photo(message.chat.id, url, caption, reply_markup=keyboard_markup)
        args = (*chat_user, msg.message_id)
        await self.redis.set_answer(*args, comb.answer(), ignore_for=self.config.guardian.ignore_expire)
        asyncio.get_running_loop().call_later(self.config.guardian.captcha_expire,
                                              callback(self.after_question_timeout, *args, user_tag))

    async def handle_left_chat_member(self, message: Message):
        try:
            await message.delete()
        except TelegramAPIError as e:
            log_exception(e)

    async def handle_inline_kb_answer(self, query: types.CallbackQuery):
        answer_expected, message = query.data, query.message
        answer = await self.redis.get_answer(message.chat.id, query.from_user.id, message.message_id, delete=True)

        if answer == None:
            await query.answer("You're not allowed to answer this catcha.")
            return

        user_tag = get_user_tag(query.from_user)
        if answer == answer_expected:
            restricted, _, _ = await asyncio.gather(
                message.chat.restrict(query.from_user.id, **PERMISSIVE_ATTRIBUTES),
                query.answer('Correct!'),
                message.delete(),
                return_exceptions=True
            )

            # Don't welcome user if restriction didn't work
            if issubclass(type(restricted), TelegramAPIError):
                logger.error(restricted)
                await message.answer(restricted)
                return

            text = f'{user_tag} Welcome!\nKindly read our rules.'
            await self.send_message(message.chat.id, text, self.config.guardian.message_expire)
        else:
            await asyncio.gather(
                query.answer('Wrong!'),
                message.delete(),
                return_exceptions=True
            )
            text = f'{user_tag} Incorrect answer.\nYou can try to join the group again after 5 minutes.'
            await self.send_message(message.chat.id, text, self.config.guardian.message_expire)

    async def on_startup(self, _dp):
        webhook_url = f'https://{self.config.telegram.webhook_host}/bot{self.config.telegram.token}/'
        await self.bot.set_webhook(webhook_url)

    async def on_shutdown(self, _dp):
        logger.warning('Shutting down..')
        await self.bot.delete_webhook()
        logger.warning('Bye!')

    def start(self):
        if 'webhook_host' in self.config.telegram:
            start_webhook(
                dispatcher=self.dp,
                webhook_path='',
                on_startup=self.on_startup,
                on_shutdown=self.on_shutdown,
                skip_updates=True,
                host=self.config.webhook.host,
                port=self.config.webhook.port
            )
        else:
            executor.start_polling(self.dp, skip_updates=True)
