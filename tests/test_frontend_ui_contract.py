from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "app/miniapp_frontend/src/main.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "app/miniapp_frontend/src/styles.css").read_text(encoding="utf-8")


def test_header_tracks_are_exact_halves_and_thirds():
    assert "grid-template-columns: repeat(6, minmax(0, 1fr));" in CSS
    assert "grid-column: 1 / 4;" in CSS
    assert "grid-column: 4 / 7;" in CSS
    assert "grid-column: 1 / 3;" in CSS
    assert "grid-column: 3 / 5;" in CSS
    assert "grid-column: 5 / 7;" in CSS
    canonical = CSS.split("/* Canonical tournament header and club identity (v3.9.15) */", 1)[1]
    assert "max-width: none;" in canonical
    assert "justify-self: stretch;" in canonical


def test_country_flag_is_beside_club_name_not_crest_overlay():
    assert "function TeamNameWithCountry" in MAIN
    assert "showCountry={Boolean(match.home_logo)}" in MAIN
    assert "showCountry={Boolean(match.away_logo)}" in MAIN
    assert "club-mark-country" not in MAIN
    assert "club-mark-country" not in CSS


def test_club_crest_is_contained_for_tall_and_wide_assets():
    block = CSS.split(".club-mark > .club-mark-logo {", 1)[1].split("}", 1)[0]
    assert "object-fit: contain;" in block
    assert "object-position: center;" in block
    assert "max-width: 100%;" in block
    assert "max-height: 100%;" in block


def test_compact_match_card_actions_and_country_flag_geometry():
    assert 'flagClassName="team-country-flag"' in MAIN
    country = CSS.split('/* v3.9.18 — compact match actions and stable country-flag geometry */', 1)[1]
    assert '.team-name-with-country > .flag.team-country-flag' in country
    assert 'width: 22px;' in country
    assert 'height: 16px;' in country
    assert 'grid-template-columns: repeat(3, minmax(0, 1fr));' in country
    assert 'className="match-details-link"' not in MAIN
    assert '<span>Отец</span>' in MAIN
    assert '<span>Участ. {participantCount}</span>' in MAIN
    assert 'hideHead' in MAIN
