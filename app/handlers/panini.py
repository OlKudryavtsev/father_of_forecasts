"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

async def panini_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for panini_handler."""
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


async def panini_photo_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for panini_photo_handler."""
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


async def panini_photo_invalid_handler(message: Message):
    """Handle asynchronous bot workflow for panini_photo_invalid_handler."""
    await message.answer(
        "Нужно отправить именно фотографию.\n\n"
        "Лучше селфи или фото по пояс, где лицо хорошо видно."
    )


async def panini_team_callback(callback: CallbackQuery, state: FSMContext):
    """Handle asynchronous bot workflow for panini_team_callback."""
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

