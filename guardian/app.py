import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ChatType, ContentType, Message
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.executor import start_webhook
from aiogram.utils.exceptions import TelegramAPIError
from guardian import qwant, qna, log
from guardian.database import Database
from guardian.settings import Settings, Setting
from guardian.redis import Redis
from guardian.filters import UsernameFilter
from guardian.util import emoji_keyboard, settings_keyboard, get_user_tag, callback, log_exception, AttrDict
from guardian.i18n import I18nMiddleware

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
        global logger

        logger = log.init(config.log_level)
        storage = MemoryStorage()
        self.use_webhook = 'webhook_host' in config.telegram
        self.bot = Bot(token=config.telegram.token, parse_mode=types.ParseMode.HTML)
        self.dp = Dispatcher(self.bot, storage=storage)
        self.dp.middleware.setup(LoggingMiddleware(logger))
        self.dp.middleware.setup(I18nMiddleware(self.lang))
        self.settings = Settings(Database())
        self.redis = Redis(config.redis.url)
        self.config = config
        self.dp.filters_factory.bind(UsernameFilter, event_handlers=[self.dp.message_handlers])
        chat_admin = {'chat_type': CHAT_TYPE, 'is_chat_admin': True}
        self.dp.register_message_handler(self.handle_new_chat_member,
                                         content_types=ContentType.NEW_CHAT_MEMBERS,
                                         chat_type=CHAT_TYPE)

        self.dp.register_message_handler(self.handle_channel_message,
                                         username='Channel_Bot',
                                         chat_type=CHAT_TYPE)

        self.dp.register_message_handler(self.handle_left_chat_member,
                                         content_types=ContentType.LEFT_CHAT_MEMBER,
                                         chat_type=CHAT_TYPE)

        self.dp.register_message_handler(self.handle_settings_command,
                                         commands=['settings'],
                                         **chat_admin)

        self.dp.register_message_handler(self.handle_setting_value,
                                         state=SettingsState.value,
                                         **chat_admin)

        self.dp.register_callback_query_handler(self.handle_inline_kb_captcha_response,
                                                state=CaptchaState.show,
                                                chat_type=CHAT_TYPE)

        self.dp.register_callback_query_handler(self.handle_inline_kb_setting_id,
                                                state=SettingsState.name,
                                                **chat_admin)

        self.dp.register_callback_query_handler(self.handle_inline_kb_setting_value,
                                                state=SettingsState.value,
                                                **chat_admin)

        self.dp.register_callback_query_handler(self.handle_inline_keyboard)

    @staticmethod
    def format_errors(errors: list[str], i18n) -> str:
        return i18n.t('errors.validation_error', errors='\n'.join(errors))

    def lang(self, chat_id: int):
        return self.settings.get(chat_id, Setting.LANGUAGE)

    # TODO: can throw exception if another admin deletes the message
    async def send_temp_message(self, chat_id: int, text: str, expire: int | float | None = None):
        if expire is None:
            expire = self.config.guardian.message_expire
        msg = await self.bot.send_message(chat_id, text)
        cb = callback(self.bot.delete_message, chat_id, msg.message_id)
        asyncio.get_running_loop().call_later(expire, cb)

    async def after_captcha_timeout(self, state: FSMContext, chat_id: int, message_id: int, text: str):
        current_state = await state.get_state()
        if current_state is not None:
            await asyncio.gather(
                self.bot.delete_message(chat_id, message_id),
                state.finish(),
                return_exceptions=True
            )
            await self.send_temp_message(chat_id, text)

    async def handle_new_chat_member(self, message: Message, state: FSMContext, i18n):
        chat_id = message.chat.id
        new_member = message.new_chat_members[0]
        if new_member.is_bot:
            bot = await message.bot.me
            if new_member.id == bot.id:
                await message.answer(i18n.t('bot.make_me_admin'))
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
        caption = i18n.t('captcha.caption', user_tag=user_tag,
                         expire=self.config.guardian.captcha_expire)

        # TODO: handle errors with sending photo and writing to redis
        msg, _ = await asyncio.gather(
            self.bot.send_photo(chat_id, url, caption, reply_markup=keyboard),
            CaptchaState.show.set()
        )
        await self.redis.ignore(chat_id, new_member.id, duration=self.config.guardian.ignore_expire)
        async with state.proxy() as data:
            # Store ID of this captcha keyboard message in the user's store.
            # Will check it later in the keyboard handler to prevent other users from using this keyboard.
            data['message_id'] = msg.message_id
            data['answer'] = comb.answer()

        text = i18n.t('captcha.time_over', user_tag=user_tag)
        asyncio.get_running_loop().call_later(self.config.guardian.captcha_expire,
                                              callback(self.after_captcha_timeout,
                                                       state,
                                                       chat_id,
                                                       msg.message_id,
                                                       text))

    async def handle_channel_message(self, message: Message):
        if self.settings.get(message.chat.id, Setting.BAN_CHANNELS):
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

    async def handle_settings_command(self, message: Message, state: FSMContext, i18n):
        pairs = map(lambda s: (str(s.value), s.title), Setting)
        keyboard = settings_keyboard(list(pairs), 2)
        msg, _ = await asyncio.gather(
            message.answer(i18n.t('settings.choose_name'), reply_markup=keyboard),
            message.delete()
        )
        async with state.proxy() as data:
            data['message_id'] = msg.message_id
        await SettingsState().name.set()

    async def handle_inline_kb_setting_id(self, query: types.CallbackQuery, state: FSMContext, i18n):
        setting, message = Setting(int(query.data)), query.message
        async with state.proxy() as data:
            if data['message_id'] != message.message_id:
                await query.answer(i18n.t('query.wrong_user'))
                return
            data['setting'] = setting
            raw_value = self.settings.get(message.chat.id, setting)
            default = ''
            if raw_value is None:
                default = ' (' + i18n.t('settings.default') + ')'
                if setting == Setting.WELCOME_MESSAGE:
                    value = i18n.t('bot.welcome', user_tag='{user_tag}')
                else:
                    value = setting.default_value
            else:
                value = raw_value
            if setting.variants is None:
                text = i18n.t('settings.enter_value', name=setting.title,
                              value=value, default=default)
                keyboard = None
            else:
                text = i18n.t('settings.choose_value', name=setting.title,
                              value=value, default=default)
                keyboard = settings_keyboard(setting.variants, 2)
            msg, _ = await asyncio.gather(
                message.answer(text, reply_markup=keyboard),
                message.delete()
            )
            data['message_id'] = msg.message_id
        await SettingsState.next()

    async def handle_inline_kb_setting_value(self, query: types.CallbackQuery, state: FSMContext, i18n):
        raw_value, message = query.data, query.message
        async with state.proxy() as data:
            if data['message_id'] != message.message_id:
                await query.answer(i18n.t('query.wrong_user'))
                return

            setting = data['setting']
            if setting.variants is None:
                return

            await self.settings.set(message.chat.id, setting, raw_value)
            text = i18n.t('settings.value_set', name=setting.title,
                          value=setting.from_str(raw_value))
            await asyncio.gather(
                self.send_temp_message(message.chat.id, text),
                message.delete()
            )
        await state.finish()

    async def handle_setting_value(self, message: Message, state: FSMContext, i18n):
        async with state.proxy() as data:
            setting = data['setting']
            if setting.variants is not None:
                return

            value, chat_id = message.text.strip(), message.chat.id
            is_valid, errors = setting.validate(value, i18n.t)
            if not is_valid:
                msg, _, _ = await asyncio.gather(
                    message.answer(self.format_errors(errors, i18n)),
                    self.bot.delete_message(chat_id, data['message_id']),
                    message.delete()
                )
                data['message_id'] = msg.message_id
                return

            await self.settings.set(chat_id, setting, value)
            text = i18n.t('settings.value_set', name=setting.title, value=value)
            await asyncio.gather(
                self.send_temp_message(chat_id, text),
                self.bot.delete_message(chat_id, data['message_id']),
                message.delete()
            )
        await state.finish()

    async def handle_inline_kb_captcha_response(self, query: types.CallbackQuery, state: FSMContext, i18n):
        user_answer, message, chat_id = query.data, query.message, query.message.chat.id

        async with state.proxy() as data:
            if data['message_id'] != message.message_id:
                await query.answer(i18n.t('query.wrong_user'))
                return

            user_tag = get_user_tag(query.from_user)
            if data['answer'] == user_answer:
                restricted, _, _, _ = await asyncio.gather(
                    message.chat.restrict(query.from_user.id, **PERMISSIVE_ATTRIBUTES),
                    query.answer(i18n.t('query.correct')),
                    message.delete(),
                    state.finish(),
                    return_exceptions=True
                )

                # Don't welcome user if restriction didn't work
                if issubclass(type(restricted), TelegramAPIError):
                    logger.error(restricted)
                    await message.answer(restricted)
                    return

                text = self.settings.get(chat_id, Setting.WELCOME_MESSAGE)
                if text is None:
                    text = i18n.t('bot.welcome', user_tag=user_tag)
                else:
                    text = text.format(user_tag=user_tag)
                await self.send_temp_message(chat_id, text)
            else:
                await asyncio.gather(
                    query.answer(i18n.t('query.wrong')),
                    message.delete(),
                    state.finish(),
                    return_exceptions=True
                )
                text = i18n.t('bot.incorrect_answer', user_tag=user_tag)
                await self.send_temp_message(chat_id, text)

    async def handle_inline_keyboard(self, query: types.CallbackQuery, i18n):
        await query.answer(i18n.t('query.wrong_user'))

    async def on_startup(self, _dp):
        await self.redis.ping()
        if self.use_webhook:
            webhook_url = f'https://{self.config.telegram.webhook_host}/bot{self.config.telegram.token}/'
            await self.bot.set_webhook(webhook_url)
        await self.settings.load()

    async def on_shutdown(self, _dp):
        logger.warning('Shutting down..')
        if self.use_webhook:
            await self.bot.delete_webhook()
        await self.redis.close()

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
