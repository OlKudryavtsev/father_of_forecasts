"""Game layer for league quizzes (v3.5.0).

This module never changes quiz scoring.  It consumes the already scored answers
and standings to create result cards, records, streaks and achievement facts.
Text recaps may use OpenAI only as a wording layer; every number and award is
calculated here first and a deterministic Russian fallback is always available.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    League,
    LeagueQuizAchievement,
    LeagueQuizRecap,
    LeagueQuizRoundResult,
    LeagueQuizScoreEvent,
    LeagueQuizSession,
    LeagueQuizSessionAnswer,
    LeagueQuizSessionParticipant,
    LeagueQuizSessionQuestion,
    LeagueQuizSessionRound,
    User,
)

QUIZ_ACHIEVEMENTS: dict[str, dict[str, str]] = {
    "first_quiz": {
        "title": "Первый квиз",
        "description": "Завершить первый квиз в лиге",
        "icon": "🎮",
    },
    "streak_5": {
        "title": "5 правильных подряд",
        "description": "Собрать серию из пяти верных ответов",
        "icon": "🔥",
    },
    "chgk_master": {
        "title": "Мастер ЧГК",
        "description": "Верно ответить на три вопроса «Что? Где? Когда?»",
        "icon": "🦉",
    },
    "hundred_king": {
        "title": "Король Сто к одному",
        "description": "Найти ответ №1 в раунде «Сто к одному»",
        "icon": "👑",
    },
    "comeback_day": {
        "title": "Камбэк дня",
        "description": "Подняться хотя бы на одну позицию по ходу квиза",
        "icon": "📈",
    },
}

TYPE_LABELS = {
    "choice_4": "Кто хочет стать миллионером?",
    "choice_2": "Выбор из двух",
    "true_false": "Правда или ложь",
    "more_less": "Больше или меньше",
    "yes_no": "Да или нет",
    "jeopardy": "Своя игра",
    "one_of_two": "Один из двух",
    "what_where_when": "Что? Где? Когда?",
    "countdown": "Обратный отсчёт",
    "hundred_to_one": "Сто к одному",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_live_quiz(quiz_session: LeagueQuizSession) -> bool:
    return not bool(getattr(quiz_session, "is_test_run", False))


def _round_score_rows(db: Session, session_id: int, round_id: int) -> dict[int, int]:
    totals: dict[int, int] = defaultdict(int)
    rows = (
        db.query(LeagueQuizScoreEvent.user_id, LeagueQuizScoreEvent.delta_points)
        .filter(
            LeagueQuizScoreEvent.session_id == session_id,
            LeagueQuizScoreEvent.round_id == round_id,
        )
        .all()
    )
    for user_id, points in rows:
        totals[int(user_id)] += int(points or 0)
    return totals


def _answer_rows_for_round(db: Session, round_id: int) -> dict[int, list[tuple[LeagueQuizSessionAnswer, LeagueQuizSessionQuestion]]]:
    result: dict[int, list[tuple[LeagueQuizSessionAnswer, LeagueQuizSessionQuestion]]] = defaultdict(list)
    rows = (
        db.query(LeagueQuizSessionAnswer, LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionQuestion, LeagueQuizSessionQuestion.id == LeagueQuizSessionAnswer.session_question_id)
        .filter(LeagueQuizSessionQuestion.round_id == round_id)
        .order_by(LeagueQuizSessionQuestion.question_order.asc(), LeagueQuizSessionAnswer.id.asc())
        .all()
    )
    for answer, question in rows:
        result[int(answer.user_id)].append((answer, question))
    return result


def _short_question_label(question: LeagueQuizSessionQuestion | None) -> str | None:
    if not question:
        return None
    text = " ".join(str(question.question_text_snapshot or "").split())
    if len(text) > 96:
        return f"{text[:93].rstrip()}…"
    return text or None


def capture_round_results(db: Session, quiz_session: LeagueQuizSession, round_row: LeagueQuizSessionRound) -> None:
    """Freeze one compact personal card for every participant after a live round.

    The operation is idempotent and intentionally does nothing for rehearsal
    sessions: test runs must not pollute records, series or statistics.
    """
    if not _is_live_quiz(quiz_session):
        return
    participants = (
        db.query(LeagueQuizSessionParticipant, User)
        .join(User, User.id == LeagueQuizSessionParticipant.user_id)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(LeagueQuizSessionParticipant.score_total.desc(), User.display_name.asc(), LeagueQuizSessionParticipant.id.asc())
        .all()
    )
    if not participants:
        return
    previous_rows = (
        db.query(LeagueQuizRoundResult)
        .filter(
            LeagueQuizRoundResult.session_id == quiz_session.id,
            LeagueQuizRoundResult.round_order < round_row.round_order,
        )
        .order_by(LeagueQuizRoundResult.round_order.desc())
        .all()
    )
    previous_order = max((row.round_order for row in previous_rows), default=None)
    previous_places = {
        int(row.user_id): int(row.place)
        for row in previous_rows
        if previous_order is not None and int(row.round_order) == int(previous_order)
    }
    round_scores = _round_score_rows(db, quiz_session.id, round_row.id)
    answers_by_user = _answer_rows_for_round(db, round_row.id)

    for place, (participant, user) in enumerate(participants, start=1):
        user_id = int(user.id)
        answers = answers_by_user.get(user_id, [])
        correct_count = sum(1 for answer, _question in answers if answer.is_correct is True)
        best_pair = max(
            answers,
            key=lambda pair: (int(pair[0].points_awarded or 0), -int(pair[1].question_order or 0)),
            default=None,
        )
        best_answer_points = max(0, int(best_pair[0].points_awarded or 0)) if best_pair else 0
        previous_place = previous_places.get(user_id)
        movement = int(previous_place - place) if previous_place is not None else 0
        row = (
            db.query(LeagueQuizRoundResult)
            .filter(
                LeagueQuizRoundResult.session_id == quiz_session.id,
                LeagueQuizRoundResult.round_id == round_row.id,
                LeagueQuizRoundResult.user_id == user_id,
            )
            .first()
        )
        if not row:
            row = LeagueQuizRoundResult(
                session_id=quiz_session.id,
                round_id=round_row.id,
                user_id=user_id,
                round_order=round_row.round_order,
            )
            db.add(row)
        row.round_score = int(round_scores.get(user_id, 0))
        row.score_total = int(participant.score_total or 0)
        row.place = place
        row.previous_place = previous_place
        row.place_change = movement
        row.best_question_id = best_pair[1].id if best_pair else None
        row.best_answer_label = _short_question_label(best_pair[1]) if best_pair else None
        row.best_answer_points = best_answer_points
        row.correct_answers = correct_count
        row.answered_count = len(answers)


def _finished_sessions_for_user(db: Session, league_id: int, user_id: int) -> list[LeagueQuizSession]:
    return (
        db.query(LeagueQuizSession)
        .join(LeagueQuizSessionParticipant, LeagueQuizSessionParticipant.session_id == LeagueQuizSession.id)
        .filter(
            LeagueQuizSession.league_id == league_id,
            LeagueQuizSession.status == "finished",
            LeagueQuizSession.is_test_run == False,  # noqa: E712
            LeagueQuizSessionParticipant.user_id == user_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(LeagueQuizSession.finished_at.asc(), LeagueQuizSession.id.asc())
        .all()
    )


def _answer_history(db: Session, league_id: int, user_id: int) -> list[tuple[LeagueQuizSessionAnswer, LeagueQuizSessionQuestion, LeagueQuizSessionRound, LeagueQuizSession]]:
    return (
        db.query(LeagueQuizSessionAnswer, LeagueQuizSessionQuestion, LeagueQuizSessionRound, LeagueQuizSession)
        .join(LeagueQuizSessionQuestion, LeagueQuizSessionQuestion.id == LeagueQuizSessionAnswer.session_question_id)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .join(LeagueQuizSession, LeagueQuizSession.id == LeagueQuizSessionRound.session_id)
        .filter(
            LeagueQuizSession.league_id == league_id,
            LeagueQuizSession.status == "finished",
            LeagueQuizSession.is_test_run == False,  # noqa: E712
            LeagueQuizSessionAnswer.user_id == user_id,
            LeagueQuizSessionAnswer.scored_at.isnot(None),
        )
        .order_by(LeagueQuizSessionAnswer.scored_at.asc(), LeagueQuizSessionAnswer.id.asc())
        .all()
    )


def _streak(values: list[bool]) -> tuple[int, int]:
    best = current = 0
    for value in values:
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return current, best


def _session_final_place(db: Session, session_id: int, user_id: int) -> int | None:
    rows = (
        db.query(LeagueQuizRoundResult)
        .filter(LeagueQuizRoundResult.session_id == session_id, LeagueQuizRoundResult.user_id == user_id)
        .order_by(LeagueQuizRoundResult.round_order.desc())
        .all()
    )
    if rows:
        return int(rows[0].place)
    # Historical fallback for quizzes played before v3.5.0.
    participants = (
        db.query(LeagueQuizSessionParticipant, User)
        .join(User, User.id == LeagueQuizSessionParticipant.user_id)
        .filter(LeagueQuizSessionParticipant.session_id == session_id, LeagueQuizSessionParticipant.status == "registered")
        .order_by(LeagueQuizSessionParticipant.score_total.desc(), User.display_name.asc(), LeagueQuizSessionParticipant.id.asc())
        .all()
    )
    for position, (participant, user) in enumerate(participants, start=1):
        if int(user.id) == int(user_id):
            return position
    return None


def _participation_series(db: Session, league_id: int, user_id: int) -> tuple[int, int, int, int]:
    sessions = (
        db.query(LeagueQuizSession)
        .filter(
            LeagueQuizSession.league_id == league_id,
            LeagueQuizSession.status == "finished",
            LeagueQuizSession.is_test_run == False,  # noqa: E712
        )
        .order_by(LeagueQuizSession.finished_at.asc(), LeagueQuizSession.id.asc())
        .all()
    )
    participated: list[bool] = []
    top3: list[bool] = []
    for session in sessions:
        participant = (
            db.query(LeagueQuizSessionParticipant)
            .filter(
                LeagueQuizSessionParticipant.session_id == session.id,
                LeagueQuizSessionParticipant.user_id == user_id,
                LeagueQuizSessionParticipant.status == "registered",
            )
            .first()
        )
        is_participant = bool(participant)
        participated.append(is_participant)
        place = _session_final_place(db, session.id, user_id) if is_participant else None
        top3.append(bool(place and place <= 3))
    current_participation, best_participation = _streak(participated)
    current_top3, best_top3 = _streak(top3)
    return current_participation, best_participation, current_top3, best_top3


def _round_result_for_user(db: Session, session_id: int, round_id: int, user_id: int) -> LeagueQuizRoundResult | None:
    return (
        db.query(LeagueQuizRoundResult)
        .filter(
            LeagueQuizRoundResult.session_id == session_id,
            LeagueQuizRoundResult.round_id == round_id,
            LeagueQuizRoundResult.user_id == user_id,
        )
        .first()
    )


def _serialize_achievement(row: LeagueQuizAchievement) -> dict[str, Any]:
    rule = QUIZ_ACHIEVEMENTS.get(row.achievement_code, {})
    return {
        "code": row.achievement_code,
        "title": rule.get("title", row.achievement_code),
        "description": rule.get("description", ""),
        "icon": rule.get("icon", "🏅"),
        "unlocked_at": row.unlocked_at.isoformat() if row.unlocked_at else None,
        "session_id": row.unlocked_in_session_id,
        "metadata": dict(row.metadata_json or {}),
    }


def sync_quiz_achievements_for_user(
    db: Session,
    *,
    league_id: int,
    user_id: int,
    session_id: int | None = None,
) -> list[LeagueQuizAchievement]:
    """Persist newly reached achievements and return only newly added rows."""
    sessions = _finished_sessions_for_user(db, league_id, user_id)
    history = _answer_history(db, league_id, user_id)
    correct_current, correct_best = _streak([answer.is_correct is True for answer, *_ in history])
    chgk_correct = sum(1 for answer, question, *_ in history if question.question_type == "what_where_when" and answer.is_correct is True)
    hundred_top = sum(
        1
        for answer, question, *_ in history
        if question.question_type == "hundred_to_one"
        and answer.is_correct is True
        and int((answer.answer_payload or {}).get("position") or 0) == 1
    )
    comeback = (
        db.query(LeagueQuizRoundResult)
        .filter(
            LeagueQuizRoundResult.user_id == user_id,
            LeagueQuizRoundResult.place_change >= 1,
        )
        .join(LeagueQuizSession, LeagueQuizSession.id == LeagueQuizRoundResult.session_id)
        .filter(LeagueQuizSession.league_id == league_id, LeagueQuizSession.is_test_run == False)  # noqa: E712
        .first()
    )
    achieved: dict[str, dict[str, Any]] = {}
    if sessions:
        achieved["first_quiz"] = {"completed_quizzes": len(sessions)}
    if correct_best >= 5:
        achieved["streak_5"] = {"best_streak": correct_best, "current_streak": correct_current}
    if chgk_correct >= 3:
        achieved["chgk_master"] = {"correct_chgk": chgk_correct}
    if hundred_top >= 1:
        achieved["hundred_king"] = {"top_answers": hundred_top}
    if comeback:
        achieved["comeback_day"] = {
            "moved_up": int(comeback.place_change),
            "round_order": int(comeback.round_order),
            "session_id": int(comeback.session_id),
        }
    existing = {
        row.achievement_code
        for row in db.query(LeagueQuizAchievement)
        .filter(LeagueQuizAchievement.league_id == league_id, LeagueQuizAchievement.user_id == user_id)
        .all()
    }
    created: list[LeagueQuizAchievement] = []
    for code, metadata in achieved.items():
        if code in existing:
            continue
        row = LeagueQuizAchievement(
            league_id=league_id,
            user_id=user_id,
            achievement_code=code,
            unlocked_in_session_id=session_id,
            metadata_json=metadata,
        )
        db.add(row)
        created.append(row)
    if created:
        db.flush()
    return created


def finalize_quiz_game_layer(db: Session, quiz_session: LeagueQuizSession) -> None:
    """Award deterministic achievement facts once a live quiz is final."""
    if not _is_live_quiz(quiz_session):
        return
    user_ids = [
        int(row.user_id)
        for row in db.query(LeagueQuizSessionParticipant)
        .filter(LeagueQuizSessionParticipant.session_id == quiz_session.id, LeagueQuizSessionParticipant.status == "registered")
        .all()
    ]
    for user_id in user_ids:
        sync_quiz_achievements_for_user(
            db,
            league_id=int(quiz_session.league_id),
            user_id=user_id,
            session_id=int(quiz_session.id),
        )


def _round_card_from_row(row: LeagueQuizRoundResult | None, round_title: str | None = None) -> dict[str, Any] | None:
    if not row:
        return None
    movement = int(row.place_change or 0)
    return {
        "round_id": row.round_id,
        "round_order": int(row.round_order),
        "round_title": round_title or "Раунд",
        "round_score": int(row.round_score or 0),
        "score_total": int(row.score_total or 0),
        "place": int(row.place),
        "previous_place": int(row.previous_place) if row.previous_place is not None else None,
        "place_change": movement,
        "place_change_label": (f"↑ {movement}" if movement > 0 else (f"↓ {abs(movement)}" if movement < 0 else "—")),
        "best_answer": row.best_answer_label,
        "best_answer_points": int(row.best_answer_points or 0),
        "correct_answers": int(row.correct_answers or 0),
        "answered_count": int(row.answered_count or 0),
    }


def build_player_quiz_stats(db: Session, user: User, league_id: int) -> dict[str, Any]:
    history = _answer_history(db, league_id, user.id)
    by_type: dict[str, dict[str, Any]] = defaultdict(lambda: {"attempts": 0, "correct": 0})
    by_topic: dict[str, dict[str, Any]] = defaultdict(lambda: {"attempts": 0, "correct": 0})
    for answer, question, _round, _session in history:
        qtype = str(question.question_type or "unknown")
        by_type[qtype]["attempts"] += 1
        by_type[qtype]["correct"] += 1 if answer.is_correct is True else 0
        payload = dict(question.payload_snapshot or {})
        meta = payload.get("_quiz_meta") if isinstance(payload.get("_quiz_meta"), dict) else {}
        topics = meta.get("topics") or []
        if not topics:
            topics = ["Без темы"]
        for topic in topics:
            clean = " ".join(str(topic or "").split()) or "Без темы"
            by_topic[clean]["attempts"] += 1
            by_topic[clean]["correct"] += 1 if answer.is_correct is True else 0

    def serialize_bucket(key: str, data: dict[str, Any], label: str | None = None) -> dict[str, Any]:
        attempts = int(data["attempts"])
        correct = int(data["correct"])
        return {
            "key": key,
            "label": label or key,
            "attempts": attempts,
            "correct": correct,
            "accuracy": round((correct / attempts) * 100) if attempts else 0,
        }

    type_rows = [serialize_bucket(key, value, TYPE_LABELS.get(key, key)) for key, value in by_type.items()]
    topic_rows = [serialize_bucket(key, value) for key, value in by_topic.items()]
    type_rows.sort(key=lambda item: (-item["attempts"], item["label"]))
    topic_rows.sort(key=lambda item: (-item["attempts"], item["label"]))
    meaningful_types = [row for row in type_rows if row["attempts"] > 0]
    best_type = max(meaningful_types, key=lambda row: (row["accuracy"], row["attempts"], row["label"]), default=None)
    weakest_type = min(meaningful_types, key=lambda row: (row["accuracy"], -row["attempts"], row["label"]), default=None)
    favorite_type = type_rows[0] if type_rows else None
    correct_current, correct_best = _streak([answer.is_correct is True for answer, *_ in history])
    current_participation, best_participation, current_top3, best_top3 = _participation_series(db, league_id, user.id)
    sessions = _finished_sessions_for_user(db, league_id, user.id)
    places = [_session_final_place(db, session.id, user.id) for session in sessions]
    valid_places = [place for place in places if place is not None]
    achievements = (
        db.query(LeagueQuizAchievement)
        .filter(LeagueQuizAchievement.league_id == league_id, LeagueQuizAchievement.user_id == user.id)
        .order_by(LeagueQuizAchievement.unlocked_at.desc(), LeagueQuizAchievement.id.desc())
        .all()
    )
    attempts = sum(row["attempts"] for row in type_rows)
    correct = sum(row["correct"] for row in type_rows)
    return {
        "summary": {
            "completed_quizzes": len(sessions),
            "answers": attempts,
            "correct": correct,
            "accuracy": round((correct / attempts) * 100) if attempts else 0,
            "average_place": round(sum(valid_places) / len(valid_places), 1) if valid_places else None,
        },
        "streaks": {
            "correct_current": correct_current,
            "correct_best": correct_best,
            "participation_current": current_participation,
            "participation_best": best_participation,
            "top3_current": current_top3,
            "top3_best": best_top3,
        },
        "achievements": [_serialize_achievement(row) for row in achievements],
        "types": type_rows,
        "topics": topic_rows,
        "favorite_type": favorite_type,
        "best_type": best_type,
        "weakest_type": weakest_type,
    }


def _personal_best_record(db: Session, quiz_session: LeagueQuizSession, user_id: int, score_total: int, place: int) -> str | None:
    old_sessions = (
        db.query(LeagueQuizSession)
        .join(LeagueQuizSessionParticipant, LeagueQuizSessionParticipant.session_id == LeagueQuizSession.id)
        .filter(
            LeagueQuizSession.league_id == quiz_session.league_id,
            LeagueQuizSession.status == "finished",
            LeagueQuizSession.is_test_run == False,  # noqa: E712
            LeagueQuizSession.id != quiz_session.id,
            LeagueQuizSessionParticipant.user_id == user_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .all()
    )
    if not old_sessions:
        return "Первый личный результат в квизе"
    previous_scores = []
    previous_places = []
    for session in old_sessions:
        participant = (
            db.query(LeagueQuizSessionParticipant)
            .filter(LeagueQuizSessionParticipant.session_id == session.id, LeagueQuizSessionParticipant.user_id == user_id)
            .first()
        )
        if participant:
            previous_scores.append(int(participant.score_total or 0))
        resolved_place = _session_final_place(db, session.id, user_id)
        if resolved_place is not None:
            previous_places.append(int(resolved_place))
    if previous_scores and score_total > max(previous_scores):
        return f"Новый личный рекорд: {score_total} очк."
    if previous_places and place < min(previous_places):
        return f"Лучшее личное место: {place}-е"
    return None


def build_final_result_card(db: Session, quiz_session: LeagueQuizSession, user: User) -> dict[str, Any] | None:
    if quiz_session.status != "finished" or not _is_live_quiz(quiz_session):
        return None
    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == user.id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .first()
    )
    if not participant:
        return None
    last_round = (
        db.query(LeagueQuizSessionRound)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id)
        .order_by(LeagueQuizSessionRound.round_order.desc())
        .first()
    )
    latest = _round_result_for_user(db, quiz_session.id, last_round.id, user.id) if last_round else None
    rows = (
        db.query(LeagueQuizRoundResult)
        .filter(LeagueQuizRoundResult.session_id == quiz_session.id, LeagueQuizRoundResult.user_id == user.id)
        .order_by(LeagueQuizRoundResult.best_answer_points.desc(), LeagueQuizRoundResult.round_order.asc())
        .all()
    )
    best = rows[0] if rows else latest
    place = int(latest.place) if latest else _session_final_place(db, quiz_session.id, user.id)
    if not place:
        return None
    unlocked = (
        db.query(LeagueQuizAchievement)
        .filter(
            LeagueQuizAchievement.league_id == quiz_session.league_id,
            LeagueQuizAchievement.user_id == user.id,
            LeagueQuizAchievement.unlocked_in_session_id == quiz_session.id,
        )
        .order_by(LeagueQuizAchievement.id.asc())
        .all()
    )
    return {
        "place": place,
        "score_total": int(participant.score_total or 0),
        "best_answer": best.best_answer_label if best else None,
        "best_answer_points": int(best.best_answer_points or 0) if best else 0,
        "record": _personal_best_record(db, quiz_session, user.id, int(participant.score_total or 0), place),
        "place_change": int(latest.place_change or 0) if latest else 0,
        "achievements": [_serialize_achievement(item) for item in unlocked],
    }


def _round_context(db: Session, quiz_session: LeagueQuizSession, round_row: LeagueQuizSessionRound, user: User | None = None) -> dict[str, Any]:
    rows = (
        db.query(LeagueQuizRoundResult, User)
        .join(User, User.id == LeagueQuizRoundResult.user_id)
        .filter(LeagueQuizRoundResult.session_id == quiz_session.id, LeagueQuizRoundResult.round_id == round_row.id)
        .order_by(LeagueQuizRoundResult.place.asc())
        .all()
    )
    leader = rows[0][1].display_name if rows else None
    leader_score = int(rows[0][0].score_total or 0) if rows else 0
    context: dict[str, Any] = {
        "quiz": quiz_session.title,
        "round": round_row.title,
        "round_type": TYPE_LABELS.get(round_row.round_type, round_row.round_type),
        "participants": len(rows),
        "leader": leader,
        "leader_score": leader_score,
    }
    if user:
        result = _round_result_for_user(db, quiz_session.id, round_row.id, user.id)
        if result:
            context.update({
                "player": user.display_name,
                "place": int(result.place),
                "round_score": int(result.round_score or 0),
                "place_change": int(result.place_change or 0),
                "best_answer_points": int(result.best_answer_points or 0),
            })
    return context


def _fallback_recap(context: dict[str, Any], personal: bool) -> str:
    if personal:
        movement = int(context.get("place_change") or 0)
        delta = int(context.get("round_score") or 0)
        if movement >= 2:
            return f"Подъём на {movement} позиции: таблица уже проверяет, не было ли VAR-вмешательства."
        if delta > 0:
            return f"+{delta} за раунд — протокол выглядит убедительнее, чем оправдания соперников."
        return "Раунд без прибавки, но квиз длинный: у таблицы ещё достаточно поводов передумать."
    leader = context.get("leader")
    if leader:
        return f"После раунда лидирует {leader}. Остальные пока выбирают: догонять или писать апелляцию в футбольную канцелярию."
    return "Раунд закрыт. Таблица проводит инвентаризацию, интрига остаётся на месте."


def get_or_create_quiz_recap(
    db: Session,
    *,
    quiz_session: LeagueQuizSession,
    round_row: LeagueQuizSessionRound | None = None,
    user: User | None = None,
    use_openai: bool = True,
) -> dict[str, Any]:
    """Return a cached factual recap with an OpenAI wording attempt when enabled."""
    if round_row:
        scope = f"round:{round_row.id}:{'user:' + str(user.id) if user else 'group'}"
    else:
        scope = f"quiz:{'user:' + str(user.id) if user else 'group'}"
    existing = (
        db.query(LeagueQuizRecap)
        .filter(LeagueQuizRecap.session_id == quiz_session.id, LeagueQuizRecap.scope_key == scope)
        .first()
    )
    # A PWA detail request stores a deterministic template instantly. Telegram
    # can later upgrade that same cached row to OpenAI wording when enabled,
    # without creating a duplicate recap or changing any factual input.
    if existing and (not use_openai or existing.source == "openai"):
        return {"text": existing.recap_text, "source": existing.source}
    if round_row:
        context = _round_context(db, quiz_session, round_row, user)
        fallback = _fallback_recap(context, personal=bool(user))
        purpose = "Короткий персональный итог игрока после раунда квиза" if user else "Короткий общий итог раунда квиза для лиги"
    else:
        context = {"quiz": quiz_session.title}
        fallback = "Квиз завершён. Таблица зафиксировала результаты, а легенды уже начали редактировать мемуары."
        purpose = "Короткий общий итог завершённого квиза"
    text = fallback
    source = "template"
    if use_openai:
        try:
            from app.services.openai_gamification import COMMENTARY_SCHEMA, _request_openai_commentary
            league = db.query(League).filter(League.id == quiz_session.league_id).first()
            text = _request_openai_commentary(
                purpose=purpose,
                context=context,
                mode=getattr(league, "humor_mode", "ironic") if league else "ironic",
                schema=COMMENTARY_SCHEMA,
                fallback=fallback,
                max_chars=360,
                extra_rules="Говори только о квизе и его подтверждённых результатах. Не упоминай ставки, деньги или личные качества игроков.",
            )
            source = "openai" if text != fallback else "template"
        except Exception:
            text = fallback
            source = "template"
    if existing:
        existing.recap_text = text
        existing.source = source
        row = existing
    else:
        row = LeagueQuizRecap(
            session_id=quiz_session.id,
            round_id=round_row.id if round_row else None,
            user_id=user.id if user else None,
            scope_key=scope,
            recap_text=text,
            source=source,
        )
        db.add(row)
    db.flush()
    return {"text": row.recap_text, "source": row.source}


def build_session_gamification_detail(db: Session, quiz_session: LeagueQuizSession, user: User, *, include_stats: bool = False) -> dict[str, Any]:
    if not _is_live_quiz(quiz_session):
        return {"enabled": False}
    latest = (
        db.query(LeagueQuizRoundResult, LeagueQuizSessionRound)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizRoundResult.round_id)
        .filter(LeagueQuizRoundResult.session_id == quiz_session.id, LeagueQuizRoundResult.user_id == user.id)
        .order_by(LeagueQuizRoundResult.round_order.desc())
        .first()
    )
    latest_card = _round_card_from_row(latest[0], latest[1].title) if latest else None
    recap = None
    if latest and latest_card:
        recap = get_or_create_quiz_recap(
            db,
            quiz_session=quiz_session,
            round_row=latest[1],
            user=user,
            use_openai=False,
        )
    final_card = build_final_result_card(db, quiz_session, user)
    final_recap = None
    if final_card:
        final_recap = get_or_create_quiz_recap(
            db, quiz_session=quiz_session, round_row=None, user=user, use_openai=False
        )
    data = {
        "enabled": True,
        "latest_round_card": latest_card,
        "final_card": final_card,
        "latest_round_recap": recap,
        "final_recap": final_recap,
    }
    if include_stats:
        data["stats"] = build_player_quiz_stats(db, user, quiz_session.league_id)
    return data


def format_round_card_text(card: dict[str, Any] | None, recap: str | None = None) -> str:
    if not card:
        return recap or ""
    movement = card.get("place_change_label") or "—"
    lines = [
        "🎯 Ваш итог раунда",
        f"Место: {card['place']}-е · всего {card['score_total']} очк. ({movement})",
        f"За раунд: {card['round_score']:+d} · верных: {card['correct_answers']}/{card['answered_count']}",
    ]
    if card.get("best_answer") and card.get("best_answer_points"):
        lines.append(f"Лучший ответ: +{card['best_answer_points']} очк.")
    if recap:
        lines.append(f"🎙️ Отец: {recap}")
    return "\n".join(lines)


def format_final_card_text(card: dict[str, Any] | None, recap: str | None = None) -> str:
    if not card:
        return recap or ""
    lines = [
        "🏅 Ваш результат",
        f"{card['place']}-е место · {card['score_total']} очк.",
    ]
    if card.get("best_answer") and card.get("best_answer_points"):
        lines.append(f"Лучший ответ: +{card['best_answer_points']} очк.")
    if card.get("record"):
        lines.append(f"⭐ {card['record']}")
    achievements = card.get("achievements") or []
    if achievements:
        lines.append("Новые достижения: " + ", ".join(f"{item['icon']} {item['title']}" for item in achievements))
    if recap:
        lines.append(f"🎙️ Отец: {recap}")
    return "\n".join(lines)
