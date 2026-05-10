
from aiogram import Bot, Dispatcher
from aiogram.types import Message
import asyncio, os

TOKEN=os.getenv("BOT_TOKEN","PUT_TOKEN")

bot=Bot(TOKEN)
dp=Dispatcher()

@dp.message()
async def echo(message: Message):
    if message.text=="/start":
        await message.answer("Добро пожаловать в Отец прогнозов")
    elif message.text=="/matches":
        await message.answer("Mexico vs South Africa")
    else:
        await message.answer("Команда принята")

async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
