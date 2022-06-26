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

PERMISSIVE_ATTRIBUTES = {
    'can_send_messages': True,
    'can_send_media_messages': True,
    'can_send_other_messages': True,
    'can_add_web_page_previews': True
}


# TODO: can fail if another admin deletes the message
async def send_message(chat_id: int, text: str, timeout: int | float):
    msg = await bot.send_message(chat_id, text)
    cb = callback(bot.delete_message, chat_id, msg.message_id)
    asyncio.get_running_loop().call_later(timeout, cb)


async def after_question_timeout(chat_id: int, user_id: int, message_id: int, user_tag: str):
    deleted = await redis.delete_answer(chat_id, user_id, message_id)
    if deleted:
        text = f'{user_tag} Time is over.\nYou can try to join the group again after 5 minutes.'
        await bot.delete_message(chat_id, message_id)
        await send_message(chat_id, text, config.guardian.message_expire)


async def handle_new_chat_member(message: Message):
    new_member = message.new_chat_members[0]
    if new_member.is_bot:
        the_bot = await message.bot.me
        if new_member.id == the_bot.id:
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
    if await redis.is_ignored(*chat_user):
        logger.info(f'Ignoring {chat_user[0]}:{chat_user[1]}')
        return

    comb = qna.pick(6)
    # TODO: handle request errors from Qwant.com
    url = await qwant.get_image_url(comb.query_phrase)

    keyboard_markup = emoji_keyboard(comb.emoji, rows=2)
    user_tag = get_user_tag(new_member)
    caption = f'{user_tag} Choose what is shown in the picture. You have {config.guardian.captcha_expire} seconds.'

    # TODO: handle errors with sending photo and writing to redis
    msg = await bot.send_photo(message.chat.id, url, caption, reply_markup=keyboard_markup)
    args = (*chat_user, msg.message_id)
    await redis.set_answer(*args, comb.answer(), ignore_for=config.guardian.ignore_expire)
    asyncio.get_running_loop().call_later(config.guardian.captcha_expire,
                                          callback(after_question_timeout, *args, user_tag))


async def handle_left_chat_member(message: Message):
    try:
        await message.delete()
    except TelegramAPIError as e:
        log_exception(e)


async def handle_inline_kb_answer(query: types.CallbackQuery):
    answer_expected, message = query.data, query.message
    answer = await redis.get_answer(message.chat.id, query.from_user.id, message.message_id, delete=True)

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
        await send_message(message.chat.id, text, config.guardian.message_expire)
    else:
        await asyncio.gather(
            query.answer('Wrong!'),
            message.delete(),
            return_exceptions=True
        )
        text = f'{user_tag} Incorrect answer.\nYou can try to join the group again after 5 minutes.'
        await send_message(message.chat.id, text, config.guardian.message_expire)


async def on_startup(dp):
    webhook_url = f'https://{config.telegram.webhook_host}/bot{config.telegram.token}/'
    await bot.set_webhook(webhook_url)


async def on_shutdown(dp):
    logger.warning('Shutting down..')
    await bot.delete_webhook()
    logger.warning('Bye!')


def start_bot(cfg):
    global bot, redis, config

    config = cfg
    bot = Bot(token=config.telegram.token, parse_mode=types.ParseMode.HTML)
    dp = Dispatcher(bot)
    dp.middleware.setup(LoggingMiddleware(logger))
    redis = Redis(config.redis.url)

    dp.register_message_handler(handle_new_chat_member,
                                chat_type=[ChatType.GROUP, ChatType.SUPERGROUP],
                                content_types=ContentType.NEW_CHAT_MEMBERS)

    dp.register_message_handler(handle_left_chat_member,
                                chat_type=[ChatType.GROUP, ChatType.SUPERGROUP],
                                content_types=ContentType.LEFT_CHAT_MEMBER)

    dp.register_callback_query_handler(handle_inline_kb_answer)

    if 'webhook_host' in config.telegram:
        start_webhook(
            dispatcher=dp,
            webhook_path='',
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=True,
            host=config.webhook.host,
            port=config.webhook.port
        )
    else:
        executor.start_polling(dp, skip_updates=True)
