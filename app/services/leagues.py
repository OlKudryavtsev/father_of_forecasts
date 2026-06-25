"""League and access-request helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import secrets
import string

from app.models import League, LeagueMember, User
from app.services.league_activity import record_league_activity
from app.services.tournament import get_tournament_starts_at

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




def league_scoring_start_at(league: League | None):
    """Return the datetime from which match points should count for a league.

    System league «Отец прогнозов» is intentionally scored from tournament start
    to preserve the historical leaderboard. New private leagues are scored from
    their creation/scoring_start_at.
    """
    if league is None:
        return None
    if getattr(league, "scoring_start_at", None):
        return league.scoring_start_at
    if league.name == DEFAULT_LEAGUE_NAME or league.league_type == "system":
        return get_tournament_starts_at()
    return league.created_at


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


def is_user_in_default_league(db, user: User) -> bool:
    """Return True when user is an active member of the system default league."""
    default_league = get_default_league(db)
    if not default_league:
        return False

    member = (
        db.query(LeagueMember)
        .filter(
            LeagueMember.league_id == default_league.id,
            LeagueMember.user_id == user.id,
            LeagueMember.status == "active",
        )
        .first()
    )
    return bool(member)


def approve_user(db, user: User, approved_by: User | None = None) -> list[str]:
    """Approve user and add them only to the pending invite league, if any.

    New public users must not be added to the system league «Отец прогнозов»
    automatically. Existing members stay there via the foundation migration, and
    invite links still add a user to the league that was explicitly invited.
    """
    now = datetime.now(timezone.utc)
    user.access_status = "approved"
    user.approved_at = user.approved_at or now
    if approved_by:
        user.approved_by_user_id = approved_by.id

    joined_leagues: list[str] = []

    invite_league = get_league_by_invite_code(db, user.pending_invite_code)
    was_active_member = False
    if invite_league:
        existing_member = get_league_member(db, invite_league, user)
        was_active_member = bool(existing_member and existing_member.status == "active")
        ensure_user_in_league(db, user, invite_league, role="admin" if user.is_admin else "member")
        joined_leagues.append(invite_league.name)

    user.pending_invite_code = None
    db.commit()
    db.refresh(user)

    if invite_league and not was_active_member:
        try:
            record_league_activity(
                db,
                league=invite_league,
                actor=user,
                action_type="member_joined",
                payload={"league_name": invite_league.name},
            )
        except Exception:
            db.rollback()
    return joined_leagues


def reject_user(db, user: User, rejected_by: User | None = None) -> None:
    user.access_status = "rejected"
    if rejected_by:
        user.rejected_by_user_id = rejected_by.id
    user.rejected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)




def get_league_member(db, league: League, user: User) -> LeagueMember | None:
    """Return membership row for a user in a league."""
    return (
        db.query(LeagueMember)
        .filter(
            LeagueMember.league_id == league.id,
            LeagueMember.user_id == user.id,
        )
        .first()
    )


def can_manage_league(db, actor: User, league: League) -> bool:
    """Return True when actor can manage a league."""
    if actor.is_admin:
        return True
    if league.owner_user_id == actor.id:
        return True
    member = get_league_member(db, league, actor)
    return bool(member and member.status == "active" and member.role in {"owner", "admin"})


def require_manage_league(db, actor: User, league_id: int) -> League:
    """Return an active league if actor has management rights."""
    league = db.query(League).filter(League.id == league_id, League.is_active == True).first()
    if not league:
        raise ValueError("Лига не найдена или отключена")
    if not can_manage_league(db, actor, league):
        raise PermissionError("Недостаточно прав для управления лигой")
    return league


def list_league_members(db, actor: User, league_id: int) -> tuple[League, list[LeagueMember]]:
    """Return league members for a manageable league."""
    league = require_manage_league(db, actor, league_id)
    members = (
        db.query(LeagueMember)
        .join(User, User.id == LeagueMember.user_id)
        .filter(LeagueMember.league_id == league.id)
        .order_by(
            LeagueMember.status.asc(),
            LeagueMember.role.desc(),
            User.display_name.asc(),
        )
        .all()
    )
    return league, members


def set_league_member_role(db, actor: User, league_id: int, user_id: int, role: str) -> LeagueMember:
    """Set league member role to admin/member."""
    if role not in {"admin", "member"}:
        raise ValueError("Роль должна быть admin или member")

    league = require_manage_league(db, actor, league_id)
    member = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == user_id)
        .first()
    )
    if not member or member.status != "active":
        raise ValueError("Участник не найден в лиге")
    if league.owner_user_id == user_id:
        raise ValueError("Нельзя изменить роль владельца лиги")

    member.role = role
    db.commit()
    db.refresh(member)
    return member


def remove_league_member(db, actor: User, league_id: int, user_id: int) -> LeagueMember:
    """Mark a league member as removed."""
    league = require_manage_league(db, actor, league_id)
    member = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == user_id)
        .first()
    )
    if not member or member.status != "active":
        raise ValueError("Участник не найден в лиге")
    if league.owner_user_id == user_id:
        raise ValueError("Нельзя исключить владельца лиги")
    if user_id == actor.id and not actor.is_admin:
        raise ValueError("Нельзя исключить самого себя из управляемой лиги")

    member.status = "removed"
    db.commit()
    db.refresh(member)
    return member


def deactivate_league(db, actor: User, league_id: int) -> League:
    """Deactivate a private league."""
    league = require_manage_league(db, actor, league_id)
    if league.league_type == "system":
        raise ValueError("Системную лигу нельзя деактивировать")
    if not actor.is_admin and league.owner_user_id != actor.id:
        raise PermissionError("Деактивировать лигу может только владелец или администратор бота")

    league.is_active = False
    db.query(LeagueMember).filter(LeagueMember.league_id == league.id).update({"status": "removed"})
    db.commit()
    db.refresh(league)
    return league


def update_league_settings(
    db,
    actor: User,
    league_id: int,
    chat_id: str | None,
    humor_mode: str | None = None,
) -> League:
    """Set optional Telegram chat id and public-summary tone for a league."""
    league = require_manage_league(db, actor, league_id)
    value = (chat_id or "").strip()
    if value:
        # Telegram group/channel ids are usually numeric and may start with -100.
        # Keep as string to avoid JS precision issues and to support future aliases.
        if len(value) > 80:
            raise ValueError("Chat ID слишком длинный")
        allowed = set("-0123456789")
        if not set(value).issubset(allowed):
            raise ValueError("Chat ID должен быть числом, например -1001234567890")
        league.chat_id = value
    else:
        league.chat_id = None

    if humor_mode is not None:
        from app.services.gamification import normalize_humor_mode
        normalized = normalize_humor_mode(humor_mode, default="")
        if not normalized:
            raise ValueError("Неизвестный режим юмора")
        league.humor_mode = normalized
    db.commit()
    db.refresh(league)
    return league


def update_league_chat_id(db, actor: User, league_id: int, chat_id: str | None) -> League:
    """Backward-compatible wrapper for older imports."""
    return update_league_settings(db, actor, league_id, chat_id, None)


def get_active_league_chat_targets(db) -> list[League]:
    """Return active leagues with an optional Telegram chat id configured.

    ``chat_id`` is optional. In some production databases this column may be
    BIGINT from an earlier migration, so never compare it with an empty string
    in SQL: PostgreSQL cannot cast ``''`` to BIGINT. Empty values are normalized
    to NULL on write, and in-memory filtering below protects old TEXT schemas.
    """
    leagues = (
        db.query(League)
        .filter(
            League.is_active == True,
            League.chat_id.isnot(None),
        )
        .order_by(League.name.asc())
        .all()
    )
    return [league for league in leagues if str(getattr(league, "chat_id", "") or "").strip()]


def get_user_active_leagues_with_chat(db, user: User) -> list[League]:
    """Return active leagues where user is active member and chat_id is configured."""
    leagues = (
        db.query(League)
        .join(LeagueMember, LeagueMember.league_id == League.id)
        .filter(
            LeagueMember.user_id == user.id,
            LeagueMember.status == "active",
            League.is_active == True,
            League.chat_id.isnot(None),
        )
        .order_by(League.name.asc())
        .all()
    )
    return [league for league in leagues if str(getattr(league, "chat_id", "") or "").strip()]

def generate_invite_code(db, length: int = 8) -> str:
    """Generate a unique invite code for a league."""
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(50):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = db.query(League).filter(League.invite_code == code).first()
        if not exists:
            return code
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12].upper()


def get_user_active_leagues(db, user: User) -> list[League]:
    """Return active leagues where the user is an active member."""
    return (
        db.query(League)
        .join(LeagueMember, LeagueMember.league_id == League.id)
        .filter(
            LeagueMember.user_id == user.id,
            LeagueMember.status == "active",
            League.is_active == True,
        )
        .order_by(
            League.league_type.desc(),
            League.name.asc(),
        )
        .all()
    )




def get_user_active_leagues_for_match(db, user: User, match) -> list[League]:
    """Return active leagues where the user was already a member at kickoff.

    This is used for match-result notifications and match-centre participant
    views: a user should not be shown or notified as a league participant for a
    match that started before they joined that league.
    """
    return (
        db.query(League)
        .join(LeagueMember, LeagueMember.league_id == League.id)
        .filter(
            LeagueMember.user_id == user.id,
            LeagueMember.status == "active",
            LeagueMember.joined_at <= match.starts_at,
            League.is_active == True,
        )
        .order_by(League.league_type.desc(), League.name.asc())
        .all()
    )

def get_default_or_first_user_league(db, user: User) -> League | None:
    """Return default league for a user, falling back to their first active league."""
    default_league = get_default_league(db)
    if default_league:
        member = (
            db.query(LeagueMember)
            .filter(
                LeagueMember.league_id == default_league.id,
                LeagueMember.user_id == user.id,
                LeagueMember.status == "active",
            )
            .first()
        )
        if member:
            return default_league

    leagues = get_user_active_leagues(db, user)
    return leagues[0] if leagues else None


def require_user_league(db, user: User, league_id: int | None = None) -> League:
    """Return a league only if the user is an active member of it."""
    if league_id is None:
        league = get_default_or_first_user_league(db, user)
        if not league:
            raise ValueError("У пользователя нет активных лиг")
        return league

    league = (
        db.query(League)
        .join(LeagueMember, LeagueMember.league_id == League.id)
        .filter(
            League.id == league_id,
            League.is_active == True,
            LeagueMember.user_id == user.id,
            LeagueMember.status == "active",
        )
        .first()
    )
    if not league:
        raise ValueError("Лига недоступна")
    return league


def create_user_league(db, owner: User, name: str, description: str | None = None) -> League:
    """Create a private league and make the owner its admin."""
    league_name = (name or "").strip()
    if not league_name:
        raise ValueError("Название лиги обязательно")
    if len(league_name) > 80:
        raise ValueError("Название лиги слишком длинное")

    existing = db.query(League).filter(League.name == league_name).first()
    if existing:
        raise ValueError("Лига с таким названием уже существует")

    league = League(
        name=league_name,
        description=(description or "").strip() or None,
        league_type="private",
        owner_user_id=owner.id,
        invite_code=generate_invite_code(db),
        is_active=True,
        scoring_start_at=datetime.now(timezone.utc),
    )
    db.add(league)
    db.flush()
    ensure_user_in_league(db, owner, league, role="owner")
    db.commit()
    db.refresh(league)

    try:
        record_league_activity(
            db,
            league=league,
            actor=owner,
            action_type="league_created",
            payload={"league_name": league.name},
        )
    except Exception:
        # Activity is supplementary. The league itself has already been saved.
        db.rollback()
    return league


def join_league_by_invite_code(db, user: User, invite_code: str | None) -> League:
    """Join a league using an invite code."""
    league = get_league_by_invite_code(db, invite_code)
    if not league:
        raise ValueError("Лига с таким кодом не найдена")

    previous = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == user.id)
        .first()
    )
    was_active = bool(previous and previous.status == "active")
    ensure_user_in_league(db, user, league, role="member")
    db.commit()
    db.refresh(league)

    if not was_active:
        try:
            record_league_activity(
                db,
                league=league,
                actor=user,
                action_type="member_joined",
                payload={"league_name": league.name},
            )
        except Exception:
            db.rollback()
    return league
