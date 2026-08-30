from app.services.team_identity import get_team_identity


def test_sabah_crest_uses_match_external_id_not_name_mapping():
    identity = get_team_identity("Sabah", "Sabah FK", 987654, "ucl_2026_2027")
    assert identity["name"] == "Сабах"
    assert identity["flag_code"] == "az"
    assert identity["logo"].endswith("/987654.png")


def test_missing_ucl_country_flags_are_resolved_centrally():
    assert get_team_identity("Shakhtar Donetsk", None, 1, "ucl_2026_2027")["flag_code"] == "ua"
    assert get_team_identity("VfB Stuttgart", None, 2, "ucl_2026_2027")["flag_code"] == "de"
    assert get_team_identity("Slovan Bratislava", None, 3, "ucl_2026_2027")["flag_code"] == "sk"


def test_world_cup_identity_keeps_flag_without_club_crest():
    identity = get_team_identity("Germany", "Germany", 25, "wc2026")
    assert identity["name"] == "Германия"
    assert identity["flag_code"] == "de"
    assert identity["logo"] == ""
