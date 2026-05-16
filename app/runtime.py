"""Runtime dependencies, bot instance, dispatcher and environment settings."""

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

ADMIN_NOTIFY_ENABLED = os.getenv("ADMIN_NOTIFY_ENABLED", "true").lower() == "true"

TOURNAMENT_CODE = os.getenv("TOURNAMENT_CODE", "wc2026")

TOURNAMENT_STARTS_AT_RAW = os.getenv(
    "TOURNAMENT_STARTS_AT",
    "2026-06-11T21:00:00+03:00",
)

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

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(token=TOKEN)

dp = Dispatcher(storage=MemoryStorage())

FACTS_SEED_PATH = Path("data/world_cup_facts_seed.json")


# Re-export configuration constants for modules that import runtime with *.
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
