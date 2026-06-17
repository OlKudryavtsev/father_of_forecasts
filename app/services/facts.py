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



async def send_daily_match_summary_to_group(db):
    """Send daily match/prognosis summary to GROUP_CHAT_ID and configured league chats."""
    from app.services.matches import build_daily_match_summary_text
    from app.services.leagues import get_default_league
    from app.services.notifications import get_leagues_with_chat_id, notify_telegram_chat

    default_league = get_default_league(db)
    group_chat_id = get_group_chat_id()

    if group_chat_id and default_league:
        text = build_daily_match_summary_text(db, league_id=default_league.id)
        if await notify_telegram_chat(group_chat_id, text):
            print(f"Daily match summary sent to group chat {group_chat_id}")
    elif not group_chat_id:
        print("GROUP_CHAT_ID is not set or invalid")

    for league in get_leagues_with_chat_id(db):
        text = build_daily_match_summary_text(db, league_id=league.id)
        await notify_telegram_chat(league.chat_id, text)


async def send_daily_match_summary_to_private_users(db):
    """Send daily match/prognosis summary to private users instead of daily fact rubric."""
    from app.services.matches import build_daily_match_summary_text

    users = db.query(User).filter(User.access_status == "approved").all()
    text = build_daily_match_summary_text(db)

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
                    title="☕ Утренняя сводка",
                    body=text[:220],
                    url="/app",
                )
            except Exception as push_error:
                print(
                    f"Failed to send daily summary web push "
                    f"to {user.telegram_id}: {push_error}"
                )
        except Exception as error:
            print(
                f"Failed to send daily match summary "
                f"to {user.telegram_id}: {error}"
            )


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
    users = db.query(User).filter(User.access_status == "approved").all()
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
                    await send_daily_match_summary_to_group(db)

                elif DAILY_FACT_TARGET == "both":
                    await send_daily_match_summary_to_group(db)
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

