from __future__ import annotations

import io
import logging
import time
from typing import Optional

from PIL import Image
from telegram import InputFile, Update
from telegram.constants import ChatType
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import RenderConfig, Settings, load_settings
from fxtwitter import FxTwitterClient
from parser import extract_status_id, parse_request
from renderer import render_tweet_card


LOGGER = logging.getLogger(__name__)
INITIAL_RETRY_DELAY_SECONDS = 5
MAX_RETRY_DELAY_SECONDS = 300
DOCUMENT_FALLBACK_ASPECT_RATIO = 3.0


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=getattr(logging, level_name, logging.INFO),
    )


def render_help(settings: Settings, user_id: int) -> str:
    return (
        "发送推文链接即可截图。\n\n"
        "用法：\n"
        "1. 直接发送 x.com / twitter.com 的 status 链接\n"
        "2. 一条消息里可以带多个链接\n"
        "3. 机器人会把截图投递到预设目标 chat\n\n"
        f"当前管理员白名单数量：{len(settings.admin_user_ids)}"
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return

    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_html(render_help(settings, update.effective_user.id))


async def send_screenshot(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    render_config: RenderConfig,
    screenshot_bytes: bytes,
    filename: str,
) -> None:
    image = Image.open(io.BytesIO(screenshot_bytes))
    width, height = image.size
    force_document = height / width > DOCUMENT_FALLBACK_ASPECT_RATIO

    for chat_id in render_config.targets:
        file_obj = InputFile(io.BytesIO(screenshot_bytes), filename=filename)
        if force_document:
            LOGGER.info(
                "Rendered image aspect ratio exceeds threshold, use send_document chat_id=%s size=%sx%s",
                chat_id,
                width,
                height,
            )
            await context.bot.send_document(chat_id=chat_id, document=file_obj)
            continue

        try:
            await context.bot.send_photo(chat_id=chat_id, photo=file_obj)
        except BadRequest:
            LOGGER.warning(
                "send_photo failed for chat_id=%s filename=%s, fallback to send_document",
                chat_id,
                filename,
            )
            file_obj = InputFile(io.BytesIO(screenshot_bytes), filename=filename)
            await context.bot.send_document(chat_id=chat_id, document=file_obj)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user or not chat:
        return

    LOGGER.info(
        "Received message chat_id=%s user_id=%s username=%s text=%r",
        chat.id,
        user.id,
        user.username,
        message.text or message.caption or "",
    )

    settings: Settings = context.application.bot_data["settings"]
    client: FxTwitterClient = context.application.bot_data["fxtwitter_client"]

    if chat.type != ChatType.PRIVATE:
        LOGGER.info("Ignore non-private message from chat %s", chat.id)
        return

    if user.id not in settings.admin_user_ids:
        LOGGER.info("Reject unauthorized user_id=%s", user.id)
        await context.bot.send_message(
            chat_id=chat.id,
            text="你没有权限使用这个机器人。",
            reply_to_message_id=message.message_id,
        )
        return

    parsed = parse_request(message.text or message.caption or "")
    if not parsed.tweet_urls:
        await context.bot.send_message(
            chat_id=chat.id,
            text="没有识别到推文链接。发送 x.com / twitter.com 的 status 链接即可。",
            reply_to_message_id=message.message_id,
        )
        return

    render_config = settings.render_config
    sent_count = 0

    for tweet_url in parsed.tweet_urls:
        status_id = extract_status_id(tweet_url)
        if not status_id:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"无法解析链接：{tweet_url}",
                reply_to_message_id=message.message_id,
            )
            continue

        try:
            tweet = client.get_tweet(tweet_url)
            screenshot_bytes = render_tweet_card(tweet, client, render_config)
            await send_screenshot(
                context=context,
                render_config=render_config,
                screenshot_bytes=screenshot_bytes,
                filename="tweet-card.png",
            )
            sent_count += 1
        except Exception as exc:
            LOGGER.exception("Failed to process %s", tweet_url)
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"截图失败：{tweet_url}\n{type(exc).__name__}: {exc}",
                reply_to_message_id=message.message_id,
            )

    if sent_count:
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"已处理 {sent_count} 条链接，已投递到 {len(render_config.targets)} 个 chat。",
            reply_to_message_id=message.message_id,
        )


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.bot_token).build()
    application.bot_data["settings"] = settings
    application.bot_data["fxtwitter_client"] = FxTwitterClient(settings.fxtwitter_api_base)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    LOGGER.info("Starting TweetSnapBot with %s targets", len(settings.render_config.targets))

    retry_delay = INITIAL_RETRY_DELAY_SECONDS
    while True:
        application: Optional[Application] = None
        try:
            application = build_application(settings)
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                bootstrap_retries=-1,
                close_loop=False,
            )
            retry_delay = INITIAL_RETRY_DELAY_SECONDS
        except KeyboardInterrupt:
            LOGGER.info("Stopping TweetSnapBot")
            break
        except Exception:
            LOGGER.exception(
                "Bot polling stopped due to a Telegram connection/runtime error. Restarting in %s seconds.",
                retry_delay,
            )
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY_SECONDS)
        finally:
            if application is not None:
                try:
                    application.stop_running()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
