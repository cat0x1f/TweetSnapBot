from __future__ import annotations

import io
import logging
import time
from html import escape
from typing import Optional

from telegram import InputFile, Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import SessionConfig, Settings, load_settings
from fxtwitter import FxTwitterClient
from parser import extract_status_id, parse_request
from renderer import render_tweet_card


LOGGER = logging.getLogger(__name__)
INITIAL_RETRY_DELAY_SECONDS = 5
MAX_RETRY_DELAY_SECONDS = 300


def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=getattr(logging, level_name, logging.INFO),
    )


def render_help(settings: Settings, user_id: int) -> str:
    sessions = settings.user_sessions.get(user_id, [])
    session_lines = "\n".join(f"- <code>{escape(name)}</code>" for name in sessions) or "- 无"
    return (
        "发送推文链接即可截图。\n\n"
        "用法：\n"
        "1. 只有一个会话时：直接发送链接\n"
        "2. 有多个会话时：<code>会话名 链接</code>\n"
        "3. 一条消息里可以带多个链接\n\n"
        "你可用的会话：\n"
        f"{session_lines}"
    )


def resolve_session_name(settings: Settings, user_id: int, requested: Optional[str]) -> Optional[str]:
    allowed = settings.user_sessions.get(user_id, [])
    if not allowed:
        return None

    if requested:
        return requested if requested in allowed else None

    if len(allowed) == 1:
        return allowed[0]

    return None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return

    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_html(render_help(settings, update.effective_user.id))


async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return

    settings: Settings = context.application.bot_data["settings"]
    await update.message.reply_html(render_help(settings, update.effective_user.id))


def build_caption(template: str, session_name: str, tweet_url: str, user) -> str:
    user_name = user.full_name if user else "Unknown"
    username = f"@{user.username}" if user and user.username else "-"
    return template.format(
        session=session_name,
        tweet_url=tweet_url,
        user_id=user.id if user else "-",
        user_name=user_name,
        username=username,
    )


async def send_screenshot(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    session: SessionConfig,
    screenshot_bytes: bytes,
    filename: str,
    caption: str,
) -> None:
    for chat_id in session.targets:
        file_obj = InputFile(io.BytesIO(screenshot_bytes), filename=filename)
        await context.bot.send_photo(chat_id=chat_id, photo=file_obj, caption=caption)


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

    parsed = parse_request(message.text or message.caption or "")
    if not parsed.tweet_urls:
        await message.reply_text("没有识别到推文链接。发送 x.com / twitter.com 的 status 链接即可。")
        return

    session_name = resolve_session_name(settings, user.id, parsed.session_name)
    if session_name is None:
        allowed = settings.user_sessions.get(user.id, [])
        if not allowed:
            await message.reply_text("你没有可用会话。")
            return

        available = ", ".join(allowed)
        await message.reply_text(f"请指定会话。可用会话：{available}")
        return

    session = settings.sessions[session_name]
    sent_count = 0

    for tweet_url in parsed.tweet_urls:
        status_id = extract_status_id(tweet_url)
        if not status_id:
            await message.reply_text(f"无法解析链接：{tweet_url}")
            continue

        try:
            tweet = client.get_tweet(tweet_url)
            screenshot_bytes = render_tweet_card(tweet, client, session)
            caption = build_caption(settings.caption_template, session_name, tweet_url, user)
            await send_screenshot(
                context=context,
                session=session,
                screenshot_bytes=screenshot_bytes,
                filename="tweet-card.png",
                caption=caption,
            )
            sent_count += 1
        except Exception as exc:
            LOGGER.exception("Failed to process %s for session %s", tweet_url, session_name)
            await message.reply_text(f"截图失败：{tweet_url}\n{type(exc).__name__}: {exc}")

    if sent_count:
        await message.reply_text(
            f"已处理 {sent_count} 条链接，目标会话：{session_name}，投递到 {len(session.targets)} 个 chat。"
        )


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.bot_token).build()
    application.bot_data["settings"] = settings
    application.bot_data["fxtwitter_client"] = FxTwitterClient(settings.fxtwitter_api_base)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("sessions", sessions_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    LOGGER.info("Starting TweetSnapBot with %s sessions", len(settings.sessions))

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
