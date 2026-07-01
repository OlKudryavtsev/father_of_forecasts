"""Core engine for league-scoped synchronous quizzes.

Version 3.0.1 intentionally implements the reliable common layer first:
question bank, registration, server-side timer, multiple-choice answers and a
separate quiz leaderboard. Text-answer mechanics are modelled in the schema but
will be enabled by later question-type handlers.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    LeagueQuizAdminAction,
    LeagueQuizEvent,
    LeagueQuizQuestion,
    LeagueQuizQuestionOption,
    LeagueQuizQuestionSource,
    LeagueQuizScoreEvent,
    LeagueQuizSession,
    LeagueQuizSessionAnswer,
    LeagueQuizSessionParticipant,
    LeagueQuizSessionQuestion,
    LeagueQuizSessionRound,
    User,
)
from app.services.leagues import require_manage_league, require_user_league


QUESTION_TYPES_STAGE_ONE = {"choice_2", "choice_4"}
QUESTION_STATUS_DRAFT = "draft"
QUESTION_STATUS_APPROVED = "approved"
QUESTION_STATUS_ARCHIVED = "archived"

SESSION_REGISTRATION_OPEN = "registration_open"
SESSION_RUNNING = "running"
SESSION_PAUSED = "paused"
SESSION_FINISHED = "finished"
SESSION_CANCELLED = "cancelled"

QUESTION_PENDING = "pending"
QUESTION_OPEN = "open"
QUESTION_REVEALED = "revealed"
QUESTION_CLOSED = "closed"


# A compact, idempotent starter pack for the first usable quiz formats. These
# facts are verified against FIFA match reports current on 2026-07-01. The
# records are intentionally created only after an administrator presses the
# explicit seed action for a particular league.
WC2026_STAGE_ONE_SEED_PREFIX = "seed:wc2026-stage-one:3.0.2"
WC2026_STAGE_ONE_SAMPLE_QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "seed_key": "four-options-france-sweden",
        "question_type": "choice_4",
        "question_text": "ЧМ‑2026, 1/16 финала: кто оформил дубль в матче Франция — Швеция (3:0)?",
        "options": ("Килиан Мбаппе", "Брэдли Баркола", "Усман Дембеле", "Антуан Гризманн"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Килиан Мбаппе забил на 45-й и 74-й минутах. Ещё один мяч Франции забил Брэдли Баркола.",
        "source_title": "FIFA: France 3-0 Sweden | Match report and highlights",
        "source_url": "https://www.fifa.com/en/articles/france-sweden-review-highlights",
    },
    {
        "seed_key": "true-false-brazil-japan",
        "question_type": "choice_2",
        "question_text": "Правда или ложь: Бразилия обыграла Японию 2:1 в 1/16 финала ЧМ‑2026.",
        "options": ("Правда", "Ложь"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Правда. Бразилия победила 2:1; решающий гол в концовке забил Габриэл Мартинелли.",
        "source_title": "FIFA: Brazil 2-1 Japan | Match report and highlights",
        "source_url": "https://www.fifa.com/en/articles/brazil-japan-review-highlights",
    },
    {
        "seed_key": "more-less-england-congo",
        "question_type": "choice_2",
        "question_text": "Больше или меньше: в матче Англия — ДР Конго (2:1) Харри Кейн забил больше голов, чем Брайан Чипенга.",
        "options": ("Больше", "Меньше"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Больше. Чипенга забил один мяч за ДР Конго, а Кейн ответил дублем на 75-й и 86-й минутах.",
        "source_title": "FIFA: England 2-1 Congo DR | Match report and highlights",
        "source_url": "https://www.fifa.com/en/articles/england-congo-dr-review-highlights",
    },
    {
        "seed_key": "yes-no-morocco-netherlands",
        "question_type": "choice_2",
        "question_text": "Да или нет: Марокко вышло в 1/8 финала ЧМ‑2026, обыграв Нидерланды в серии пенальти.",
        "options": ("Да", "Нет"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Да. Основное время завершилось со счётом 1:1, а в серии пенальти Марокко победило 3:2.",
        "source_title": "FIFA: Netherlands 1-1 Morocco (PSO 2-3)",
        "source_url": "https://www.fifa.com/en/articles/netherlands-morocco-review-highlights",
    },
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_manager(db: Session, user: User, league_id: int) -> bool:
    try:
        require_manage_league(db, user, league_id)
        return True
    except (ValueError, PermissionError):
        return False


def require_quiz_manager(db: Session, user: User, league_id: int):
    """Return an active league only when the user can run its quizzes."""
    return require_manage_league(db, user, league_id)


def _event(db: Session, quiz_session: LeagueQuizSession, event_type: str, payload: dict | None = None) -> None:
    db.add(
        LeagueQuizEvent(
            session_id=quiz_session.id,
            event_type=event_type,
            payload=payload or {},
        )
    )


def _admin_action(
    db: Session,
    quiz_session: LeagueQuizSession,
    actor: User,
    action_type: str,
    payload: dict | None = None,
) -> None:
    db.add(
        LeagueQuizAdminAction(
            session_id=quiz_session.id,
            actor_user_id=actor.id,
            action_type=action_type,
            payload=payload or {},
        )
    )


def _question_type_label(question_type: str) -> str:
    return {
        "choice_2": "Выбор из 2 вариантов",
        "choice_4": "Выбор из 4 вариантов",
    }.get(question_type, question_type)


def _validate_question_payload(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]], int]:
    question_type = str(payload.get("question_type") or "").strip()
    if question_type not in QUESTION_TYPES_STAGE_ONE:
        raise ValueError("В этапе 1 доступны только вопросы с 2 или 4 вариантами")

    text = str(payload.get("question_text") or "").strip()
    if len(text) < 3:
        raise ValueError("Текст вопроса слишком короткий")
    if len(text) > 6000:
        raise ValueError("Текст вопроса слишком длинный")

    options = payload.get("options") or []
    expected = 2 if question_type == "choice_2" else 4
    if not isinstance(options, list) or len(options) != expected:
        raise ValueError(f"Для этого вопроса нужно ровно {expected} варианта ответа")

    clean_options: list[dict[str, Any]] = []
    for index, raw in enumerate(options):
        option_text = str(raw.get("text") if isinstance(raw, dict) else raw or "").strip()
        if not option_text:
            raise ValueError(f"Не заполнен вариант ответа {index + 1}")
        if len(option_text) > 1000:
            raise ValueError(f"Вариант ответа {index + 1} слишком длинный")
        clean_options.append({"option_key": chr(65 + index), "text": option_text})

    correct_index = payload.get("correct_option_index")
    if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= expected:
        raise ValueError("Укажите правильный вариант ответа")

    return question_type, clean_options, correct_index


def seed_wc2026_stage_one_questions(
    db: Session,
    actor: User,
    league_id: int,
) -> dict[str, Any]:
    """Add one approved WC-2026 test question for every implemented choice format.

    The operation is idempotent per league: pressing the button again does not
    duplicate questions. It intentionally does not start a quiz or notify users.
    """
    require_quiz_manager(db, actor, league_id)

    existing_rows = (
        db.query(LeagueQuizQuestion)
        .filter(
            LeagueQuizQuestion.league_id == league_id,
            LeagueQuizQuestion.tags.like(f"{WC2026_STAGE_ONE_SEED_PREFIX}:%"),
        )
        .all()
    )
    existing_keys = {
        str(question.tags).rsplit(":", 1)[-1]
        for question in existing_rows
        if question.tags
    }

    created: list[LeagueQuizQuestion] = []
    now = utcnow()
    for item in WC2026_STAGE_ONE_SAMPLE_QUESTIONS:
        seed_key = item["seed_key"]
        if seed_key in existing_keys:
            continue

        question = LeagueQuizQuestion(
            league_id=league_id,
            created_by_user_id=actor.id,
            approved_by_user_id=actor.id,
            question_type=item["question_type"],
            status=QUESTION_STATUS_APPROVED,
            question_text=item["question_text"],
            explanation=item["explanation"],
            default_points=int(item["points"]),
            tags=f"{WC2026_STAGE_ONE_SEED_PREFIX}:{seed_key}",
            approved_at=now,
        )
        db.add(question)
        db.flush()

        for index, option_text in enumerate(item["options"], start=1):
            db.add(
                LeagueQuizQuestionOption(
                    question_id=question.id,
                    option_key=chr(64 + index),
                    option_text=option_text,
                    position=index,
                    is_correct=(index - 1) == int(item["correct_index"]),
                )
            )

        db.add(
            LeagueQuizQuestionSource(
                question_id=question.id,
                source_title=item["source_title"],
                source_url=item["source_url"],
                source_note="Проверено для тестового набора v3.0.2 1 июля 2026 года.",
            )
        )
        created.append(question)

    db.commit()
    for question in created:
        db.refresh(question)

    return {
        "created": created,
        "created_count": len(created),
        "existing_count": len(WC2026_STAGE_ONE_SAMPLE_QUESTIONS) - len(created),
    }


def create_bank_question(db: Session, actor: User, league_id: int, payload: dict[str, Any]) -> LeagueQuizQuestion:
    """Create a draft question in a league-scoped question bank."""
    require_quiz_manager(db, actor, league_id)
    question_type, options, correct_index = _validate_question_payload(payload)

    points = int(payload.get("default_points") or 100)
    if points < 0 or points > 10000:
        raise ValueError("Количество баллов должно быть от 0 до 10 000")

    question = LeagueQuizQuestion(
        league_id=league_id,
        created_by_user_id=actor.id,
        question_type=question_type,
        status=QUESTION_STATUS_DRAFT,
        question_text=str(payload.get("question_text") or "").strip(),
        explanation=(str(payload.get("explanation") or "").strip() or None),
        default_points=points,
        tags=(str(payload.get("tags") or "").strip() or None),
    )
    db.add(question)
    db.flush()

    for index, option in enumerate(options):
        db.add(
            LeagueQuizQuestionOption(
                question_id=question.id,
                option_key=option["option_key"],
                option_text=option["text"],
                position=index + 1,
                is_correct=index == correct_index,
            )
        )

    source_url = str(payload.get("source_url") or "").strip()
    source_title = str(payload.get("source_title") or "").strip()
    if source_url or source_title:
        db.add(
            LeagueQuizQuestionSource(
                question_id=question.id,
                source_title=source_title or None,
                source_url=source_url or None,
                source_note=(str(payload.get("source_note") or "").strip() or None),
            )
        )

    db.commit()
    db.refresh(question)
    return question


def approve_bank_question(db: Session, actor: User, league_id: int, question_id: int) -> LeagueQuizQuestion:
    require_quiz_manager(db, actor, league_id)
    question = (
        db.query(LeagueQuizQuestion)
        .filter(LeagueQuizQuestion.id == question_id, LeagueQuizQuestion.league_id == league_id)
        .first()
    )
    if not question:
        raise ValueError("Вопрос не найден")
    if question.status == QUESTION_STATUS_ARCHIVED:
        raise ValueError("Архивный вопрос нельзя одобрить")
    question.status = QUESTION_STATUS_APPROVED
    question.approved_at = utcnow()
    question.approved_by_user_id = actor.id
    db.commit()
    db.refresh(question)
    return question


def list_bank_questions(db: Session, actor: User, league_id: int, include_archived: bool = False) -> list[LeagueQuizQuestion]:
    require_quiz_manager(db, actor, league_id)
    query = db.query(LeagueQuizQuestion).filter(LeagueQuizQuestion.league_id == league_id)
    if not include_archived:
        query = query.filter(LeagueQuizQuestion.status != QUESTION_STATUS_ARCHIVED)
    return query.order_by(LeagueQuizQuestion.updated_at.desc(), LeagueQuizQuestion.id.desc()).all()


def _options_snapshot(question: LeagueQuizQuestion) -> list[dict[str, Any]]:
    options = sorted(question.options, key=lambda item: (item.position, item.id))
    return [
        {
            "key": option.option_key,
            "text": option.option_text,
            "is_correct": bool(option.is_correct),
        }
        for option in options
    ]


def create_quiz_session(db: Session, actor: User, payload: dict[str, Any]) -> LeagueQuizSession:
    """Create a scheduled one-round Stage 1 quiz from approved bank questions."""
    league_id = int(payload.get("league_id") or 0)
    require_quiz_manager(db, actor, league_id)

    title = str(payload.get("title") or "").strip()
    if len(title) < 2 or len(title) > 160:
        raise ValueError("Название квиза должно содержать от 2 до 160 символов")

    question_ids = payload.get("question_ids") or []
    if not isinstance(question_ids, list) or not question_ids:
        raise ValueError("Выберите хотя бы один одобренный вопрос")
    if len(question_ids) > 60:
        raise ValueError("В одном квизе этапа 1 может быть не более 60 вопросов")
    normalized_ids = [int(value) for value in question_ids]
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("Один вопрос нельзя добавить в квиз дважды")

    questions = (
        db.query(LeagueQuizQuestion)
        .filter(
            LeagueQuizQuestion.id.in_(normalized_ids),
            LeagueQuizQuestion.league_id == league_id,
            LeagueQuizQuestion.status == QUESTION_STATUS_APPROVED,
        )
        .all()
    )
    if len(questions) != len(normalized_ids):
        raise ValueError("Можно использовать только одобренные вопросы текущей лиги")
    by_id = {question.id: question for question in questions}

    seconds_per_question = int(payload.get("seconds_per_question") or 30)
    reveal_seconds = int(payload.get("reveal_seconds") or 12)
    if not 10 <= seconds_per_question <= 300:
        raise ValueError("Время на вопрос должно быть от 10 до 300 секунд")
    if not 3 <= reveal_seconds <= 90:
        raise ValueError("Время показа ответа должно быть от 3 до 90 секунд")

    scheduled_start_at = ensure_utc(payload.get("scheduled_start_at"))
    if scheduled_start_at and scheduled_start_at < utcnow() - timedelta(minutes=1):
        raise ValueError("Нельзя планировать квиз в прошлом")

    quiz_session = LeagueQuizSession(
        league_id=league_id,
        created_by_user_id=actor.id,
        title=title,
        description=(str(payload.get("description") or "").strip() or None),
        status=SESSION_REGISTRATION_OPEN,
        scheduled_start_at=scheduled_start_at,
        registration_opened_at=utcnow(),
        seconds_per_question=seconds_per_question,
        reveal_seconds=reveal_seconds,
        allow_late_registration=bool(payload.get("allow_late_registration", False)),
        rounds_total=1,
    )
    db.add(quiz_session)
    db.flush()

    round_row = LeagueQuizSessionRound(
        session_id=quiz_session.id,
        round_order=1,
        round_type="choice",
        title=(str(payload.get("round_title") or "").strip() or "Раунд с вариантами"),
        status="pending",
        points_mode="positive",
    )
    db.add(round_row)
    db.flush()

    for order, question_id in enumerate(normalized_ids, start=1):
        question = by_id[question_id]
        db.add(
            LeagueQuizSessionQuestion(
                round_id=round_row.id,
                bank_question_id=question.id,
                question_order=order,
                question_type=question.question_type,
                question_text_snapshot=question.question_text,
                explanation_snapshot=question.explanation,
                options_snapshot=_options_snapshot(question),
                points=int(question.default_points or 0),
                negative_on_wrong=False,
                status=QUESTION_PENDING,
            )
        )
        question.last_used_at = utcnow()
        question.times_used = int(question.times_used or 0) + 1

    _event(db, quiz_session, "quiz_created", {"questions_total": len(normalized_ids)})
    _admin_action(db, quiz_session, actor, "quiz_created", {"questions_total": len(normalized_ids)})
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _get_session(db: Session, session_id: int) -> LeagueQuizSession:
    quiz_session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == session_id).first()
    if not quiz_session:
        raise ValueError("Квиз не найден")
    return quiz_session


def _registered_participants(db: Session, session_id: int) -> list[LeagueQuizSessionParticipant]:
    return (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == session_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(LeagueQuizSessionParticipant.joined_at.asc(), LeagueQuizSessionParticipant.id.asc())
        .all()
    )


def register_for_quiz(db: Session, actor: User, session_id: int) -> LeagueQuizSessionParticipant:
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)

    if quiz_session.status not in {SESSION_REGISTRATION_OPEN, SESSION_RUNNING}:
        raise ValueError("Регистрация на этот квиз уже закрыта")
    if quiz_session.status == SESSION_RUNNING and not quiz_session.allow_late_registration:
        raise ValueError("Квиз уже начался: позднее подключение отключено")

    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
        )
        .first()
    )
    if participant:
        participant.status = "registered"
    else:
        participant = LeagueQuizSessionParticipant(
            session_id=quiz_session.id,
            user_id=actor.id,
            status="registered",
            joined_at=utcnow(),
            score_total=0,
        )
        db.add(participant)
    _event(db, quiz_session, "participant_registered", {"user_id": actor.id})
    db.commit()
    db.refresh(participant)
    return participant


def start_quiz_session(db: Session, actor: User, session_id: int, automatic: bool = False) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    if not automatic:
        require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_REGISTRATION_OPEN:
        raise ValueError("Квиз нельзя запустить в текущем состоянии")

    now = utcnow()
    quiz_session.status = SESSION_RUNNING
    quiz_session.started_at = now
    quiz_session.current_round_order = 1
    round_row = (
        db.query(LeagueQuizSessionRound)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id, LeagueQuizSessionRound.round_order == 1)
        .first()
    )
    if not round_row:
        raise ValueError("У квиза отсутствует раунд")
    round_row.status = "running"
    round_row.started_at = now
    _event(db, quiz_session, "quiz_started", {"automatic": bool(automatic)})
    if not automatic:
        _admin_action(db, quiz_session, actor, "quiz_started")
    _open_next_question(db, quiz_session, now)
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def pause_quiz_session(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Поставить на паузу можно только идущий квиз")
    quiz_session.status = SESSION_PAUSED
    quiz_session.paused_at = utcnow()
    _event(db, quiz_session, "quiz_paused")
    _admin_action(db, quiz_session, actor, "quiz_paused")
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def resume_quiz_session(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_PAUSED:
        raise ValueError("Продолжить можно только квиз на паузе")
    now = utcnow()
    pause_delta = now - ensure_utc(quiz_session.paused_at or now)
    current = _current_session_question(db, quiz_session.id)
    if current:
        if current.status == QUESTION_OPEN and current.closes_at:
            current.closes_at = ensure_utc(current.closes_at) + pause_delta
        if current.status == QUESTION_REVEALED and current.revealed_until:
            current.revealed_until = ensure_utc(current.revealed_until) + pause_delta
    quiz_session.status = SESSION_RUNNING
    quiz_session.paused_at = None
    _event(db, quiz_session, "quiz_resumed")
    _admin_action(db, quiz_session, actor, "quiz_resumed")
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def cancel_quiz_session(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status in {SESSION_FINISHED, SESSION_CANCELLED}:
        raise ValueError("Завершенный квиз нельзя отменить")
    quiz_session.status = SESSION_CANCELLED
    quiz_session.cancelled_at = utcnow()
    _event(db, quiz_session, "quiz_cancelled")
    _admin_action(db, quiz_session, actor, "quiz_cancelled")
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _current_session_question(db: Session, session_id: int) -> LeagueQuizSessionQuestion | None:
    return (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionRound.session_id == session_id,
            LeagueQuizSessionQuestion.status.in_([QUESTION_OPEN, QUESTION_REVEALED]),
        )
        .order_by(LeagueQuizSessionQuestion.id.desc())
        .first()
    )


def _open_next_question(db: Session, quiz_session: LeagueQuizSession, now: datetime) -> LeagueQuizSessionQuestion | None:
    next_question = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionRound.session_id == quiz_session.id,
            LeagueQuizSessionQuestion.status == QUESTION_PENDING,
        )
        .order_by(LeagueQuizSessionRound.round_order.asc(), LeagueQuizSessionQuestion.question_order.asc())
        .first()
    )
    if not next_question:
        _finish_quiz(db, quiz_session, now)
        return None

    next_question.status = QUESTION_OPEN
    next_question.opened_at = now
    next_question.closes_at = now + timedelta(seconds=int(quiz_session.seconds_per_question or 30))
    quiz_session.current_question_order = next_question.question_order
    _event(
        db,
        quiz_session,
        "question_opened",
        {"session_question_id": next_question.id, "question_order": next_question.question_order},
    )
    return next_question


def _finish_quiz(db: Session, quiz_session: LeagueQuizSession, now: datetime) -> None:
    if quiz_session.status == SESSION_FINISHED:
        return
    for round_row in db.query(LeagueQuizSessionRound).filter(LeagueQuizSessionRound.session_id == quiz_session.id).all():
        if round_row.status != "finished":
            round_row.status = "finished"
            round_row.finished_at = now
    quiz_session.status = SESSION_FINISHED
    quiz_session.finished_at = now
    _event(db, quiz_session, "quiz_finished")


def _score_question(db: Session, quiz_session: LeagueQuizSession, session_question: LeagueQuizSessionQuestion, now: datetime) -> None:
    # Text formats are accepted by the Telegram transport in Stage 2, but their
    # semantic checking belongs to their dedicated round handlers. Do not mark
    # them wrong merely because there is no selected option key.
    if session_question.question_type not in QUESTION_TYPES_STAGE_ONE:
        for answer in (
            db.query(LeagueQuizSessionAnswer)
            .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id)
            .all()
        ):
            answer.is_correct = None
            answer.points_awarded = 0
            answer.scored_at = now
        return

    correct_keys = {
        str(item.get("key"))
        for item in (session_question.options_snapshot or [])
        if bool(item.get("is_correct"))
    }
    answers = (
        db.query(LeagueQuizSessionAnswer)
        .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id)
        .all()
    )
    for answer in answers:
        is_correct = str(answer.selected_option_key or "") in correct_keys
        points = int(session_question.points or 0) if is_correct else (-int(session_question.points or 0) if session_question.negative_on_wrong else 0)
        answer.is_correct = is_correct
        answer.points_awarded = points
        answer.scored_at = now

        participant = (
            db.query(LeagueQuizSessionParticipant)
            .filter(
                LeagueQuizSessionParticipant.session_id == quiz_session.id,
                LeagueQuizSessionParticipant.user_id == answer.user_id,
            )
            .first()
        )
        if participant:
            participant.score_total = int(participant.score_total or 0) + points
        db.add(
            LeagueQuizScoreEvent(
                session_id=quiz_session.id,
                round_id=session_question.round_id,
                session_question_id=session_question.id,
                user_id=answer.user_id,
                event_type="correct" if is_correct else "incorrect",
                delta_points=points,
                reason="Автоматическая проверка ответа",
                created_at=now,
            )
        )


def close_current_question(
    db: Session,
    quiz_session: LeagueQuizSession,
    now: datetime | None = None,
    actor: User | None = None,
    manual: bool = False,
) -> LeagueQuizSessionQuestion | None:
    now = ensure_utc(now) or utcnow()
    session_question = _current_session_question(db, quiz_session.id)
    if not session_question or session_question.status != QUESTION_OPEN:
        return session_question

    _score_question(db, quiz_session, session_question, now)
    session_question.status = QUESTION_REVEALED
    session_question.closed_at = now
    session_question.revealed_at = now
    session_question.revealed_until = now + timedelta(seconds=int(quiz_session.reveal_seconds or 12))
    _event(
        db,
        quiz_session,
        "question_revealed",
        {"session_question_id": session_question.id, "manual": bool(manual)},
    )
    if actor and manual:
        _admin_action(db, quiz_session, actor, "question_closed_manually", {"session_question_id": session_question.id})
    return session_question


def _all_registered_answered(db: Session, quiz_session: LeagueQuizSession, session_question: LeagueQuizSessionQuestion) -> bool:
    participants = _registered_participants(db, quiz_session.id)
    if not participants:
        return False
    participant_ids = {participant.user_id for participant in participants}
    answered_ids = {
        row.user_id
        for row in db.query(LeagueQuizSessionAnswer.user_id)
        .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id)
        .all()
    }
    return participant_ids.issubset(answered_ids)


def advance_quiz_state(db: Session, quiz_session: LeagueQuizSession, now: datetime | None = None, commit: bool = True) -> LeagueQuizSession:
    """Advance one quiz according to server time; safe to call frequently."""
    now = ensure_utc(now) or utcnow()
    if quiz_session.status == SESSION_REGISTRATION_OPEN:
        starts_at = ensure_utc(quiz_session.scheduled_start_at)
        if starts_at and starts_at <= now:
            # Automatic start does not require a user object and is intentionally
            # allowed even with zero registrations: late registration policy and
            # a visible empty game are preferable to a silently lost schedule.
            quiz_session.status = SESSION_RUNNING
            quiz_session.started_at = now
            quiz_session.current_round_order = 1
            round_row = (
                db.query(LeagueQuizSessionRound)
                .filter(LeagueQuizSessionRound.session_id == quiz_session.id, LeagueQuizSessionRound.round_order == 1)
                .first()
            )
            if round_row:
                round_row.status = "running"
                round_row.started_at = now
            _event(db, quiz_session, "quiz_started", {"automatic": True})
            _open_next_question(db, quiz_session, now)

    if quiz_session.status == SESSION_RUNNING:
        current = _current_session_question(db, quiz_session.id)
        if current and current.status == QUESTION_OPEN:
            closes_at = ensure_utc(current.closes_at)
            if (closes_at and closes_at <= now) or _all_registered_answered(db, quiz_session, current):
                close_current_question(db, quiz_session, now=now)
        elif current and current.status == QUESTION_REVEALED:
            reveal_until = ensure_utc(current.revealed_until)
            if reveal_until and reveal_until <= now:
                current.status = QUESTION_CLOSED
                _open_next_question(db, quiz_session, now)
        elif current is None:
            _open_next_question(db, quiz_session, now)

    if commit:
        db.commit()
        db.refresh(quiz_session)
    return quiz_session


def advance_due_quizzes(db: Session) -> int:
    """Run scheduler tick for all active quiz sessions.

    Railway production currently runs a single web process. Row locks still make
    concurrent calls from a future worker deployment harmless at the session
    level when PostgreSQL is used.
    """
    sessions = (
        db.query(LeagueQuizSession)
        .filter(LeagueQuizSession.status.in_([SESSION_REGISTRATION_OPEN, SESSION_RUNNING]))
        .with_for_update(skip_locked=True)
        .all()
    )
    for quiz_session in sessions:
        advance_quiz_state(db, quiz_session, commit=False)
    if sessions:
        db.commit()
    return len(sessions)


def submit_choice_answer(
    db: Session,
    actor: User,
    session_id: int,
    session_question_id: int,
    selected_option_key: str,
) -> LeagueQuizSessionAnswer:
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не принимает ответы")

    session_question = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionQuestion.id == session_question_id,
            LeagueQuizSessionRound.session_id == quiz_session.id,
        )
        .first()
    )
    if not session_question or session_question.status != QUESTION_OPEN:
        raise ValueError("Этот вопрос уже закрыт")
    if session_question.question_type not in QUESTION_TYPES_STAGE_ONE:
        raise ValueError("Для этого вопроса нужно ввести текстовый ответ")
    if ensure_utc(session_question.closes_at) and ensure_utc(session_question.closes_at) < utcnow():
        advance_quiz_state(db, quiz_session)
        raise ValueError("Время ответа истекло")

    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .first()
    )
    if not participant:
        raise ValueError("Сначала зарегистрируйтесь для участия в квизе")

    selected_key = str(selected_option_key or "").upper().strip()
    available_keys = {str(item.get("key")) for item in (session_question.options_snapshot or [])}
    if selected_key not in available_keys:
        raise ValueError("Выберите один из предложенных вариантов")

    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == actor.id,
        )
        .first()
    )
    if answer:
        answer.selected_option_key = selected_key
        answer.updated_at = utcnow()
    else:
        answer = LeagueQuizSessionAnswer(
            session_question_id=session_question.id,
            user_id=actor.id,
            selected_option_key=selected_key,
            answered_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(answer)
    db.flush()

    if _all_registered_answered(db, quiz_session, session_question):
        close_current_question(db, quiz_session, now=utcnow())
    db.commit()
    db.refresh(answer)
    return answer


def submit_text_answer(
    db: Session,
    actor: User,
    session_id: int,
    session_question_id: int,
    answer_text: str,
) -> LeagueQuizSessionAnswer:
    """Store a Telegram text answer for future text-based round handlers.

    Stage 2 only transports the answer reliably.  Dedicated round handlers will
    later decide whether it is correct and how many points it earns.
    """
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не принимает ответы")

    session_question = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionQuestion.id == session_question_id,
            LeagueQuizSessionRound.session_id == quiz_session.id,
        )
        .first()
    )
    if not session_question or session_question.status != QUESTION_OPEN:
        raise ValueError("Этот вопрос уже закрыт")
    if session_question.question_type in QUESTION_TYPES_STAGE_ONE:
        raise ValueError("Для этого вопроса выберите вариант кнопкой")
    if ensure_utc(session_question.closes_at) and ensure_utc(session_question.closes_at) < utcnow():
        advance_quiz_state(db, quiz_session)
        raise ValueError("Время ответа истекло")

    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .first()
    )
    if not participant:
        raise ValueError("Сначала зарегистрируйтесь для участия в квизе")

    cleaned = " ".join(str(answer_text or "").strip().split())
    if not cleaned:
        raise ValueError("Введите ответ текстом")
    if len(cleaned) > 1000:
        raise ValueError("Ответ слишком длинный: максимум 1000 символов")

    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == actor.id,
        )
        .first()
    )
    if answer:
        answer.answer_text = cleaned
        answer.updated_at = utcnow()
    else:
        answer = LeagueQuizSessionAnswer(
            session_question_id=session_question.id,
            user_id=actor.id,
            answer_text=cleaned,
            answered_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(answer)
    db.flush()

    if _all_registered_answered(db, quiz_session, session_question):
        close_current_question(db, quiz_session, now=utcnow())
    db.commit()
    db.refresh(answer)
    return answer


def manually_close_current_question(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не идет")
    close_current_question(db, quiz_session, actor=actor, manual=True)
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _stable_options_for_user(options: list[dict[str, Any]], session_question_id: int, user_id: int) -> list[dict[str, Any]]:
    """Return a stable per-user option order so an answer never jumps on refresh."""
    public = [{"key": item.get("key"), "text": item.get("text")} for item in options]
    seed = hashlib.sha256(f"{session_question_id}:{user_id}".encode("utf-8")).hexdigest()
    random.Random(seed).shuffle(public)
    return public


def get_choice_question_options_for_user(
    session_question: LeagueQuizSessionQuestion,
    user_id: int,
) -> list[dict[str, Any]]:
    """Expose the same stable option order to Telegram and PWA clients."""
    return _stable_options_for_user(session_question.options_snapshot or [], session_question.id, user_id)


def _serialize_session_question(
    db: Session,
    session_question: LeagueQuizSessionQuestion | None,
    user_id: int,
    now: datetime,
) -> dict | None:
    if not session_question:
        return None
    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == user_id,
        )
        .first()
    )
    revealed = session_question.status in {QUESTION_REVEALED, QUESTION_CLOSED}
    raw_options = session_question.options_snapshot or []
    options = _stable_options_for_user(raw_options, session_question.id, user_id)
    if revealed:
        correct_keys = {str(item.get("key")) for item in raw_options if item.get("is_correct")}
        for option in options:
            option["is_correct"] = option["key"] in correct_keys

    deadline = ensure_utc(session_question.closes_at if session_question.status == QUESTION_OPEN else session_question.revealed_until)
    seconds_remaining = max(0, int((deadline - now).total_seconds())) if deadline else 0
    return {
        "id": session_question.id,
        "order": session_question.question_order,
        "type": session_question.question_type,
        "type_label": _question_type_label(session_question.question_type),
        "text": session_question.question_text_snapshot,
        "points": int(session_question.points or 0),
        "status": session_question.status,
        "options": options,
        "answer": {
            "selected_option_key": answer.selected_option_key if answer else None,
            "is_correct": answer.is_correct if revealed and answer else None,
            "points_awarded": answer.points_awarded if revealed and answer else None,
        },
        "explanation": session_question.explanation_snapshot if revealed else None,
        "seconds_remaining": seconds_remaining,
        "deadline_at": deadline.isoformat() if deadline else None,
    }


def build_quiz_scoreboard(db: Session, session_id: int) -> list[dict[str, Any]]:
    participants = (
        db.query(LeagueQuizSessionParticipant, User)
        .join(User, User.id == LeagueQuizSessionParticipant.user_id)
        .filter(
            LeagueQuizSessionParticipant.session_id == session_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(LeagueQuizSessionParticipant.score_total.desc(), User.display_name.asc(), LeagueQuizSessionParticipant.id.asc())
        .all()
    )
    rows: list[dict[str, Any]] = []
    for index, (participant, user) in enumerate(participants, start=1):
        rows.append(
            {
                "place": index,
                "user_id": user.id,
                "display_name": user.display_name,
                "score_total": int(participant.score_total or 0),
            }
        )
    return rows


def serialize_quiz_summary(db: Session, quiz_session: LeagueQuizSession, user: User) -> dict[str, Any]:
    current = _current_session_question(db, quiz_session.id)
    registered = _registered_participants(db, quiz_session.id)
    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == user.id,
        )
        .first()
    )
    total_questions = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id)
        .count()
    )
    return {
        "id": quiz_session.id,
        "league_id": quiz_session.league_id,
        "title": quiz_session.title,
        "description": quiz_session.description,
        "status": quiz_session.status,
        "scheduled_start_at": ensure_utc(quiz_session.scheduled_start_at).isoformat() if quiz_session.scheduled_start_at else None,
        "started_at": ensure_utc(quiz_session.started_at).isoformat() if quiz_session.started_at else None,
        "finished_at": ensure_utc(quiz_session.finished_at).isoformat() if quiz_session.finished_at else None,
        "seconds_per_question": int(quiz_session.seconds_per_question or 0),
        "reveal_seconds": int(quiz_session.reveal_seconds or 0),
        "registered_count": len(registered),
        "questions_total": total_questions,
        "current_question_order": current.question_order if current else int(quiz_session.current_question_order or 0),
        "is_registered": bool(participant and participant.status == "registered"),
        "my_user_id": user.id,
        "my_score": int(participant.score_total or 0) if participant else 0,
        "can_manage": _is_manager(db, user, quiz_session.league_id),
    }


def build_quiz_detail(db: Session, actor: User, session_id: int) -> dict[str, Any]:
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session)
    current = _current_session_question(db, quiz_session.id)
    summary = serialize_quiz_summary(db, quiz_session, actor)
    return {
        "quiz": summary,
        "current_question": _serialize_session_question(db, current, actor.id, utcnow()),
        "scoreboard": build_quiz_scoreboard(db, quiz_session.id),
        "server_time": utcnow().isoformat(),
    }


def list_quizzes_for_league(db: Session, actor: User, league_id: int) -> list[dict[str, Any]]:
    require_user_league(db, actor, league_id)
    sessions = (
        db.query(LeagueQuizSession)
        .filter(LeagueQuizSession.league_id == league_id)
        .order_by(
            LeagueQuizSession.status.in_([SESSION_RUNNING, SESSION_PAUSED]).desc(),
            LeagueQuizSession.scheduled_start_at.desc().nullslast(),
            LeagueQuizSession.id.desc(),
        )
        .limit(30)
        .all()
    )
    for quiz_session in sessions:
        advance_quiz_state(db, quiz_session, commit=False)
    if sessions:
        db.commit()
    return [serialize_quiz_summary(db, quiz_session, actor) for quiz_session in sessions]


def serialize_bank_question(question: LeagueQuizQuestion, include_correct: bool = True) -> dict[str, Any]:
    options = sorted(question.options, key=lambda item: (item.position, item.id))
    return {
        "id": question.id,
        "question_type": question.question_type,
        "type_label": _question_type_label(question.question_type),
        "status": question.status,
        "question_text": question.question_text,
        "explanation": question.explanation,
        "default_points": int(question.default_points or 0),
        "tags": question.tags,
        "times_used": int(question.times_used or 0),
        "last_used_at": ensure_utc(question.last_used_at).isoformat() if question.last_used_at else None,
        "created_at": ensure_utc(question.created_at).isoformat() if question.created_at else None,
        "options": [
            {
                "key": option.option_key,
                "text": option.option_text,
                "is_correct": bool(option.is_correct) if include_correct else None,
            }
            for option in options
        ],
        "sources": [
            {"title": source.source_title, "url": source.source_url, "note": source.source_note}
            for source in sorted(question.sources, key=lambda item: item.id)
        ],
    }
