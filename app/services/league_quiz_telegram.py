"""Durable Telegram delivery for league quizzes.

Every quiz transition becomes a ``LeagueQuizEvent``. This adapter claims each
recipient in PostgreSQL *before* sending the Telegram message. That makes the
workflow safe even when Railway temporarily starts two workers during deploys.
Question events carry their own immutable display snapshot, so delayed delivery
never reads a later question/stage from the live database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.handlers.miniapp import get_bot_username, get_miniapp_url
from app.keyboards.league_quiz import (
    build_group_quiz_open_keyboard,
    build_private_quiz_open_keyboard,
    build_private_quiz_question_keyboard,
    build_private_quiz_registration_keyboard,
    build_private_quiz_text_keyboard,
)
from app.models import (
    League,
    LeagueMember,
    LeagueQuizEvent,
    LeagueQuizSession,
    LeagueQuizSessionAnswer,
    LeagueQuizSessionParticipant,
    LeagueQuizSessionQuestion,
    LeagueQuizTelegramDelivery,
    User,
)
from app.runtime import APP_TIMEZONE, bot
from app.services.league_quiz import (
    QUESTION_OPEN,
    build_quiz_scoreboard,
    ensure_utc,
    get_choice_question_options_for_user,
    get_correct_answer_text,
    get_question_display_text,
    is_choice_question_type,
)

DELIVERY_DONE_KEY = "event:dispatched"
SUPPORTED_EVENT_TYPES = {
    "quiz_created",
    "quiz_started",
    "round_started",
    "question_opened",
    "question_revealed",
    "countdown_stage_opened",
    "round_finished",
    "quiz_finished",
    "quiz_cancelled",
    "quiz_paused",
    "quiz_resumed",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _event_skipped(event: LeagueQuizEvent) -> bool:
    return bool((event.payload or {}).get("telegram_skip"))


def _delivery_exists(db: Session, event_id: int, destination_key: str) -> bool:
    return bool(
        db.query(LeagueQuizTelegramDelivery.id)
        .filter(
            LeagueQuizTelegramDelivery.event_id == event_id,
            LeagueQuizTelegramDelivery.destination_key == destination_key,
        )
        .first()
    )


def _claim_delivery(
    db: Session,
    event: LeagueQuizEvent,
    destination_key: str,
    message_kind: str,
    *,
    recipient_user_id: int | None = None,
    chat_id: str | None = None,
) -> int | None:
    """Create a durable claim before network I/O.

    The unique DB constraint is the lock. A second worker sees IntegrityError
    and must not send an identical message.
    """
    row = LeagueQuizTelegramDelivery(
        event_id=event.id,
        destination_key=destination_key,
        recipient_user_id=recipient_user_id,
        chat_id=chat_id,
        message_kind=message_kind,
        status="processing",
    )
    db.add(row)
    try:
        db.commit()
        return row.id
    except IntegrityError:
        db.rollback()
        return None


def _finish_delivery(db: Session, delivery_id: int, *, status: str, error_text: str | None = None) -> None:
    row = db.query(LeagueQuizTelegramDelivery).filter(LeagueQuizTelegramDelivery.id == delivery_id).first()
    if not row:
        return
    row.status = status
    row.error_text = error_text[:2000] if error_text else None
    row.delivered_at = _utcnow()
    db.commit()


async def _send_private(
    db: Session,
    event: LeagueQuizEvent,
    user: User,
    text: str,
    message_kind: str,
    reply_markup=None,
) -> None:
    delivery_id = _claim_delivery(
        db,
        event,
        f"user:{user.id}",
        message_kind,
        recipient_user_id=user.id,
        chat_id=str(user.telegram_id),
    )
    if not delivery_id:
        return
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text, reply_markup=reply_markup)
        _finish_delivery(db, delivery_id, status="sent")
    except Exception as error:
        print(f"League quiz Telegram DM failed: event={event.id} user={user.id} error={error}")
        _finish_delivery(db, delivery_id, status="failed", error_text=str(error))


async def _send_group(
    db: Session,
    event: LeagueQuizEvent,
    league: League,
    text: str,
    message_kind: str,
    reply_markup=None,
) -> None:
    chat_id = str(getattr(league, "chat_id", "") or "").strip()
    if not chat_id:
        return
    delivery_id = _claim_delivery(db, event, f"chat:{chat_id}", message_kind, chat_id=chat_id)
    if not delivery_id:
        return
    try:
        await bot.send_message(chat_id=int(chat_id), text=text, reply_markup=reply_markup)
        _finish_delivery(db, delivery_id, status="sent")
    except Exception as error:
        print(f"League quiz Telegram group delivery failed: event={event.id} chat={chat_id} error={error}")
        _finish_delivery(db, delivery_id, status="failed", error_text=str(error))


def _mark_event_done(db: Session, event: LeagueQuizEvent) -> None:
    delivery_id = _claim_delivery(db, event, DELIVERY_DONE_KEY, "event_complete")
    if delivery_id:
        _finish_delivery(db, delivery_id, status="sent")


def _active_league_users(db: Session, league_id: int) -> list[User]:
    return (
        db.query(User)
        .join(LeagueMember, LeagueMember.user_id == User.id)
        .filter(
            LeagueMember.league_id == league_id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .order_by(User.display_name.asc(), User.id.asc())
        .all()
    )


def _registered_users(db: Session, session_id: int) -> list[User]:
    return (
        db.query(User)
        .join(LeagueQuizSessionParticipant, LeagueQuizSessionParticipant.user_id == User.id)
        .filter(
            LeagueQuizSessionParticipant.session_id == session_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(User.display_name.asc(), User.id.asc())
        .all()
    )


def _session_and_league(db: Session, event: LeagueQuizEvent) -> tuple[LeagueQuizSession | None, League | None]:
    quiz_session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == event.session_id).first()
    if not quiz_session:
        return None, None
    league = db.query(League).filter(League.id == quiz_session.league_id).first()
    return quiz_session, league


def _scheduled_text(value) -> str:
    instant = ensure_utc(value)
    if not instant:
        return "Ведущий запустит игру вручную."
    return f"Старт запланирован: {instant.astimezone(APP_TIMEZONE).strftime('%d.%m в %H:%M')}."


def _scoreboard_text(db: Session, session_id: int, limit: int = 10, title: str = "🏆 Таблица квиза") -> str:
    rows = build_quiz_scoreboard(db, session_id)[:limit]
    if not rows:
        return "Пока нет зарегистрированных участников."
    lines = [title]
    for row in rows:
        lines.append(f"{row['place']}. {row['display_name']} — {row['score_total']} очк.")
    return "\n".join(lines)


def _payload_question(event: LeagueQuizEvent, question: LeagueQuizSessionQuestion | None) -> dict:
    payload = dict(event.payload or {})
    if payload.get("display_text"):
        return payload
    # Backward-compatible fallback for events created before v3.4.0.
    if question:
        payload.update(
            {
                "session_question_id": question.id,
                "question_order": question.question_order,
                "question_type": question.question_type,
                "points": int(question.points or 0),
                "display_text": get_question_display_text(question),
                "timer_seconds": 30,
            }
        )
    return payload


def _question_header(payload: dict) -> str:
    round_order = payload.get("round_order")
    round_title = str(payload.get("round_title") or "Раунд")
    question_order = payload.get("question_order") or "—"
    base = f"❓ Вопрос {question_order} раунда"
    if round_order:
        base += f" {round_order}"
    base += f" «{round_title}»"
    stage = payload.get("countdown_stage")
    if stage:
        base += f" · подсказка {stage}/3"
    return base


def _question_text(quiz: LeagueQuizSession, payload: dict) -> str:
    points = int(payload.get("points") or 0)
    seconds = int(payload.get("timer_seconds") or 30)
    stage = payload.get("countdown_stage")
    points_text = "500 / 300 / 100 очк." if payload.get("question_type") == "countdown" else f"{points} очк."
    instruction = "В «Обратном отсчёте» ответ можно отправить только один раз." if stage else "Ответ можно изменить до закрытия вопроса."
    return (
        f"🧠 {quiz.title}\n\n"
        f"{_question_header(payload)}\n"
        f"⏱ На ответ: {seconds} сек. · {points_text}\n\n"
        f"{payload.get('display_text') or 'Вопрос готовится'}\n\n"
        f"{instruction}"
    )


async def _dispatch_quiz_created(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    miniapp_url = get_miniapp_url()
    text = (
        "🧠 Новый квиз в лиге\n\n"
        f"Лига: {league.name}\n{quiz.title}\n"
        f"Вопросов: {sum(len(round_row.questions) for round_row in quiz.rounds)}\n"
        f"{_scheduled_text(quiz.scheduled_start_at)}\n\n"
        "Нажми «Участвовать», чтобы войти в состав игроков."
    )
    for user in _active_league_users(db, league.id):
        await _send_private(db, event, user, text, "quiz_announcement", build_private_quiz_registration_keyboard(quiz.id, miniapp_url))
    username = await get_bot_username()
    await _send_group(
        db,
        event,
        league,
        f"🧠 Квиз объявлен\n\n{quiz.title}\nВопросов: {sum(len(round_row.questions) for round_row in quiz.rounds)}\n{_scheduled_text(quiz.scheduled_start_at)}\n\nУчастие и ответы — в личном диалоге с ботом или в приложении.",
        "quiz_announcement",
        build_group_quiz_open_keyboard(username, quiz.id),
    )


async def _dispatch_quiz_started(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    text = f"▶️ Старт квиза «{quiz.title}»\n\nВопросы будут приходить в личный чат с ботом. Удачи!"
    miniapp_url = get_miniapp_url()
    for user in _registered_users(db, quiz.id):
        await _send_private(db, event, user, text, "quiz_started", build_private_quiz_open_keyboard(quiz.id, miniapp_url))
    username = await get_bot_username()
    await _send_group(db, event, league, text, "quiz_started", build_group_quiz_open_keyboard(username, quiz.id, "🧠 Открыть текущий квиз"))


async def _dispatch_round_started(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    payload = event.payload or {}
    order = payload.get("round_order") or "—"
    title = str(payload.get("title") or "Раунд")
    text = f"▶️ Старт раунда {order}: «{title}»"
    miniapp_url = get_miniapp_url()
    for user in _registered_users(db, quiz.id):
        await _send_private(db, event, user, text, "quiz_round_started", build_private_quiz_open_keyboard(quiz.id, miniapp_url))
    username = await get_bot_username()
    await _send_group(db, event, league, text, "quiz_round_started", build_group_quiz_open_keyboard(username, quiz.id, "🧠 Открыть квиз"))


async def _send_question_to_user(
    db: Session,
    event: LeagueQuizEvent,
    quiz: LeagueQuizSession,
    question: LeagueQuizSessionQuestion | None,
    user: User,
    message_kind: str,
) -> None:
    payload = _payload_question(event, question)
    miniapp_url = get_miniapp_url()
    interactive = bool(question and question.status == QUESTION_OPEN)
    if question and question.question_type == "countdown":
        current_stage = int((question.runtime_state or {}).get("stage") or 1)
        interactive = interactive and current_stage == int(payload.get("countdown_stage") or 1)
    existing = (
        db.query(LeagueQuizSessionAnswer)
        .filter(LeagueQuizSessionAnswer.session_question_id == question.id, LeagueQuizSessionAnswer.user_id == user.id)
        .first()
        if question
        else None
    )
    locked = bool(existing and question and question.question_type == "countdown")
    if interactive and question and is_choice_question_type(question.question_type):
        options = get_choice_question_options_for_user(question, user.id)
        keyboard = build_private_quiz_question_keyboard(quiz.id, question.id, options, existing.selected_option_key if existing else None, miniapp_url)
    elif interactive and question and not locked:
        keyboard = build_private_quiz_text_keyboard(quiz.id, question.id, miniapp_url)
    else:
        keyboard = build_private_quiz_open_keyboard(quiz.id, miniapp_url)
    suffix = "\n\nЭтот вопрос уже закрыт — откройте квиз, чтобы увидеть результат." if not interactive else ""
    await _send_private(db, event, user, _question_text(quiz, payload) + suffix, message_kind, keyboard)


async def _dispatch_question_event(
    db: Session,
    event: LeagueQuizEvent,
    quiz: LeagueQuizSession,
    league: League,
    message_kind: str,
) -> None:
    question_id = int((event.payload or {}).get("session_question_id") or 0)
    question = db.query(LeagueQuizSessionQuestion).filter(LeagueQuizSessionQuestion.id == question_id).first()
    payload = _payload_question(event, question)
    for user in _registered_users(db, quiz.id):
        await _send_question_to_user(db, event, quiz, question, user, message_kind)
    username = await get_bot_username()
    # The group receives the same question context, but no answer controls.
    await _send_group(
        db,
        event,
        league,
        _question_text(quiz, payload) + "\n\nОтветы отправляйте боту в личном чате или в приложении.",
        message_kind,
        build_group_quiz_open_keyboard(username, quiz.id, "🧠 Открыть квиз"),
    )


async def _dispatch_question_revealed(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    question_id = int((event.payload or {}).get("session_question_id") or 0)
    question = db.query(LeagueQuizSessionQuestion).filter(LeagueQuizSessionQuestion.id == question_id).first()
    if not question:
        return
    correct_text = get_correct_answer_text(question)
    explanation = f"\n\n{question.explanation_snapshot}" if question.explanation_snapshot else ""
    for user in _registered_users(db, quiz.id):
        answer = (
            db.query(LeagueQuizSessionAnswer)
            .filter(LeagueQuizSessionAnswer.session_question_id == question.id, LeagueQuizSessionAnswer.user_id == user.id)
            .first()
        )
        personal = f"Верно · +{answer.points_awarded or 0} очк." if answer and answer.is_correct else ("Пока без очков." if answer else "Ответ не получен.")
        await _send_private(
            db,
            event,
            user,
            f"✅ {_question_header(_payload_question(event, question))}\n\nПравильный ответ: {correct_text}\n{personal}{explanation}",
            "quiz_reveal",
            build_private_quiz_open_keyboard(quiz.id, get_miniapp_url()),
        )
    await _send_group(
        db,
        event,
        league,
        f"✅ {_question_header(_payload_question(event, question))}\n\nПравильный ответ: {correct_text}{explanation}",
        "quiz_reveal",
    )


async def _dispatch_round_finished(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    payload = event.payload or {}
    order = payload.get("round_order") or "—"
    title = str(payload.get("title") or "Раунд")
    text = f"📊 Раунд {order} «{title}» завершён.\n\nПромежуточная таблица:\n{_scoreboard_text(db, quiz.id, title='')}"
    miniapp_url = get_miniapp_url()
    for user in _registered_users(db, quiz.id):
        await _send_private(db, event, user, text, "quiz_round_finished", build_private_quiz_open_keyboard(quiz.id, miniapp_url))
    username = await get_bot_username()
    await _send_group(db, event, league, text, "quiz_round_finished", build_group_quiz_open_keyboard(username, quiz.id, "🧠 Открыть таблицу"))


async def _dispatch_quiz_finished(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    rows = build_quiz_scoreboard(db, quiz.id)
    winner = rows[0]["display_name"] if rows else "нет зарегистрированных участников"
    table = _scoreboard_text(db, quiz.id, title="")
    text = f"🏁 Квиз «{quiz.title}» завершён.\n\nПобедитель: {winner}.\n\nИтоговая таблица:\n{table}"
    username = await get_bot_username()
    await _send_group(db, event, league, text, "quiz_finished", build_group_quiz_open_keyboard(username, quiz.id, "🧠 Открыть результаты"))
    by_user = {row["user_id"]: row for row in rows}
    for user in _registered_users(db, quiz.id):
        row = by_user.get(user.id)
        result = f"Ваш результат: {row['place']}-е место · {row['score_total']} очк.\n\n" if row else ""
        await _send_private(db, event, user, f"🏁 {quiz.title} завершён.\n\n{result}{text}", "quiz_finished", build_private_quiz_open_keyboard(quiz.id, get_miniapp_url()))


async def _dispatch_status_change(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    labels = {
        "quiz_cancelled": "⛔ Квиз отменён",
        "quiz_paused": "⏸ Квиз поставлен на паузу",
        "quiz_resumed": "▶️ Квиз продолжен",
    }
    text = f"{labels[event.event_type]}\n\n{quiz.title}"
    for user in _registered_users(db, quiz.id):
        await _send_private(db, event, user, text, event.event_type, build_private_quiz_open_keyboard(quiz.id, get_miniapp_url()))
    await _send_group(db, event, league, text, event.event_type)


async def dispatch_league_quiz_telegram_event(db: Session, event: LeagueQuizEvent) -> None:
    if event.event_type not in SUPPORTED_EVENT_TYPES or _event_skipped(event):
        return
    if _delivery_exists(db, event.id, DELIVERY_DONE_KEY):
        return
    quiz, league = _session_and_league(db, event)
    if not quiz or not league:
        _mark_event_done(db, event)
        return
    if event.event_type == "quiz_created":
        await _dispatch_quiz_created(db, event, quiz, league)
    elif event.event_type == "quiz_started":
        await _dispatch_quiz_started(db, event, quiz, league)
    elif event.event_type == "round_started":
        await _dispatch_round_started(db, event, quiz, league)
    elif event.event_type == "question_opened":
        await _dispatch_question_event(db, event, quiz, league, "quiz_question")
    elif event.event_type == "countdown_stage_opened":
        await _dispatch_question_event(db, event, quiz, league, "quiz_countdown_stage")
    elif event.event_type == "question_revealed":
        await _dispatch_question_revealed(db, event, quiz, league)
    elif event.event_type == "round_finished":
        await _dispatch_round_finished(db, event, quiz, league)
    elif event.event_type == "quiz_finished":
        await _dispatch_quiz_finished(db, event, quiz, league)
    elif event.event_type in {"quiz_cancelled", "quiz_paused", "quiz_resumed"}:
        await _dispatch_status_change(db, event, quiz, league)
    _mark_event_done(db, event)


async def process_league_quiz_telegram_events(db: Session, limit: int = 40) -> int:
    events = (
        db.query(LeagueQuizEvent)
        .filter(LeagueQuizEvent.event_type.in_(SUPPORTED_EVENT_TYPES))
        .order_by(LeagueQuizEvent.id.asc())
        .limit(limit)
        .all()
    )
    processed = 0
    for event in events:
        if _event_skipped(event) or _delivery_exists(db, event.id, DELIVERY_DONE_KEY):
            continue
        try:
            await dispatch_league_quiz_telegram_event(db, event)
            processed += 1
        except Exception as error:
            db.rollback()
            print(f"League quiz Telegram event dispatch failed: event={event.id} error={error}")
    return processed

# v3.4.2: rehearsal sessions are private to the host and (optionally) a test
# chat. They must never fan out to the live league chat or its members.
from types import SimpleNamespace

async def _dispatch_test_quiz_created(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    host = db.query(User).filter(User.id == quiz.test_host_user_id).first()
    if not host:
        return
    payload = event.payload or {}
    text = (
        f"🧪 Тестовый прогон квиза «{quiz.title}»\n\n"
        f"Раундов: {payload.get('rounds_total') or '—'} · вопросов: {payload.get('questions_total') or '—'}.\n"
        "В тесте участвует только ведущий; рейтинг лиги и статистика вопросов не меняются."
    )
    await _send_private(
        db, event, host, text, "test_quiz_created",
        build_private_quiz_open_keyboard(quiz.id, get_miniapp_url()),
    )
    test_league = SimpleNamespace(chat_id=quiz.test_chat_id, name=f"Тест: {league.name}")
    username = await get_bot_username()
    await _send_group(
        db, event, test_league, text, "test_quiz_created",
        build_group_quiz_open_keyboard(username, quiz.id, "🧪 Открыть тест"),
    )

async def dispatch_league_quiz_telegram_event(db: Session, event: LeagueQuizEvent) -> None:  # noqa: F811
    if event.event_type not in SUPPORTED_EVENT_TYPES or _event_skipped(event):
        return
    if _delivery_exists(db, event.id, DELIVERY_DONE_KEY):
        return
    quiz, league = _session_and_league(db, event)
    if not quiz or not league:
        _mark_event_done(db, event)
        return

    delivery_league = league
    if bool(getattr(quiz, "is_test_run", False)):
        if event.event_type == "quiz_created":
            await _dispatch_test_quiz_created(db, event, quiz, league)
            _mark_event_done(db, event)
            return
        # Every following event naturally goes only to the auto-registered host.
        # Replace the real league chat with the explicit test destination.
        delivery_league = SimpleNamespace(chat_id=quiz.test_chat_id, name=f"Тест: {league.name}")

    if event.event_type == "quiz_created":
        await _dispatch_quiz_created(db, event, quiz, delivery_league)
    elif event.event_type == "quiz_started":
        await _dispatch_quiz_started(db, event, quiz, delivery_league)
    elif event.event_type == "round_started":
        await _dispatch_round_started(db, event, quiz, delivery_league)
    elif event.event_type == "question_opened":
        await _dispatch_question_event(db, event, quiz, delivery_league, "quiz_question")
    elif event.event_type == "countdown_stage_opened":
        await _dispatch_question_event(db, event, quiz, delivery_league, "quiz_countdown_stage")
    elif event.event_type == "question_revealed":
        await _dispatch_question_revealed(db, event, quiz, delivery_league)
    elif event.event_type == "round_finished":
        await _dispatch_round_finished(db, event, quiz, delivery_league)
    elif event.event_type == "quiz_finished":
        await _dispatch_quiz_finished(db, event, quiz, delivery_league)
    elif event.event_type in {"quiz_cancelled", "quiz_paused", "quiz_resumed"}:
        await _dispatch_status_change(db, event, quiz, delivery_league)
    _mark_event_done(db, event)
