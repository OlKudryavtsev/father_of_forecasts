"""Real implementation extracted from the former bot_runtime monolith."""


from app.constants.categories import FACT_QUIZ_CATEGORIES, WC2026_START_DATE
from app.formatters.facts import format_daily_world_cup_rubric, format_world_cup_fact
from app.runtime import (
    DAILY_FACTS_ENABLED,
    DAILY_FACT_HOUR,
    DAILY_FACT_MINUTE,
    DAILY_FACT_TARGET,
    DAILY_FACT_TIMEZONE,
    FACTS_SEED_PATH,
    FactDeliveryLog,
    HistoricalArchiveCard,
    Message,
    SessionLocal,
    User,
    WorldCupFact,
    asyncio,
    bot,
    datetime,
    json,
    random,
    timedelta,
    timezone,
)
from app.services.misc import get_group_chat_id
from app.services.users import get_or_create_user


def get_random_archive_card_for_daily_rubric(db) -> HistoricalArchiveCard | None:
    """Return a random public active archive card for the daily rubric."""
    cards = (
        db.query(HistoricalArchiveCard)
        .filter(
            HistoricalArchiveCard.is_active == True,
            HistoricalArchiveCard.is_public == True,
        )
        .all()
    )

    if not cards:
        return None

    return random.choice(cards)



def _daily_group_text(context: dict, commentary: str) -> str:
    lines = [f"☀️ Итоги дня · лига «{context['league_name']}»", ""]
    matches = context.get("matches") or []
    if matches:
        lines.append("🏁 За последние 24 часа:")
        for match in matches[:6]:
            lines.append(f"— {match['label']} · {match['score']}")
    else:
        lines.append("🏁 За последние 24 часа завершённых матчей не было.")

    player = context.get("player_of_day") or {}
    if player and player.get("predictions"):
        lines.extend([
            "",
            f"🏆 Игрок дня: {player.get('name')} · {int(player.get('points') or 0)} очк.",
        ])
    leader = context.get("leader") or {}
    if leader:
        lines.append(f"👑 Лидер лиги: {leader.get('name')} · {int(leader.get('points') or 0)} очк.")
    if commentary:
        lines.extend(["", commentary])
    return "\n".join(lines)


def _daily_personal_text(context: dict, commentary: str) -> str:
    today = context.get("today") or {}
    lines = [f"☀️ Лига «{context['league_name']}» · твой итог дня", ""]
    if context.get("matches_count"):
        lines.append(
            f"За сутки: {int(today.get('points') or 0)} очк. · "
            f"🎯 {int(today.get('exact') or 0)} · 🔵 {int(today.get('outcomes') or 0)} · "
            f"промахов: {int(today.get('misses') or 0)}"
        )
    else:
        lines.append("За сутки завершённых матчей не было. Рейтинг выдержал паузу.")
    if context.get("rank"):
        lines.append(f"🏆 Сейчас ты #{context['rank']} · {int(context.get('league_points') or 0)} очк.")
    if commentary:
        lines.extend(["", commentary])
    return "\n".join(lines)


async def _daily_league_message(db, league):
    from app.services.gamification import build_daily_league_context, normalize_humor_mode
    from app.services.openai_gamification import generate_daily_league_commentary

    context = build_daily_league_context(db, league)
    tone = normalize_humor_mode(getattr(league, "humor_mode", None))
    commentary = await asyncio.to_thread(generate_daily_league_commentary, context, tone)
    return _daily_group_text(context, commentary)


async def _daily_personal_message(db, user, league):
    from app.services.gamification import build_daily_user_context, normalize_humor_mode
    from app.services.openai_gamification import generate_daily_personal_commentary

    context = build_daily_user_context(db, user, league)
    tone = normalize_humor_mode(
        getattr(user, "personal_humor_mode", None),
        default=normalize_humor_mode(getattr(league, "humor_mode", None)),
    )
    commentary = await asyncio.to_thread(generate_daily_personal_commentary, context, tone)
    return _daily_personal_text(context, commentary)


async def send_daily_match_summary_to_group(db):
    """Send an OpenAI-worded but fact-first morning result to the legacy group."""
    from app.services.leagues import get_default_league

    group_chat_id = get_group_chat_id()
    if not group_chat_id:
        print("GROUP_CHAT_ID is not set or invalid")
        return

    default_league = get_default_league(db)
    if not default_league:
        return
    text = await _daily_league_message(db, default_league)
    try:
        await bot.send_message(chat_id=group_chat_id, text=text)
        print(f"Daily match summary sent to group chat {group_chat_id}")
    except Exception as error:
        print(f"Failed to send daily match summary to group {group_chat_id}: {error}")


async def send_daily_match_summary_to_league_chats(db):
    """Send one daily story per unique chat, including the legacy default chat."""
    from app.services.leagues import get_unique_league_chat_destinations
    from app.services.notifications import notify_league_chat

    for league, _chat_id in get_unique_league_chat_destinations(db):
        text = await _daily_league_message(db, league)
        await notify_league_chat(league, text)


async def send_daily_match_summary_to_private_users(db):
    """Send each league participant their own humorous but factual daily recap."""
    from app.services.leagues import get_user_active_leagues
    from app.services.notifications import notify_private_user

    users = (
        db.query(User)
        .filter(User.access_status == "approved")
        .order_by(User.display_name.asc())
        .all()
    )
    for user in users:
        for league in get_user_active_leagues(db, user):
            try:
                text = await _daily_personal_message(db, user, league)
                await notify_private_user(
                    db,
                    user=user,
                    notification_key="daily_facts",
                    title=f"☀️ Твой итог · {league.name}",
                    text=text,
                    url="/app",
                )
            except Exception as error:
                print(f"Failed to send personal daily recap to {user.telegram_id} for league {league.id}: {error}")


async def send_daily_fact_to_group(db, fact: WorldCupFact):
    """Handle asynchronous bot workflow for send_daily_fact_to_group."""
    group_chat_id = get_group_chat_id()

    if not group_chat_id:
        print("GROUP_CHAT_ID is not set or invalid")
        return

    archive_card = get_random_archive_card_for_daily_rubric(db)
    text = format_daily_world_cup_rubric(fact, archive_card=archive_card)

    try:
        await bot.send_message(
            chat_id=group_chat_id,
            text=text,
        )

        try:
            from app.services.web_push import notify_active_web_push_subscribers_for_notification

            notify_active_web_push_subscribers_for_notification(
                db,
                notification_key="daily_facts",
                title="🏆 Факт дня",
                body=text[:220],
                url="/app",
            )
        except Exception as push_error:
            print(f"Failed to send daily fact web push notifications: {push_error}")

        db.add(
            FactDeliveryLog(
                fact_id=fact.id,
                user_id=None,
                telegram_id=None,
                chat_id=group_chat_id,
                delivery_type="daily_group",
            )
        )

        db.commit()

        print(f"Daily fact sent to group chat {group_chat_id}")

    except Exception as error:
        db.rollback()
        print(f"Failed to send daily fact to group {group_chat_id}: {error}")


def get_random_fact_not_sent_today(db) -> WorldCupFact | None:
    """Provide bot helper logic for get_random_fact_not_sent_today."""
    now_local = datetime.now(DAILY_FACT_TIMEZONE)

    start_local = now_local.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_local = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    sent_fact_ids_today = [
        row.fact_id
        for row in db.query(FactDeliveryLog)
        .filter(
            FactDeliveryLog.delivery_type.in_(
                ["daily", "daily_group", "daily_private"]
            ),
            FactDeliveryLog.sent_at >= start_utc,
            FactDeliveryLog.sent_at < end_utc,
        )
        .all()
    ]

    query = db.query(WorldCupFact).filter(
        WorldCupFact.is_active == True,
        WorldCupFact.needs_verification == False,
    )

    if sent_fact_ids_today:
        query = query.filter(WorldCupFact.id.notin_(sent_fact_ids_today))

    facts = query.all()

    if not facts:
        return None

    return random.choice(facts)


def import_world_cup_facts_from_seed(db) -> dict:
    """Provide bot helper logic for import_world_cup_facts_from_seed."""
    if not FACTS_SEED_PATH.exists():
        raise FileNotFoundError(f"Файл не найден: {FACTS_SEED_PATH}")

    payload = json.loads(
        FACTS_SEED_PATH.read_text(encoding="utf-8")
    )

    facts = payload.get("facts", [])

    created = 0
    updated = 0
    skipped = 0

    for item in facts:
        external_id = item.get("id")

        if not external_id:
            skipped += 1
            continue

        fact = db.query(WorldCupFact).filter(
            WorldCupFact.external_id == external_id
        ).first()

        if not fact:
            fact = WorldCupFact(external_id=external_id)
            db.add(fact)
            created += 1
        else:
            updated += 1

        fact.title = item.get("title") or "Факт о ЧМ"
        fact.fact_text = item.get("fact_text") or ""
        fact.category = item.get("category")
        fact.tournament_year = item.get("tournament_year")
        fact.source_text = item.get("source_text")
        fact.source_url = item.get("source_url")
        fact.spicy_comment = item.get("spicy_comment")
        fact.needs_verification = bool(item.get("needs_verification", False))
        fact.is_active = bool(item.get("is_active", True))

    db.commit()

    return {
        "total": len(facts),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


def plural_days_ru(value: int) -> str:
    """Provide bot helper logic for plural_days_ru."""
    if 11 <= value % 100 <= 14:
        return "дней"

    last_digit = value % 10

    if last_digit == 1:
        return "день"

    if 2 <= last_digit <= 4:
        return "дня"

    return "дней"


def get_days_until_wc2026() -> int:
    """Provide bot helper logic for get_days_until_wc2026."""
    today = datetime.now(DAILY_FACT_TIMEZONE).date()
    return max((WC2026_START_DATE - today).days, 0)


async def send_daily_fact_to_private_users(db, fact: WorldCupFact):
    """Handle asynchronous bot workflow for send_daily_fact_to_private_users."""
    users = db.query(User).all()
    archive_card = get_random_archive_card_for_daily_rubric(db)
    text = format_daily_world_cup_rubric(fact, archive_card=archive_card)

    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
            )

            try:
                from app.services.web_push import notify_web_push_subscribers_for_user_if_enabled

                notify_web_push_subscribers_for_user_if_enabled(
                    db,
                    user_id=user.id,
                    notification_key="daily_facts",
                    title="🏆 Факт дня",
                    body=text[:220],
                    url="/app",
                )
            except Exception as push_error:
                print(
                    f"Failed to send daily fact web push "
                    f"to {user.telegram_id}: {push_error}"
                )

            db.add(
                FactDeliveryLog(
                    fact_id=fact.id,
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    delivery_type="daily_private",
                )
            )

            db.commit()

        except Exception as error:
            db.rollback()
            print(
                f"Failed to send daily fact "
                f"to {user.telegram_id}: {error}"
            )


async def daily_facts_loop():
    """Handle asynchronous bot workflow for daily_facts_loop."""
    if not DAILY_FACTS_ENABLED:
        print("Daily facts are disabled")
        return

    print(
        "Daily facts loop started. "
        f"Time: {DAILY_FACT_HOUR:02d}:{DAILY_FACT_MINUTE:02d} "
        f"{DAILY_FACT_TIMEZONE}"
    )

    last_sent_date = None

    while True:
        now_local = datetime.now(DAILY_FACT_TIMEZONE)

        should_send = (
                now_local.hour == DAILY_FACT_HOUR
                and now_local.minute == DAILY_FACT_MINUTE
                and last_sent_date != now_local.date()
        )

        if should_send:
            db = SessionLocal()

            try:
                # Since the tournament has started, the morning rubric is now a daily
                # match/prognosis summary instead of Fact of the Day + archive.
                if DAILY_FACT_TARGET == "group":
                    await send_daily_match_summary_to_league_chats(db)
                    await send_daily_match_summary_to_private_users(db)

                elif DAILY_FACT_TARGET == "both":
                    await send_daily_match_summary_to_league_chats(db)
                    await send_daily_match_summary_to_private_users(db)

                else:
                    await send_daily_match_summary_to_private_users(db)

                last_sent_date = now_local.date()

            finally:
                db.close()

        await asyncio.sleep(30)


async def send_fact_by_category(
    message: Message,
    db,
    category: str | None,
    delivery_type: str = "manual",
):
    """Handle asynchronous bot workflow for send_fact_by_category."""
    query = db.query(WorldCupFact).filter(
        WorldCupFact.is_active == True,
        WorldCupFact.needs_verification == False,
    )

    if category:
        query = query.filter(WorldCupFact.category == category)

    facts = query.all()

    if not facts:
        await message.answer(
            "Фактов по такой категории пока нет.\n\n"
            "Попробуй выбрать другую категорию: /fact"
        )
        return

    fact = random.choice(facts)

    user, _ = get_or_create_user(db, message.from_user)

    db.add(
        FactDeliveryLog(
            fact_id=fact.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            delivery_type=delivery_type,
        )
    )
    db.commit()

    category_text = FACT_QUIZ_CATEGORIES.get(category or "any", "🎲 Любая категория")

    await message.answer(
        f"{category_text}\n\n"
        f"{format_world_cup_fact(fact)}"
    )

