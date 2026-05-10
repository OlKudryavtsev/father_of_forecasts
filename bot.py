import asyncio
import os
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.db import SessionLocal
from app.models import Match, Prediction, User

from zoneinfo import ZoneInfo


TOKEN = os.getenv("BOT_TOKEN")
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Moscow"))

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(token=TOKEN)
dp = Dispatcher()


def get_or_create_user(db, telegram_user):
    existing_user = db.query(User).filter(
        User.telegram_id == telegram_user.id
    ).first()

    if existing_user:
        return existing_user, False

    new_user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        display_name=telegram_user.full_name,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user, True


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
    return (
        f"#{match.id} {match.home_team} — {match.away_team}\n"
        f"Стадия: {match.stage}\n"
        f"Старт: {start_text}"
    )

def format_datetime(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_dt = dt.astimezone(APP_TIMEZONE)
    return local_dt.strftime("%d.%m.%Y %H:%M")

@dp.message(Command("start"))
async def start_handler(message: Message):
    db = SessionLocal()

    try:
        user, created = get_or_create_user(db, message.from_user)

        if created:
            await message.answer(
                f"Добро пожаловать в Отец прогнозов, {user.display_name} 🏆"
            )
        else:
            await message.answer(
                f"С возвращением, {user.display_name} ⚽"
            )

    finally:
        db.close()


@dp.message(Command("matches"))
async def matches_handler(message: Message):
    db = SessionLocal()

    try:
        matches = db.query(Match).order_by(Match.starts_at).all()

        if not matches:
            await message.answer("Пока матчей нет.")
            return

        text = "📅 Матчи:\n\n"
        text += "\n\n".join(format_match(match) for match in matches)

        text += (
            "\n\nЧтобы сделать прогноз, напиши:\n"
            "/predict ID СЧЕТ\n\n"
            "Например:\n"
            "/predict 1 2:1\n\n"
            "Чтобы посмотреть прогнозы по матчу:\n"
            "/predictions ID\n\n"
            "Например:\n"
            "/predictions 1"
        )

        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("predict"))
async def predict_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        if len(parts) != 3:
            await message.answer(
                "Формат прогноза:\n"
                "/predict ID СЧЕТ\n\n"
                "Например:\n"
                "/predict 1 2:1"
            )
            return

        _, match_id_raw, score_raw = parts

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

        existing_prediction = db.query(Prediction).filter(
            Prediction.user_id == user.id,
            Prediction.match_id == match.id,
        ).first()

        if existing_prediction:
            existing_prediction.pred_home = pred_home
            existing_prediction.pred_away = pred_away
            db.commit()

            await message.answer(
                f"Прогноз обновлен:\n"
                f"{match.home_team} — {match.away_team}: "
                f"{pred_home}:{pred_away}"
            )
            return

        prediction = Prediction(
            user_id=user.id,
            match_id=match.id,
            pred_home=pred_home,
            pred_away=pred_away,
        )

        db.add(prediction)
        db.commit()

        await message.answer(
            f"Прогноз принят:\n"
            f"{match.home_team} — {match.away_team}: "
            f"{pred_home}:{pred_away}"
        )

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
            lines.append(
                f"{match.home_team} — {match.away_team}: "
                f"{prediction.pred_home}:{prediction.pred_away}"
            )

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("predictions"))
async def predictions_handler(message: Message):
    db = SessionLocal()

    try:
        parts = message.text.split()

        if len(parts) != 2:
            await message.answer(
                "Формат команды:\n"
                "/predictions ID_МАТЧА\n\n"
                "Например:\n"
                "/predictions 1"
            )
            return

        _, match_id_raw = parts

        if not match_id_raw.isdigit():
            await message.answer("ID матча должен быть числом.")
            return

        match_id = int(match_id_raw)

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

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
            f"🔮 Прогнозы на матч #{match.id}",
            f"{match.home_team} — {match.away_team}",
            f"Старт: {start_text}",
            "",
        ]

        if is_revealed:
            lines.append("Матч уже начался — прогнозы открыты:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if prediction:
                    lines.append(
                        f"{user.display_name}: "
                        f"{prediction.pred_home}:{prediction.pred_away}"
                    )
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

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("table"))
async def table_handler(message: Message):
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.display_name).all()

        if not users:
            await message.answer("Пока нет участников.")
            return

        rows = []

        for user in users:
            predictions = db.query(Prediction).filter(
                Prediction.user_id == user.id
            ).all()

            total_points = sum(prediction.points or 0 for prediction in predictions)

            exact_scores = sum(
                1
                for prediction in predictions
                if prediction.points == 3
            )

            outcomes = sum(
                1
                for prediction in predictions
                if prediction.points == 1
            )

            rows.append(
                {
                    "name": user.display_name,
                    "points": total_points,
                    "exact_scores": exact_scores,
                    "outcomes": outcomes,
                    "predictions_count": len(predictions),
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

        lines = ["🏆 Таблица «Отец прогнозов»", ""]

        for index, row in enumerate(rows, start=1):
            lines.append(
                f"{index}. {row['name']} — {row['points']} очк. "
                f"🎯 {row['exact_scores']} | ✅ {row['outcomes']} | "
                f"📋 {row['predictions_count']}"
            )

        lines.append("")
        lines.append("🎯 точные счета")
        lines.append("✅ угаданные исходы")
        lines.append("📋 всего прогнозов")

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("rules"))
async def rules_handler(message: Message):
    await message.answer(
        "📜 Правила «Отец прогнозов»\n\n"
        "За каждый матч:\n"
        "🎯 3 очка — точный счет\n"
        "✅ 1 очко — угаданный исход\n"
        "❌ 0 очков — если не угадан ни счет, ни исход\n\n"
        "Пример:\n"
        "Прогноз: Мексика — ЮАР 2:1\n\n"
        "Если матч закончился 2:1 — 3 очка.\n"
        "Если матч закончился 3:1 — 1 очко.\n"
        "Если матч закончился 2:2 или 0:1 — 0 очков.\n\n"
        "Прогноз можно менять только до стартового свистка."
    )

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())