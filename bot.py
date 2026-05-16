import asyncio
import os
import csv
import io
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
import random
import json
from pathlib import Path
import base64
import uuid
from openai import OpenAI, APITimeoutError
from aiogram import F
from aiogram.types import FSInputFile


from aiogram import Bot, Dispatcher, BaseMiddleware, F
from typing import Any, Awaitable, Callable
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from app.openai_forecaster import generate_openai_forecast
from app.wc2026_forecast_context import build_wc2026_openai_context

from app.db import SessionLocal
from app.models import (
    CommandLog,
    Match,
    Prediction,
    ReminderLog,
    TournamentPrediction,
    TournamentResult,
    User,
    WorldCupFact,
    FactDeliveryLog,
    QuizQuestion,
    QuizAnswer,
    HistoricalArchiveCard,
    HistoricalArchiveDeliveryLog,
    GroupQuizSession,
    GroupQuizAnswer,

)
from app.admin import is_admin_telegram_id

from app.scoring import score_match_prediction, score_tournament_prediction

from app.ai_summary import generate_ai_summary
from app.wc2026_sync import sync_wc2026_schedule
from app.api_football import ApiFootballClient
from app.wc2026_sync import (
    get_fixture_score,
    get_winner_side,
    sync_wc2026_schedule,
)
from app.fifa_rankings import FifaRankingsStore
from app.team_names import get_team_name_ru

TOKEN = os.getenv("BOT_TOKEN")
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Moscow"))
MATCHDAY_TIMEZONE_NAME = os.getenv("MATCHDAY_TIMEZONE", "America/New_York")
MATCHDAY_TIMEZONE = ZoneInfo(MATCHDAY_TIMEZONE_NAME)
DAILY_FACTS_ENABLED = os.getenv("DAILY_FACTS_ENABLED", "false").lower() == "true"
DAILY_FACT_HOUR = int(os.getenv("DAILY_FACT_HOUR", "9"))
DAILY_FACT_MINUTE = int(os.getenv("DAILY_FACT_MINUTE", "0"))
DAILY_FACT_TIMEZONE = ZoneInfo(os.getenv("DAILY_FACT_TIMEZONE", "Europe/Moscow"))

DAILY_FACT_TARGET = os.getenv("DAILY_FACT_TARGET", "private").lower()
GROUP_CHAT_ID_RAW = os.getenv("GROUP_CHAT_ID", "").strip()


def get_group_chat_id() -> int | None:
    if not GROUP_CHAT_ID_RAW:
        return None

    try:
        return int(GROUP_CHAT_ID_RAW)
    except ValueError:
        return None

ADMIN_NOTIFY_ENABLED = os.getenv("ADMIN_NOTIFY_ENABLED", "true").lower() == "true"

TOURNAMENT_CODE = os.getenv("TOURNAMENT_CODE", "wc2026")
TOURNAMENT_STARTS_AT_RAW = os.getenv(
    "TOURNAMENT_STARTS_AT",
    "2026-06-11T21:00:00+03:00",
)
USER_HELP_TEXT = (
    "👋 Как играть в «Отец прогнозов»\n\n"
    "1️⃣ Прогноз на турнир\n"
    "До старта турнира нужно один раз внести прогноз на итоги:\n"
    "🏆 чемпион\n"
    "🥈 финалист\n"
    "🥉 3 место\n"
    "⚽ лучший бомбардир\n\n"
    "Команда:\n"
    "/tournament_set\n\n"
    "Бот пошагово спросит все ответы. "
    "До старта турнира прогноз можно менять сколько угодно раз.\n\n"
    "2️⃣ Прогнозы на матчи\n"
    "Перед каждым матчем нужно сделать прогноз на счет.\n\n"
    "Команда:\n"
    "/predict\n\n"
    "Бот покажет ближайшие матчи кнопками. "
    "Прогноз на матч можно менять сколько угодно раз, но только до стартового свистка.\n\n"
    "3️⃣ Скрытие прогнозов\n"
    "До начала матча другие участники не видят твой счет. "
    "Видно только, что прогноз сделан ✅.\n\n"
    "После старта матча прогнозы всех участников открываются.\n\n"
    "Прогнозы на итоги турнира тоже скрыты до старта турнира.\n\n"
    "4️⃣ Плей-офф\n"
    "В матчах на вылет можно дополнительно рискнуть и поставить, "
    "кто пройдет дальше:\n"
    "🟢 угадал проход — +1 очко\n"
    "🔴 не угадал — -1 очко\n"
    "⚪ не ставил на проход — 0 очков\n\n"
    "\n5️⃣ Основные команды\n"
    "/rules — правила начисления очков\n"
    "/predict — прогноз на ближайший игровой день\n"
    "/matches_all — все ближайшие матчи (30)\n"
    "/predictions — прогнозы участников по матчу\n"
    "/missing — где еще нет твоего прогноза\n"
    "/table — таблица участников\n"
    "/summary — твоя статистика\n"
    
    "\nТурнирные прогнозы:\n"
    "/tournament_set — прогноз на итоги турнира\n"
    "/tournament_predictions — прогнозы участников на турнир\n\n"
    
    "\nПолезные команды\n"
    "/forecast — прогноз Отца прогнозов 😎\n"
    "/predict_all — прогноз на любой будущий матч\n"
    "/missing_all — все ближайшие матчи без прогноза\n"
    "/match — карточка матча\n"
    "/mybets — твои прогнозы\n"
    "/ai_summary — ИИ-разбор твоей игры\n"
    
    "\nРазвлечения до старта турнира:\n"
    "/fact — факт о чемпионатах мира с выбором категории\n"
    "/fact wc2026 — факт про ЧМ-2026\n"
    "/fact record — факт про рекорды\n"
    "/quiz — мини-квиз с выбором категории\n"
    "/quiz_stats — твоя статистика квиза\n"
    "/archive — архив прошлых турниров\n"
    "/panini — сделать карточку игрока сборной по фото\n\n"

    "В общем чате доступны:\n"
    "/fact, /quiz, /quiz_table, /quiz_finish, /archive, /panini, /matches_all, /forecast, /table, /predictions, /tournament_predictions, /rules, /help\n\n"
)

TEAM_FLAGS = {
    # Русские названия
    "Мексика": "🇲🇽",
    "ЮАР": "🇿🇦",
    "Южная Корея": "🇰🇷",
    "Канада": "🇨🇦",
    "США": "🇺🇸",
    "Аргентина": "🇦🇷",
    "Бразилия": "🇧🇷",
    "Франция": "🇫🇷",
    "Испания": "🇪🇸",
    "Англия": "🏴",
    "Португалия": "🇵🇹",
    "Германия": "🇩🇪",
    "Нидерланды": "🇳🇱",
    "Бельгия": "🇧🇪",
    "Хорватия": "🇭🇷",
    "Италия": "🇮🇹",
    "Колумбия": "🇨🇴",
    "Сенегал": "🇸🇳",
    "Уругвай": "🇺🇾",
    "Япония": "🇯🇵",
    "Швейцария": "🇨🇭",
    "Дания": "🇩🇰",
    "Иран": "🇮🇷",
    "Турция": "🇹🇷",
    "Эквадор": "🇪🇨",
    "Австрия": "🇦🇹",
    "Нигерия": "🇳🇬",
    "Австралия": "🇦🇺",
    "Алжир": "🇩🇿",
    "Египет": "🇪🇬",
    "Норвегия": "🇳🇴",
    "Украина": "🇺🇦",
    "Панама": "🇵🇦",
    "Кот-д’Ивуар": "🇨🇮",
    "Польша": "🇵🇱",
    "Уэльс": "🏴",
    "Швеция": "🇸🇪",
    "Сербия": "🇷🇸",
    "Парагвай": "🇵🇾",
    "Чехия": "🇨🇿",
    "Венгрия": "🇭🇺",
    "Шотландия": "🏴",
    "Тунис": "🇹🇳",
    "Камерун": "🇨🇲",
    "ДР Конго": "🇨🇩",
    "Греция": "🇬🇷",
    "Словакия": "🇸🇰",
    "Венесуэла": "🇻🇪",
    "Узбекистан": "🇺🇿",
    "Коста-Рика": "🇨🇷",
    "Мали": "🇲🇱",
    "Перу": "🇵🇪",
    "Чили": "🇨🇱",
    "Катар": "🇶🇦",
    "Румыния": "🇷🇴",
    "Ирак": "🇮🇶",
    "Словения": "🇸🇮",
    "Ирландия": "🇮🇪",
    "Саудовская Аравия": "🇸🇦",
    "Новая Зеландия": "🇳🇿",
    "Босния и Герцеговина": "🇧🇦",

    # API/английские названия
    "Mexico": "🇲🇽",
    "South Africa": "🇿🇦",
    "South Korea": "🇰🇷",
    "Korea Republic": "🇰🇷",
    "Canada": "🇨🇦",
    "United States": "🇺🇸",
    "USA": "🇺🇸",
    "Argentina": "🇦🇷",
    "Brazil": "🇧🇷",
    "France": "🇫🇷",
    "Spain": "🇪🇸",
    "England": "🏴",
    "Portugal": "🇵🇹",
    "Germany": "🇩🇪",
    "Netherlands": "🇳🇱",
    "Belgium": "🇧🇪",
    "Croatia": "🇭🇷",
    "Italy": "🇮🇹",
    "Colombia": "🇨🇴",
    "Senegal": "🇸🇳",
    "Uruguay": "🇺🇾",
    "Japan": "🇯🇵",
    "Switzerland": "🇨🇭",
    "Denmark": "🇩🇰",
    "Iran": "🇮🇷",
    "IR Iran": "🇮🇷",
    "Turkey": "🇹🇷",
    "Türkiye": "🇹🇷",
    "Ecuador": "🇪🇨",
    "Austria": "🇦🇹",
    "Nigeria": "🇳🇬",
    "Australia": "🇦🇺",
    "Algeria": "🇩🇿",
    "Egypt": "🇪🇬",
    "Norway": "🇳🇴",
    "Ukraine": "🇺🇦",
    "Panama": "🇵🇦",
    "Côte d'Ivoire": "🇨🇮",
    "Ivory Coast": "🇨🇮",
    "Poland": "🇵🇱",
    "Wales": "🏴",
    "Sweden": "🇸🇪",
    "Serbia": "🇷🇸",
    "Paraguay": "🇵🇾",
    "Czechia": "🇨🇿",
    "Czech Republic": "🇨🇿",
    "Hungary": "🇭🇺",
    "Scotland": "🏴",
    "Tunisia": "🇹🇳",
    "Cameroon": "🇨🇲",
    "DR Congo": "🇨🇩",
    "Congo DR": "🇨🇩",
    "Greece": "🇬🇷",
    "Slovakia": "🇸🇰",
    "Venezuela": "🇻🇪",
    "Uzbekistan": "🇺🇿",
    "Costa Rica": "🇨🇷",
    "Mali": "🇲🇱",
    "Peru": "🇵🇪",
    "Chile": "🇨🇱",
    "Qatar": "🇶🇦",
    "Romania": "🇷🇴",
    "Iraq": "🇮🇶",
    "Slovenia": "🇸🇮",
    "Ireland": "🇮🇪",
    "Saudi Arabia": "🇸🇦",
    "New Zealand": "🇳🇿",
    "Bosnia and Herzegovina": "🇧🇦",
    "Bosnia & Herzegovina": "🇧🇦",

    # Заглушки
    "TBD": "🏳️",
}

FIRST_START_MESSAGES_BY_TELEGRAM_ID = {
    147860673: (
        "Вадик, добро пожаловать обратно в «Отец прогнозов» 🏆\n\n"
        "Архивы беспощадны: ЧМ-2022 — 7 место, ЧЕ-2024 — уже 3/4 место после турнирных прогнозов. "
        "Рост очевиден: еще пара турниров — и таблица начнет бояться первой.\n\n"
        "Твой стиль — тихо зайти, не шуметь, а потом внезапно оказаться рядом с медалями. "
        "Как команда, которую никто не обсуждал перед турниром, но она почему-то уже в четвертьфинале.\n\n"
        "На ЧМ-2026 ждем продолжения камбэка: меньше нулей, больше точных счетов, "
        "и никаких подарков людям сверху таблицы.\n\n"
        "Прогноз на турнир: /tournament_set\n"
        "Прогнозы на матчи: /predict\n"
        "Где еще не поставил: /missing\n\n"
        "Правила: /rules\n"
        "Как играть: /help"
    ),

    186972507: (
        "Саня, добро пожаловать обратно в кабинет Отца прогнозов 🔴⚫️\n\n"
        "ЧМ-2022 — 5 место, ЧЕ-2024 без долгосрока — 3 место, но после турнирных прогнозов тебя аккуратно подвинули. "
        "Типичный Милан: первая половина выглядит многообещающе, потом приходит реальность и просит переставить мебель.\n\n"
        "Впрочем, стабильность у тебя есть: очки ты цеплять умеешь. "
        "Теперь задача — не просто быть рядом с призами, а наконец забрать то, что плохо лежит.\n\n"
        "Прогноз на турнир: /tournament_set\n"
        "Матчевые прогнозы: /predict\n"
        "Таблица: /table\n\n"
        "Правила: /rules\n"
        "Как играть: /help"
    ),

    244378697: (
        "Пикан, Willkommen обратно 🇩🇪🚂\n\n"
        "ЧМ-2022 — 3 место. ЧЕ-2024 — 6 место после турнирных прогнозов. "
        "График формы напоминает сборную Германии: вроде история великая, форма красивая, "
        "а потом кто-то снова спрашивает: «А точно всё под контролем?»\n\n"
        "Интер сейчас на ходу, Германия всегда где-то между машиной и мемом, Локомотив — отдельная философия. "
        "Идеальный набор для человека, который должен понимать: стабильность в футболе — миф, а таблица не прощает.\n\n"
        "На ЧМ-2026 ждем Пикана версии 2022, а не режим группового этапа Германии.\n\n"
        "Камбэк: /tournament_set\n"
        "Прогнозы: /predict\n"
        "Долги по матчам: /missing\n\n"
        "Правила: /rules\n"
        "Как играть: /help"
    ),

    342304476: (
        "Антонио, benvenuto в «Отец прогнозов» 🇮🇹🤌\n\n"
        "ЧМ-2022 — 4 место, ЧЕ-2024 — 6 место после турнирных прогнозов. "
        "Очень в стиле большого клуба: база есть, имя звучит, но где-то в мае обязательно находится таблица, "
        "которая портит вечер.\n\n"
        "С Интером сейчас всё бодро: титулы, финалы, статус. Но Отец прогнозов помнит и 0:5 от ПСЖ — "
        "идеальное напоминание, что даже сильная команда может внезапно стать скриншотом в чужом чате.\n\n"
        "На ЧМ-2026 ждем от тебя не эстетики Серии A, а холодных точных счетов.\n\n"
        "Прогноз на турнир: /tournament_set\n"
        "Прогнозы на матчи: /predict\n"
        "Личная статистика: /summary\n\n"
        "Правила: /rules\n"
        "Как играть: /help"
    ),
}

REPEAT_START_MESSAGES_BY_TELEGRAM_ID = {
    147860673: [
        "Вадик, ЧЕ-2024 показал: ты умеешь не шуметь и внезапно оказаться в медальной зоне. Подозрительно. Продолжай: /predict",
        "Вадик снова в здании. Таблица напряглась, нули приготовились к эвакуации. /missing",
        "Вадик, камбэк начинается не с громких слов, а с прогноза до стартового свистка. /predict",
        "Вадик, Отец прогнозов проверил архивы: потенциал есть, алиби нет. /table",
    ],

    186972507: [
        "Саня, Милан знает: быть рядом с вершиной больно. Отец прогнозов знает: еще больнее быть четвертым из-за долгосрока. /tournament_set",
        "Саня, красиво начать мало. Надо еще не подарить таблицу в концовке. /predict",
        "Саня, сегодня без романтики Милана: только счет, исход и холодный расчет. /missing",
        "Саня, долгосроки уже однажды пришли за тобой. Не дай им повторить это. /tournament_set",
    ],

    244378697: [
        "Пикан, Германия, Интер и Локомотив — это не клубные симпатии, а эмоциональный триатлон. Надеюсь, прогнозы будут стабильнее. /predict",
        "Пикан, включай режим ЧМ-2022. Режим ЧЕ-2024 лучше оставить в архиве. /table",
        "Пикан, немецкий порядок, интеровская мощь и локомотивский хаос ждут твоего прогноза. /predict",
        "Пикан, если Германия может верить в перезагрузку, то и ты можешь. /missing",
    ],

    342304476: [
        "Антонио, Интер берет титулы, Динамо тренирует нервы, а Отец прогнозов проверит, осталось ли у тебя чувство счета. /tournament_set",
        "Антонио, сегодня без итальянской драмы: просто поставь 2:1 и не спорь с судьбой. /predict",
        "Антонио, Динамо и Интер научили тебя терпеть. Теперь научись добивать таблицу. /table",
        "Антонио, если видишь 1:0 — это не обязательно катеначчо. Иногда это просто шанс на очко. /predict",
    ],
}

DEFAULT_FIRST_START_MESSAGE = (
    "Добро пожаловать в «Отец прогнозов» 🏆\n\n"
    "Здесь люди уверенно ставят 2:1, потом матч заканчивается 0:0, "
    "и начинается классика: судья, VAR, газон, тренер и «я вообще хотел поставить ничью».\n\n"
    "До старта турнира сделай прогноз на итоги: /tournament_set\n"
    "Перед матчами делай прогнозы: /predict\n"
    "Если забыл, где еще не поставил: /missing\n\n"
    "Правила: /rules\n"
    "Как играть: /help"
)

DEFAULT_REPEAT_START_MESSAGES = [
    "Отец прогнозов снова на связи. Таблица открыта, оправдания закрыты. /predict",
    "С возвращением. Где нет прогноза — там нет алиби. /missing",
    "Ты снова здесь. Значит, вера в 2:1 еще жива. /predict",
    "Отец прогнозов напоминает: матч начинается — прогнозы закрываются, паника открывается. /missing",
]

WC2026_START_DATE = date(2026, 6, 11)
QUIZ_SEED_PATH = Path("data/world_cup_quiz_seed.json")
HISTORICAL_ARCHIVE_SEED_PATH = Path("data/historical_archive_seed.json")

FACT_QUIZ_CATEGORIES = {
    "any": "🎲 Любая категория",
    "wc2026": "🏆 ЧМ-2026",
    "history": "📜 История",
    "record": "📊 Рекорды",
    "team": "👥 Сборные",
    "player": "⭐ Игроки",
    "host": "🏟 Хозяева",
    "trophy": "🏆 Трофеи",
    "funny": "😂 Курьезы",
}

GROUP_ALLOWED_COMMANDS = {
    "/start",
    "/help",
    "/rules",
    "/fact",
    "/quiz",
    "/quiz_finish",
    "/quiz_table",
    "/archive",
    "/chat_id",
    "/panini",

    # Добавляем:
    "/matches_all",
    "/forecast",
    "/match",
    "/predictions",
    "/table",
    "/tournament_predictions",
}

PRIVATE_ONLY_COMMANDS_HINT = (
    "Эта команда доступна только в личке с ботом.\n\n"
    "В общем чате можно использовать:\n"
    "/fact — факты о ЧМ\n"
    "/quiz — квиз о ЧМ\n"
    "/archive — архив прошлых турниров\n"
    "/matches_all — все будущие матчи\n"
    "/match — карточка матча\n"
    "/predictions — прогнозы по матчу\n"
    "/forecast — прогноз Отца прогнозов\n"
    "/table — таблица\n"
    "/tournament_predictions — турнирные прогнозы\n"
    "/rules — правила\n"
    "/help — как играть\n\n"
    "Делать и менять свои прогнозы лучше в личке: /predict"
)

GROUP_ALLOWED_CALLBACK_PREFIXES = {
    "fact_category:",
    "quiz_category:",
    "group_quiz_answer:",
    "archive_category:",

    # Добавляем:
    "forecast_match:",
    "panini_team:",
}

PLAYOFF_STAGES = {
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "third_place",
    "final",
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
PANINI_ENABLED = os.getenv("PANINI_ENABLED", "true").lower() == "true"
PANINI_IMAGE_MODEL = os.getenv("PANINI_IMAGE_MODEL", "gpt-image-1")
PANINI_COOLDOWN_SECONDS = int(os.getenv("PANINI_COOLDOWN_SECONDS", "120"))
PANINI_LAST_USED_BY_USER: dict[int, datetime] = {}
PANINI_IMAGE_SIZE = os.getenv("PANINI_IMAGE_SIZE", "1024x1536")

OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "300"))

openai_client = (
    OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=OPENAI_TIMEOUT_SECONDS,
        max_retries=1,
    )
    if OPENAI_API_KEY
    else None
)

def get_admin_telegram_ids() -> list[int]:
    raw_value = os.getenv("ADMIN_TELEGRAM_IDS", "")

    admin_ids = []

    for item in raw_value.split(","):
        item = item.strip()

        if item.isdigit():
            admin_ids.append(int(item))

    return admin_ids


class TournamentPredictionForm(StatesGroup):
    champion = State()
    runner_up = State()
    third_place = State()
    top_scorer = State()


class MatchPredictionForm(StatesGroup):
    custom_score = State()


class AdminResultForm(StatesGroup):
    custom_score = State()


class CommandLoggingMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            command = extract_command_from_text(event.text)

            if command:
                db = SessionLocal()

                try:
                    user = None

                    if event.from_user:
                        user, _ = get_or_create_user(db, event.from_user)

                    log = CommandLog(
                        user_id=user.id if user else None,
                        telegram_id=event.from_user.id if event.from_user else None,
                        display_name=user.display_name if user else None,
                        command=command,
                        full_text=event.text,
                    )

                    db.add(log)
                    db.commit()

                except Exception as error:
                    db.rollback()
                    print(f"Failed to log command: {error}")

                finally:
                    db.close()

        return await handler(event, data)


class GroupCommandAccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler,
        event,
        data,
    ):
        if isinstance(event, Message):
            command = extract_command_from_text(event.text)

            if command and event.chat.type != "private":
                if command not in GROUP_ALLOWED_COMMANDS:
                    await event.answer(PRIVATE_ONLY_COMMANDS_HINT)
                    return

        return await handler(event, data)


class GroupCallbackAccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler,
        event,
        data,
    ):
        if isinstance(event, CallbackQuery):
            message = event.message

            if message and message.chat.type != "private":
                callback_data = event.data or ""

                is_allowed = any(
                    callback_data.startswith(prefix)
                    for prefix in GROUP_ALLOWED_CALLBACK_PREFIXES
                )

                if not is_allowed:
                    await event.answer(
                        "Эта кнопка работает только в личке с ботом.",
                        show_alert=True,
                    )
                    return

        return await handler(event, data)


class PaniniForm(StatesGroup):
    waiting_for_photo = State()
    waiting_for_team = State()


def get_tournament_starts_at():
    dt = datetime.fromisoformat(
        TOURNAMENT_STARTS_AT_RAW.replace("Z", "+00:00")
    )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=APP_TIMEZONE)

    return dt.astimezone(timezone.utc)


def is_tournament_started() -> bool:
    return datetime.now(timezone.utc) >= get_tournament_starts_at()

def is_group_chat(message: Message) -> bool:
    return message.chat.type in {"group", "supergroup"}

def is_forecast_bot_user(user: User) -> bool:
    return getattr(user, "telegram_id", None) == 0

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(GroupCommandAccessMiddleware())
dp.message.middleware(CommandLoggingMiddleware())
dp.callback_query.middleware(GroupCallbackAccessMiddleware())


def get_or_create_user(db, telegram_user):
    admin_status = is_admin_telegram_id(telegram_user.id)

    existing_user = db.query(User).filter(
        User.telegram_id == telegram_user.id
    ).first()

    if existing_user:
        changed = False

        if existing_user.username != telegram_user.username:
            existing_user.username = telegram_user.username
            changed = True

        if existing_user.display_name != telegram_user.full_name:
            existing_user.display_name = telegram_user.full_name
            changed = True

        if existing_user.is_admin != admin_status:
            existing_user.is_admin = admin_status
            changed = True

        if changed:
            db.commit()
            db.refresh(existing_user)

        return existing_user, False

    new_user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        display_name=telegram_user.full_name,
        is_admin=admin_status,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user, True



def is_playoff_match(match: Match) -> bool:
    return match.stage in PLAYOFF_STAGES


def parse_advancement_choice(choice: str | None):
    if choice is None:
        return False, None

    normalized = choice.lower().strip()

    if normalized in ("none", "no", "нет", "не"):
        return False, None

    if normalized in ("home", "1", "хозяин", "хозяева"):
        return True, "home"

    if normalized in ("away", "2", "гость", "гости"):
        return True, "away"

    raise ValueError("Invalid advancement choice")


def format_advancement_prediction(prediction: Prediction, match: Match) -> str:
    if not prediction.advancement_bet_enabled:
        return "проход: не ставил"

    if prediction.predicted_advancing_side == "home":
        return f"проход: {match.home_team}"

    if prediction.predicted_advancing_side == "away":
        return f"проход: {match.away_team}"

    return "проход: не указан"


def parse_score(score_text: str):
    normalized = score_text.replace("-", ":").replace(" ", "")

    if ":" not in normalized:
        raise ValueError("Score must contain ':'")

    home_raw, away_raw = normalized.split(":", 1)

    if not home_raw.isdigit() or not away_raw.isdigit():
        raise ValueError("Score must contain numbers")

    return int(home_raw), int(away_raw)


def format_match(match: Match):
    start_text = format_datetime(match.starts_at)

    round_text = match.match_round or get_default_match_round(match.stage)

    group_text = ""
    if match.group_code:
        group_text = f"\nГруппа: {match.group_code}"

    return (
        f"#{match.id} {match.home_team} — {match.away_team}\n"
        f"Стадия: {match.stage}\n"
        f"Тур/стадия: {round_text}"
        f"{group_text}\n"
        f"Старт: {start_text}"
    )


def format_match_short_for_group(match: Match) -> str:
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)

    home_flag = get_team_flag(match.home_team_api_name or match.home_team)
    away_flag = get_team_flag(match.away_team_api_name or match.away_team)

    if match.group_code:
        group_text = f"Группа {match.group_code}"
    else:
        group_text = "Плей-офф"

    match_round = match.match_round or get_default_match_round(match.stage)

    if match.stage == "group":
        round_text = f"Тур {match_round}"
    else:
        round_text = f"Стадия {match_round}"

    return (
        f"#{match.id}. {group_text}. {round_text}. "
        f"{home_name} {home_flag} — {away_flag} {away_name}"
    )


def format_datetime(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_dt = dt.astimezone(APP_TIMEZONE)
    return local_dt.strftime("%d.%m.%Y %H:%M")


def get_today_moscow_range_utc() -> tuple[datetime, datetime]:
    now_moscow = datetime.now(APP_TIMEZONE)

    start_moscow = now_moscow.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_moscow = start_moscow + timedelta(days=1)

    return (
        start_moscow.astimezone(timezone.utc),
        end_moscow.astimezone(timezone.utc),
    )


def build_command_stats_for_period(
        db,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit_users: int = 20,
) -> list[dict]:
    query = db.query(CommandLog)

    if start_at:
        query = query.filter(CommandLog.created_at >= start_at)

    if end_at:
        query = query.filter(CommandLog.created_at < end_at)

    logs = query.order_by(CommandLog.created_at.desc()).all()

    stats_by_user = {}

    for log in logs:
        key = log.user_id or f"tg:{log.telegram_id}"

        if key not in stats_by_user:
            stats_by_user[key] = {
                "display_name": log.display_name or f"Telegram {log.telegram_id}",
                "telegram_id": log.telegram_id,
                "total": 0,
                "commands": {},
                "last_command": None,
                "last_at": None,
            }

        row = stats_by_user[key]

        row["total"] += 1
        row["commands"][log.command] = row["commands"].get(log.command, 0) + 1

        if row["last_at"] is None or log.created_at > row["last_at"]:
            row["last_at"] = log.created_at
            row["last_command"] = log.command

    rows = list(stats_by_user.values())

    rows.sort(
        key=lambda item: item["total"],
        reverse=True,
    )

    return rows[:limit_users]


def format_command_stats_block(title: str, rows: list[dict]) -> list[str]:
    lines = [title]

    if not rows:
        lines.append("Нет данных.")
        return lines

    for index, row in enumerate(rows, start=1):
        commands_sorted = sorted(
            row["commands"].items(),
            key=lambda item: item[1],
            reverse=True,
        )

        top_commands = ", ".join(
            f"{command} {count}"
            for command, count in commands_sorted[:5]
        )

        last_text = ""

        if row["last_at"] and row["last_command"]:
            last_text = (
                f"\n   последний: {row['last_command']} "
                f"в {format_datetime(row['last_at'])}"
            )

        lines.append(
            f"{index}. {row['display_name']} — {row['total']} выз."
            f"{last_text}\n"
            f"   {top_commands}"
        )

    return lines


def is_user_admin(user: User) -> bool:
    return bool(user.is_admin)

def is_private_chat(message: Message) -> bool:
    return message.chat.type == "private"

def ensure_admin_or_reply(user: User) -> bool:
    return bool(user.is_admin)


def parse_admin_match_payload(text: str):
    payload = text.replace("/admin_add_match", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) not in (4, 5, 6):
        raise ValueError("Invalid admin match format")

    home_team = parts[0]
    away_team = parts[1]
    starts_at_raw = parts[2]
    stage = parts[3]
    match_round = parts[4] if len(parts) >= 5 else get_default_match_round(stage)
    tournament_code = parts[5] if len(parts) == 6 else TOURNAMENT_CODE

    starts_at = datetime.fromisoformat(
        starts_at_raw.replace("Z", "+00:00")
    )

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

    starts_at = starts_at.astimezone(timezone.utc)

    return home_team, away_team, starts_at, stage, match_round, tournament_code


def parse_admin_edit_match_payload(text: str):
    payload = text.replace("/admin_edit_match", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) not in (5, 6, 7):
        raise ValueError("Invalid admin edit match format")

    match_id_raw = parts[0]

    if not match_id_raw.isdigit():
        raise ValueError("Match ID must be number")

    match_id = int(match_id_raw)
    home_team = parts[1]
    away_team = parts[2]
    starts_at_raw = parts[3]
    stage = parts[4]
    match_round = parts[5] if len(parts) >= 6 else get_default_match_round(stage)
    tournament_code = parts[6] if len(parts) == 7 else TOURNAMENT_CODE

    starts_at = datetime.fromisoformat(
        starts_at_raw.replace("Z", "+00:00")
    )

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

    starts_at = starts_at.astimezone(timezone.utc)

    return match_id, home_team, away_team, starts_at, stage, match_round, tournament_code


def parse_match_id_command(text: str, command: str) -> int:
    payload = text.replace(command, "", 1).strip()

    if not payload.isdigit():
        raise ValueError("Match ID must be number")

    return int(payload)


def parse_result_payload(text: str):
    parts = text.split()

    if len(parts) not in (3, 4):
        raise ValueError("Invalid result format")

    _, match_id_raw, score_raw, *winner_side_raw = parts

    if not match_id_raw.isdigit():
        raise ValueError("Match ID must be number")

    match_id = int(match_id_raw)
    score_home, score_away = parse_score(score_raw)

    winner_side = winner_side_raw[0].lower() if winner_side_raw else None

    if winner_side not in (None, "home", "away"):
        raise ValueError("Invalid winner_side")

    return match_id, score_home, score_away, winner_side


def build_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"predict_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_score_keyboard(match_id: int) -> InlineKeyboardMarkup:
    common_scores = [
        ("0:0", 0, 0),
        ("1:0", 1, 0),
        ("0:1", 0, 1),
        ("1:1", 1, 1),
        ("2:0", 2, 0),
        ("0:2", 0, 2),
        ("2:1", 2, 1),
        ("1:2", 1, 2),
        ("2:2", 2, 2),
        ("3:1", 3, 1),
        ("1:3", 1, 3),
    ]

    rows = []

    for index in range(0, len(common_scores), 3):
        row = []

        for label, home, away in common_scores[index:index + 3]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"predict_score:{match_id}:{home}:{away}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="Другой счет",
                callback_data=f"predict_custom:{match_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_category_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """
    prefix:
    - fact_category
    - quiz_category
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎲 Любая категория",
                    callback_data=f"{prefix}:any",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 ЧМ-2026",
                    callback_data=f"{prefix}:wc2026",
                ),
                InlineKeyboardButton(
                    text="📜 История",
                    callback_data=f"{prefix}:history",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Рекорды",
                    callback_data=f"{prefix}:record",
                ),
                InlineKeyboardButton(
                    text="👥 Сборные",
                    callback_data=f"{prefix}:team",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Игроки",
                    callback_data=f"{prefix}:player",
                ),
                InlineKeyboardButton(
                    text="🏟 Хозяева",
                    callback_data=f"{prefix}:host",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Трофеи",
                    callback_data=f"{prefix}:trophy",
                ),
                InlineKeyboardButton(
                    text="😂 Курьезы",
                    callback_data=f"{prefix}:funny",
                ),
            ],
        ]
    )

def build_admin_result_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"admin_result_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_admin_result_score_keyboard(match_id: int) -> InlineKeyboardMarkup:
    common_scores = [
        ("0:0", 0, 0),
        ("1:0", 1, 0),
        ("0:1", 0, 1),
        ("1:1", 1, 1),
        ("2:0", 2, 0),
        ("0:2", 0, 2),
        ("2:1", 2, 1),
        ("1:2", 1, 2),
        ("2:2", 2, 2),
        ("3:0", 3, 0),
        ("0:3", 0, 3),
        ("3:1", 3, 1),
        ("1:3", 1, 3),
        ("3:2", 3, 2),
        ("2:3", 2, 3),
    ]

    rows = []

    for index in range(0, len(common_scores), 3):
        row = []

        for label, home, away in common_scores[index:index + 3]:
            row.append(
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"admin_result_score:{match_id}:{home}:{away}",
                )
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="Другой счет",
                callback_data=f"admin_result_custom:{match_id}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_admin_result_winner_keyboard(
        match_id: int,
        score_home: int,
        score_away: int,
        match: Match,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Прошла {match.home_team}",
                    callback_data=(
                        f"admin_result_winner:{match_id}:{score_home}:{score_away}:home"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Прошла {match.away_team}",
                    callback_data=(
                        f"admin_result_winner:{match_id}:{score_home}:{score_away}:away"
                    ),
                )
            ],
        ]
    )


def build_advancement_keyboard(
        match_id: int,
        pred_home: int,
        pred_away: int,
        match: Match,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Рискнуть: пройдет {match.home_team}",
                    callback_data=(
                        f"predict_adv:{match_id}:{pred_home}:{pred_away}:home"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Рискнуть: пройдет {match.away_team}",
                    callback_data=(
                        f"predict_adv:{match_id}:{pred_home}:{pred_away}:away"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Не ставить на проход",
                    callback_data=(
                        f"predict_adv:{match_id}:{pred_home}:{pred_away}:none"
                    ),
                )
            ],
        ]
    )


def build_archive_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎲 Любая карточка",
                    callback_data="archive_category:any",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇶🇦 ЧМ-2022",
                    callback_data="archive_category:wc2022",
                ),
                InlineKeyboardButton(
                    text="🇩🇪 ЧЕ-2024",
                    callback_data="archive_category:euro2024",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🤦 Коллективные нули",
                    callback_data="archive_category:collective_fail",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Коллективные попадания",
                    callback_data="archive_category:collective_success",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎭 Долгосрок-драма",
                    callback_data="archive_category:longterm_drama",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏅 Достижения",
                    callback_data="archive_category:achievement",
                ),
                InlineKeyboardButton(
                    text="⚔️ Дерби",
                    callback_data="archive_category:rivalry",
                ),
            ],
        ]
    )


def build_group_quiz_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="A",
                    callback_data=f"group_quiz_answer:{session_id}:A",
                ),
                InlineKeyboardButton(
                    text="B",
                    callback_data=f"group_quiz_answer:{session_id}:B",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="C",
                    callback_data=f"group_quiz_answer:{session_id}:C",
                ),
                InlineKeyboardButton(
                    text="D",
                    callback_data=f"group_quiz_answer:{session_id}:D",
                ),
            ],
        ]
    )


def save_prediction(
        db,
        user: User,
        match: Match,
        pred_home: int,
        pred_away: int,
        advancement_bet_enabled: bool = False,
        predicted_advancing_side: str | None = None,
) -> tuple[bool, str]:
    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    if now >= match_start:
        return (
            False,
            "Ставки на этот матч уже закрыты. "
            "Отец прогнозов суров, но справедлив.",
        )

    existing_prediction = db.query(Prediction).filter(
        Prediction.user_id == user.id,
        Prediction.match_id == match.id,
    ).first()

    if existing_prediction:
        existing_prediction.pred_home = pred_home
        existing_prediction.pred_away = pred_away
        existing_prediction.advancement_bet_enabled = advancement_bet_enabled
        existing_prediction.predicted_advancing_side = predicted_advancing_side

        db.commit()
        db.refresh(existing_prediction)

        prediction = existing_prediction
        prefix = "Прогноз обновлен"
    else:
        prediction = Prediction(
            user_id=user.id,
            match_id=match.id,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        db.add(prediction)
        db.commit()
        db.refresh(prediction)

        prefix = "Прогноз принят"

    text = (
        f"{prefix}:\n"
        f"{format_match_label(match, include_id=False)}: "
        f"{pred_home}:{pred_away}"
    )

    if is_playoff_match(match):
        text += f"\n{format_advancement_prediction(prediction, match)}"

    return True, text


def save_tournament_prediction(
        db,
        user: User,
        champion: str,
        runner_up: str,
        third_place: str,
        top_scorer: str,
) -> tuple[bool, str]:
    existing_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == TOURNAMENT_CODE,
    ).first()

    if existing_prediction:
        existing_prediction.champion = champion
        existing_prediction.runner_up = runner_up
        existing_prediction.third_place = third_place
        existing_prediction.top_scorer = top_scorer

        existing_prediction.champion_points = 0
        existing_prediction.runner_up_points = 0
        existing_prediction.third_place_points = 0
        existing_prediction.top_scorer_points = 0
        existing_prediction.points = 0

        db.commit()

        return (
            True,
            "Турнирный прогноз обновлен 🏆\n\n"
            f"1 место: {champion}\n"
            f"2 место: {runner_up}\n"
            f"3 место: {third_place}\n"
            f"Бомбардир: {top_scorer}",
        )

    prediction = TournamentPrediction(
        user_id=user.id,
        tournament_code=TOURNAMENT_CODE,
        champion=champion,
        runner_up=runner_up,
        third_place=third_place,
        top_scorer=top_scorer,
    )

    db.add(prediction)
    db.commit()

    return (
        True,
        "Турнирный прогноз принят 🏆\n\n"
        f"1 место: {champion}\n"
        f"2 место: {runner_up}\n"
        f"3 место: {third_place}\n"
        f"Бомбардир: {top_scorer}",
    )


async def save_tournament_prediction_and_notify_admins(
        db,
        user: User,
        champion: str,
        runner_up: str,
        third_place: str,
        top_scorer: str,
) -> tuple[bool, str]:
    existing_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == TOURNAMENT_CODE,
    ).first()

    was_update = existing_prediction is not None

    success, text = save_tournament_prediction(
        db=db,
        user=user,
        champion=champion,
        runner_up=runner_up,
        third_place=third_place,
        top_scorer=top_scorer,
    )

    if success:
        action_text = "обновил" if was_update else "сделал"

        await notify_admins(
            "🏆 Турнирный прогноз\n\n"
            f"{user.display_name} {action_text} прогноз на турнир\n"
            f"1 место: {champion}\n"
            f"2 место: {runner_up}\n"
            f"3 место: {third_place}\n"
            f"Бомбардир: {top_scorer}",
            exclude_telegram_id=user.telegram_id,
        )

        await notify_group_tournament_prediction_saved(
            user=user,
            is_update=was_update,
        )

    return success, text


async def save_prediction_and_notify_admins(
        db,
        user: User,
        match: Match,
        pred_home: int,
        pred_away: int,
        advancement_bet_enabled: bool = False,
        predicted_advancing_side: str | None = None,
) -> tuple[bool, str]:
    existing_prediction = db.query(Prediction).filter(
        Prediction.user_id == user.id,
        Prediction.match_id == match.id,
    ).first()

    was_update = existing_prediction is not None

    success, text = save_prediction(
        db=db,
        user=user,
        match=match,
        pred_home=pred_home,
        pred_away=pred_away,
        advancement_bet_enabled=advancement_bet_enabled,
        predicted_advancing_side=predicted_advancing_side,
    )

    if success:
        action_text = "обновил прогноз" if was_update else "сделал прогноз"

        advancement_text = ""

        if is_playoff_match(match):
            if advancement_bet_enabled:
                if predicted_advancing_side == "home":
                    advancement_text = f"\nПроход: {match.home_team}"
                elif predicted_advancing_side == "away":
                    advancement_text = f"\nПроход: {match.away_team}"
            else:
                advancement_text = "\nПроход: не ставил"

        await notify_admins(
            "🔮 Участник сделал прогноз на матч\n\n"
            f"{user.display_name} {action_text}\n"
            f"{format_match_label(match, include_id=True)}\n"
            f"Прогноз: {pred_home}:{pred_away}"
            f"{advancement_text}",
            exclude_telegram_id=user.telegram_id,
        )

        await notify_group_prediction_saved(
            user=user,
            match=match,
            is_update=was_update,
        )

    return success, text


def get_available_matches_query(db):
    now = datetime.now(timezone.utc)

    return db.query(Match).filter(
        Match.is_finished == False,
        Match.starts_at > now,
    ).order_by(Match.starts_at.asc())


def get_panini_teams_from_matches(
    db,
    limit: int = 20,
) -> list[dict]:
    """
    Берем уникальные сборные из матчей текущего турнира,
    оставляем только тех, у кого найден FIFA ranking,
    сортируем по рейтингу и возвращаем топ-N.
    """

    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .all()
    )

    teams_by_key = {}

    for match in matches:
        candidates = [
            (
                getattr(match, "home_team_api_name", None) or match.home_team,
                match.home_team,
            ),
            (
                getattr(match, "away_team_api_name", None) or match.away_team,
                match.away_team,
            ),
        ]

        for api_name, display_name in candidates:
            if not api_name or api_name == "TBD":
                continue

            if api_name not in teams_by_key:
                teams_by_key[api_name] = {
                    "api_name": api_name,
                    "display_name": get_team_name_ru(display_name or api_name),
                }

    rankings = FifaRankingsStore()
    result = []

    for team in teams_by_key.values():
        ranking = rankings.get_context(team["api_name"])

        if not ranking or ranking.get("rank") is None:
            continue

        result.append(
            {
                "api_name": team["api_name"],
                "display_name": team["display_name"],
                "rank": int(ranking["rank"]),
                "flag": get_team_flag(
                    team["display_name"],
                    team["api_name"],
                ),
            }
        )

    result.sort(
        key=lambda item: (
            item["rank"],
            item["display_name"],
        )
    )

    return result[:limit]


def can_use_panini(user_id: int) -> tuple[bool, int]:
    now = datetime.now(timezone.utc)

    last_used = PANINI_LAST_USED_BY_USER.get(user_id)

    if not last_used:
        return True, 0

    elapsed = int((now - last_used).total_seconds())
    remaining = PANINI_COOLDOWN_SECONDS - elapsed

    if remaining > 0:
        return False, remaining

    return True, 0


def mark_panini_used(user_id: int):
    PANINI_LAST_USED_BY_USER[user_id] = datetime.now(timezone.utc)


def get_nearest_matchday_matches(
    db,
    matchdays_count: int = 1,
) -> list[Match]:
    """
    Возвращает матчи ближайших N игровых дней.

    По умолчанию matchdays_count=1 — текущее поведение:
    только ближайший игровой день.

    Игровой день считаем не по Москве, а по MATCHDAY_TIMEZONE.
    Например, для WC2026 удобно использовать America/New_York.
    """

    if matchdays_count < 1:
        matchdays_count = 1

    all_future_matches = get_available_matches_query(db).all()

    if not all_future_matches:
        return []

    selected_matchday_dates = []
    result = []

    for match in all_future_matches:
        matchday_date = match.starts_at.astimezone(
            MATCHDAY_TIMEZONE
        ).date()

        if matchday_date not in selected_matchday_dates:
            if len(selected_matchday_dates) >= matchdays_count:
                break

            selected_matchday_dates.append(matchday_date)

        if matchday_date in selected_matchday_dates:
            result.append(match)

    return result


def get_all_available_matches(db, limit: int = 30) -> list[Match]:
    return get_available_matches_query(db).limit(limit).all()


def format_match(match: Match):
    start_text = format_datetime(match.starts_at)

    group_text = ""
    if match.group_code:
        group_text = f"\nГруппа: {match.group_code}"

    venue_text = ""
    if match.venue or match.city:
        venue_parts = [part for part in [match.venue, match.city] if part]
        venue_text = f"\nСтадион: {', '.join(venue_parts)}"

    return (
        f"{format_match_label(match, include_id=True)}\n"
        f"Стадия: {match.stage}"
        f"{group_text}\n"
        f"Старт: {start_text}"
        f"{venue_text}"
    )


def get_default_match_round(stage: str) -> str:
    mapping = {
        "group": "1",
        "round_of_32": "1/16",
        "round_of_16": "1/8",
        "quarterfinal": "1/4",
        "semifinal": "1/2",
        "third_place": "матч за 3 место",
        "final": "финал",
    }

    return mapping.get(stage, stage)


def parse_csv_matches(csv_text: str) -> list[dict]:
    csv_text = csv_text.replace("\ufeff", "").strip()

    if not csv_text:
        raise ValueError("CSV is empty")

    first_line = csv_text.splitlines()[0]

    delimiter = ";" if ";" in first_line else ","

    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=delimiter,
    )

    required_columns = {
        "home_team",
        "away_team",
        "starts_at",
        "stage",
    }

    if not reader.fieldnames:
        raise ValueError("CSV has no header")

    fieldnames = {name.strip() for name in reader.fieldnames}

    missing = required_columns - fieldnames

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing))
        )

    rows = []

    for index, row in enumerate(reader, start=2):
        cleaned = {
            key.strip(): (value.strip() if value else "")
            for key, value in row.items()
            if key
        }

        if not cleaned.get("home_team") and not cleaned.get("away_team"):
            continue

        try:
            starts_at = datetime.fromisoformat(
                cleaned["starts_at"].replace("Z", "+00:00")
            )
        except ValueError:
            raise ValueError(
                f"Invalid starts_at at CSV line {index}: {cleaned.get('starts_at')}"
            )

        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

        starts_at = starts_at.astimezone(timezone.utc)

        fifa_match_no_raw = cleaned.get("fifa_match_no") or ""
        fifa_match_no = int(fifa_match_no_raw) if fifa_match_no_raw.isdigit() else None

        stage = cleaned.get("stage") or "group"

        rows.append(
            {
                "fifa_match_no": fifa_match_no,
                "home_team": cleaned["home_team"],
                "away_team": cleaned["away_team"],
                "starts_at": starts_at,
                "stage": stage,
                "match_round": cleaned.get("match_round") or get_default_match_round(stage),
                "tournament_code": cleaned.get("tournament_code") or TOURNAMENT_CODE,
                "group_code": cleaned.get("group_code") or None,
                "venue": cleaned.get("venue") or None,
                "city": cleaned.get("city") or None,
            }
        )

    return rows


def import_matches_from_rows(db, rows: list[dict]) -> dict:
    created = 0
    updated = 0
    skipped = 0
    imported_matches = []

    for row in rows:
        existing_match = None

        if row["fifa_match_no"] is not None:
            existing_match = db.query(Match).filter(
                Match.tournament_code == row["tournament_code"],
                Match.fifa_match_no == row["fifa_match_no"],
            ).first()

        if existing_match is None:
            existing_match = db.query(Match).filter(
                Match.tournament_code == row["tournament_code"],
                Match.home_team == row["home_team"],
                Match.away_team == row["away_team"],
                Match.starts_at == row["starts_at"],
            ).first()

        if existing_match:
            existing_match.home_team = row["home_team"]
            existing_match.away_team = row["away_team"]
            existing_match.starts_at = row["starts_at"]
            existing_match.stage = row["stage"]
            existing_match.match_round = row["match_round"]
            existing_match.group_code = row["group_code"]
            existing_match.venue = row["venue"]
            existing_match.city = row["city"]

            if row["fifa_match_no"] is not None:
                existing_match.fifa_match_no = row["fifa_match_no"]

            updated += 1
            match = existing_match
        else:
            match = Match(
                fifa_match_no=row["fifa_match_no"],
                home_team=row["home_team"],
                away_team=row["away_team"],
                starts_at=row["starts_at"],
                stage=row["stage"],
                match_round=row["match_round"],
                tournament_code=row["tournament_code"],
                group_code=row["group_code"],
                venue=row["venue"],
                city=row["city"],
            )

            db.add(match)
            created += 1

        imported_matches.append(row)

    db.commit()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(imported_matches),
    }


def reminders_enabled() -> bool:
    return os.getenv("REMINDERS_ENABLED", "false").lower() == "true"


def get_reminder_offsets_minutes() -> list[int]:
    raw_value = os.getenv("REMINDER_OFFSETS_MINUTES", "1440,180,30")

    offsets = []

    for item in raw_value.split(","):
        item = item.strip()

        if item.isdigit():
            offsets.append(int(item))

    return sorted(offsets, reverse=True)


def get_reminder_check_interval_seconds() -> int:
    raw_value = os.getenv("REMINDER_CHECK_INTERVAL_SECONDS", "60")

    if raw_value.isdigit():
        return int(raw_value)

    return 60


def format_reminder_offset(minutes: int) -> str:
    if minutes >= 1440:
        days = minutes // 1440

        if days == 1:
            return "24 часа"

        return f"{days} дн."

    if minutes >= 60:
        hours = minutes // 60

        if hours == 1:
            return "1 час"

        return f"{hours} часа"

    return f"{minutes} минут"


def user_has_prediction(db, user: User, match: Match) -> bool:
    prediction = db.query(Prediction).filter(
        Prediction.user_id == user.id,
        Prediction.match_id == match.id,
    ).first()

    return prediction is not None


def reminder_was_sent(
        db,
        user: User,
        match: Match,
        reminder_type: str,
        reminder_key: str,
) -> bool:
    existing_log = db.query(ReminderLog).filter(
        ReminderLog.user_id == user.id,
        ReminderLog.match_id == match.id,
        ReminderLog.reminder_type == reminder_type,
        ReminderLog.reminder_key == reminder_key,
    ).first()

    return existing_log is not None


def mark_reminder_sent(
        db,
        user: User,
        match: Match,
        reminder_type: str,
        reminder_key: str,
):
    log = ReminderLog(
        user_id=user.id,
        match_id=match.id,
        reminder_type=reminder_type,
        reminder_key=reminder_key,
    )

    db.add(log)
    db.commit()


def apply_match_result_from_admin(
        db,
        match: Match,
        score_home: int,
        score_away: int,
        winner_side: str | None = None,
) -> list[str]:
    if is_playoff_match(match) and winner_side is None:
        raise ValueError("Playoff match requires winner_side")

    if not is_playoff_match(match) and winner_side is not None:
        raise ValueError("Group match must not have winner_side")

    match.score_home = score_home
    match.score_away = score_away
    match.winner_side = winner_side
    match.is_finished = True

    predictions = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).all()

    recalculated = []

    for prediction in predictions:
        result = score_match_prediction(
            pred_home=prediction.pred_home,
            pred_away=prediction.pred_away,
            actual_home=score_home,
            actual_away=score_away,
            advancement_bet_enabled=prediction.advancement_bet_enabled,
            predicted_advancing_side=prediction.predicted_advancing_side,
            actual_winner_side=winner_side,
        )

        prediction.score_points = result["score_points"]
        prediction.advancement_points = result["advancement_points"]
        prediction.points = result["total_points"]

        recalculated.append(
            {
                "user": prediction.user.display_name,
                "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                "score_points": prediction.score_points,
                "advancement_points": prediction.advancement_points,
                "total_points": prediction.points,
            }
        )

    db.commit()

    lines = [
        "Результат сохранен ✅",
        "",
        f"{format_match_label(match, include_id=False)}: {score_home}:{score_away}",
    ]

    if winner_side == "home":
        lines.append(f"Прошла команда: {match.home_team}")
    elif winner_side == "away":
        lines.append(f"Прошла команда: {match.away_team}")

    lines.append("")
    lines.append("Пересчет прогнозов:")

    if not recalculated:
        lines.append("Прогнозов на этот матч нет.")
    else:
        for item in recalculated:
            lines.append(
                f"{item['user']}: {item['prediction']} → "
                f"{item['total_points']} очк. "
                f"({item['score_points']} за счет/исход, "
                f"{item['advancement_points']} за проход)"
            )

    return lines


def build_predictions_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"predictions_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_recent_and_upcoming_matches(db, limit: int = 20) -> list[Match]:
    now = datetime.now(timezone.utc)

    # Берем последние завершенные/начавшиеся и ближайшие будущие
    past_matches = (
        db.query(Match)
            .filter(Match.starts_at <= now)
            .order_by(Match.starts_at.desc())
            .limit(5)
            .all()
    )

    future_matches = (
        db.query(Match)
            .filter(Match.starts_at > now)
            .order_by(Match.starts_at)
            .limit(limit - len(past_matches))
            .all()
    )

    matches = list(reversed(past_matches)) + future_matches

    return matches


def build_match_card_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"match_card:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_panini_team_keyboard_from_list(
    teams: list[dict],
) -> InlineKeyboardMarkup:
    rows = []

    for index, team in enumerate(teams):
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{team['flag']} "
                        f"#{team['rank']} "
                        f"{team['display_name']}"
                    ).strip(),
                    callback_data=f"panini_team:{index}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_predictions_text(db, match: Match) -> str:
    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    is_revealed = now >= match_start

    users = db.query(User).order_by(User.display_name).all()

    predictions = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).all()

    predictions_by_user_id = {
        prediction.user_id: prediction
        for prediction in predictions
    }

    start_text = format_datetime(match.starts_at)

    lines = [
        "🔮 Прогнозы на матч",
        format_match_label(match, include_id=True),
        f"Старт: {start_text}",
        "",
    ]

    if is_revealed:
        lines.append("Матч уже начался — прогнозы открыты:")
        lines.append("")

        for user in users:
            prediction = predictions_by_user_id.get(user.id)

            if prediction:
                line = (
                    f"{user.display_name}: "
                    f"{prediction.pred_home}:{prediction.pred_away}"
                )

                if is_playoff_match(match):
                    line += f" ({format_advancement_prediction(prediction, match)})"

                if match.is_finished:
                    line += f" — {prediction.points or 0} очк."

                lines.append(line)
            else:
                lines.append(f"{user.display_name}: прогноза нет")

    else:
        lines.append("До старта матча прогнозы скрыты.")
        lines.append("Видно только, кто уже сделал прогноз:")
        lines.append("")

        for user in users:
            prediction = predictions_by_user_id.get(user.id)

            if prediction:
                lines.append(f"{user.display_name}: ✅ прогноз сделан")
            else:
                lines.append(f"{user.display_name}: ❌ прогноза нет")

    return "\n".join(lines)


def build_forecast_text(db, match: Match) -> str:
    context = build_wc2026_openai_context(db, match)

    forecast = generate_openai_forecast(context)

    pred_home = int(forecast["pred_home"])
    pred_away = int(forecast["pred_away"])

    outcome_text = {
        "home": f"победа {match.home_team}",
        "away": f"победа {match.away_team}",
        "draw": "ничья",
    }[forecast["outcome"]]

    confidence = int(float(forecast["confidence"]) * 100)

    fixture = context["fixture"]

    home_api_name = fixture["home_team_api_name"]
    away_api_name = fixture["away_team_api_name"]

    rankings = context.get("fifa_rankings_sofascore") or {}
    recent_short = context.get("recent_matches_short") or {}
    h2h = context.get("head_to_head") or {}

    ranking_home = rankings.get(home_api_name)
    ranking_away = rankings.get(away_api_name)

    recent_home = recent_short.get(home_api_name, [])
    recent_away = recent_short.get(away_api_name, [])

    h2h_rows = h2h.get("matches_short", [])

    facts_text = (
        "📌 Факты перед матчем\n\n"
        "FIFA ranking:\n"
        f"{format_ranking_fact(match.home_team, ranking_home)}\n"
        f"{format_ranking_fact(match.away_team, ranking_away)}\n\n"
        "Последние 3 матча:\n"
        f"{format_short_matches_fact(match.home_team, recent_home)}\n\n"
        f"{format_short_matches_fact(match.away_team, recent_away)}\n\n"
        "Личные встречи:\n"
        f"{format_h2h_fact(h2h_rows)}"
    )

    return (
        "🤖 Прогноз Отца прогнозов\n\n"
        f"{format_match_label(match, include_id=True)}\n"
        f"Старт: {format_datetime(match.starts_at)}\n\n"
        f"Прогноз счета: {pred_home}:{pred_away}\n"
        f"Исход: {outcome_text}\n"
        f"Уверенность: {confidence}%\n\n"
        f"{forecast.get('reason', '')}\n\n"
        f"{facts_text}\n\n"
        "Это развлекательный прогноз по футбольным данным и ИИ-анализу, "
        "не гарантия результата."
    )


def format_ranking_fact(team_name: str, ranking: dict | None) -> str:
    if not ranking:
        return f"{team_name}: рейтинг не найден"

    rank = ranking.get("rank")
    total_points = ranking.get("total_points")

    if total_points is not None:
        return f"{team_name}: #{rank}, {total_points} очк."

    return f"{team_name}: #{rank}"


def format_short_matches_fact(team_name: str, rows: list[dict]) -> str:
    if not rows:
        return f"{team_name}: нет данных"

    lines = [f"{team_name}:"]

    for row in rows[-3:]:
        lines.append(
            f"— {row.get('date')}: {row.get('match')} {row.get('score')}"
        )

    return "\n".join(lines)


def format_h2h_fact(rows: list[dict]) -> str:
    if not rows:
        return "Личных встреч в данных не найдено."

    lines = []

    for row in rows[-5:]:
        lines.append(
            f"— {row.get('date')}: {row.get('match')} {row.get('score')}"
        )

    return "\n".join(lines)


def build_forecast_matches_keyboard(matches: list[Match]) -> InlineKeyboardMarkup:
    buttons = []

    for match in matches:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=format_match_label(match, include_id=False),
                    callback_data=f"forecast_match:{match.id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def extract_command_from_text(text: str | None) -> str | None:
    if not text:
        return None

    first_part = text.strip().split()[0]

    if not first_part.startswith("/"):
        return None

    # Если команда пришла как /start@bot_name
    command = first_part.split("@")[0]

    return command.lower()





def get_start_message_for_user(user: User, created: bool) -> str:
    if created:
        return FIRST_START_MESSAGES_BY_TELEGRAM_ID.get(
            user.telegram_id,
            DEFAULT_FIRST_START_MESSAGE,
        )

    repeat_messages = REPEAT_START_MESSAGES_BY_TELEGRAM_ID.get(
        user.telegram_id,
        DEFAULT_REPEAT_START_MESSAGES,
    )

    return random.choice(repeat_messages)


def import_historical_archive_from_seed(db) -> dict:
    if not HISTORICAL_ARCHIVE_SEED_PATH.exists():
        raise FileNotFoundError(
            f"Файл не найден: {HISTORICAL_ARCHIVE_SEED_PATH}"
        )

    payload = json.loads(
        HISTORICAL_ARCHIVE_SEED_PATH.read_text(encoding="utf-8")
    )

    cards = payload.get("cards", [])

    created = 0
    updated = 0
    skipped = 0

    for item in cards:
        external_id = item.get("id")

        if not external_id:
            skipped += 1
            continue

        card = db.query(HistoricalArchiveCard).filter(
            HistoricalArchiveCard.external_id == external_id
        ).first()

        if not card:
            card = HistoricalArchiveCard(external_id=external_id)
            db.add(card)
            created += 1
        else:
            updated += 1

        card.title = item.get("title") or "Архив Отца прогнозов"
        card.text = item.get("text") or ""
        card.card_type = item.get("card_type")
        card.tournament_code = item.get("tournament_code")
        card.related_name = item.get("related_name")
        card.related_telegram_id = item.get("related_telegram_id")
        card.is_public = bool(item.get("is_public", True))
        card.is_active = bool(item.get("is_active", True))

    db.commit()

    return {
        "total": len(cards),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


def format_archive_card(card: HistoricalArchiveCard) -> str:
    tournament_title = {
        "wc2022": "ЧМ-2022",
        "euro2024": "ЧЕ-2024",
        "multi": "Архив турниров",
    }.get(card.tournament_code, "Архив турниров")

    return (
        "🔥 Архив Отца прогнозов\n\n"
        f"🏷 {card.title}\n"
        f"🗓 {tournament_title}\n\n"
        f"{card.text}"
    )


def format_group_quiz_question(question: QuizQuestion) -> str:
    category_text = FACT_QUIZ_CATEGORIES.get(
        question.category or "any",
        question.category or "История ЧМ",
    )

    year_text = (
        f"ЧМ-{question.tournament_year}"
        if question.tournament_year
        else "История ЧМ"
    )

    return (
        "❓ Квиз от Отца прогнозов\n\n"
        f"Категория: {category_text}\n"
        f"Тема: {year_text}\n\n"
        f"{question.question_text}\n\n"
        f"A) {question.option_a}\n"
        f"B) {question.option_b}\n"
        f"C) {question.option_c}\n"
        f"D) {question.option_d}\n\n"
        "Отвечайте кнопками ниже. Ответы пока скрыты."
    )


def get_random_quiz_question(db, category: str | None = None) -> QuizQuestion | None:
    query = db.query(QuizQuestion).filter(
        QuizQuestion.is_active == True,
    )

    if category:
        query = query.filter(QuizQuestion.category == category)

    questions = query.all()

    if not questions:
        return None

    return random.choice(questions)


async def private_quiz_handler(message: Message):
    db = SessionLocal()

    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) == 1:
            await message.answer(
                "❓ Выбери категорию квиза:",
                reply_markup=build_category_keyboard("quiz_category"),
            )
            return

        category = parts[1].strip().lower()

        if category == "any":
            category = None

        await send_quiz_by_category(
            message=message,
            db=db,
            category=category,
        )

    finally:
        db.close()


async def group_quiz_start_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        existing_session = db.query(GroupQuizSession).filter(
            GroupQuizSession.chat_id == message.chat.id,
            GroupQuizSession.status == "open",
        ).first()

        if existing_session:
            await message.answer(
                "В этом чате уже идет квиз ❓\n\n"
                "Сначала завершите текущий вопрос: /quiz_finish"
            )
            return

        parts = message.text.split(maxsplit=1)
        category = parts[1].strip().lower() if len(parts) > 1 else None

        if category == "any":
            category = None

        question = get_random_quiz_question(db, category=category)

        if not question:
            await message.answer(
                "Вопросов по такой категории пока нет.\n\n"
                "Попробуй просто /quiz"
            )
            return

        session = GroupQuizSession(
            chat_id=message.chat.id,
            quiz_question_id=question.id,
            status="open",
            started_by_user_id=user.id,
            category=category,
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        sent_message = await message.answer(
            format_group_quiz_question(question),
            reply_markup=build_group_quiz_keyboard(session.id),
        )

        session.message_id = sent_message.message_id
        db.commit()

    finally:
        db.close()

def finish_group_quiz_and_build_result_text(db, session: GroupQuizSession) -> str:
    question = session.question

    answers = db.query(GroupQuizAnswer).filter(
        GroupQuizAnswer.session_id == session.id,
    ).all()

    session.status = "finished"
    session.finished_at = datetime.now(timezone.utc)
    db.commit()

    option_texts = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }

    correct_option = question.correct_option.upper()
    correct_text = option_texts[correct_option]

    correct_answers = [
        answer.display_name
        for answer in answers
        if answer.is_correct
    ]

    wrong_answers = [
        f"{answer.display_name} ({answer.selected_option})"
        for answer in answers
        if not answer.is_correct
    ]

    lines = [
        "🏁 Квиз завершен",
        "",
        f"Вопрос: {question.question_text}",
        "",
        f"Правильный ответ: {correct_option}) {correct_text}",
    ]

    if question.explanation:
        lines.extend(["", question.explanation])

    lines.extend(["", "✅ Верно ответили:"])

    if correct_answers:
        lines.append(", ".join(correct_answers))
    else:
        lines.append("Никто. Очень мощно, господа.")

    lines.extend(["", "❌ Мимо:"])

    if wrong_answers:
        lines.append(", ".join(wrong_answers))
    else:
        lines.append("Никто.")

    if not answers:
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                "Вопрос был настолько сложный, что чат сделал вид, будто занят.",
            ]
        )
    elif correct_answers:
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                "Кто ответил верно — красавчики. Кто мимо — добро пожаловать в зону прогнозов 1:1.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                "Коллективный ноль. Архив Отца прогнозов уже заинтересовался.",
            ]
        )

    return "\n".join(lines)


def generate_panini_card(
    photo_path: str,
    person_name: str,
    team_api_name: str,
    team_display_name: str,
    team_flag: str,
) -> str:
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is not set")

    output_path = f"/tmp/panini_result_{uuid.uuid4().hex}.png"

    prompt = (
        "Create a collectible football sticker portrait card inspired by "
        "classic football sticker album cards, but do not copy any official Panini design. "
        "Use the uploaded person photo as the identity reference. "
        "Preserve the person's facial features, approximate age, hairstyle, and general appearance. "
        f"Depict the person as a player of the {team_api_name} national football team. "
        "Use a football jersey inspired by the national team's colors, "
        "without exact official logos, federation crests, or brand marks. "
        "Make it look like a polished collectible football card: portrait framing, "
        "decorative border, stadium or graphic background, premium sports lighting, "
        "dynamic but clean composition. "
        "Leave safe margins around the player and all text. "
        "The player should be centered in the upper-middle area, with enough space below for the nameplate. "
        f"Add readable card text with player name '{person_name}' and team name '{team_display_name}'. "
        f"Include the country flag vibe: {team_flag}. "
        "Vertical portrait collectible football sticker card, approximately 2:3 aspect ratio. "
        "Full card must be visible with no cropping: include the complete head, shoulders, jersey, border, nameplate, and team label. "
        "Do not crop the top of the head or the bottom nameplate. "
        "High quality, fun, realistic-stylized."
    )

    with open(photo_path, "rb") as image_file:
        result = openai_client.images.edit(
            model=PANINI_IMAGE_MODEL,
            image=image_file,
            prompt=prompt,
            size=PANINI_IMAGE_SIZE,
            n=1,
        )

    image_base64 = result.data[0].b64_json

    with open(output_path, "wb") as file:
        file.write(base64.b64decode(image_base64))

    return output_path


async def send_daily_fact_to_group(db, fact: WorldCupFact):
    group_chat_id = get_group_chat_id()

    if not group_chat_id:
        print("GROUP_CHAT_ID is not set or invalid")
        return

    text = format_daily_world_cup_rubric(fact)

    try:
        await bot.send_message(
            chat_id=group_chat_id,
            text=text,
        )

        db.add(
            FactDeliveryLog(
                fact_id=fact.id,
                user_id=None,
                telegram_id=None,
                chat_id=group_chat_id,
                delivery_type="daily_group",
            )
        )

        db.commit()

        print(f"Daily fact sent to group chat {group_chat_id}")

    except Exception as error:
        db.rollback()
        print(f"Failed to send daily fact to group {group_chat_id}: {error}")


async def notify_group_prediction_saved(
    user: User,
    match: Match,
    is_update: bool = False,
):
    if is_forecast_bot_user(user):
        return
    action_text = "обновил прогноз" if is_update else "сделал прогноз"

    await notify_group_chat(
        "✍️ Прогноз зафиксирован\n\n"
        f"{user.display_name} {action_text} на матч:\n"
        f"{format_match_short_for_group(match)}\n\n"
        "Сам прогноз пока скрыт. "
        "Отец прогнозов уважает тайну до стартового свистка."
    )

async def notify_group_tournament_prediction_saved(
    user: User,
    is_update: bool = False,
):
    if is_forecast_bot_user(user):
        return

    action_text = "обновил турнирный прогноз" if is_update else "сделал турнирный прогноз"

    await notify_group_chat(
        "🏆 Турнирный прогноз зафиксирован\n\n"
        f"{user.display_name} {action_text} на ЧМ-2026.\n\n"
        "Детали пока не раскрываем. "
        "Пусть интрига живет хотя бы до первого спорного VAR."
    )

@dp.message(Command("start"))
async def start_handler(message: Message):
    # В группе /start не регистрируем как полноценный личный старт
    if message.chat.type != "private":
        await message.answer(
            "Я тут для развлечений и общей статистики: /fact, /quiz, /archive, /table.\n\n"
            "Прогнозы лучше делать в личке с ботом: /predict"
        )
        return

    db = SessionLocal()

    try:
        user, created = get_or_create_user(db, message.from_user)

        await message.answer(
            get_start_message_for_user(user, created)
        )

        if created:
            username_text = (
                f"@{message.from_user.username}"
                if message.from_user.username
                else "без username"
            )

            # Старое уведомление админам, если оно есть
            await notify_admins(
                "🆕 Новый участник зарегистрировался\n\n"
                f"Имя: {user.display_name}\n"
                f"Telegram ID: {user.telegram_id}\n"
                f"Username: {username_text}",
                exclude_telegram_id=user.telegram_id,
            )

            # Новое уведомление в общий чат
            await notify_group_chat(
                "🆕 Новый участник зашел в турнир\n\n"
                f"{user.display_name} зарегистрировался в «Отце прогнозов».\n\n"
                "Отец прогнозов одобрительно открыл Excel, хотя Excel уже не нужен."
            )

    finally:
        db.close()


@dp.message(Command("matches"))
async def matches_handler(message: Message):
    db = SessionLocal()

    try:
        matches = get_nearest_matchday_matches(db)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        text = format_matches_list(
            matches,
            "📅 Ближайший игровой день",
        )

        await message.answer(
            text,
            reply_markup=build_matches_keyboard(matches),
        )

    finally:
        db.close()


@dp.message(Command("predict"))
async def predict_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        if len(parts) == 1:
            matches = get_nearest_matchday_matches(db)

            if not matches:
                await message.answer("Нет доступных матчей для прогноза.")
                return

            await message.answer(
                "Выбери матч ближайшего игрового дня:",
                reply_markup=build_matches_keyboard(matches),
            )
            return

        if len(parts) not in (3, 4):
            await message.answer(
                "Формат прогноза:\n"
                "/predict ID СЧЕТ\n\n"
                "Например:\n"
                "/predict 1 2:1\n\n"
                "Для плей-офф:\n"
                "/predict ID СЧЕТ home\n"
                "/predict ID СЧЕТ away\n"
                "/predict ID СЧЕТ none"
            )
            return

        _, match_id_raw, score_raw, *advancement_raw = parts

        if not match_id_raw.isdigit():
            await message.answer("ID матча должен быть числом.")
            return

        match_id = int(match_id_raw)

        try:
            pred_home, pred_away = parse_score(score_raw)
        except ValueError:
            await message.answer(
                "Не понял счет. Используй формат 2:1 или 2-1."
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if now >= match_start:
            await message.answer(
                "Ставки на этот матч уже закрыты. "
                "Отец прогнозов суров, но справедлив."
            )
            return

        advancement_bet_enabled = False
        predicted_advancing_side = None

        if is_playoff_match(match):
            choice = advancement_raw[0] if advancement_raw else "none"

            try:
                advancement_bet_enabled, predicted_advancing_side = (
                    parse_advancement_choice(choice)
                )
            except ValueError:
                await message.answer(
                    "Не понял ставку на проход.\n\n"
                    "Используй:\n"
                    "home — пройдет первая команда\n"
                    "away — пройдет вторая команда\n"
                    "none — не ставить на проход\n\n"
                    "Пример:\n"
                    "/predict 5 1:1 home"
                )
                return
        else:
            if advancement_raw:
                await message.answer(
                    "Это не матч плей-офф. "
                    "Ставка на проход доступна только в матчах на вылет."
                )
                return
        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        await message.answer(text)
        """
        existing_prediction = db.query(Prediction).filter(
            Prediction.user_id == user.id,
            Prediction.match_id == match.id,
        ).first()

        if existing_prediction:
            existing_prediction.pred_home = pred_home
            existing_prediction.pred_away = pred_away
            existing_prediction.advancement_bet_enabled = advancement_bet_enabled
            existing_prediction.predicted_advancing_side = predicted_advancing_side
            db.commit()

            text = (
                f"Прогноз обновлен:\n"
                f"{match.home_team} — {match.away_team}: "
                f"{pred_home}:{pred_away}"
            )

            if is_playoff_match(match):
                text += f"\n{format_advancement_prediction(existing_prediction, match)}"

            await message.answer(text)
            return

        prediction = Prediction(
            user_id=user.id,
            match_id=match.id,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        db.add(prediction)
        db.commit()
        db.refresh(prediction)

        text = (
            f"Прогноз принят:\n"
            f"{match.home_team} — {match.away_team}: "
            f"{pred_home}:{pred_away}"
        )

        if is_playoff_match(match):
            text += f"\n{format_advancement_prediction(prediction, match)}"

        await message.answer(text) 
        """

    finally:
        db.close()


@dp.message(Command("forecast"))
async def forecast_handler(message: Message):
    db = SessionLocal()

    try:
        parts = message.text.split()

        if len(parts) == 1:
            matches = get_nearest_matchday_matches(
                db,
                matchdays_count=3,
            )

            if not matches:
                await message.answer("Нет будущих матчей для прогноза.")
                return

            await message.answer(
                "🤖 Прогноз Отца прогнозов\nВыбери матч для ИИ-прогноза.\nПоказаны ближайшие 3 игровых дня:",
                reply_markup=build_forecast_matches_keyboard(matches),
            )
            return

        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат:\n\n"
                "/forecast\n\n"
                "или:\n"
                "/forecast ID\n\n"
                "Например:\n"
                "/forecast 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        await message.answer(build_forecast_text(db, match))

    finally:
        db.close()

@dp.message(Command("mybets"))
async def mybets_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        predictions = db.query(Prediction).filter(
            Prediction.user_id == user.id
        ).all()

        if not predictions:
            await message.answer("У тебя пока нет прогнозов.")
            return

        lines = ["🎯 Мои прогнозы:\n"]

        for prediction in predictions:
            match = prediction.match

            line = (
                f"{format_match_label(match, include_id=False)}: "
                f"{prediction.pred_home}:{prediction.pred_away}"
            )

            if is_playoff_match(match):
                line += f" ({format_advancement_prediction(prediction, match)})"

            lines.append(line)

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("predictions"))
async def predictions_handler(message: Message):
    db = SessionLocal()

    try:
        parts = message.text.split()

        # Новый кнопочный режим
        if len(parts) == 1:
            matches = get_recent_and_upcoming_matches(db, limit=20)

            if not matches:
                await message.answer("Матчей пока нет.")
                return

            await message.answer(
                "Выбери матч, по которому хочешь посмотреть прогнозы:",
                reply_markup=build_predictions_matches_keyboard(matches),
            )
            return

        # Старый ручной режим: /predictions ID
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат команды:\n\n"
                "/predictions\n\n"
                "или:\n"
                "/predictions ID\n\n"
                "Например:\n"
                "/predictions 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        await message.answer(build_predictions_text(db, match))

    finally:
        db.close()


@dp.message(Command("table"))
async def table_handler(message: Message):
    db = SessionLocal()

    try:
        users = db.query(User).all()

        rows = []

        for user in users:
            predictions = db.query(Prediction).filter(
                Prediction.user_id == user.id
            ).all()

            tournament_prediction = db.query(TournamentPrediction).filter(
                TournamentPrediction.user_id == user.id,
                TournamentPrediction.tournament_code == TOURNAMENT_CODE,
            ).first()

            match_points = sum(
                prediction.points or 0
                for prediction in predictions
            )

            tournament_points = (
                tournament_prediction.points
                if tournament_prediction
                else 0
            )

            total_points = match_points + tournament_points

            exact_scores = sum(
                1
                for prediction in predictions
                if prediction.score_points == 3
            )

            outcomes = sum(
                1
                for prediction in predictions
                if prediction.score_points == 1
            )

            advancement_plus = sum(
                1
                for prediction in predictions
                if prediction.advancement_points == 1
            )

            advancement_minus = sum(
                1
                for prediction in predictions
                if prediction.advancement_points == -1
            )

            total_predictions = len(predictions)

            rows.append(
                {
                    "name": user.display_name,
                    "points": total_points,
                    "exact_scores": exact_scores,
                    "outcomes": outcomes,
                    "advancement_plus": advancement_plus,
                    "advancement_minus": advancement_minus,
                    "tournament_points": tournament_points,
                    "total_predictions": total_predictions,
                }
            )

        rows.sort(
            key=lambda row: (
                row["points"],
                row["exact_scores"],
                row["outcomes"],
            ),
            reverse=True,
        )

        if not rows:
            await message.answer("Таблица пока пустая.")
            return

        lines = [
            "🏆 Таблица «Отец прогнозов»",
            "№ Игрок — Очки | 🎯 ✅ 🟢 🔴 🏆 📋",
            "",
        ]

        for index, row in enumerate(rows, start=1):
            name = row["name"]

            # Чтобы длинные имена не ломали таблицу
            if len(name) > 16:
                name = name[:15] + "…"

            lines.append(
                f"{index}. {name} — {row['points']} | "
                f"{row['exact_scores']} "
                f"{row['outcomes']} "
                f"{row['advancement_plus']} "
                f"{row['advancement_minus']} "
                f"{row['tournament_points']} "
                f"{row['total_predictions']}"
            )

        lines.append("")
        lines.append("🎯 точные счета (+3)")
        lines.append("✅ угаданные исходы (+1)")
        lines.append("🟢 угаданные проходы (+1)")
        lines.append("🔴 неугаданные проходы (-1)")
        lines.append("🏆 очки за прогноз на турнир")
        lines.append("📋 всего матчевых прогнозов")

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("rules"))
async def rules_handler(message: Message):
    await message.answer(
        "📜 Правила начисления очков\n\n"
        "За каждый матч:\n"
        "🎯 3 очка — точный счет\n"
        "✅ 1 очко — угаданный исход\n"
        "❌ 0 очков — если не угадан ни счет, ни исход\n\n"
        "Пример:\n"
        "Прогноз: Мексика — ЮАР 2:1\n\n"
        "Если матч закончился 2:1 — 3 очка.\n"
        "Если матч закончился 3:1 — 1 очко.\n"
        "Если матч закончился 2:2 или 0:1 — 0 очков.\n\n"
        "Плей-офф:\n"
        "В матчах на вылет можно дополнительно поставить, кто пройдет дальше:\n"
        "🟢 +1 очко — если проход угадан\n"
        "🔴 -1 очко — если проход не угадан\n"
        "⚪ 0 очков — если участник решил не ставить на проход\n\n"
        "Прогноз на итоги турнира:\n"
        "🏆 Чемпион — 15 очков\n"
        "🥈 Финалист — 10 очков\n"
        "🥉 3 место — 5 очков\n"
        "⚽ Бомбардир — 15 очков\n\n"
        "Краткая инструкция участника: /help"
    )


def parse_tournament_prediction_payload(text: str):
    payload = text.replace("/tournament_set", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("Invalid tournament prediction format")

    champion, runner_up, third_place, top_scorer = parts

    return champion, runner_up, third_place, top_scorer


def parse_tournament_result_payload(text: str):
    payload = text.replace("/admin_set_tournament_result", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("Invalid tournament result format")

    champion, runner_up, third_place, top_scorer = parts

    return champion, runner_up, third_place, top_scorer


def get_team_flag(team_name: str | None, api_name: str | None = None) -> str:
    if api_name and api_name in TEAM_FLAGS:
        return TEAM_FLAGS[api_name]

    if team_name and team_name in TEAM_FLAGS:
        return TEAM_FLAGS[team_name]

    return ""


def format_team_with_flag(
        display_name: str,
        api_name: str | None = None,
        flag_before: bool = False,
) -> str:
    flag = get_team_flag(display_name, api_name)

    if not flag:
        return display_name

    if flag_before:
        return f"{flag} {display_name}"

    return f"{display_name} {flag}"


def format_match_label(match: Match, include_id: bool = False) -> str:
    home_text = format_team_with_flag(
        display_name=match.home_team,
        api_name=getattr(match, "home_team_api_name", None),
        flag_before=False,
    )

    away_text = format_team_with_flag(
        display_name=match.away_team,
        api_name=getattr(match, "away_team_api_name", None),
        flag_before=True,
    )

    team_text = f"{home_text} — {away_text}"

    prefix_parts = []

    if match.stage == "group":
        if match.group_code:
            prefix_parts.append(f"Группа {match.group_code}")

        round_text = match.match_round or get_default_match_round(match.stage)

        if round_text:
            prefix_parts.append(f"Тур {round_text}")
    else:
        round_text = match.match_round or get_default_match_round(match.stage)

        if round_text:
            prefix_parts.append(round_text.capitalize())

    prefix = ". ".join(prefix_parts)

    if prefix:
        label = f"{prefix}. {team_text}"
    else:
        label = team_text

    if include_id:
        return f"#{match.id}. {label}"

    return label


def format_matches_list(matches: list[Match], title: str) -> str:
    lines = [title, ""]

    current_date = None

    for match in matches:
        matchday_dt = match.starts_at.astimezone(MATCHDAY_TIMEZONE)
        matchday_date = matchday_dt.date()

        if current_date != matchday_date:
            current_date = matchday_date
            lines.append(
                f"📅 Игровой день {matchday_dt.strftime('%d.%m.%Y')} "
                f"({MATCHDAY_TIMEZONE_NAME})"
            )

        status = "✅ завершен" if match.is_finished else "⏳ открыт"

        if match.score_home is not None and match.score_away is not None:
            status = f"🏁 {match.score_home}:{match.score_away}"

        lines.append(
            f"{format_match_label(match, include_id=True)}\n"
            f"Старт: {format_datetime(match.starts_at)}\n"
            f"Стадия: {match.stage} | {status}"
        )
        lines.append("")

    lines.append(
        "Сделать прогноз кнопками: /predict\n"
        "Посмотреть все будущие матчи: /matches_all"
    )

    return "\n".join(lines)


def get_user_prediction_match_ids(db, user: User) -> set[int]:
    predictions = db.query(Prediction).filter(
        Prediction.user_id == user.id
    ).all()

    return {
        prediction.match_id
        for prediction in predictions
    }


def get_missing_predictions_for_matches(
        db,
        user: User,
        matches: list[Match],
) -> list[Match]:
    predicted_match_ids = get_user_prediction_match_ids(db, user)

    return [
        match
        for match in matches
        if match.id not in predicted_match_ids
    ]


def format_missing_matches_list(matches: list[Match], title: str) -> str:
    lines = [title, ""]

    if not matches:
        lines.append("Все прогнозы сделаны ✅")
        return "\n".join(lines)

    current_date = None

    for match in matches:
        local_dt = match.starts_at.astimezone(APP_TIMEZONE)
        local_date = local_dt.date()

        if current_date != local_date:
            current_date = local_date
            lines.append(f"📅 {local_dt.strftime('%d.%m.%Y')}")
            lines.append("")

        lines.append(
            f"{format_match_label(match, include_id=True)}\n"
            f"Старт: {format_datetime(match.starts_at)}"
        )
        lines.append("")

    lines.append("Сделать прогноз: /predict")

    return "\n".join(lines)


def get_match_status(match: Match) -> str:
    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    if match.is_finished:
        return "🏁 Завершен"

    if now >= match_start:
        return "🔓 Идет / прогнозы открыты"

    return "⏳ Открыт для прогнозов"


def format_match_result(match: Match) -> str:
    if match.score_home is None or match.score_away is None:
        return "Результат: еще не внесен"

    result = f"Результат: {match.score_home}:{match.score_away}"

    if match.winner_side == "home":
        result += f"\nПрошла команда: {match.home_team}"
    elif match.winner_side == "away":
        result += f"\nПрошла команда: {match.away_team}"

    return result


def get_prediction_points_breakdown(prediction: Prediction) -> str:
    return (
        f"Очки: {prediction.points or 0} "
        f"({prediction.score_points or 0} за счет/исход, "
        f"{prediction.advancement_points or 0} за проход)"
    )


def format_user_match_prediction(
        prediction: Prediction | None,
        match: Match,
        reveal: bool = True,
) -> str:
    if not prediction:
        return "прогноза нет"

    if not reveal:
        return "✅ прогноз сделан"

    text = f"{prediction.pred_home}:{prediction.pred_away}"

    if is_playoff_match(match):
        text += f" ({format_advancement_prediction(prediction, match)})"

    if match.is_finished:
        text += f" — {get_prediction_points_breakdown(prediction)}"

    return text


def build_match_card_text(db, user: User, match: Match) -> str:
    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    predictions_are_revealed = now >= match_start

    my_prediction = db.query(Prediction).filter(
        Prediction.user_id == user.id,
        Prediction.match_id == match.id,
    ).first()

    predictions_count = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).count()

    users_count = db.query(User).count()

    lines = [
        "⚽ Карточка матча",
        "",
        format_match_label(match, include_id=True),
        f"Старт: {format_datetime(match.starts_at)}",
        f"Статус: {get_match_status(match)}",
        f"Стадия: {match.stage}",
    ]

    if match.group_code:
        lines.append(f"Группа: {match.group_code}")

    if match.match_round:
        if match.stage == "group":
            lines.append(f"Тур: {match.match_round}")
        else:
            lines.append(f"Раунд: {match.match_round}")

    if match.venue or match.city:
        venue_parts = [part for part in [match.venue, match.city] if part]
        lines.append(f"Стадион: {', '.join(venue_parts)}")

    lines.extend(
        [
            "",
            format_match_result(match),
            "",
            f"Прогнозов сделано: {predictions_count} из {users_count}",
            "",
            "Твой прогноз:",
            format_user_match_prediction(
                my_prediction,
                match,
                reveal=True,
            ),
            "",
        ]
    )

    users = db.query(User).order_by(User.display_name).all()

    predictions = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).all()

    predictions_by_user_id = {
        prediction.user_id: prediction
        for prediction in predictions
    }

    if predictions_are_revealed:
        lines.append("Прогнозы участников:")
        lines.append("")

        for participant in users:
            prediction = predictions_by_user_id.get(participant.id)

            lines.append(
                f"{participant.display_name}: "
                f"{format_user_match_prediction(prediction, match, reveal=True)}"
            )
    else:
        lines.append("До старта матча чужие прогнозы скрыты.")
        lines.append("Видно только, кто уже сделал прогноз:")
        lines.append("")

        for participant in users:
            prediction = predictions_by_user_id.get(participant.id)

            lines.append(
                f"{participant.display_name}: "
                f"{format_user_match_prediction(prediction, match, reveal=False)}"
            )

    return "\n".join(lines)


def build_user_summary_context(db, user: User) -> dict:
    predictions = db.query(Prediction).filter(
        Prediction.user_id == user.id
    ).all()

    tournament_prediction = db.query(TournamentPrediction).filter(
        TournamentPrediction.user_id == user.id,
        TournamentPrediction.tournament_code == TOURNAMENT_CODE,
    ).first()

    all_users = db.query(User).all()

    leaderboard_rows = []

    for participant in all_users:
        participant_predictions = db.query(Prediction).filter(
            Prediction.user_id == participant.id
        ).all()

        participant_match_points = sum(
            prediction.points or 0
            for prediction in participant_predictions
        )

        participant_tournament_prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == participant.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        participant_tournament_points = (
            participant_tournament_prediction.points
            if participant_tournament_prediction
            else 0
        )

        leaderboard_rows.append(
            {
                "user_id": participant.id,
                "name": participant.display_name,
                "points": participant_match_points + participant_tournament_points,
            }
        )

    leaderboard_rows.sort(
        key=lambda row: row["points"],
        reverse=True,
    )

    user_position = None
    leader_points = 0

    if leaderboard_rows:
        leader_points = leaderboard_rows[0]["points"]

    for index, row in enumerate(leaderboard_rows, start=1):
        if row["user_id"] == user.id:
            user_position = index
            break

    total_predictions = len(predictions)

    match_points = sum(prediction.points or 0 for prediction in predictions)

    tournament_points = (
        tournament_prediction.points
        if tournament_prediction
        else 0
    )

    total_points = match_points + tournament_points

    finished_predictions = [
        prediction
        for prediction in predictions
        if prediction.match.is_finished
    ]

    future_predictions = [
        prediction
        for prediction in predictions
        if not prediction.match.is_finished
           and prediction.match.starts_at > datetime.now(timezone.utc)
    ]

    exact_scores = sum(
        1
        for prediction in finished_predictions
        if prediction.score_points == 3
    )

    outcomes = sum(
        1
        for prediction in finished_predictions
        if prediction.score_points == 1
    )

    misses = sum(
        1
        for prediction in finished_predictions
        if (prediction.score_points or 0) == 0
    )

    advancement_plus = sum(
        1
        for prediction in finished_predictions
        if prediction.advancement_points == 1
    )

    advancement_minus = sum(
        1
        for prediction in finished_predictions
        if prediction.advancement_points == -1
    )

    advancement_risk_count = sum(
        1
        for prediction in predictions
        if prediction.advancement_bet_enabled
    )

    best_predictions = sorted(
        finished_predictions,
        key=lambda prediction: (
            prediction.points or 0,
            prediction.score_points or 0,
            prediction.advancement_points or 0,
        ),
        reverse=True,
    )[:3]

    best_predictions_payload = []

    for prediction in best_predictions:
        best_predictions_payload.append(
            {
                "match": format_match_label(prediction.match, include_id=False),
                "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                "points": prediction.points or 0,
                "score_points": prediction.score_points or 0,
                "advancement_points": prediction.advancement_points or 0,
            }
        )

    missing_nearest = get_missing_predictions_for_matches(
        db=db,
        user=user,
        matches=get_nearest_matchday_matches(db),
    )

    tournament_payload = None

    if tournament_prediction:
        tournament_payload = {
            "champion": tournament_prediction.champion,
            "runner_up": tournament_prediction.runner_up,
            "third_place": tournament_prediction.third_place,
            "top_scorer": tournament_prediction.top_scorer,
            "points": tournament_prediction.points or 0,
        }

    return {
        "user": {
            "name": user.display_name,
            "position": user_position,
            "participants_count": len(all_users),
            "leader_points": leader_points,
            "points_behind_leader": max(leader_points - total_points, 0),
        },
        "points": {
            "total": total_points,
            "match_points": match_points,
            "tournament_points": tournament_points,
        },
        "match_predictions": {
            "total": total_predictions,
            "finished": len(finished_predictions),
            "future": len(future_predictions),
            "exact_scores": exact_scores,
            "outcomes": outcomes,
            "misses": misses,
        },
        "playoff": {
            "risk_count": advancement_risk_count,
            "advancement_plus": advancement_plus,
            "advancement_minus": advancement_minus,
        },
        "tournament_prediction": tournament_payload,
        "best_predictions": best_predictions_payload,
        "missing_predictions_nearest_matchday": len(missing_nearest),
        "available_commands": {
            "missing": "/missing",
            "summary": "/summary",
            "table": "/table",
            "predict": "/predict",
        },
    }


def format_world_cup_fact(fact: WorldCupFact) -> str:
    year_text = f"ЧМ-{fact.tournament_year}" if fact.tournament_year else "История ЧМ"

    lines = [
        "📚 Факт от Отца прогнозов",
        "",
        f"🏷 {fact.title}",
        f"🗓 {year_text}",
        "",
        fact.fact_text,
    ]

    if fact.spicy_comment:
        lines.extend(["", f"🔥 {fact.spicy_comment}"])

    return "\n".join(lines)


def get_random_fact_not_sent_today(db) -> WorldCupFact | None:
    now_local = datetime.now(DAILY_FACT_TIMEZONE)

    start_local = now_local.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_local = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    sent_fact_ids_today = [
        row.fact_id
        for row in db.query(FactDeliveryLog)
        .filter(
            FactDeliveryLog.delivery_type.in_(
                ["daily", "daily_group", "daily_private"]
            ),
            FactDeliveryLog.sent_at >= start_utc,
            FactDeliveryLog.sent_at < end_utc,
        )
        .all()
    ]

    query = db.query(WorldCupFact).filter(
        WorldCupFact.is_active == True,
        WorldCupFact.needs_verification == False,
    )

    if sent_fact_ids_today:
        query = query.filter(WorldCupFact.id.notin_(sent_fact_ids_today))

    facts = query.all()

    if not facts:
        return None

    return random.choice(facts)


FACTS_SEED_PATH = Path("data/world_cup_facts_seed.json")


def import_world_cup_facts_from_seed(db) -> dict:
    if not FACTS_SEED_PATH.exists():
        raise FileNotFoundError(f"Файл не найден: {FACTS_SEED_PATH}")

    payload = json.loads(
        FACTS_SEED_PATH.read_text(encoding="utf-8")
    )

    facts = payload.get("facts", [])

    created = 0
    updated = 0
    skipped = 0

    for item in facts:
        external_id = item.get("id")

        if not external_id:
            skipped += 1
            continue

        fact = db.query(WorldCupFact).filter(
            WorldCupFact.external_id == external_id
        ).first()

        if not fact:
            fact = WorldCupFact(external_id=external_id)
            db.add(fact)
            created += 1
        else:
            updated += 1

        fact.title = item.get("title") or "Факт о ЧМ"
        fact.fact_text = item.get("fact_text") or ""
        fact.category = item.get("category")
        fact.tournament_year = item.get("tournament_year")
        fact.source_text = item.get("source_text")
        fact.source_url = item.get("source_url")
        fact.spicy_comment = item.get("spicy_comment")
        fact.needs_verification = bool(item.get("needs_verification", False))
        fact.is_active = bool(item.get("is_active", True))

    db.commit()

    return {
        "total": len(facts),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


def plural_days_ru(value: int) -> str:
    if 11 <= value % 100 <= 14:
        return "дней"

    last_digit = value % 10

    if last_digit == 1:
        return "день"

    if 2 <= last_digit <= 4:
        return "дня"

    return "дней"


def get_days_until_wc2026() -> int:
    today = datetime.now(DAILY_FACT_TIMEZONE).date()
    return max((WC2026_START_DATE - today).days, 0)


def build_quiz_teaser_for_fact(fact: WorldCupFact) -> str:
    if fact.tournament_year:
        return f"Какой факт связан с ЧМ-{fact.tournament_year}?"

    category_questions = {
        "wc2026": "Что необычного будет в формате ЧМ-2026?",
        "record": "Какой рекорд чемпионатов мира связан с этим фактом?",
        "team": "Какая сборная связана с этим фактом?",
        "player": "Какой футболист связан с этим фактом?",
        "trophy": "Какой трофей или награда связаны с этим фактом?",
        "host": "Какая страна или турнир связаны с этим фактом?",
        "history": "Что произошло в истории чемпионатов мира?",
        "funny": "Какой необычный эпизод связан с этим фактом?",
    }

    return category_questions.get(
        fact.category,
        "Что интересного произошло в истории чемпионатов мира?",
    )


def format_daily_world_cup_rubric(fact: WorldCupFact) -> str:
    days_left = get_days_until_wc2026()

    if days_left == 0:
        countdown_text = "⏳ ЧМ-2026 стартует сегодня!"
    else:
        day_word = plural_days_ru(days_left)
        countdown_text = f"⏳ До ЧМ-2026 осталось {days_left} {day_word}"

    lines = [
        countdown_text,
        "",
        "📚 Факт дня:",
        fact.fact_text,
    ]

    if fact.spicy_comment:
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                fact.spicy_comment,
            ]
        )

    lines.extend(
        [
            "",
            "❓ Мини-вопрос:",
            build_quiz_teaser_for_fact(fact),
            "",
            "Ответ: /quiz",
        ]
    )

    return "\n".join(lines)



def build_quiz_keyboard(question: QuizQuestion) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"A. {question.option_a}",
                    callback_data=f"quiz_answer:{question.id}:A",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"B. {question.option_b}",
                    callback_data=f"quiz_answer:{question.id}:B",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"C. {question.option_c}",
                    callback_data=f"quiz_answer:{question.id}:C",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"D. {question.option_d}",
                    callback_data=f"quiz_answer:{question.id}:D",
                )
            ],
        ]
    )

def format_quiz_question(question: QuizQuestion) -> str:
    year_text = f"ЧМ-{question.tournament_year}" if question.tournament_year else "История ЧМ"

    return (
        "❓ Мини-вопрос от Отца прогнозов\n\n"
        f"🗓 {year_text}\n"
        f"🏷 {question.category or 'history'}\n\n"
        f"{question.question_text}"
    )

def import_quiz_questions_from_seed(db) -> dict:
    if not QUIZ_SEED_PATH.exists():
        raise FileNotFoundError(f"Файл не найден: {QUIZ_SEED_PATH}")

    payload = json.loads(QUIZ_SEED_PATH.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    created = 0
    updated = 0
    skipped = 0

    for item in questions:
        external_id = item.get("id")

        if not external_id:
            skipped += 1
            continue

        options = item.get("options") or {}

        required_options = ["A", "B", "C", "D"]

        if any(option not in options for option in required_options):
            skipped += 1
            continue

        question = db.query(QuizQuestion).filter(
            QuizQuestion.external_id == external_id
        ).first()

        if not question:
            question = QuizQuestion(external_id=external_id)
            db.add(question)
            created += 1
        else:
            updated += 1

        question.question_text = item["question_text"]
        question.option_a = options["A"]
        question.option_b = options["B"]
        question.option_c = options["C"]
        question.option_d = options["D"]
        question.correct_option = item["correct_option"]
        question.explanation = item.get("explanation")
        question.category = item.get("category")
        question.tournament_year = item.get("tournament_year")
        question.is_active = bool(item.get("is_active", True))

    db.commit()

    return {
        "total": len(questions),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


async def send_daily_fact_to_private_users(db, fact: WorldCupFact):
    users = db.query(User).all()
    text = format_daily_world_cup_rubric(fact)

    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
            )

            db.add(
                FactDeliveryLog(
                    fact_id=fact.id,
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    delivery_type="daily_private",
                )
            )

            db.commit()

        except Exception as error:
            db.rollback()
            print(
                f"Failed to send daily fact "
                f"to {user.telegram_id}: {error}"
            )

async def daily_facts_loop():
    if not DAILY_FACTS_ENABLED:
        print("Daily facts are disabled")
        return

    print(
        "Daily facts loop started. "
        f"Time: {DAILY_FACT_HOUR:02d}:{DAILY_FACT_MINUTE:02d} "
        f"{DAILY_FACT_TIMEZONE}"
    )

    last_sent_date = None

    while True:
        now_local = datetime.now(DAILY_FACT_TIMEZONE)

        should_send = (
                now_local.hour == DAILY_FACT_HOUR
                and now_local.minute == DAILY_FACT_MINUTE
                and last_sent_date != now_local.date()
        )

        if should_send:
            db = SessionLocal()

            try:
                fact = get_random_fact_not_sent_today(db)

                if fact:
                    if DAILY_FACT_TARGET == "group":
                        await send_daily_fact_to_group(db, fact)

                    elif DAILY_FACT_TARGET == "both":
                        await send_daily_fact_to_group(db, fact)
                        await send_daily_fact_to_private_users(db, fact)

                    else:
                        await send_daily_fact_to_private_users(db, fact)

                last_sent_date = now_local.date()

            finally:
                db.close()

        await asyncio.sleep(30)


async def notify_admins(text: str, exclude_telegram_id: int | None = None):
    if not ADMIN_NOTIFY_ENABLED:
        return

    admin_ids = get_admin_telegram_ids()

    if not admin_ids:
        return

    for admin_telegram_id in admin_ids:
        if exclude_telegram_id and admin_telegram_id == exclude_telegram_id:
            continue

        try:
            await bot.send_message(
                chat_id=admin_telegram_id,
                text=text,
            )
        except Exception as error:
            print(
                f"Failed to send admin notification "
                f"to {admin_telegram_id}: {error}"
            )


async def notify_group_chat(text: str):
    group_chat_id = get_group_chat_id()

    if not group_chat_id:
        print("GROUP_CHAT_ID is not set")
        return

    try:
        await bot.send_message(
            chat_id=group_chat_id,
            text=text,
        )
    except Exception as error:
        print(f"Failed to send message to group chat {group_chat_id}: {error}")


async def send_long_message(message: Message, lines: list[str], chunk_size: int = 3500):
    chunks = []
    current_chunk = ""

    for line in lines:
        line_with_break = line + "\n"

        if len(current_chunk) + len(line_with_break) > chunk_size:
            chunks.append(current_chunk)
            current_chunk = line_with_break
        else:
            current_chunk += line_with_break

    if current_chunk:
        chunks.append(current_chunk)

    for chunk in chunks:
        await message.answer(chunk)


async def send_fact_by_category(
    message: Message,
    db,
    category: str | None,
    delivery_type: str = "manual",
):
    query = db.query(WorldCupFact).filter(
        WorldCupFact.is_active == True,
        WorldCupFact.needs_verification == False,
    )

    if category:
        query = query.filter(WorldCupFact.category == category)

    facts = query.all()

    if not facts:
        await message.answer(
            "Фактов по такой категории пока нет.\n\n"
            "Попробуй выбрать другую категорию: /fact"
        )
        return

    fact = random.choice(facts)

    user, _ = get_or_create_user(db, message.from_user)

    db.add(
        FactDeliveryLog(
            fact_id=fact.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            delivery_type=delivery_type,
        )
    )
    db.commit()

    category_text = FACT_QUIZ_CATEGORIES.get(category or "any", "🎲 Любая категория")

    await message.answer(
        f"{category_text}\n\n"
        f"{format_world_cup_fact(fact)}"
    )


async def send_quiz_by_category(
    message: Message,
    db,
    category: str | None,
):
    query = db.query(QuizQuestion).filter(
        QuizQuestion.is_active == True,
    )

    if category:
        query = query.filter(QuizQuestion.category == category)

    questions = query.all()

    if not questions:
        await message.answer(
            "Вопросов по такой категории пока нет.\n\n"
            "Попробуй выбрать другую категорию: /quiz"
        )
        return

    question = random.choice(questions)

    category_text = FACT_QUIZ_CATEGORIES.get(category or "any", "🎲 Любая категория")

    await message.answer(
        f"{category_text}\n\n"
        f"{format_quiz_question(question)}",
        reply_markup=build_quiz_keyboard(question),
    )


@dp.message(Command("tournament_set"))
async def tournament_set_handler(message: Message, state: FSMContext):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if is_tournament_started():
            await message.answer(
                "Прогнозы на итоги турнира уже закрыты. "
                "Турнир стартовал."
            )
            return

        # Если пользователь ввел старый формат через ;
        if ";" in message.text:
            try:
                champion, runner_up, third_place, top_scorer = (
                    parse_tournament_prediction_payload(message.text)
                )
            except ValueError:
                await message.answer(
                    "Формат прогноза на турнир:\n\n"
                    "/tournament_set Чемпион; Финалист; Третье место; Бомбардир\n\n"
                    "Пример:\n"
                    "/tournament_set Аргентина; Франция; Бразилия; Мбаппе"
                )
                return

            _, text = await save_tournament_prediction_and_notify_admins(
                db=db,
                user=user,
                champion=champion,
                runner_up=runner_up,
                third_place=third_place,
                top_scorer=top_scorer,
            )

            await message.answer(text)
            return

        # Новый пошаговый режим
        await state.clear()
        await state.set_state(TournamentPredictionForm.champion)

        await message.answer(
            "Начинаем прогноз на итоги турнира 🏆\n\n"
            "Кто станет чемпионом?\n\n"
            "Напиши название команды, например:\n"
            "Аргентина"
        )

    finally:
        db.close()


@dp.message(Command("tournament"))
async def tournament_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        if not prediction:
            await message.answer(
                "У тебя пока нет прогноза на итоги турнира.\n\n"
                "Создать прогноз пошагово:\n"
                "/tournament_set\n\n"
                "Или одной строкой:\n"
                "/tournament_set Чемпион; Финалист; Третье место; Бомбардир\n\n"
                "Пример:\n"
                "/tournament_set Аргентина; Франция; Бразилия; Мбаппе"
            )
            return

        await message.answer(
            "🏆 Твой прогноз на итоги турнира:\n\n"
            f"1 место: {prediction.champion}\n"
            f"2 место: {prediction.runner_up}\n"
            f"3 место: {prediction.third_place}\n"
            f"Бомбардир: {prediction.top_scorer}\n\n"
            f"Очки за турнир: {prediction.points}"
        )

    finally:
        db.close()


@dp.message(Command("tournament_predictions"))
async def tournament_predictions_handler(message: Message):
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.display_name).all()

        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == TOURNAMENT_CODE
        ).all()

        predictions_by_user_id = {
            prediction.user_id: prediction
            for prediction in predictions
        }

        tournament_started = is_tournament_started()

        start_text = format_datetime(get_tournament_starts_at())

        lines = [
            "🏆 Прогнозы на итоги турнира",
            f"Старт турнира: {start_text}",
            "",
        ]

        if tournament_started:
            lines.append("Турнир уже стартовал — прогнозы открыты:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if not prediction:
                    lines.append(f"{user.display_name}: прогноза нет")
                    continue

                lines.append(
                    f"{user.display_name}:\n"
                    f"1 место: {prediction.champion}\n"
                    f"2 место: {prediction.runner_up}\n"
                    f"3 место: {prediction.third_place}\n"
                    f"Бомбардир: {prediction.top_scorer}\n"
                    f"Очки: {prediction.points}"
                )
                lines.append("")

        else:
            lines.append("До старта турнира прогнозы скрыты.")
            lines.append("Видно только, кто уже сделал прогноз:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if prediction:
                    lines.append(f"{user.display_name}: ✅ прогноз сделан")
                else:
                    lines.append(f"{user.display_name}: ❌ прогноза нет")

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("admin"))
async def admin_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not is_user_admin(user):
            await message.answer(
                "У тебя нет админских прав.\n"
                "Отец прогнозов не выдал тебе свисток судьи."
            )
            return

        await message.answer(
            "🛠 Админ-панель\n\n"
            "Список матчей:\n"
            "/admin_matches\n\n"
            "Полный список матчей:\n"
            "/admin_matches_all\n\n"
            "Импорт матчей из CSV:\n"
            "/admin_import_matches\n\n"
            "Добавить матч:\n"
            "/admin_add_match Мексика; ЮАР; 2026-06-11T21:00:00+03:00; group\n\n"
            "Редактировать матч:\n"
            "/admin_edit_match 5; Аргентина; Франция; 2026-06-30T21:00:00+03:00; round_of_16\n\n"
            "Удалить матч без прогнозов:\n"
            "/admin_delete_match 5\n\n"
            "Удалить матч вместе с прогнозами:\n"
            "/admin_force_delete_match 5\n\n"
            "Внести результат матча кнопками:\n"
            "/admin_set_result\n\n"
            "Или вручную для группового матча:\n"
            "/admin_set_result 1 2:1\n\n"
            "Или вручную для плей-офф:\n"
            "/admin_set_result 5 1:1 home\n"
            "/admin_set_result 5 1:1 away\n\n"
            "Пересчитать все завершенные матчи:\n"
            "/admin_recalculate\n\n"
            "Внести итоги турнира:\n"
            "/admin_set_tournament_result Аргентина; Франция; Бразилия; Мбаппе\n\n"
            "Пересчитать турнирные прогнозы:\n"
            "/admin_tournament_recalculate\n\n"
            "Стадии:\n"
            "group, round_of_32, round_of_16, quarterfinal, semifinal, "
            "third_place, final\n\n"
            "Статус напоминаний:\n"
            "/admin_reminders_status\n\n"
            "Синхронизировать календарь WC2026 из API-Football:\n"
            "/admin_sync_wc2026_schedule\n\n"
            "Синхронизировать результаты из API-Football:\n"
            "/admin_sync_results\n\n"
            "Оповещения админа:\n"
            "новые регистрации, прогнозы на матч и турнир включаются через ADMIN_NOTIFY_ENABLED\n\n"
            "Статистика команд:\n"
            "/admin_command_stats\n"
            "/admin_command_stats_user Имя или TelegramID\n\n"
        )

    finally:
        db.close()


@dp.message(Command("match"))
async def match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        # Новый кнопочный режим
        if len(parts) == 1:
            matches = get_recent_and_upcoming_matches(db, limit=20)

            if not matches:
                await message.answer("Матчей пока нет.")
                return

            await message.answer(
                "Выбери матч, карточку которого хочешь открыть:",
                reply_markup=build_match_card_keyboard(matches),
            )
            return

        # Старый ручной режим: /match ID
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат команды:\n\n"
                "/match\n\n"
                "или:\n"
                "/match ID\n\n"
                "Например:\n"
                "/match 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        text = build_match_card_text(db, user, match)

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if not match.is_finished and now < match_start:
            await message.answer(
                text,
                reply_markup=build_matches_keyboard([match]),
            )
        else:
            await message.answer(text)

    finally:
        db.close()


@dp.message(Command("admin_set_result"))
async def admin_set_result_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        parts = message.text.split()

        # Новый кнопочный режим
        if len(parts) == 1:
            now = datetime.now(timezone.utc)

            matches = (
                db.query(Match)
                    .filter(
                    Match.is_finished == False,
                    Match.starts_at <= now + timedelta(days=3),
                )
                    .order_by(Match.starts_at)
                    .limit(20)
                    .all()
            )

            if not matches:
                await message.answer(
                    "Нет незавершенных матчей для внесения результата."
                )
                return

            await message.answer(
                "Выбери матч, для которого нужно внести результат:",
                reply_markup=build_admin_result_matches_keyboard(matches),
            )
            return

        # Старый текстовый режим
        try:
            match_id, score_home, score_away, winner_side = (
                parse_result_payload(message.text)
            )
        except ValueError:
            await message.answer(
                "Формат результата:\n\n"
                "Кнопками:\n"
                "/admin_set_result\n\n"
                "Или вручную:\n"
                "/admin_set_result ID СЧЕТ\n\n"
                "Пример для группового матча:\n"
                "/admin_set_result 1 2:1\n\n"
                "Пример для плей-офф:\n"
                "/admin_set_result 5 1:1 home\n"
                "/admin_set_result 5 1:1 away\n\n"
                "home — прошла первая команда\n"
                "away — прошла вторая команда"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        try:
            lines = apply_match_result_from_admin(
                db=db,
                match=match,
                score_home=score_home,
                score_away=score_away,
                winner_side=winner_side,
            )
        except ValueError:
            if is_playoff_match(match):
                await message.answer(
                    "Это матч плей-офф. Нужно указать, кто прошел дальше:\n\n"
                    f"/admin_set_result {match.id} {score_home}:{score_away} home\n"
                    f"/admin_set_result {match.id} {score_home}:{score_away} away"
                )
            else:
                await message.answer(
                    "Это не матч плей-офф. Для группового матча не нужно "
                    "указывать home/away."
                )
            return

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("admin_recalculate"))
async def admin_recalculate_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        finished_matches = db.query(Match).filter(
            Match.is_finished == True
        ).all()

        recalculated_predictions_count = 0

        for match in finished_matches:
            if match.score_home is None or match.score_away is None:
                continue

            predictions = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).all()

            for prediction in predictions:
                from app.scoring import score_match_prediction

                result = score_match_prediction(
                    pred_home=prediction.pred_home,
                    pred_away=prediction.pred_away,
                    actual_home=match.score_home,
                    actual_away=match.score_away,
                    advancement_bet_enabled=prediction.advancement_bet_enabled,
                    predicted_advancing_side=prediction.predicted_advancing_side,
                    actual_winner_side=match.winner_side,
                )

                prediction.score_points = result["score_points"]
                prediction.advancement_points = result["advancement_points"]
                prediction.points = result["total_points"]

                recalculated_predictions_count += 1

        db.commit()

        await message.answer(
            "Пересчет завершен ✅\n\n"
            f"Матчей обработано: {len(finished_matches)}\n"
            f"Прогнозов пересчитано: {recalculated_predictions_count}"
        )

    finally:
        db.close()


@dp.message(Command("admin_set_tournament_result"))
async def admin_set_tournament_result_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            champion, runner_up, third_place, top_scorer = (
                parse_tournament_result_payload(message.text)
            )
        except ValueError:
            await message.answer(
                "Формат итогов турнира:\n\n"
                "/admin_set_tournament_result Чемпион; Финалист; Третье место; Бомбардир\n\n"
                "Пример:\n"
                "/admin_set_tournament_result Аргентина; Франция; Бразилия; Мбаппе"
            )
            return

        tournament_result = db.query(TournamentResult).filter(
            TournamentResult.tournament_code == TOURNAMENT_CODE
        ).first()

        if tournament_result:
            tournament_result.champion = champion
            tournament_result.runner_up = runner_up
            tournament_result.third_place = third_place
            tournament_result.top_scorer = top_scorer
        else:
            tournament_result = TournamentResult(
                tournament_code=TOURNAMENT_CODE,
                champion=champion,
                runner_up=runner_up,
                third_place=third_place,
                top_scorer=top_scorer,
            )
            db.add(tournament_result)

        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == TOURNAMENT_CODE
        ).all()

        recalculated = []

        for prediction in predictions:
            result = score_tournament_prediction(
                pred_champion=prediction.champion,
                pred_runner_up=prediction.runner_up,
                pred_third_place=prediction.third_place,
                pred_top_scorer=prediction.top_scorer,
                actual_champion=champion,
                actual_runner_up=runner_up,
                actual_third_place=third_place,
                actual_top_scorer=top_scorer,
            )

            prediction.champion_points = result["champion_points"]
            prediction.runner_up_points = result["runner_up_points"]
            prediction.third_place_points = result["third_place_points"]
            prediction.top_scorer_points = result["top_scorer_points"]
            prediction.points = result["total_points"]

            recalculated.append(
                {
                    "user": prediction.user.display_name,
                    "champion": prediction.champion,
                    "runner_up": prediction.runner_up,
                    "third_place": prediction.third_place,
                    "top_scorer": prediction.top_scorer,
                    "champion_points": prediction.champion_points,
                    "runner_up_points": prediction.runner_up_points,
                    "third_place_points": prediction.third_place_points,
                    "top_scorer_points": prediction.top_scorer_points,
                    "total_points": prediction.points,
                }
            )

        db.commit()

        lines = [
            "Итоги турнира сохранены ✅",
            "",
            f"🏆 Чемпион: {champion}",
            f"🥈 Финалист: {runner_up}",
            f"🥉 3 место: {third_place}",
            f"⚽ Бомбардир: {top_scorer}",
            "",
            "Пересчет турнирных прогнозов:",
            "",
        ]

        if not recalculated:
            lines.append("Турнирных прогнозов пока нет.")
        else:
            for item in recalculated:
                lines.append(
                    f"{item['user']} — {item['total_points']} очк.\n"
                    f"🏆 {item['champion_points']} | "
                    f"🥈 {item['runner_up_points']} | "
                    f"🥉 {item['third_place_points']} | "
                    f"⚽ {item['top_scorer_points']}"
                )
                lines.append("")

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("admin_tournament_recalculate"))
async def admin_tournament_recalculate_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        tournament_result = db.query(TournamentResult).filter(
            TournamentResult.tournament_code == TOURNAMENT_CODE
        ).first()

        if not tournament_result:
            await message.answer(
                "Итоги турнира еще не внесены.\n\n"
                "Сначала используй:\n"
                "/admin_set_tournament_result Чемпион; Финалист; Третье место; Бомбардир"
            )
            return

        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == TOURNAMENT_CODE
        ).all()

        recalculated_count = 0

        for prediction in predictions:
            result = score_tournament_prediction(
                pred_champion=prediction.champion,
                pred_runner_up=prediction.runner_up,
                pred_third_place=prediction.third_place,
                pred_top_scorer=prediction.top_scorer,
                actual_champion=tournament_result.champion,
                actual_runner_up=tournament_result.runner_up,
                actual_third_place=tournament_result.third_place,
                actual_top_scorer=tournament_result.top_scorer,
            )

            prediction.champion_points = result["champion_points"]
            prediction.runner_up_points = result["runner_up_points"]
            prediction.third_place_points = result["third_place_points"]
            prediction.top_scorer_points = result["top_scorer_points"]
            prediction.points = result["total_points"]

            recalculated_count += 1

        db.commit()

        await message.answer(
            "Турнирные прогнозы пересчитаны ✅\n\n"
            f"Турнир: {TOURNAMENT_CODE}\n"
            f"Прогнозов пересчитано: {recalculated_count}\n\n"
            f"🏆 Чемпион: {tournament_result.champion}\n"
            f"🥈 Финалист: {tournament_result.runner_up}\n"
            f"🥉 3 место: {tournament_result.third_place}\n"
            f"⚽ Бомбардир: {tournament_result.top_scorer}"
        )

    finally:
        db.close()


@dp.message(Command("admin_matches"))
async def admin_matches_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        matches = (
            db.query(Match)
                .order_by(Match.starts_at)
                .limit(20)
                .all()
        )

        total_matches = db.query(Match).count()

        if not matches:
            await message.answer("Матчей пока нет.")
            return

        lines = [
            "🛠 Матчи в базе",
            f"Показаны первые {len(matches)} из {total_matches}.",
            "Для полного списка: /admin_matches_all",
            "",
        ]

        for match in matches:
            status = "✅ завершен" if match.is_finished else "⏳ не завершен"

            result = ""
            if match.score_home is not None and match.score_away is not None:
                result = f" | счет {match.score_home}:{match.score_away}"

            winner = ""
            if match.winner_side == "home":
                winner = f" | прошла {match.home_team}"
            elif match.winner_side == "away":
                winner = f" | прошла {match.away_team}"

            predictions_count = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).count()

            round_text = match.match_round or get_default_match_round(match.stage)

            group_text = f" | группа {match.group_code}" if match.group_code else ""

            fifa_no_text = (
                f"FIFA #{match.fifa_match_no} | "
                if match.fifa_match_no
                else ""
            )

            lines.append(
                f"{format_match_label(match, include_id=True)}\n"
                f"{fifa_no_text}"
                f"Старт: {format_datetime(match.starts_at)}\n"
                f"Стадия: {match.stage}\n"
                f"{status}{result}{winner}\n"
                f"Прогнозов: {predictions_count}"
            )
            lines.append("")

        await send_long_message(message, lines)

    finally:
        db.close()


@dp.message(Command("admin_matches_all"))
async def admin_matches_all_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        matches = db.query(Match).order_by(Match.starts_at).all()

        if not matches:
            await message.answer("Матчей пока нет.")
            return

        lines = ["🛠 Все матчи в базе:", ""]

        for match in matches:
            status = "✅ завершен" if match.is_finished else "⏳ не завершен"

            result = ""
            if match.score_home is not None and match.score_away is not None:
                result = f" | счет {match.score_home}:{match.score_away}"

            winner = ""
            if match.winner_side == "home":
                winner = f" | прошла {match.home_team}"
            elif match.winner_side == "away":
                winner = f" | прошла {match.away_team}"

            predictions_count = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).count()

            round_text = match.match_round or get_default_match_round(match.stage)

            group_text = f" | группа {match.group_code}" if match.group_code else ""

            fifa_no_text = (
                f"FIFA #{match.fifa_match_no} | "
                if match.fifa_match_no
                else ""
            )

            lines.append(
                f"{format_match_label(match, include_id=True)}\n"
                f"{fifa_no_text}"
                f"Старт: {format_datetime(match.starts_at)}\n"
                f"Стадия: {match.stage}\n"
                f"{status}{result}{winner}\n"
                f"Прогнозов: {predictions_count}"
            )
            lines.append("")

        await send_long_message(message, lines)

    finally:
        db.close()


@dp.message(Command("admin_edit_match"))
async def admin_edit_match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            (
                match_id,
                home_team,
                away_team,
                starts_at,
                stage,
                match_round,
                tournament_code,
            ) = parse_admin_edit_match_payload(message.text)
        except ValueError:
            await message.answer(
                "Формат редактирования матча:\n\n"
                "/admin_edit_match ID; Команда1; Команда2; Дата; Стадия\n\n"
                "Пример:\n"
                "/admin_edit_match 5; Аргентина; Франция; "
                "2026-06-30T21:00:00+03:00; round_of_16\n\n"
                "Стадии:\n"
                "group, round_of_32, round_of_16, quarterfinal, "
                "semifinal, third_place, final"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        old_text = (
            f"Было:\n"
            f"{format_match_label(match, include_id=True)}\n"
            f"Старт: {format_datetime(match.starts_at)}\n"
            f"Стадия: {match.stage}"
        )

        match.home_team = home_team
        match.away_team = away_team
        match.starts_at = starts_at
        match.stage = stage
        match.tournament_code = tournament_code
        match.match_round = match_round

        db.commit()
        db.refresh(match)

        new_text = (
            f"Стало:\n"
            f"{format_match_label(match, include_id=True)}\n"
            f"Старт: {format_datetime(match.starts_at)}\n"
            f"Стадия: {match.stage}"
        )

        await message.answer(
            "Матч обновлен ✅\n\n"
            f"{old_text}\n\n"
            f"{new_text}"
        )

    finally:
        db.close()


@dp.message(Command("admin_delete_match"))
async def admin_delete_match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            match_id = parse_match_id_command(
                message.text,
                "/admin_delete_match",
            )
        except ValueError:
            await message.answer(
                "Формат удаления матча:\n\n"
                "/admin_delete_match ID\n\n"
                "Пример:\n"
                "/admin_delete_match 5"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        predictions_count = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).count()

        reminder_logs_count = db.query(ReminderLog).filter(
            ReminderLog.match_id == match.id
        ).count()

        if predictions_count > 0 or reminder_logs_count > 0:
            await message.answer(
                "Матч не удален, потому что у него уже есть связанные данные.\n\n"
                f"Матч: {format_match_label(match, include_id=True)}\n"
                f"Прогнозов: {predictions_count}\n"
                f"Логов напоминаний: {reminder_logs_count}\n\n"
                "Если это тестовый или ошибочный матч, используй:\n"
                f"/admin_force_delete_match {match.id}\n\n"
                "Осторожно: эта команда удалит матч и все связанные данные."
            )
            return

        match_text = format_match_label(match, include_id=True)

        db.delete(match)
        db.commit()

        await message.answer(
            "Матч удален ✅\n\n"
            f"{match_text}"
        )

    finally:
        db.close()


@dp.message(Command("admin_force_delete_match"))
async def admin_force_delete_match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            match_id = parse_match_id_command(
                message.text,
                "/admin_force_delete_match",
            )
        except ValueError:
            await message.answer(
                "Формат принудительного удаления матча:\n\n"
                "/admin_force_delete_match ID\n\n"
                "Пример:\n"
                "/admin_force_delete_match 5"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        predictions = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).all()

        reminder_logs = db.query(ReminderLog).filter(
            ReminderLog.match_id == match.id
        ).all()

        predictions_count = len(predictions)
        reminder_logs_count = len(reminder_logs)

        match_text = format_match_label(match, include_id=True)

        for prediction in predictions:
            db.delete(prediction)

        for reminder_log in reminder_logs:
            db.delete(reminder_log)

        db.delete(match)
        db.commit()

        await message.answer(
            "Матч удален ✅\n\n"
            f"{match_text}\n"
            f"Удалено прогнозов: {predictions_count}\n"
            f"Удалено логов напоминаний: {reminder_logs_count}"
        )

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("predict_match:"))
async def predict_match_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if now >= match_start:
            await callback.message.answer(
                "Ставки на этот матч уже закрыты."
            )
            await callback.answer()
            return

        await callback.message.answer(
            f"Выбран матч:\n"
            f"{format_match_label(match, include_id=False)}\n"
            f"Старт: {format_datetime(match.starts_at)}\n\n"
            f"Выбери счет:",
            reply_markup=build_score_keyboard(match.id),
        )

        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("predict_score:"))
async def predict_score_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        _, match_id_raw, pred_home_raw, pred_away_raw = callback.data.split(":")

        match_id = int(match_id_raw)
        pred_home = int(pred_home_raw)
        pred_away = int(pred_away_raw)

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        if is_playoff_match(match):
            await callback.message.answer(
                f"Счет выбран: {pred_home}:{pred_away}\n\n"
                "Это матч плей-офф. Хочешь рискнуть и поставить, "
                "кто пройдет дальше?\n\n"
                "Если угадаешь — +1 очко.\n"
                "Если не угадаешь — -1 очко.",
                reply_markup=build_advancement_keyboard(
                    match_id=match.id,
                    pred_home=pred_home,
                    pred_away=pred_away,
                    match=match,
                ),
            )

            await callback.answer()
            return

        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
        )

        await callback.message.answer(text)
        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("predict_adv:"))
async def predict_advancement_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        _, match_id_raw, pred_home_raw, pred_away_raw, choice = (
            callback.data.split(":")
        )

        match_id = int(match_id_raw)
        pred_home = int(pred_home_raw)
        pred_away = int(pred_away_raw)

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        try:
            advancement_bet_enabled, predicted_advancing_side = (
                parse_advancement_choice(choice)
            )
        except ValueError:
            await callback.message.answer("Не понял ставку на проход.")
            await callback.answer()
            return

        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        await callback.message.answer(text)
        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("predict_custom:"))
async def predict_custom_callback(callback: CallbackQuery, state: FSMContext):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if now >= match_start:
            await callback.message.answer(
                "Ставки на этот матч уже закрыты."
            )
            await callback.answer()
            return

        await state.clear()
        await state.set_state(MatchPredictionForm.custom_score)
        await state.update_data(match_id=match.id)

        await callback.message.answer(
            f"Введи счет для матча:\n"
            f"{format_match_label(match, include_id=False)}\n\n"
            "Например:\n"
            "3:2\n\n"
            "Можно также через дефис:\n"
            "3-2\n\n"
            "Отмена: /cancel"
        )

        await callback.answer()

    finally:
        db.close()


@dp.message(TournamentPredictionForm.champion)
async def tournament_champion_handler(message: Message, state: FSMContext):
    champion = message.text.strip()

    if not champion:
        await message.answer("Напиши название команды-чемпиона.")
        return

    await state.update_data(champion=champion)
    await state.set_state(TournamentPredictionForm.runner_up)

    await message.answer(
        f"Чемпион: {champion}\n\n"
        "Кто займет 2 место?"
    )


@dp.message(TournamentPredictionForm.runner_up)
async def tournament_runner_up_handler(message: Message, state: FSMContext):
    runner_up = message.text.strip()

    if not runner_up:
        await message.answer("Напиши команду, которая займет 2 место.")
        return

    data = await state.get_data()

    if runner_up.lower() == data["champion"].lower():
        await message.answer(
            "Чемпион и финалист не могут быть одной и той же командой.\n"
            "Напиши другую команду."
        )
        return

    await state.update_data(runner_up=runner_up)
    await state.set_state(TournamentPredictionForm.third_place)

    await message.answer(
        f"2 место: {runner_up}\n\n"
        "Кто займет 3 место?"
    )


@dp.message(TournamentPredictionForm.third_place)
async def tournament_third_place_handler(message: Message, state: FSMContext):
    third_place = message.text.strip()

    if not third_place:
        await message.answer("Напиши команду, которая займет 3 место.")
        return

    data = await state.get_data()

    existing_teams = {
        data["champion"].lower(),
        data["runner_up"].lower(),
    }

    if third_place.lower() in existing_teams:
        await message.answer(
            "Команда на 3 месте не должна совпадать с 1 или 2 местом.\n"
            "Напиши другую команду."
        )
        return

    await state.update_data(third_place=third_place)
    await state.set_state(TournamentPredictionForm.top_scorer)

    await message.answer(
        f"3 место: {third_place}\n\n"
        "Кто станет лучшим бомбардиром турнира?\n\n"
        "Напиши фамилию или имя игрока, например:\n"
        "Мбаппе"
    )


@dp.message(TournamentPredictionForm.top_scorer)
async def tournament_top_scorer_handler(message: Message, state: FSMContext):
    top_scorer = message.text.strip()

    if not top_scorer:
        await message.answer("Напиши имя или фамилию бомбардира.")
        return

    data = await state.get_data()

    champion = data["champion"]
    runner_up = data["runner_up"]
    third_place = data["third_place"]

    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if is_tournament_started():
            await state.clear()
            await message.answer(
                "Прогнозы на итоги турнира уже закрыты. "
                "Турнир стартовал."
            )
            return

        _, text = await save_tournament_prediction_and_notify_admins(
            db=db,
            user=user,
            champion=champion,
            runner_up=runner_up,
            third_place=third_place,
            top_scorer=top_scorer,
        )

        await state.clear()
        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state is None:
        await message.answer("Сейчас нечего отменять.")
        return

    await state.clear()

    await message.answer("Действие отменено.")


@dp.message(MatchPredictionForm.custom_score)
async def match_custom_score_handler(message: Message, state: FSMContext):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        data = await state.get_data()
        match_id = data.get("match_id")

        if not match_id:
            await state.clear()
            await message.answer(
                "Не нашел выбранный матч. Начни заново через /predict."
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await state.clear()
            await message.answer(
                "Матч не найден. Начни заново через /predict."
            )
            return

        try:
            pred_home, pred_away = parse_score(message.text)
        except ValueError:
            await message.answer(
                "Не понял счет.\n\n"
                "Введи в формате:\n"
                "3:2\n\n"
                "Или:\n"
                "3-2\n\n"
                "Отмена: /cancel"
            )
            return

        if is_playoff_match(match):
            await state.clear()

            await message.answer(
                f"Счет выбран: {pred_home}:{pred_away}\n\n"
                "Это матч плей-офф. Хочешь рискнуть и поставить, "
                "кто пройдет дальше?\n\n"
                "Если угадаешь — +1 очко.\n"
                "Если не угадаешь — -1 очко.",
                reply_markup=build_advancement_keyboard(
                    match_id=match.id,
                    pred_home=pred_home,
                    pred_away=pred_away,
                    match=match,
                ),
            )
            return

        success, text = await save_prediction_and_notify_admins(
            db=db,
            user=user,
            match=match,
            pred_home=pred_home,
            pred_away=pred_away,
        )

        await state.clear()
        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("matches_all"))
async def matches_all_handler(message: Message):
    db = SessionLocal()

    try:
        matches = get_all_available_matches(db, limit=30)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        text = format_matches_list(
            matches,
            "📅 Все будущие матчи",
        )

        text += "\n\nПоказаны ближайшие 30 матчей."

        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("predict_all"))
async def predict_all_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        matches = get_all_available_matches(db)

        if not matches:
            await message.answer("Нет доступных матчей для прогноза.")
            return

        await message.answer(
            "Выбери матч для прогноза:",
            reply_markup=build_matches_keyboard(matches),
        )

    finally:
        db.close()


@dp.message(Command("admin_import_matches"))
async def admin_import_matches_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        csv_text = None

        if message.document:
            if not message.document.file_name.lower().endswith(".csv"):
                await message.answer("Пришли CSV-файл.")
                return

            downloaded = await bot.download(message.document)

            if downloaded is None:
                await message.answer("Не удалось скачать файл.")
                return

            content = downloaded.read()
            csv_text = content.decode("utf-8-sig")

        else:
            csv_text = message.text.replace("/admin_import_matches", "", 1).strip()

            if not csv_text:
                await message.answer(
                    "Импорт матчей из CSV.\n\n"
                    "Вариант 1: отправь CSV-файл с подписью:\n"
                    "/admin_import_matches\n\n"
                    "Вариант 2: вставь CSV текстом после команды.\n\n"
                    "Обязательные колонки:\n"
                    "home_team;away_team;starts_at;stage\n\n"
                    "Рекомендуемые колонки:\n"
                    "fifa_match_no;home_team;away_team;starts_at;stage;"
                    "match_round;tournament_code;group_code;venue;city\n\n"
                    "Пример строки:\n"
                    "1;Mexico;South Africa;2026-06-11T22:00:00+03:00;"
                    "group;1;wc2026;A;Estadio Azteca;Mexico City"
                )
                return

        try:
            rows = parse_csv_matches(csv_text)
        except ValueError as error:
            await message.answer(
                f"CSV не импортирован.\n\nОшибка:\n{error}"
            )
            return

        result = import_matches_from_rows(db, rows)

        await message.answer(
            "Импорт матчей завершен ✅\n\n"
            f"Всего строк: {result['total']}\n"
            f"Создано: {result['created']}\n"
            f"Обновлено: {result['updated']}\n"
            f"Пропущено: {result['skipped']}\n\n"
            "Проверить:\n"
            "/admin_matches"
        )

    finally:
        db.close()


@dp.message(Command("missing"))
async def missing_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        matches = get_nearest_matchday_matches(db)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        missing_matches = get_missing_predictions_for_matches(
            db=db,
            user=user,
            matches=matches,
        )

        text = format_missing_matches_list(
            missing_matches,
            "❌ Матчи ближайшего игрового дня без твоего прогноза",
        )

        if missing_matches:
            await message.answer(
                text,
                reply_markup=build_matches_keyboard(missing_matches),
            )
        else:
            await message.answer(text)

    finally:
        db.close()


@dp.message(Command("missing_all"))
async def missing_all_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        matches = get_all_available_matches(db, limit=30)

        if not matches:
            await message.answer("Нет будущих матчей.")
            return

        missing_matches = get_missing_predictions_for_matches(
            db=db,
            user=user,
            matches=matches,
        )

        text = format_missing_matches_list(
            missing_matches,
            "❌ Ближайшие матчи без твоего прогноза",
        )

        text += "\n\nПроверены ближайшие 30 будущих матчей."

        if missing_matches:
            await message.answer(
                text,
                reply_markup=build_matches_keyboard(missing_matches),
            )
        else:
            await message.answer(text)

    finally:
        db.close()


async def send_match_reminders_once():
    if not reminders_enabled():
        return

    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        offsets = get_reminder_offsets_minutes()
        check_interval_seconds = get_reminder_check_interval_seconds()

        if not offsets:
            return

        max_offset = max(offsets)

        matches = db.query(Match).filter(
            Match.is_finished == False,
            Match.starts_at > now,
            Match.starts_at <= now + timedelta(minutes=max_offset + 10),
        ).order_by(Match.starts_at).all()

        if not matches:
            return

        users = db.query(User).all()

        for match in matches:
            match_start = match.starts_at

            if match_start.tzinfo is None:
                match_start = match_start.replace(tzinfo=timezone.utc)

            for offset_minutes in offsets:
                reminder_due_at = match_start - timedelta(minutes=offset_minutes)

                window_end = reminder_due_at + timedelta(
                    seconds=check_interval_seconds + 30
                )

                if not (reminder_due_at <= now <= window_end):
                    continue

                reminder_type = "match_missing_prediction"
                reminder_key = f"{offset_minutes}m"

                for user in users:
                    if user_has_prediction(db, user, match):
                        continue

                    if reminder_was_sent(
                            db=db,
                            user=user,
                            match=match,
                            reminder_type=reminder_type,
                            reminder_key=reminder_key,
                    ):
                        continue

                    text = (
                        f"⏰ Напоминание от Отца прогнозов\n\n"
                        f"До матча осталось: {format_reminder_offset(offset_minutes)}\n\n"
                        f"{format_match_label(match, include_id=False)}\n"
                        f"Старт: {format_datetime(match.starts_at)}\n\n"
                        f"У тебя еще нет прогноза на этот матч."
                    )

                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=text,
                            reply_markup=build_matches_keyboard([match]),
                        )

                        mark_reminder_sent(
                            db=db,
                            user=user,
                            match=match,
                            reminder_type=reminder_type,
                            reminder_key=reminder_key,
                        )

                    except Exception as error:
                        print(
                            f"Failed to send reminder to user "
                            f"{user.telegram_id}: {error}"
                        )

    finally:
        db.close()


def format_percent(part: int, total: int) -> str:
    if total == 0:
        return "0%"

    return f"{round(part / total * 100)}%"


async def reminders_loop():
    if not reminders_enabled():
        print("Reminders are disabled")
        return

    interval_seconds = get_reminder_check_interval_seconds()

    print(
        "Reminders loop started. "
        f"Interval: {interval_seconds} seconds. "
        f"Offsets: {get_reminder_offsets_minutes()} minutes."
    )

    await asyncio.sleep(10)

    while True:
        try:
            await send_match_reminders_once()
        except Exception as error:
            print(f"Reminder loop error: {error}")

        await asyncio.sleep(interval_seconds)


@dp.message(Command("admin_reminders_status"))
async def admin_reminders_status_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        now = datetime.now(timezone.utc)

        offsets = get_reminder_offsets_minutes()

        matches = db.query(Match).filter(
            Match.is_finished == False,
            Match.starts_at > now,
        ).order_by(Match.starts_at).limit(5).all()

        lines = [
            "⏰ Статус напоминаний",
            "",
            f"Включены: {reminders_enabled()}",
            f"Интервал проверки: {get_reminder_check_interval_seconds()} сек.",
            f"Напоминания за минуты: {offsets}",
            "",
            "Ближайшие матчи:",
            "",
        ]

        if not matches:
            lines.append("Будущих матчей нет.")
        else:
            for match in matches:
                lines.append(
                    f"{format_match_label(match, include_id=True)}\n"
                    f"Старт: {format_datetime(match.starts_at)}"
                )

                match_start = match.starts_at

                if match_start.tzinfo is None:
                    match_start = match_start.replace(tzinfo=timezone.utc)

                for offset in offsets:
                    due_at = match_start - timedelta(minutes=offset)
                    lines.append(
                        f"— напоминание за {format_reminder_offset(offset)}: "
                        f"{format_datetime(due_at)}"
                    )

                lines.append("")

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("match"))
async def match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(
                "Формат команды:\n\n"
                "/match ID\n\n"
                "Например:\n"
                "/match 12"
            )
            return

        match_id = int(parts[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        predictions_are_revealed = now >= match_start

        my_prediction = db.query(Prediction).filter(
            Prediction.user_id == user.id,
            Prediction.match_id == match.id,
        ).first()

        predictions_count = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).count()

        users_count = db.query(User).count()

        lines = [
            "⚽ Карточка матча",
            "",
            format_match_label(match, include_id=True),
            f"Старт: {format_datetime(match.starts_at)}",
            f"Статус: {get_match_status(match)}",
            f"Стадия: {match.stage}",
        ]

        if match.group_code:
            lines.append(f"Группа: {match.group_code}")

        if match.match_round:
            if match.stage == "group":
                lines.append(f"Тур: {match.match_round}")
            else:
                lines.append(f"Раунд: {match.match_round}")

        if match.venue or match.city:
            venue_parts = [part for part in [match.venue, match.city] if part]
            lines.append(f"Стадион: {', '.join(venue_parts)}")

        lines.extend(
            [
                "",
                format_match_result(match),
                "",
                f"Прогнозов сделано: {predictions_count} из {users_count}",
                "",
                "Твой прогноз:",
                format_user_match_prediction(
                    my_prediction,
                    match,
                    reveal=True,
                ),
                "",
            ]
        )

        if predictions_are_revealed:
            lines.append("Прогнозы участников:")
            lines.append("")

            users = db.query(User).order_by(User.display_name).all()

            predictions = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).all()

            predictions_by_user_id = {
                prediction.user_id: prediction
                for prediction in predictions
            }

            for participant in users:
                prediction = predictions_by_user_id.get(participant.id)

                lines.append(
                    f"{participant.display_name}: "
                    f"{format_user_match_prediction(prediction, match, reveal=True)}"
                )
        else:
            lines.append("До старта матча чужие прогнозы скрыты.")
            lines.append("Видно только, кто уже сделал прогноз:")
            lines.append("")

            users = db.query(User).order_by(User.display_name).all()

            predictions = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).all()

            predictions_by_user_id = {
                prediction.user_id: prediction
                for prediction in predictions
            }

            for participant in users:
                prediction = predictions_by_user_id.get(participant.id)

                lines.append(
                    f"{participant.display_name}: "
                    f"{format_user_match_prediction(prediction, match, reveal=False)}"
                )

        if not match.is_finished and now < match_start:
            await message.answer(
                "\n".join(lines),
                reply_markup=build_matches_keyboard([match]),
            )
        else:
            await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("summary"))
async def summary_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        predictions = db.query(Prediction).filter(
            Prediction.user_id == user.id
        ).all()

        tournament_prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        total_predictions = len(predictions)

        match_points = sum(prediction.points or 0 for prediction in predictions)
        tournament_points = (
            tournament_prediction.points
            if tournament_prediction
            else 0
        )

        total_points = match_points + tournament_points

        exact_scores = sum(
            1
            for prediction in predictions
            if prediction.score_points == 3
        )

        outcomes = sum(
            1
            for prediction in predictions
            if prediction.score_points == 1
        )

        misses = sum(
            1
            for prediction in predictions
            if prediction.match.is_finished
            and (prediction.score_points or 0) == 0
        )

        finished_predictions = sum(
            1
            for prediction in predictions
            if prediction.match.is_finished
        )

        advancement_plus = sum(
            1
            for prediction in predictions
            if prediction.advancement_points == 1
        )

        advancement_minus = sum(
            1
            for prediction in predictions
            if prediction.advancement_points == -1
        )

        advancement_risk_count = sum(
            1
            for prediction in predictions
            if prediction.advancement_bet_enabled
        )

        upcoming_predictions = sum(
            1
            for prediction in predictions
            if not prediction.match.is_finished
            and prediction.match.starts_at > datetime.now(timezone.utc)
        )

        best_predictions = sorted(
            [
                prediction
                for prediction in predictions
                if prediction.match.is_finished
            ],
            key=lambda prediction: (
                prediction.points or 0,
                prediction.score_points or 0,
                prediction.advancement_points or 0,
            ),
            reverse=True,
        )

        lines = [
            "📊 Твоя статистика",
            "",
            f"Участник: {user.display_name}",
            f"Всего очков: {total_points}",
            f"Очки за матчи: {match_points}",
            f"Очки за турнир: {tournament_points}",
            "",
            "Матчевые прогнозы:",
            f"Всего прогнозов: {total_predictions}",
            f"Завершенных прогнозов: {finished_predictions}",
            f"Будущих прогнозов: {upcoming_predictions}",
            "",
            f"🎯 Точные счета: {exact_scores} "
            f"({format_percent(exact_scores, finished_predictions)})",
            f"✅ Исходы: {outcomes} "
            f"({format_percent(outcomes, finished_predictions)})",
            f"❌ Без очков за счет/исход: {misses} "
            f"({format_percent(misses, finished_predictions)})",
            "",
            "Плей-офф:",
            f"Рисковых ставок на проход: {advancement_risk_count}",
            f"🟢 Угадано проходов: {advancement_plus}",
            f"🔴 Не угадано проходов: {advancement_minus}",
            "",
        ]

        if tournament_prediction:
            lines.extend(
                [
                    "Турнирный прогноз:",
                    f"1 место: {tournament_prediction.champion}",
                    f"2 место: {tournament_prediction.runner_up}",
                    f"3 место: {tournament_prediction.third_place}",
                    f"Бомбардир: {tournament_prediction.top_scorer}",
                    f"Очки: {tournament_prediction.points}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "Турнирный прогноз:",
                    "пока не сделан",
                    "",
                    "Создать: /tournament_set",
                    "",
                ]
            )

        if best_predictions:
            lines.append("Лучшие прогнозы:")

            for prediction in best_predictions[:3]:
                match = prediction.match

                lines.append(
                    f"{format_match_label(match, include_id=True)}\n"
                    f"Прогноз: {prediction.pred_home}:{prediction.pred_away}\n"
                    f"{get_prediction_points_breakdown(prediction)}"
                )
                lines.append("")
        else:
            lines.append("Завершенных матчей с твоими прогнозами пока нет.")

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("admin_result_match:"))
async def admin_result_match_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        if not ensure_admin_or_reply(user):
            await callback.message.answer("У тебя нет админских прав.")
            await callback.answer()
            return

        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        if match.is_finished:
            await callback.message.answer(
                "Этот матч уже завершен. "
                "Результат можно перезаписать вручную командой:\n\n"
                f"/admin_set_result {match.id} 2:1"
            )
            await callback.answer()
            return

        await callback.message.answer(
            "Выбран матч:\n\n"
            f"{format_match_label(match, include_id=True)}\n"
            f"Старт: {format_datetime(match.starts_at)}\n\n"
            "Выбери итоговый счет:",
            reply_markup=build_admin_result_score_keyboard(match.id),
        )

        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("admin_result_score:"))
async def admin_result_score_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        if not ensure_admin_or_reply(user):
            await callback.message.answer("У тебя нет админских прав.")
            await callback.answer()
            return

        _, match_id_raw, score_home_raw, score_away_raw = callback.data.split(":")

        match_id = int(match_id_raw)
        score_home = int(score_home_raw)
        score_away = int(score_away_raw)

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        if is_playoff_match(match):
            await callback.message.answer(
                f"Счет выбран: {score_home}:{score_away}\n\n"
                "Это матч плей-офф. Кто прошел дальше?",
                reply_markup=build_admin_result_winner_keyboard(
                    match_id=match.id,
                    score_home=score_home,
                    score_away=score_away,
                    match=match,
                ),
            )
            await callback.answer()
            return

        lines = apply_match_result_from_admin(
            db=db,
            match=match,
            score_home=score_home,
            score_away=score_away,
            winner_side=None,
        )

        await callback.message.answer("\n".join(lines))
        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("admin_result_winner:"))
async def admin_result_winner_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        if not ensure_admin_or_reply(user):
            await callback.message.answer("У тебя нет админских прав.")
            await callback.answer()
            return

        _, match_id_raw, score_home_raw, score_away_raw, winner_side = (
            callback.data.split(":")
        )

        match_id = int(match_id_raw)
        score_home = int(score_home_raw)
        score_away = int(score_away_raw)

        if winner_side not in ("home", "away"):
            await callback.message.answer("Некорректный победитель.")
            await callback.answer()
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        lines = apply_match_result_from_admin(
            db=db,
            match=match,
            score_home=score_home,
            score_away=score_away,
            winner_side=winner_side,
        )

        await callback.message.answer("\n".join(lines))
        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("admin_result_custom:"))
async def admin_result_custom_callback(callback: CallbackQuery, state: FSMContext):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        if not ensure_admin_or_reply(user):
            await callback.message.answer("У тебя нет админских прав.")
            await callback.answer()
            return

        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        await state.clear()
        await state.set_state(AdminResultForm.custom_score)
        await state.update_data(match_id=match.id)

        await callback.message.answer(
            "Введи итоговый счет для матча:\n\n"
            f"{format_match_label(match, include_id=True)}\n\n"
            "Например:\n"
            "3:2\n\n"
            "Можно также через дефис:\n"
            "3-2\n\n"
            "Отмена: /cancel"
        )

        await callback.answer()

    finally:
        db.close()


@dp.message(AdminResultForm.custom_score)
async def admin_result_custom_score_handler(message: Message, state: FSMContext):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await state.clear()
            await message.answer("У тебя нет админских прав.")
            return

        data = await state.get_data()
        match_id = data.get("match_id")

        if not match_id:
            await state.clear()
            await message.answer(
                "Не нашел выбранный матч. Начни заново через /admin_set_result."
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await state.clear()
            await message.answer(
                "Матч не найден. Начни заново через /admin_set_result."
            )
            return

        try:
            score_home, score_away = parse_score(message.text)
        except ValueError:
            await message.answer(
                "Не понял счет.\n\n"
                "Введи в формате:\n"
                "3:2\n\n"
                "Или:\n"
                "3-2\n\n"
                "Отмена: /cancel"
            )
            return

        await state.clear()

        if is_playoff_match(match):
            await message.answer(
                f"Счет выбран: {score_home}:{score_away}\n\n"
                "Это матч плей-офф. Кто прошел дальше?",
                reply_markup=build_admin_result_winner_keyboard(
                    match_id=match.id,
                    score_home=score_home,
                    score_away=score_away,
                    match=match,
                ),
            )
            return

        lines = apply_match_result_from_admin(
            db=db,
            match=match,
            score_home=score_home,
            score_away=score_away,
            winner_side=None,
        )

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(USER_HELP_TEXT)


@dp.callback_query(lambda callback: callback.data.startswith("predictions_match:"))
async def predictions_match_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        await callback.message.answer(build_predictions_text(db, match))
        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("match_card:"))
async def match_card_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        text = build_match_card_text(db, user, match)

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if not match.is_finished and now < match_start:
            await callback.message.answer(
                text,
                reply_markup=build_matches_keyboard([match]),
            )
        else:
            await callback.message.answer(text)

        await callback.answer()

    finally:
        db.close()


@dp.message(Command("ai_summary"))
async def ai_summary_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        await message.answer("🤖 Отец прогнозов изучает твою статистику...")

        context = build_user_summary_context(db, user)

        try:
            text = generate_ai_summary(context)
        except Exception as error:
            print(f"AI summary error: {error}")

            await message.answer(
                "ИИ-сводка сейчас не получилась. "
                "Обычная статистика доступна через /summary."
            )
            return

        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("admin_sync_wc2026_schedule"))
async def admin_sync_wc2026_schedule_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        await message.answer("🔄 Загружаю календарь WC2026 из API-Football...")

        try:
            result = sync_wc2026_schedule(db)
        except Exception as error:
            print(f"WC2026 schedule sync error: {error}")
            await message.answer(
                "Не удалось синхронизировать календарь WC2026.\n\n"
                f"Ошибка: {error}"
            )
            return

        await message.answer(
            "Календарь WC2026 синхронизирован ✅\n\n"
            f"Всего матчей из API: {result['total']}\n"
            f"Создано: {result['created']}\n"
            f"Обновлено: {result['updated']}\n\n"
            "Проверить: /admin_matches"
        )

    finally:
        db.close()


@dp.message(Command("admin_sync_results"))
async def admin_sync_results_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        client = ApiFootballClient()

        now = datetime.now(timezone.utc)

        matches = (
            db.query(Match)
                .filter(
                Match.tournament_code == TOURNAMENT_CODE,
                Match.external_provider == "api-football",
                Match.external_fixture_id.isnot(None),
                Match.is_finished == False,
                Match.starts_at <= now,
            )
                .order_by(Match.starts_at)
                .limit(20)
                .all()
        )

        if not matches:
            await message.answer("Нет матчей для синхронизации результатов.")
            return

        checked = 0
        updated = 0
        skipped = 0
        lines = ["🔄 Синхронизация результатов", ""]

        for match in matches:
            checked += 1

            try:
                api_fixture = client.get_fixture_by_id(match.external_fixture_id)
            except Exception as error:
                skipped += 1
                lines.append(
                    f"{format_match_label(match, include_id=True)} — ошибка API: {error}"
                )
                continue

            if not api_fixture:
                skipped += 1
                lines.append(
                    f"{format_match_label(match, include_id=True)} — fixture не найден"
                )
                continue

            status = api_fixture["fixture"]["status"]["short"]

            match.status_short = status
            match.status_long = api_fixture["fixture"]["status"].get("long")
            match.synced_at = datetime.now(timezone.utc)

            if status not in {"FT", "AET", "PEN"}:
                skipped += 1
                lines.append(
                    f"{format_match_label(match, include_id=True)} — статус {status}, еще не завершен"
                )
                continue

            score_home, score_away = get_fixture_score(api_fixture)

            if score_home is None or score_away is None:
                skipped += 1
                lines.append(
                    f"{format_match_label(match, include_id=True)} — нет счета в API"
                )
                continue

            winner_side = None

            if is_playoff_match(match):
                winner_side = get_winner_side(api_fixture)

                if winner_side is None:
                    skipped += 1
                    lines.append(
                        f"{format_match_label(match, include_id=True)} — плей-офф, но API не вернул winner"
                    )
                    continue

            result_lines = apply_match_result_from_admin(
                db=db,
                match=match,
                score_home=score_home,
                score_away=score_away,
                winner_side=winner_side,
            )

            updated += 1

            lines.append(
                f"{format_match_label(match, include_id=True)} — обновлен: {score_home}:{score_away}"
            )

        lines.append("")
        lines.append(f"Проверено: {checked}")
        lines.append(f"Обновлено: {updated}")
        lines.append(f"Пропущено: {skipped}")

        await send_long_message(message, lines)

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("forecast_match:"))
async def forecast_match_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        match_id = int(callback.data.split(":")[1])

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await callback.message.answer("Матч не найден.")
            await callback.answer()
            return

        await callback.message.answer(build_forecast_text(db, match))
        await callback.answer()

    finally:
        db.close()


@dp.message(Command("admin_rankings_check"))
async def admin_rankings_check_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        parts = message.text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else "Mexico"

        rankings = FifaRankingsStore()
        result = rankings.get_context(query)

        if not result:
            await message.answer(
                f"Рейтинг не найден для: {query}\n\n"
                "Проверь JSON-файл в data/ и TEAM_ALIASES."
            )
            return

        await message.answer(
            "Рейтинг найден ✅\n\n"
            f"Запрос: {query}\n"
            f"Страна: {result.get('country')}\n"
            f"Место: #{result.get('rank')}\n"
            f"Очки: {result.get('total_points')}\n"
            f"Очки доступны: {result.get('points_available')}"
        )

    finally:
        db.close()


@dp.message(Command("admin_notify_test"))
async def admin_notify_test_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        admin_ids = get_admin_telegram_ids()

        await notify_admins(
            "✅ Тестовое уведомление администратора\n\n"
            "Если ты видишь это сообщение, уведомления работают."
        )

        await message.answer(
            "Тест уведомлений отправлен.\n\n"
            f"ADMIN_NOTIFY_ENABLED: {ADMIN_NOTIFY_ENABLED}\n"
            f"ADMIN_TELEGRAM_IDS: {admin_ids}"
        )

    finally:
        db.close()


@dp.message(Command("admin_command_stats"))
async def admin_command_stats_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        today_start_utc, today_end_utc = get_today_moscow_range_utc()

        today_rows = build_command_stats_for_period(
            db=db,
            start_at=today_start_utc,
            end_at=today_end_utc,
            limit_users=20,
        )

        total_rows = build_command_stats_for_period(
            db=db,
            start_at=None,
            end_at=None,
            limit_users=20,
        )

        now_moscow = datetime.now(APP_TIMEZONE)

        lines = [
            "📊 Статистика вызовов команд",
            f"Сегодня по Москве: {now_moscow.strftime('%d.%m.%Y')}",
            "",
        ]

        lines.extend(
            format_command_stats_block(
                "За сегодня:",
                today_rows,
            )
        )

        lines.append("")
        lines.extend(
            format_command_stats_block(
                "Всего:",
                total_rows,
            )
        )

        await send_long_message(message, lines)

    finally:
        db.close()


@dp.message(Command("admin_command_stats_user"))
async def admin_command_stats_user_handler(message: Message):
    db = SessionLocal()

    try:
        admin_user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(admin_user):
            await message.answer("У тебя нет админских прав.")
            return

        payload = message.text.replace("/admin_command_stats_user", "", 1).strip()

        if not payload:
            await message.answer(
                "Формат:\n\n"
                "/admin_command_stats_user TelegramID\n\n"
                "или:\n"
                "/admin_command_stats_user Имя"
            )
            return

        user_query = db.query(User)

        target_user = None

        if payload.isdigit():
            target_user = user_query.filter(
                User.telegram_id == int(payload)
            ).first()
        else:
            target_user = user_query.filter(
                User.display_name.ilike(f"%{payload}%")
            ).first()

        if not target_user:
            await message.answer("Пользователь не найден.")
            return

        today_start_utc, today_end_utc = get_today_moscow_range_utc()

        today_logs = (
            db.query(CommandLog)
                .filter(
                CommandLog.user_id == target_user.id,
                CommandLog.created_at >= today_start_utc,
                CommandLog.created_at < today_end_utc,
            )
                .order_by(CommandLog.created_at.desc())
                .all()
        )

        total_logs = (
            db.query(CommandLog)
                .filter(CommandLog.user_id == target_user.id)
                .order_by(CommandLog.created_at.desc())
                .all()
        )

        def summarize_logs(logs: list[CommandLog]) -> dict:
            commands = {}

            for log in logs:
                commands[log.command] = commands.get(log.command, 0) + 1

            return {
                "total": len(logs),
                "commands": sorted(
                    commands.items(),
                    key=lambda item: item[1],
                    reverse=True,
                ),
                "last": logs[:10],
            }

        today_summary = summarize_logs(today_logs)
        total_summary = summarize_logs(total_logs)

        lines = [
            "📊 Статистика пользователя",
            "",
            f"Пользователь: {target_user.display_name}",
            f"Telegram ID: {target_user.telegram_id}",
            "",
            f"Сегодня: {today_summary['total']} выз.",
        ]

        if today_summary["commands"]:
            lines.append(
                ", ".join(
                    f"{command} {count}"
                    for command, count in today_summary["commands"]
                )
            )
        else:
            lines.append("Нет вызовов сегодня.")

        lines.extend(
            [
                "",
                f"Всего: {total_summary['total']} выз.",
            ]
        )

        if total_summary["commands"]:
            lines.append(
                ", ".join(
                    f"{command} {count}"
                    for command, count in total_summary["commands"][:10]
                )
            )

        lines.extend(
            [
                "",
                "Последние 10 вызовов:",
            ]
        )

        if not total_summary["last"]:
            lines.append("Нет данных.")
        else:
            for log in total_summary["last"]:
                lines.append(
                    f"{format_datetime(log.created_at)} — {log.command}"
                )

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("fact"))
async def fact_handler(message: Message):
    db = SessionLocal()

    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) == 1:
            await message.answer(
                "📚 Выбери категорию факта:",
                reply_markup=build_category_keyboard("fact_category"),
            )
            return

        category = parts[1].strip().lower()

        if category == "any":
            category = None

        await send_fact_by_category(
            message=message,
            db=db,
            category=category,
            delivery_type="manual",
        )

    finally:
        db.close()


@dp.message(Command("admin_facts_count"))
async def admin_facts_count_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        total = db.query(WorldCupFact).count()
        active = db.query(WorldCupFact).filter(WorldCupFact.is_active == True).count()
        verified = db.query(WorldCupFact).filter(
            WorldCupFact.is_active == True,
            WorldCupFact.needs_verification == False,
        ).count()

        await message.answer(
            "📚 Факты ЧМ\n\n"
            f"Всего: {total}\n"
            f"Активных: {active}\n"
            f"Готовых к показу: {verified}"
        )

    finally:
        db.close()


@dp.message(Command("admin_import_facts"))
async def admin_import_facts_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            result = import_world_cup_facts_from_seed(db)
        except Exception as error:
            db.rollback()
            print(f"Facts import error: {error}")

            await message.answer(
                "Не удалось импортировать факты ❌\n\n"
                f"Ошибка: {error}"
            )
            return

        await message.answer(
            "Факты импортированы ✅\n\n"
            f"Всего в seed-файле: {result['total']}\n"
            f"Создано: {result['created']}\n"
            f"Обновлено: {result['updated']}\n"
            f"Пропущено: {result['skipped']}\n\n"
            "Проверить: /admin_facts_count\n"
            "Случайный факт: /fact"
        )

    finally:
        db.close()


@dp.message(Command("admin_daily_fact_preview"))
async def admin_daily_fact_preview_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        fact = get_random_fact_not_sent_today(db)

        if not fact:
            await message.answer("Нет доступных фактов для предпросмотра.")
            return

        await message.answer(format_daily_world_cup_rubric(fact))

    finally:
        db.close()


@dp.message(Command("quiz"))
async def quiz_handler(message: Message):
    if is_group_chat(message):
        await group_quiz_start_handler(message)
        return

    await private_quiz_handler(message)


@dp.message(Command("admin_import_quiz"))
async def admin_import_quiz_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            result = import_quiz_questions_from_seed(db)
        except Exception as error:
            db.rollback()
            print(f"Quiz import error: {error}")

            await message.answer(
                "Не удалось импортировать вопросы ❌\n\n"
                f"Ошибка: {error}"
            )
            return

        await message.answer(
            "Вопросы импортированы ✅\n\n"
            f"Всего в seed-файле: {result['total']}\n"
            f"Создано: {result['created']}\n"
            f"Обновлено: {result['updated']}\n"
            f"Пропущено: {result['skipped']}\n\n"
            "Проверить: /quiz"
        )

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("quiz_answer:"))
async def quiz_answer_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        _, question_id_text, selected_option = callback.data.split(":")

        question = db.query(QuizQuestion).filter(
            QuizQuestion.id == int(question_id_text)
        ).first()

        if not question:
            await callback.answer("Вопрос не найден", show_alert=True)
            return

        user, _ = get_or_create_user(db, callback.from_user)

        selected_option = selected_option.upper()
        correct_option = question.correct_option.upper()

        is_correct = selected_option == correct_option

        answer = QuizAnswer(
            quiz_question_id=question.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            selected_option=selected_option,
            is_correct=is_correct,
        )

        db.add(answer)
        db.commit()

        selected_text = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }[selected_option]

        correct_text = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }[correct_option]

        if is_correct:
            result_text = "✅ Верно!"
            roast_text = "Отец прогнозов доволен. Такое бы еще в точный счет перенести."
        else:
            result_text = "❌ Мимо."
            roast_text = "Ничего страшного. Некоторые так целые турниры прогнозируют."

        explanation = question.explanation or ""

        await callback.message.answer(
            f"{result_text}\n\n"
            f"Твой ответ: {selected_option}. {selected_text}\n"
            f"Правильный ответ: {correct_option}. {correct_text}\n\n"
            f"{explanation}\n\n"
            f"🔥 {roast_text}"
        )

        await callback.answer()

    finally:
        db.close()


@dp.message(Command("quiz_stats"))
async def quiz_stats_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        answers = db.query(QuizAnswer).filter(
            QuizAnswer.user_id == user.id
        ).all()

        total = len(answers)
        correct = sum(1 for answer in answers if answer.is_correct)

        if total == 0:
            await message.answer(
                "Ты еще не отвечал на вопросы.\n\n"
                "Попробуй: /quiz"
            )
            return

        accuracy = correct / total * 100

        await message.answer(
            "📊 Твоя статистика квиза\n\n"
            f"Ответов: {total}\n"
            f"Верных: {correct}\n"
            f"Точность: {accuracy:.0f}%\n\n"
            "Новый вопрос: /quiz"
        )

    finally:
        db.close()


@dp.message(Command("admin_quiz_stats"))
async def admin_quiz_stats_handler(message: Message):
    db = SessionLocal()

    try:
        admin_user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(admin_user):
            await message.answer("У тебя нет админских прав.")
            return

        users = db.query(User).all()

        rows = []

        for user in users:
            answers = db.query(QuizAnswer).filter(
                QuizAnswer.user_id == user.id
            ).all()

            total = len(answers)

            if total == 0:
                continue

            correct = sum(1 for answer in answers if answer.is_correct)

            rows.append(
                {
                    "name": user.display_name,
                    "total": total,
                    "correct": correct,
                    "accuracy": correct / total * 100,
                }
            )

        rows.sort(
            key=lambda row: (row["correct"], row["accuracy"], row["total"]),
            reverse=True,
        )

        if not rows:
            await message.answer("По квизу пока нет ответов.")
            return

        lines = [
            "📊 Статистика квиза",
            "",
        ]

        for index, row in enumerate(rows, start=1):
            lines.append(
                f"{index}. {row['name']} — "
                f"{row['correct']}/{row['total']} "
                f"({row['accuracy']:.0f}%)"
            )

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.callback_query(lambda callback: callback.data.startswith("fact_category:"))
async def fact_category_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        category = callback.data.split(":")[1]

        if category == "any":
            category = None

        query = db.query(WorldCupFact).filter(
            WorldCupFact.is_active == True,
            WorldCupFact.needs_verification == False,
        )

        if category:
            query = query.filter(WorldCupFact.category == category)

        facts = query.all()

        if not facts:
            await callback.message.answer(
                "Фактов по такой категории пока нет.\n\n"
                "Попробуй другую категорию: /fact"
            )
            await callback.answer()
            return

        fact = random.choice(facts)

        user, _ = get_or_create_user(db, callback.from_user)

        db.add(
            FactDeliveryLog(
                fact_id=fact.id,
                user_id=user.id,
                telegram_id=user.telegram_id,
                delivery_type="manual",
            )
        )
        db.commit()

        category_text = FACT_QUIZ_CATEGORIES.get(
            category or "any",
            "🎲 Любая категория",
        )

        await callback.message.answer(
            f"{category_text}\n\n"
            f"{format_world_cup_fact(fact)}"
        )

        await callback.answer()

    finally:
        db.close()


@dp.callback_query(lambda callback: callback.data.startswith("quiz_category:"))
async def quiz_category_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        category = callback.data.split(":")[1]

        if category == "any":
            category = None

        query = db.query(QuizQuestion).filter(
            QuizQuestion.is_active == True,
        )

        if category:
            query = query.filter(QuizQuestion.category == category)

        questions = query.all()

        if not questions:
            await callback.message.answer(
                "Вопросов по такой категории пока нет.\n\n"
                "Попробуй другую категорию: /quiz"
            )
            await callback.answer()
            return

        question = random.choice(questions)

        category_text = FACT_QUIZ_CATEGORIES.get(
            category or "any",
            "🎲 Любая категория",
        )

        await callback.message.answer(
            f"{category_text}\n\n"
            f"{format_quiz_question(question)}",
            reply_markup=build_quiz_keyboard(question),
        )

        await callback.answer()

    finally:
        db.close()


@dp.message(Command("admin_import_archive"))
async def admin_import_archive_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            result = import_historical_archive_from_seed(db)
        except Exception as error:
            db.rollback()
            print(f"Archive import error: {error}")

            await message.answer(
                "Не удалось импортировать архив ❌\n\n"
                f"Ошибка: {error}"
            )
            return

        await message.answer(
            "Архив импортирован ✅\n\n"
            f"Всего в seed-файле: {result['total']}\n"
            f"Создано: {result['created']}\n"
            f"Обновлено: {result['updated']}\n"
            f"Пропущено: {result['skipped']}\n\n"
            "Проверить: /archive"
        )

    finally:
        db.close()


@dp.message(Command("archive"))
async def archive_handler(message: Message):
    db = SessionLocal()

    try:
        parts = message.text.split(maxsplit=1)
        filter_value = parts[1].strip().lower() if len(parts) > 1 else None

        query = db.query(HistoricalArchiveCard).filter(
            HistoricalArchiveCard.is_active == True,
            HistoricalArchiveCard.is_public == True,
        )

        if filter_value:
            # Можно фильтровать по турниру или типу:
            # /archive wc2022
            # /archive euro2024
            # /archive collective_fail
            query = query.filter(
                (HistoricalArchiveCard.tournament_code == filter_value)
                | (HistoricalArchiveCard.card_type == filter_value)
            )

        cards = query.all()

        if not cards:
            await message.answer(
                "Архивных карточек по такому фильтру пока нет.\n\n"
                "Попробуй просто /archive"
            )
            return

        card = random.choice(cards)

        user, _ = get_or_create_user(db, message.from_user)

        db.add(
            HistoricalArchiveDeliveryLog(
                archive_card_id=card.id,
                user_id=user.id,
                telegram_id=user.telegram_id,
                chat_id=message.chat.id,
                delivery_type="manual",
            )
        )
        db.commit()

        await message.answer(format_archive_card(card))

    finally:
        db.close()


@dp.message(Command("admin_archive_count"))
async def admin_archive_count_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        total = db.query(HistoricalArchiveCard).count()
        active = db.query(HistoricalArchiveCard).filter(
            HistoricalArchiveCard.is_active == True
        ).count()
        public = db.query(HistoricalArchiveCard).filter(
            HistoricalArchiveCard.is_active == True,
            HistoricalArchiveCard.is_public == True,
        ).count()

        await message.answer(
            "🔥 Архив Отца прогнозов\n\n"
            f"Всего карточек: {total}\n"
            f"Активных: {active}\n"
            f"Публичных активных: {public}"
        )

    finally:
        db.close()


@dp.message(Command("panini"))
async def panini_handler(message: Message, state: FSMContext):
    allowed, remaining = can_use_panini(message.from_user.id)

    if not allowed:
        await message.answer(
            f"🎴 Панини-станок перегрелся.\n\n"
            f"Попробуй снова через {remaining} сек."
        )
        return

    if not PANINI_ENABLED:
        await message.answer("🎴 Панини-режим временно выключен.")
        return

    if not openai_client:
        await message.answer(
            "🎴 Панини-режим не настроен: нет OPENAI_API_KEY."
        )
        return

    await state.clear()
    await state.set_state(PaniniForm.waiting_for_photo)

    await message.answer(
        "🎴 Панини-режим активирован\n\n"
        "Отправь фотографию человека, из которой нужно сделать карточку игрока сборной.\n\n"
        "Лучше подходит:\n"
        "— один человек в кадре\n"
        "— лицо хорошо видно\n"
        "— хороший свет\n"
        "— без сильных перекрытий\n\n"
        "Используйте только фото с согласия человека."
    )


@dp.message(Command("chat_id"))
async def chat_id_handler(message: Message):
    await message.answer(
        f"chat_id: {message.chat.id}\n"
        f"type: {message.chat.type}"
    )

@dp.callback_query(lambda callback: callback.data.startswith("group_quiz_answer:"))
async def group_quiz_answer_callback(callback: CallbackQuery):
    db = SessionLocal()

    try:
        _, session_id_text, selected_option = callback.data.split(":")
        session_id = int(session_id_text)

        session = db.query(GroupQuizSession).filter(
            GroupQuizSession.id == session_id
        ).first()

        if not session:
            await callback.answer(
                "Квиз не найден.",
                show_alert=True,
            )
            return

        if session.status != "open":
            await callback.answer(
                "Этот вопрос уже завершен.",
                show_alert=True,
            )
            return

        user, _ = get_or_create_user(db, callback.from_user)

        existing_answer = db.query(GroupQuizAnswer).filter(
            GroupQuizAnswer.session_id == session.id,
            GroupQuizAnswer.user_id == user.id,
        ).first()

        if existing_answer:
            await callback.answer(
                "Ты уже ответил на этот вопрос. Переобуться не получится 😈",
                show_alert=True,
            )
            return

        question = session.question

        selected_option = selected_option.upper()
        correct_option = question.correct_option.upper()
        is_correct = selected_option == correct_option

        answer = GroupQuizAnswer(
            session_id=session.id,
            quiz_question_id=question.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            display_name=user.display_name,
            selected_option=selected_option,
            is_correct=is_correct,
        )

        db.add(answer)
        db.commit()

        await callback.answer(
            "Ответ принят ✅",
            show_alert=False,
        )

    finally:
        db.close()


@dp.message(Command("quiz_finish"))
async def group_quiz_finish_handler(message: Message):
    if not is_group_chat(message):
        await message.answer("Эта команда нужна для группового квиза.")
        return

    db = SessionLocal()

    try:
        session = db.query(GroupQuizSession).filter(
            GroupQuizSession.chat_id == message.chat.id,
            GroupQuizSession.status == "open",
        ).first()

        if not session:
            await message.answer("В этом чате сейчас нет активного квиза.")
            return

        text = finish_group_quiz_and_build_result_text(db, session)

        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("quiz_table"))
async def group_quiz_table_handler(message: Message):
    db = SessionLocal()

    try:
        query = db.query(GroupQuizAnswer)

        if is_group_chat(message):
            session_ids = [
                row.id
                for row in db.query(GroupQuizSession)
                .filter(GroupQuizSession.chat_id == message.chat.id)
                .all()
            ]

            if not session_ids:
                await message.answer("В этом чате еще не было групповых квизов.")
                return

            query = query.filter(GroupQuizAnswer.session_id.in_(session_ids))

        answers = query.all()

        if not answers:
            await message.answer("Ответов по квизу пока нет.")
            return

        stats = {}

        for answer in answers:
            key = answer.user_id

            if key not in stats:
                stats[key] = {
                    "name": answer.display_name or f"User {answer.telegram_id}",
                    "total": 0,
                    "correct": 0,
                }

            stats[key]["total"] += 1

            if answer.is_correct:
                stats[key]["correct"] += 1

        rows = list(stats.values())

        rows.sort(
            key=lambda row: (
                row["correct"],
                row["correct"] / row["total"],
                row["total"],
            ),
            reverse=True,
        )

        lines = [
            "🏆 Рейтинг группового квиза",
            "",
        ]

        for index, row in enumerate(rows, start=1):
            accuracy = row["correct"] / row["total"] * 100

            lines.append(
                f"{index}. {row['name']} — "
                f"{row['correct']}/{row['total']} "
                f"({accuracy:.0f}%)"
            )

        await message.answer("\n".join(lines))

    finally:
        db.close()


@dp.message(Command("admin_send_daily_fact_group"))
async def admin_send_daily_fact_group_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        fact = get_random_fact_not_sent_today(db)

        if not fact:
            await message.answer("Нет доступных фактов для отправки.")
            return

        await send_daily_fact_to_group(db, fact)

        await message.answer(
            "Ежедневная рубрика отправлена в групповой чат ✅"
        )

    finally:
        db.close()


@dp.message(PaniniForm.waiting_for_photo, F.photo)
async def panini_photo_handler(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    local_path = f"/tmp/panini_{message.from_user.id}_{photo.file_unique_id}.jpg"

    await bot.download(file, destination=local_path)

    db = SessionLocal()

    try:
        teams = get_panini_teams_from_matches(db, limit=20)

        if not teams:
            await message.answer(
                "Не нашел сборные ЧМ-2026 с FIFA ranking в базе матчей.\n\n"
                "Проверь, что матчи загружены и рейтинги доступны."
            )
            await state.clear()
            return

        await state.update_data(
            photo_path=local_path,
            panini_teams=teams,
        )

        await state.set_state(PaniniForm.waiting_for_team)

        await message.answer(
            "Фото получил ✅\n\n"
            "Выбери сборную из топ-20 участников ЧМ-2026 по FIFA ranking:",
            reply_markup=build_panini_team_keyboard_from_list(teams),
        )

    finally:
        db.close()


@dp.message(PaniniForm.waiting_for_photo)
async def panini_photo_invalid_handler(message: Message):
    await message.answer(
        "Нужно отправить именно фотографию.\n\n"
        "Лучше селфи или фото по пояс, где лицо хорошо видно."
    )


@dp.callback_query(
    PaniniForm.waiting_for_team,
    lambda callback: callback.data.startswith("panini_team:")
)
async def panini_team_callback(callback: CallbackQuery, state: FSMContext):
    index_text = callback.data.split(":")[1]

    if not index_text.isdigit():
        await callback.answer("Некорректный выбор", show_alert=True)
        return

    index = int(index_text)

    data = await state.get_data()

    teams = data.get("panini_teams") or []

    if index < 0 or index >= len(teams):
        await callback.answer("Сборная не найдена", show_alert=True)
        return

    photo_path = data.get("photo_path")

    if not photo_path:
        await callback.answer("Фото не найдено. Начни заново: /panini", show_alert=True)
        await state.clear()
        return

    team = teams[index]

    team_api_name = team["api_name"]
    team_display_name = team["display_name"]
    team_flag = team["flag"]
    team_rank = team["rank"]

    user_name = callback.from_user.full_name or "Игрок"

    await callback.answer("Генерирую карточку...")

    await callback.message.answer(
        f"🎨 Делаю карточку: {team_flag} #{team_rank} {team_display_name}\n"
        "Это может занять до минуты."
    )

    try:
        result_path = await asyncio.to_thread(
            generate_panini_card,
            photo_path=photo_path,
            person_name=user_name,
            team_api_name=team_api_name,
            team_display_name=team_display_name,
            team_flag=team_flag,
        )

        mark_panini_used(callback.from_user.id)
        await callback.message.answer_photo(
            photo=FSInputFile(result_path),
            caption=(
                "🎴 Панини-карточка готова!\n\n"
                f"Игрок: {user_name}\n"
                f"Сборная: {team_flag} {team_display_name}"
            ),
        )

    except APITimeoutError:
        await callback.message.answer(
            "Не удалось сгенерировать карточку 😢\n\n"
            "OpenAI не успел вернуть изображение по таймауту.\n"
            "Попробуй еще раз через минуту или отправь фото покрупнее/с лучшим светом."
        )

    except Exception as error:
        print(f"Panini generation error: {error}")
        await callback.message.answer(
            "Не удалось сгенерировать карточку 😢\n\n"
            f"Ошибка: {error}"
        )

    finally:
        await state.clear()

        try:
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as cleanup_error:
            print(f"Panini cleanup input error: {cleanup_error}")

        try:
            if "result_path" in locals() and os.path.exists(result_path):
                os.remove(result_path)
        except Exception as cleanup_error:
            print(f"Panini cleanup output error: {cleanup_error}")


async def main():
    if reminders_enabled():
        asyncio.create_task(reminders_loop())
    if DAILY_FACTS_ENABLED:
        asyncio.create_task(daily_facts_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
