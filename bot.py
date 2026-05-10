import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.db import SessionLocal
from app.models import User

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start_handler(message: Message):
    db = SessionLocal()

    try:
        telegram_user = message.from_user

        existing_user = db.query(User).filter(
            User.telegram_id == telegram_user.id
        ).first()

        if existing_user:
            await message.answer(
                f"С возвращением, {existing_user.display_name} ⚽"
            )
            return

        new_user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            display_name=telegram_user.full_name
        )

        db.add(new_user)
        db.commit()

        await message.answer(
            f"Добро пожаловать в Отец прогнозов, {telegram_user.full_name} 🏆"
        )

    finally:
        db.close()


@dp.message(Command("matches"))
async def matches_handler(message: Message):
    await message.answer(
        "Пока матчей нет. Скоро добавим календарь ЧМ-2026 ⚽"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())