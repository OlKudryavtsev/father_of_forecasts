"""League and access-request helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import League, LeagueMember, User

DEFAULT_LEAGUE_NAME = "Отец прогнозов"


def normalize_invite_code(invite_code: str | None) -> str | None:
    code = (invite_code or "").strip()
    if not code:
        return None
    for prefix in ("league_", "invite_"):
        if code.startswith(prefix):
            code = code.removeprefix(prefix).strip()
    return code or None


def extract_invite_code_from_start_text(text: str | None) -> str | None:
    """Extract invite-code from Telegram /start payload.

    Supported payloads:
    - /start league_ABC123
    - /start invite_ABC123
    - /start ABC123
    """
    raw = (text or "").strip()
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        return None

    payload = parts[1].strip()
    if not payload or payload == "app":
        return None

    return normalize_invite_code(payload)


def get_default_league(db) -> League | None:
    return (
        db.query(League)
        .filter(League.name == DEFAULT_LEAGUE_NAME, League.is_active == True)
        .first()
    )


def get_league_by_invite_code(db, invite_code: str | None) -> League | None:
    code = normalize_invite_code(invite_code)
    if not code:
        return None
    return (
        db.query(League)
        .filter(League.invite_code == code, League.is_active == True)
        .first()
    )


def ensure_user_in_league(db, user: User, league: League, role: str = "member") -> LeagueMember:
    member = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == user.id)
        .first()
    )
    if member:
        member.status = "active"
        if role == "admin" and member.role != "admin":
            member.role = "admin"
        return member

    member = LeagueMember(
        league_id=league.id,
        user_id=user.id,
        role=role,
        status="active",
    )
    db.add(member)
    return member


def approve_user(db, user: User, approved_by: User | None = None) -> list[str]:
    """Approve user and add them to the default league and pending invite league."""
    now = datetime.now(timezone.utc)
    user.access_status = "approved"
    user.approved_at = user.approved_at or now
    if approved_by:
        user.approved_by_user_id = approved_by.id

    joined_leagues: list[str] = []

    default_league = get_default_league(db)
    if default_league:
        ensure_user_in_league(
            db,
            user,
            default_league,
            role="admin" if user.is_admin else "member",
        )
        joined_leagues.append(default_league.name)

    invite_league = get_league_by_invite_code(db, user.pending_invite_code)
    if invite_league and (not default_league or invite_league.id != default_league.id):
        ensure_user_in_league(db, user, invite_league, role="member")
        joined_leagues.append(invite_league.name)

    user.pending_invite_code = None
    db.commit()
    db.refresh(user)
    return joined_leagues


def reject_user(db, user: User, rejected_by: User | None = None) -> None:
    user.access_status = "rejected"
    if rejected_by:
        user.rejected_by_user_id = rejected_by.id
    user.rejected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
