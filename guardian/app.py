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
from guardian.database import Database, SETTINGS
from guardian.redis import Redis
from guardian.filters import UsernameFilter
from guardian.util import emoji_keyboard, settings_keyboard, get_user_tag, callback, log_exception, AttrDict
from guardian.i18n import I18n

i18n = I18n()
PERMISSIVE_ATTRIBUTES = {
    'can_send_messages': True,
    'can_send_media_messages': True,
    'can_send_other_messages': True,
    'can_add_web_page_previews': True
}
CHAT_TYPE = [ChatType.GROUP, ChatType.SUPERGROUP]


class CaptchaState(StatesGroup):
    show = State()


class SettingsState(StatesGroup):
    name = State()
    value = State()


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

        self.dp.register_message_handler(self.handle_settings_command,
                                         commands=['settings'],
                                         chat_type=CHAT_TYPE,
                                         is_chat_admin=True)

        self.dp.register_callback_query_handler(self.handle_inline_kb_captcha_response,
                                                state=CaptchaState.show)

        self.dp.register_callback_query_handler(self.handle_inline_kb_setting_name,
                                                state=SettingsState.name)

        self.dp.register_callback_query_handler(self.handle_inline_kb_setting_value,
                                                state=SettingsState.value)

        self.dp.register_callback_query_handler(self.handle_inline_keyboard)

    def lang(self, chat_id: int):
        return self.db.get_setting(chat_id, 'language')

    # TODO: can fail if another admin deletes the message
    async def send_message(self, chat_id: int, text: str, expire: int | float):
        msg = await self.bot.send_message(chat_id, text)
        cb = callback(self.bot.delete_message, chat_id, msg.message_id)
        asyncio.get_running_loop().call_later(expire, cb)

    async def after_captcha_timeout(self, state: FSMContext, chat_id: int, message_id: int, user_tag: str):
        current_state = await state.get_state()
        if current_state is not None:
            await asyncio.gather(
                self.bot.delete_message(chat_id, message_id),
                state.finish(),
                return_exceptions=True
            )
            text = i18n.t(self.lang(chat_id), 'captcha.time_over', user_tag=user_tag)
            await self.send_message(chat_id, text, self.config.guardian.message_expire)

    async def handle_new_chat_member(self, message: Message, state: FSMContext):
        chat_id = message.chat.id
        lang = self.lang(chat_id)
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
        if await self.redis.is_ignored(chat_id, new_member.id):
            logger.info(f'Ignoring {chat_id}:{new_member.id}')
            return

        comb = qna.pick(6)
        # TODO: handle request errors from Qwant.com
        url = await qwant.get_image_url(comb.query_phrase)

        keyboard = emoji_keyboard(comb.emoji, rows=2)
        user_tag = get_user_tag(new_member)
        caption = i18n.t(lang, 'captcha.caption', user_tag=user_tag,
                         expire=self.config.guardian.captcha_expire)

        # TODO: handle errors with sending photo and writing to redis
        msg, _ = await asyncio.gather(
            self.bot.send_photo(chat_id, url, caption, reply_markup=keyboard),
            CaptchaState.show.set(),
            return_exceptions=True
        )
        await self.redis.ignore(chat_id, new_member.id, duration=self.config.guardian.ignore_expire)
        async with state.proxy() as data:
            # Store ID of this captcha keyboard message in the user's store.
            # Will check it later in the keyboard handler to prevent other users from using this keyboard.
            data['message_id'] = msg.message_id
            data['answer'] = comb.answer()

        asyncio.get_running_loop().call_later(self.config.guardian.captcha_expire,
                                              callback(self.after_captcha_timeout,
                                                       state,
                                                       chat_id,
                                                       msg.message_id,
                                                       user_tag))

    async def handle_channel_message(self, message: Message):
        await asyncio.gather(
            self.bot.ban_chat_sender_chat(message.chat.id, message.sender_chat.id),
            message.delete(),
            return_exceptions=True
        )

    async def handle_left_chat_member(self, message: Message):
        try:
            await message.delete()
        except TelegramAPIError as e:
            log_exception(e)

    async def handle_settings_command(self, message: Message, state: FSMContext):
        pairs = map(lambda k: (k, k.replace('_', ' ').capitalize()), Database.DEFAULTS.keys())
        keyboard = settings_keyboard(list(pairs), 2)
        msg, _, _ = await asyncio.gather(
            message.answer('Choose setting to change', reply_markup=keyboard),
            message.delete(),
            SettingsState().name.set()
        )
        async with state.proxy() as data:
            data['message_id'] = msg.message_id

    async def handle_inline_kb_setting_name(self, query: types.CallbackQuery, state: FSMContext):
        setting_name, message = query.data, query.message
        async with state.proxy() as data:
            if data['message_id'] != message.message_id:
                await query.answer(i18n.t(lang, 'query.wrong_user'))
                return
            data['name'] = setting_name

            keyboard = settings_keyboard(SETTINGS[setting_name], 2)

            msg, _ = await asyncio.gather(
                message.answer(
                    f'Choose new <code>{setting_name}</code> setting value', reply_markup=keyboard),
                message.delete()
            )
            data['message_id'] = msg.message_id
        await SettingsState.next()

    async def handle_inline_kb_setting_value(self, query: types.CallbackQuery, state: FSMContext):
        setting_value, message = query.data, query.message
        async with state.proxy() as data:
            if data['message_id'] != message.message_id:
                await query.answer(i18n.t(lang, 'query.wrong_user'))
                return

        await self.db.set_setting(message.chat.id, data['name'], setting_value)
        text = f'Setting <code>{data["name"]}</code> set to <code>{setting_value}</code>'
        await asyncio.gather(
            self.send_message(message.chat.id, text, self.config.guardian.message_expire),
            message.delete(),
            state.finish()
        )

    async def handle_inline_kb_captcha_response(self, query: types.CallbackQuery, state: FSMContext):
        user_answer, message = query.data, query.message
        lang = self.lang(message.chat.id)

        async with state.proxy() as data:
            if data['message_id'] != message.message_id:
                await query.answer(i18n.t(lang, 'query.wrong_user'))
                return

            user_tag = get_user_tag(query.from_user)
            if data['answer'] == user_answer:
                restricted, _, _, _ = await asyncio.gather(
                    message.chat.restrict(query.from_user.id, **PERMISSIVE_ATTRIBUTES),
                    query.answer(i18n.t(lang, 'query.correct')),
                    message.delete(),
                    state.finish(),
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
                    state.finish(),
                    return_exceptions=True
                )
                text = i18n.t(lang, 'bot.incorrect_answer', user_tag=user_tag)
                await self.send_message(message.chat.id, text, self.config.guardian.message_expire)

    async def handle_inline_keyboard(self, query: types.CallbackQuery):
        lang = self.lang(query.message.chat.id)
        await query.answer(i18n.t(lang, 'query.wrong_user'))

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
        kwargs = {
            'dispatcher': self.dp,
            'on_startup': self.on_startup,
            'on_shutdown': self.on_shutdown,
            'skip_updates': True
        }
        if self.use_webhook:
            start_webhook(
                webhook_path='',
                host=self.config.webhook.host,
                port=self.config.webhook.port,
                **kwargs
            )
        else:
            executor.start_polling(**kwargs)
