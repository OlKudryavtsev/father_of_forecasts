"""Real implementation extracted from the former bot_runtime monolith."""


from app.constants.texts import USER_HELP_TEXT
from app.runtime import Message

async def rules_handler(message: Message):
    """Handle asynchronous bot workflow for rules_handler."""
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
        "🕒 Прогноз счёта учитывается только по основному времени (90 минут). "
        "Дополнительное время и пенальти учитываются только для прохода дальше.\n\n"
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


async def help_handler(message: Message):
    """Handle asynchronous bot workflow for help_handler."""
    await message.answer(USER_HELP_TEXT)

