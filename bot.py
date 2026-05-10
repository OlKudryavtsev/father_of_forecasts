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

PLAYOFF_STAGES = {
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "third_place",
    "final",
}


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
            "\n\nЧтобы сделать прогноз:\n"
            "/predict ID СЧЕТ\n\n"
            "Например:\n"
            "/predict 1 2:1\n\n"
            "Для плей-офф можно добавить ставку на проход:\n"
            "/predict ID СЧЕТ home\n"
            "/predict ID СЧЕТ away\n"
            "/predict ID СЧЕТ none\n\n"
            "home — пройдет первая команда\n"
            "away — пройдет вторая команда\n"
            "none — не рисковать ставкой на проход\n\n"
            "Чтобы посмотреть прогнозы по матчу:\n"
            "/predictions ID"
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
                f"{match.home_team} — {match.away_team}: "
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
                    line = (
                        f"{user.display_name}: "
                        f"{prediction.pred_home}:{prediction.pred_away}"
                    )

                    if is_playoff_match(match):
                        line += f" ({format_advancement_prediction(prediction, match)})"

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

            rows.append(
                {
                    "name": user.display_name,
                    "points": total_points,
                    "exact_scores": exact_scores,
                    "outcomes": outcomes,
                    "predictions_count": len(predictions),
                    "advancement_plus": advancement_plus,
                    "advancement_minus": advancement_minus,
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
                f"🟢 {row['advancement_plus']} | 🔴 {row['advancement_minus']} | "
                f"📋 {row['predictions_count']}"
            )

        lines.append("")
        lines.append("🎯 точные счета")
        lines.append("✅ угаданные исходы")
        lines.append("🟢 угаданные проходы")
        lines.append("🔴 неугаданные проходы")
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
        "В матчах плей-офф можно дополнительно рискнуть "
        "и поставить, кто пройдет дальше:\n"
        "🟢 +1 очко — если проход угадан\n"
        "🔴 -1 очко — если проход не угадан\n"
        "⚪ 0 очков — если участник решил не ставить на проход\n\n"
        "Пример плей-офф:\n"
        "/predict 5 1:1 home\n"
        "Это значит: счет 1:1, дальше пройдет первая команда.\n\n"
        "Можно не рисковать:\n"
        "/predict 5 1:1 none\n\n"
        "Прогноз можно менять только до стартового свистка."
    )

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())