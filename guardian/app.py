import asyncio
import random
import typing
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ChatType, ContentType, Message
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_webhook
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.exceptions import TelegramAPIError
from guardian import qwant, qna
from guardian.log import logger
from guardian.database import Database
from guardian.redis import Redis
from guardian.filters import UsernameFilter
from guardian.util import emoji_keyboard, lang_keyboard, get_user_tag, get_lang, callback, log_exception, AttrDict, LANG_EMOJI
from guardian.i18n import I18n

i18n = I18n()
PERMISSIVE_ATTRIBUTES = {
    'can_send_messages': True,
    'can_send_media_messages': True,
    'can_send_other_messages': True,
    'can_add_web_page_previews': True
}
CHAT_TYPE = [ChatType.GROUP, ChatType.SUPERGROUP]


class LangState(StatesGroup):
    lang = State()


class App:
    def __init__(self, config: AttrDict):
        storage = MemoryStorage()
        self.use_webhook = 'webhook_host' in config.telegram
        self.bot = Bot(token=config.telegram.token, parse_mode=types.ParseMode.HTML)
        self.dp = Dispatcher(self.bot, storage=storage)
        self.dp.middleware.setup(LoggingMiddleware(logger))
        self.db = Database()
        self.redis = Redis(config.redis.url)
        self.config = config
        self.dp.filters_factory.bind(UsernameFilter, event_handlers=[self.dp.message_handlers])
        self.dp.register_message_handler(self.handle_new_chat_member,
                                         chat_type=CHAT_TYPE,
                                         content_types=ContentType.NEW_CHAT_MEMBERS)

        self.dp.register_message_handler(self.handle_channel_message,
                                         username='Channel_Bot',
                                         chat_type=CHAT_TYPE)

        self.dp.register_message_handler(self.handle_left_chat_member,
                                         chat_type=CHAT_TYPE,
                                         content_types=ContentType.LEFT_CHAT_MEMBER)

        self.dp.register_message_handler(self.handle_lang_command,
                                         commands=['lang'],
                                         chat_type=CHAT_TYPE,
                                         is_chat_admin=True)

        self.dp.register_message_handler(self.handle_set_lang, state=LangState.lang)
        self.dp.register_callback_query_handler(self.handle_inline_kb_answer)

    def lang(self, chat_id: int):
        return self.db.get_setting(chat_id, 'lang')

    # TODO: can fail if another admin deletes the message
    async def send_message(self, chat_id: int, text: str, expire: int | float):
        msg = await self.bot.send_message(chat_id, text)
        cb = callback(self.bot.delete_message, chat_id, msg.message_id)
        asyncio.get_running_loop().call_later(expire, cb)

    async def after_question_timeout(self, chat_id: int, user_id: int, message_id: int, user_tag: str):
        deleted = await self.redis.delete_answer(chat_id, user_id, message_id)
        if deleted:
            text = i18n.t(self.lang(chat_id), 'captcha.time_over', user_tag=user_tag)
            await self.bot.delete_message(chat_id, message_id)
            await self.send_message(chat_id, text, self.config.guardian.message_expire)

    async def handle_new_chat_member(self, message: Message):
        lang = self.lang(message.chat.id)
        new_member = message.new_chat_members[0]
        if new_member.is_bot:
            bot = await message.bot.me
            if new_member.id == bot.id:
                await message.answer(i18n.t(lang, 'bot.make_me_admin'))
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

        keyboard = emoji_keyboard(comb.emoji, rows=2)
        user_tag = get_user_tag(new_member)
        caption = i18n.t(lang, 'captcha.caption', user_tag=user_tag,
                         expire=self.config.guardian.captcha_expire)

        # TODO: handle errors with sending photo and writing to redis
        msg = await self.bot.send_photo(message.chat.id, url, caption, reply_markup=keyboard)
        args = (*chat_user, msg.message_id)
        await self.redis.set_answer(*args, comb.answer(), ignore_for=self.config.guardian.ignore_expire)
        asyncio.get_running_loop().call_later(self.config.guardian.captcha_expire,
                                              callback(self.after_question_timeout, *args, user_tag))

    async def handle_channel_message(self, message: Message):
        await message.delete()

    async def handle_left_chat_member(self, message: Message):
        try:
            await message.delete()
        except TelegramAPIError as e:
            log_exception(e)

    async def handle_lang_command(self, message: Message):
        keyboard = lang_keyboard(list(LANG_EMOJI.keys()), 3)
        await LangState.lang.set()
        await message.reply(i18n.t(self.lang(message.chat.id), 'lang.choose'), reply_markup=keyboard)

    async def handle_set_lang(self, message: Message, state: FSMContext):
        keyboard = types.ReplyKeyboardRemove()
        flag = message.text.strip()
        lang = get_lang(flag)
        if lang == None:
            await message.reply(i18n.t(self.lang(message.chat.id), 'lang.not_found'), reply_markup=keyboard)
        else:
            await self.db.set_setting(message.chat.id, 'lang', lang)
            await message.reply(i18n.t(self.lang(message.chat.id), 'lang.changed'), reply_markup=keyboard)
        await state.finish()

    async def handle_inline_kb_answer(self, query: types.CallbackQuery):
        answer_expected, message = query.data, query.message
        lang = self.lang(message.chat.id)
        answer = await self.redis.get_answer(message.chat.id, query.from_user.id, message.message_id, delete=True)

        if answer == None:
            await query.answer(i18n.t(lang, 'query.wrong_user'))
            return

        user_tag = get_user_tag(query.from_user)
        if answer == answer_expected:
            restricted, _, _ = await asyncio.gather(
                message.chat.restrict(query.from_user.id, **PERMISSIVE_ATTRIBUTES),
                query.answer(i18n.t(lang, 'query.correct')),
                message.delete(),
                return_exceptions=True
            )

            # Don't welcome user if restriction didn't work
            if issubclass(type(restricted), TelegramAPIError):
                logger.error(restricted)
                await message.answer(restricted)
                return

            text = i18n.t(lang, 'bot.welcome', user_tag=user_tag)
            await self.send_message(message.chat.id, text, self.config.guardian.message_expire)
        else:
            await asyncio.gather(
                query.answer(i18n.t(lang, 'query.wrong')),
                message.delete(),
                return_exceptions=True
            )
            text = i18n.t(lang, 'bot.incorrect_answer', user_tag=user_tag)
            await self.send_message(message.chat.id, text, self.config.guardian.message_expire)

    async def on_startup(self, _dp):
        if self.use_webhook:
            webhook_url = f'https://{self.config.telegram.webhook_host}/bot{self.config.telegram.token}/'
            await self.bot.set_webhook(webhook_url)
        await self.db.load_settings()

    async def on_shutdown(self, _dp):
        logger.warning('Shutting down..')
        if self.use_webhook:
            await self.bot.delete_webhook()

    def start(self):
        if self.use_webhook:
            start_webhook(
                dispatcher=self.dp,
                webhook_path='',
                on_startup=self.on_startup,
                on_shutdown=self.on_shutdown,
                host=self.config.webhook.host,
                port=self.config.webhook.port,
                skip_updates=True
            )
        else:
            executor.start_polling(
                self.dp,
                on_startup=self.on_startup,
                on_shutdown=self.on_shutdown,
                skip_updates=True
            )
