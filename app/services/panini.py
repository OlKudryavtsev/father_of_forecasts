"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

def get_panini_teams_from_matches(
    db,
    limit: int = 20,
) -> list[dict]:
    """
    Берем уникальные сборные из матчей текущего турнира,
    оставляем только тех, у кого найден FIFA ranking,
    сортируем по рейтингу и возвращаем топ-N.
    """

    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .all()
    )

    teams_by_key = {}

    for match in matches:
        candidates = [
            (
                getattr(match, "home_team_api_name", None) or match.home_team,
                match.home_team,
            ),
            (
                getattr(match, "away_team_api_name", None) or match.away_team,
                match.away_team,
            ),
        ]

        for api_name, display_name in candidates:
            if not api_name or api_name == "TBD":
                continue

            if api_name not in teams_by_key:
                teams_by_key[api_name] = {
                    "api_name": api_name,
                    "display_name": get_team_name_ru(display_name or api_name),
                }

    rankings = FifaRankingsStore()
    result = []

    for team in teams_by_key.values():
        ranking = rankings.get_context(team["api_name"])

        if not ranking or ranking.get("rank") is None:
            continue

        result.append(
            {
                "api_name": team["api_name"],
                "display_name": team["display_name"],
                "rank": int(ranking["rank"]),
                "flag": get_team_flag(
                    team["display_name"],
                    team["api_name"],
                ),
            }
        )

    result.sort(
        key=lambda item: (
            item["rank"],
            item["display_name"],
        )
    )

    return result[:limit]


def can_use_panini(user_id: int) -> tuple[bool, int]:
    """Provide bot helper logic for can_use_panini."""
    now = datetime.now(timezone.utc)

    last_used = PANINI_LAST_USED_BY_USER.get(user_id)

    if not last_used:
        return True, 0

    elapsed = int((now - last_used).total_seconds())
    remaining = PANINI_COOLDOWN_SECONDS - elapsed

    if remaining > 0:
        return False, remaining

    return True, 0


def mark_panini_used(user_id: int):
    """Provide bot helper logic for mark_panini_used."""
    PANINI_LAST_USED_BY_USER[user_id] = datetime.now(timezone.utc)


def generate_panini_card(
    photo_path: str,
    person_name: str,
    team_api_name: str,
    team_display_name: str,
    team_flag: str,
) -> str:
    """Provide bot helper logic for generate_panini_card."""
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is not set")

    output_path = f"/tmp/panini_result_{uuid.uuid4().hex}.png"

    prompt = (
        "Create a collectible football sticker portrait card inspired by "
        "classic football sticker album cards, but do not copy any official Panini design. "
        "Use the uploaded person photo as the identity reference. "
        "Preserve the person's facial features, approximate age, hairstyle, and general appearance. "
        f"Depict the person as a player of the {team_api_name} national football team. "
        "Use a football jersey inspired by the national team's colors, "
        "without exact official logos, federation crests, or brand marks. "
        "Make it look like a polished collectible football card: portrait framing, "
        "decorative border, stadium or graphic background, premium sports lighting, "
        "dynamic but clean composition. "
        "Leave safe margins around the player and all text. "
        "The player should be centered in the upper-middle area, with enough space below for the nameplate. "
        f"Add readable card text with player name '{person_name}' and team name '{team_display_name}'. "
        f"Include the country flag vibe: {team_flag}. "
        "Vertical portrait collectible football sticker card, approximately 2:3 aspect ratio. "
        "Full card must be visible with no cropping: include the complete head, shoulders, jersey, border, nameplate, and team label. "
        "Do not crop the top of the head or the bottom nameplate. "
        "High quality, fun, realistic-stylized."
    )

    with open(photo_path, "rb") as image_file:
        result = openai_client.images.edit(
            model=PANINI_IMAGE_MODEL,
            image=image_file,
            prompt=prompt,
            size=PANINI_IMAGE_SIZE,
            n=1,
        )

    image_base64 = result.data[0].b64_json

    with open(output_path, "wb") as file:
        file.write(base64.b64decode(image_base64))

    return output_path

