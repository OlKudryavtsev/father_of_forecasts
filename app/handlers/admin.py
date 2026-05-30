"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.admin import format_command_stats_block
from app.formatters.facts import format_daily_world_cup_rubric
from app.formatters.matches import format_datetime, format_match_label
from app.formatters.misc import format_reminder_offset
from app.jobs.reminders import get_reminder_check_interval_seconds, get_reminder_offsets_minutes, reminders_enabled
from app.keyboards.admin import build_admin_result_matches_keyboard, build_admin_result_score_keyboard, build_admin_result_winner_keyboard
from app.runtime import (
    ADMIN_NOTIFY_ENABLED,
    APP_TIMEZONE,
    ApiFootballClient,
    CallbackQuery,
    CommandLog,
    FSMContext,
    FifaRankingsStore,
    HistoricalArchiveCard,
    Match,
    Message,
    Prediction,
    QuizAnswer,
    ReminderLog,
    SessionLocal,
    TOURNAMENT_CODE,
    TournamentPrediction,
    TournamentResult,
    User,
    WorldCupFact,
    bot,
    datetime,
    get_fixture_score,
    get_winner_side,
    score_tournament_prediction,
    sync_wc2026_schedule,
    timedelta,
    timezone,
)
from app.services.admin import build_command_stats_for_period, ensure_admin_or_reply, get_admin_telegram_ids, get_today_moscow_range_utc, is_user_admin
from app.services.archive import import_historical_archive_from_seed
from app.services.facts import get_random_archive_card_for_daily_rubric, get_random_fact_not_sent_today, import_world_cup_facts_from_seed, send_daily_fact_to_group
from app.services.matches import (
    apply_match_result_from_admin,
    get_default_match_round,
    import_matches_from_rows,
    is_playoff_match,
    parse_admin_edit_match_payload,
    parse_csv_matches,
    parse_match_id_command,
    parse_result_payload,
)
from app.services.misc import send_long_message
from app.services.notifications import notify_admins
from app.services.predictions import parse_score
from app.services.quiz import import_quiz_questions_from_seed
from app.services.tournament import parse_tournament_result_payload
from app.services.users import get_or_create_user
from app.states import AdminResultForm



def _parse_admin_release_payload(text: str) -> tuple[str | None, str]:
    """Parse /admin_release payload into target mode and message text.

    Expected format:
        /admin_release group|users|both
        Release notes text...
    """
    lines = text.splitlines()

    if not lines:
        return None, ""

    first_line_parts = lines[0].strip().split(maxsplit=1)

    if len(first_line_parts) < 2:
        return None, ""

    target = first_line_parts[1].strip().lower()
    release_text = "\n".join(lines[1:]).strip()

    return target, release_text


async def _send_text_chunks(chat_id: int, text: str, chunk_size: int = 3900) -> int:
    """Send a long plain-text message to a chat in Telegram-safe chunks."""
    if not text:
        return 0

    sent = 0

    for start in range(0, len(text), chunk_size):
        chunk = text[start:start + chunk_size]
        await bot.send_message(chat_id=chat_id, text=chunk)
        sent += 1

    return sent


async def admin_handler(message: Message):
    """Handle asynchronous bot workflow for admin_handler."""
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
            "Release Notes:\n"
            "/admin_release group — отправить релиз в общий чат\n"
            "/admin_release users — отправить релиз всем пользователям в личку\n"
            "/admin_release both — отправить релиз и в чат, и пользователям\n\n"
            "Статистика команд:\n"
            "/admin_command_stats\n"
            "/admin_command_stats_user Имя или TelegramID\n\n"
        )

    finally:
        db.close()


async def admin_release_handler(message: Message):
    """Send release notes from the bot to the group, users or both targets."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        target, release_text = _parse_admin_release_payload(message.text or "")

        if target not in {"group", "users", "both"}:
            await message.answer(
                "Формат:\n\n"
                "/admin_release group\n"
                "текст релиза\n\n"
                "Доступные режимы:\n"
                "group — в общий чат\n"
                "users — всем зарегистрированным пользователям в личку\n"
                "both — и в общий чат, и пользователям"
            )
            return

        if not release_text:
            await message.answer(
                "После первой строки добавь текст релиза.\n\n"
                "Пример:\n"
                "/admin_release group\n"
                "🚀 Release Notes v0.7\n\n"
                "Добавлено:\n"
                "— /quiz_battle"
            )
            return

        sent_group = False
        sent_users = 0
        failed_users = 0

        if target in {"group", "both"}:
            from app.services.misc import get_group_chat_id

            group_chat_id = get_group_chat_id()

            if not group_chat_id:
                await message.answer("GROUP_CHAT_ID не задан.")
                return

            await _send_text_chunks(
                chat_id=group_chat_id,
                text=release_text,
            )
            sent_group = True

        if target in {"users", "both"}:
            users = db.query(User).all()

            for target_user in users:
                if not target_user.telegram_id:
                    continue

                if target_user.telegram_id == 0:
                    continue

                try:
                    await _send_text_chunks(
                        chat_id=target_user.telegram_id,
                        text=release_text,
                    )
                    sent_users += 1
                except Exception as error:
                    failed_users += 1
                    print(
                        f"Failed to send release notes to "
                        f"{target_user.telegram_id}: {error}"
                    )

        await message.answer(
            "Release Notes отправлены ✅\n\n"
            f"В группу: {'да' if sent_group else 'нет'}\n"
            f"Пользователям: {sent_users}\n"
            f"Ошибок по пользователям: {failed_users}"
        )

    finally:
        db.close()


async def admin_set_result_handler(message: Message):
    """Handle asynchronous bot workflow for admin_set_result_handler."""
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


async def admin_recalculate_handler(message: Message):
    """Handle asynchronous bot workflow for admin_recalculate_handler."""
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


async def admin_set_tournament_result_handler(message: Message):
    """Handle asynchronous bot workflow for admin_set_tournament_result_handler."""
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


async def admin_tournament_recalculate_handler(message: Message):
    """Handle asynchronous bot workflow for admin_tournament_recalculate_handler."""
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


async def admin_matches_handler(message: Message):
    """Handle asynchronous bot workflow for admin_matches_handler."""
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


async def admin_matches_all_handler(message: Message):
    """Handle asynchronous bot workflow for admin_matches_all_handler."""
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


async def admin_edit_match_handler(message: Message):
    """Handle asynchronous bot workflow for admin_edit_match_handler."""
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


async def admin_delete_match_handler(message: Message):
    """Handle asynchronous bot workflow for admin_delete_match_handler."""
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


async def admin_force_delete_match_handler(message: Message):
    """Handle asynchronous bot workflow for admin_force_delete_match_handler."""
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


async def admin_import_matches_handler(message: Message):
    """Handle asynchronous bot workflow for admin_import_matches_handler."""
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


async def admin_reminders_status_handler(message: Message):
    """Handle asynchronous bot workflow for admin_reminders_status_handler."""
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


async def admin_result_match_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for admin_result_match_callback."""
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


async def admin_result_score_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for admin_result_score_callback."""
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


async def admin_result_winner_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for admin_result_winner_callback."""
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


async def admin_result_custom_callback(callback: CallbackQuery, state: FSMContext):
    """Handle asynchronous bot workflow for admin_result_custom_callback."""
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


async def admin_result_custom_score_handler(message: Message, state: FSMContext):
    """Handle asynchronous bot workflow for admin_result_custom_score_handler."""
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


async def admin_sync_wc2026_schedule_handler(message: Message):
    """Handle asynchronous bot workflow for admin_sync_wc2026_schedule_handler."""
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


async def admin_sync_results_handler(message: Message):
    """Handle asynchronous bot workflow for admin_sync_results_handler."""
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


async def admin_rankings_check_handler(message: Message):
    """Handle asynchronous bot workflow for admin_rankings_check_handler."""
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


async def admin_notify_test_handler(message: Message):
    """Handle asynchronous bot workflow for admin_notify_test_handler."""
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


async def admin_command_stats_handler(message: Message):
    """Handle asynchronous bot workflow for admin_command_stats_handler."""
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


async def admin_command_stats_user_handler(message: Message):
    """Handle asynchronous bot workflow for admin_command_stats_user_handler."""
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
            """Provide bot helper logic for summarize_logs."""
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


async def admin_facts_count_handler(message: Message):
    """Handle asynchronous bot workflow for admin_facts_count_handler."""
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


async def admin_import_facts_handler(message: Message):
    """Handle asynchronous bot workflow for admin_import_facts_handler."""
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


async def admin_daily_fact_preview_handler(message: Message):
    """Handle asynchronous bot workflow for admin_daily_fact_preview_handler."""
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

        archive_card = get_random_archive_card_for_daily_rubric(db)

        await message.answer(
            format_daily_world_cup_rubric(fact, archive_card=archive_card)
        )

    finally:
        db.close()


async def admin_import_quiz_handler(message: Message):
    """Handle asynchronous bot workflow for admin_import_quiz_handler."""
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


async def admin_quiz_stats_handler(message: Message):
    """Handle asynchronous bot workflow for admin_quiz_stats_handler."""
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


async def admin_import_archive_handler(message: Message):
    """Handle asynchronous bot workflow for admin_import_archive_handler."""
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


async def admin_archive_count_handler(message: Message):
    """Handle asynchronous bot workflow for admin_archive_count_handler."""
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


async def admin_send_daily_fact_group_handler(message: Message):
    """Handle asynchronous bot workflow for admin_send_daily_fact_group_handler."""
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

