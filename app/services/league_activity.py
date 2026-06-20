"""League-scoped participant activity feed helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models import League, LeagueActivityEvent, LeagueMember, User


def _event_key(action_type: str) -> str:
    return f"{action_type}:{uuid4().hex}"


def record_league_activity(
    db,
    *,
    league: League,
    actor: User,
    action_type: str,
    payload: dict | None = None,
    created_at: datetime | None = None,
) -> LeagueActivityEvent:
    """Persist one activity event for a known league.

    The caller may have already committed its business change. The feed must
    never make a valid prediction/join fail, so callers can safely catch a
    database exception from this helper and continue.
    """
    event = LeagueActivityEvent(
        league_id=league.id,
        actor_user_id=actor.id,
        action_type=action_type,
        event_key=_event_key(action_type),
        payload=payload or {},
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def record_user_league_activity(
    db,
    *,
    actor: User,
    action_type: str,
    payload: dict | None = None,
    only_league_ids: set[int] | None = None,
) -> int:
    """Write the same participant action into every active league of user.

    It is intentionally scoped at the moment of the action: a later join must
    not make a historical prediction appear in a league feed retroactively.
    """
    query = (
        db.query(League)
        .join(LeagueMember, LeagueMember.league_id == League.id)
        .filter(
            LeagueMember.user_id == actor.id,
            LeagueMember.status == "active",
            League.is_active == True,
        )
    )
    if only_league_ids:
        query = query.filter(League.id.in_(list(only_league_ids)))

    leagues = query.order_by(League.name.asc()).all()
    if not leagues:
        return 0

    now = datetime.now(timezone.utc)
    for league in leagues:
        db.add(
            LeagueActivityEvent(
                league_id=league.id,
                actor_user_id=actor.id,
                action_type=action_type,
                event_key=_event_key(action_type),
                payload=payload or {},
                created_at=now,
            )
        )
    db.commit()
    return len(leagues)
