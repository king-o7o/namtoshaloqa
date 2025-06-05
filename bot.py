import asyncio
import json
import logging
import time
from pathlib import Path
from typing import List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramNetworkError
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties


BOT_TOKEN = ""
SOURCE_CHAT_IDS: set[int] = {
    -1001433669620, # @namangantoshkent24
    -1001327239978, # @Namangantoshkent26
    -1001737181397, # @Namangan_toshkent_taksi_29
}

KEYWORDS = ["http://", "https://", "t.me/", "оламиз", "olamiz", "ketamiz", "💸", "⚡️", "🔥", "₽", "$","деньги", "О Л А М И З", "руб", "тыс", "заработ", "на", "одам оламиз", "почта оламиз", "юрамиз", "машина", "жентра", "кобалт", "без заправка", "тел", "телефон", "🏖", "👨‍🦱", "👩‍🦰", "💌", "🚔"]

RECIPIENTS_FILE = Path("recipients.json")

ADMINS: list[int] = [1189419672, 1602393068]

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)

log = logging.getLogger("bot")

router = Router()


# --- JSON ---
def load_recipients() -> List[int]:
    if not RECIPIENTS_FILE.exists():
        log.warning("Файл %s не найден, создаю пустой.", RECIPIENTS_FILE)
        save_recipients([])
        return []
    try:
        data = json.loads(RECIPIENTS_FILE.read_text(encoding="utf-8"))
        recips = list(map(int, data.get("recipients", [])))
        log.info("Загружено %d получателей.", len(recips))
        return recips
    except Exception:
        log.exception("Не удалось прочитать %s, использую пустой список.", RECIPIENTS_FILE)
        return []


def save_recipients(recipients: List[int]) -> None:
    data = {"recipients": recipients}
    RECIPIENTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    log.info("Список получателей сохранён (%d шт.).", len(recipients))


recipients: List[int] = load_recipients()
# --- #


# --- HANDLERЫ ---
@router.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message) -> None:
    await message.answer(f"👋 Ассалому алейкум!\nID: <code>{message.from_user.id}</code>")
    if message.from_user.id in ADMINS:
        await message.answer("Сиз бот администраторисиз. Қабул қилувчиларни бошқариш учун /add, /remove ва /list буйруқларидан фойдаланишингиз мумкин.\n\nМисол: <code>/add 123456789</code>")


@router.message(F.chat.id.in_(SOURCE_CHAT_IDS) & F.text)
async def relay_message(message: Message, bot: Bot) -> None:
    txt = (message.text or "").lower()

    if any(kw in txt for kw in KEYWORDS):
        return

    for user_id in recipients:
        try:
            # а) пересылаем оригинал
            await bot.forward_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )

            # б) доп сообщение
            info_text = build_info_text(message)
            await bot.send_message(
                chat_id=user_id,
                text=info_text,
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("Не удалось переслать сообщение получателю %s", user_id)


def build_info_text(message: Message) -> str:
    user = message.from_user
    full_name = (user.full_name or "—").replace("<", "&lt;").replace(">", "&gt;")
    username = f"@{user.username}" if user.username else "Йоқ"
    link = (
        f"https://t.me/{message.chat.username}/{message.message_id}"
        if message.chat.username
        else "Ссылка недоступна"
    )

    return (
        "✅ Мижоз ҳақида маълумот:\n"
        f"👤 Исм — <a href=\"tg://user?id={user.id}\">{full_name}</a>\n"
        f"💬 Username — {username}\n\n"
        f"🔗 {link}"
    )

# --- ADMIN PANEL--- #
def admin_only(handler):
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id not in ADMINS:
            await message.reply("⛔️ Сизда етарли ҳуқуқ йўқ.")
            log.warning("Пользователь %s пытался выполнить админ-команду.", message.from_user.id)
            return
        return await handler(message, *args, **kwargs)

    return wrapper


@router.message(Command("add"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_add(message: Message, **kwargs) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await message.reply("Фойдаланиш: /add [user_id]")
        return

    uid = int(parts[1])
    if uid in recipients:
        await message.reply("Бу id рўйхатда аллақачон мавжуд.")
        return

    recipients.append(uid)
    save_recipients(recipients)
    await message.reply(f"✅ Қўшилди: <code>{uid}</code>")
    

@router.message(Command("remove"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_remove(message: Message, **kwargs) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await message.reply("Фойдаланиш: /remove [user_id]")
        return

    uid = int(parts[1])
    if uid not in recipients:
        await message.reply("Бу id рўйхатда йўқ.")
        return

    recipients.remove(uid)
    save_recipients(recipients)
    await message.reply(f"🗑 Ўчирилди: <code>{uid}</code>")


@router.message(Command("list"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_list(message: Message, **kwargs) -> None:
    if not recipients:
        await message.reply("Рўйхат бўш.")
        return
    rows = "\n".join(map(str, recipients))
    await message.reply(f"Жорий қабул қилувчилар рўйхати:\n<code>{rows}</code>")


# --- POLLING --- #
async def _start_bot() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def main() -> None:
    """Перезапуск polling'а при критических ошибках."""
    while True:
        try:
            asyncio.run(_start_bot())
        except (KeyboardInterrupt, SystemExit):
            log.info("Бот остановлен вручную.")
            break
        except TelegramRetryAfter as e:
            # Flood-wait
            delay = int(e.retry_after) + 1
            log.warning("Flood-wait %s сек.", delay)
            time.sleep(delay)
        except TelegramNetworkError:
            log.exception("Проблемы сети, перезапуск через 5 секунд.")
            time.sleep(5)
        except Exception:
            log.exception("Критическая ошибка, перезапуск через 5 секунд.")
            time.sleep(5)


if __name__ == "__main__":
    main()