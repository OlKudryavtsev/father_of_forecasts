from pathlib import Path
import json
import re

ROOT = Path('.')
MAIN = ROOT / 'app/miniapp_frontend/src/main.jsx'
CSS = ROOT / 'app/miniapp_frontend/src/styles.css'
PKG = ROOT / 'app/miniapp_frontend/package.json'
LOCK = ROOT / 'app/miniapp_frontend/package-lock.json'
TEST = ROOT / 'tests/test_frontend_ui_contract.py'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly 1 occurrence, found {count}')
    return text.replace(old, new, 1)


main = MAIN.read_text(encoding='utf-8')

old_logo_branch = '''  if (logo && !logoFailed) {
    return (
      <span className={`${className} club-mark`.trim()} title={name} aria-label={name ? `Эмблема: ${name}` : 'Эмблема клуба'}>
        <img
          className="club-mark-logo"
          src={logo}
          alt=""
          loading="lazy"
          onError={() => setLogoFailed(true)}
        />
        {(hasCode || emoji) && (
          <span className="club-mark-country" aria-label={name ? `Страна клуба: ${name}` : 'Страна клуба'}>
            {hasCode
              ? <img src={`https://flagcdn.com/${normalizedCode}.svg`} alt="" loading="lazy" />
              : <span>{emoji}</span>}
          </span>
        )}
      </span>
    );
  }
'''
new_logo_branch = '''  if (logo && !logoFailed) {
    return (
      <span className={`${className} club-mark`.trim()} title={name} aria-label={name ? `Эмблема: ${name}` : 'Эмблема клуба'}>
        <img
          className="club-mark-logo"
          src={logo}
          alt=""
          loading="lazy"
          onError={() => setLogoFailed(true)}
        />
      </span>
    );
  }
'''
main = replace_once(main, old_logo_branch, new_logo_branch, 'remove crest-overlay country flag')

helper = '''
function TeamNameWithCountry({ code, emoji, name = '', showCountry = false, className = '' }) {
  return (
    <span className={`team-name-with-country ${className}`.trim()}>
      {showCountry && <TeamFlag code={code} emoji={emoji} name={name} size="mini" />}
      <strong>{name}</strong>
    </span>
  );
}

'''
main = replace_once(main, '\nfunction Icon({ name, className = \'\' }) {', '\n' + helper + 'function Icon({ name, className = \'\' }) {', 'insert TeamNameWithCountry')

# Systematically update the vertically-stacked match identities (home/away in
# the hero, match cards and any equivalent card with the same canonical markup).
stacked_pattern = re.compile(
    r'(?P<indent>^[ \t]*)<TeamFlag code=\{(?P<code>[A-Za-z0-9_.]+)\} emoji=\{(?P<emoji>[A-Za-z0-9_.]+)\} logo=\{(?P<logo>[A-Za-z0-9_.]+)\} name=\{(?P<name>[A-Za-z0-9_.]+)\} />\n'
    r'(?P=indent)<strong>\{(?P=name)\}</strong>',
    re.MULTILINE,
)

def stacked_repl(match: re.Match) -> str:
    d = match.groupdict()
    return (
        f'{d["indent"]}<TeamFlag code={{{d["code"]}}} emoji={{{d["emoji"]}}} logo={{{d["logo"]}}} name={{{d["name"]}}} />\n'
        f'{d["indent"]}<TeamNameWithCountry code={{{d["code"]}}} emoji={{{d["emoji"]}}} name={{{d["name"]}}} showCountry={{Boolean({d["logo"]})}} />'
    )

main, stacked_count = stacked_pattern.subn(stacked_repl, main)
if stacked_count < 4:
    raise SystemExit(f'stacked club identities: expected at least 4 replacements, found {stacked_count}')

old_ucl_row = '<td><span className="ucl-table-club"><TeamFlag code={row.flag_code} emoji={row.flag} logo={row.logo} name={row.name} size="mini" /><strong>{row.name}</strong></span></td>'
new_ucl_row = '<td><span className="ucl-table-club"><TeamFlag code={row.flag_code} emoji={row.flag} logo={row.logo} name={row.name} size="mini" /><TeamNameWithCountry code={row.flag_code} emoji={row.flag} name={row.name} showCountry={Boolean(row.logo)} /></span></td>'
main = replace_once(main, old_ucl_row, new_ucl_row, 'UCL standings club identity')

old_filter = '''                <TeamFlag code={team.flag_code} emoji={team.flag} logo={team.logo} name={team.name} size="mini" />
                <span>{team.name}</span>'''
new_filter = '''                <TeamFlag code={team.flag_code} emoji={team.flag} logo={team.logo} name={team.name} size="mini" />
                <TeamNameWithCountry code={team.flag_code} emoji={team.flag} name={team.name} showCountry={Boolean(team.logo)} className="filter-team-name" />'''
main = replace_once(main, old_filter, new_filter, 'team filter club identity')

old_hub_home = '<span><TeamFlag code={match.home_flag_code} emoji={match.home_flag} logo={match.home_logo} name={match.home_team} size="mini" /> {match.home_team}</span>'
new_hub_home = '<span className="hub-club-line"><TeamFlag code={match.home_flag_code} emoji={match.home_flag} logo={match.home_logo} name={match.home_team} size="mini" /><TeamNameWithCountry code={match.home_flag_code} emoji={match.home_flag} name={match.home_team} showCountry={Boolean(match.home_logo)} /></span>'
if old_hub_home in main:
    main = main.replace(old_hub_home, new_hub_home, 1)

old_hub_away = '<span>{match.away_team} <TeamFlag code={match.away_flag_code} emoji={match.away_flag} logo={match.away_logo} name={match.away_team} size="mini" /></span>'
new_hub_away = '<span className="hub-club-line away"><TeamFlag code={match.away_flag_code} emoji={match.away_flag} logo={match.away_logo} name={match.away_team} size="mini" /><TeamNameWithCountry code={match.away_flag_code} emoji={match.away_flag} name={match.away_team} showCountry={Boolean(match.away_logo)} /></span>'
if old_hub_away in main:
    main = main.replace(old_hub_away, new_hub_away, 1)

if 'club-mark-country' in main:
    raise SystemExit('club-mark-country overlay still exists in main.jsx')

MAIN.write_text(main, encoding='utf-8')

css = CSS.read_text(encoding='utf-8')

# The generic flag image is intentionally cropped to a flag aspect ratio.  A
# club crest is not a flag, so make generic cover rules explicitly exclude it.
def isolate_crest_from_flag_cover(match: re.Match) -> str:
    selector, body = match.group(1), match.group(2)
    if 'flag-img' not in selector or 'object-fit: cover' not in body or 'club-mark' in selector:
        return match.group(0)
    selector = selector.replace('.flag-img', '.flag-img:not(.club-mark)')
    return selector + '{' + body + '}'

css = re.sub(r'([^{}]+)\{([^{}]*object-fit:\s*cover;[^{}]*)\}', isolate_crest_from_flag_cover, css)

old_header_sizing = '''.league-status > .header-tournament-selector,
.league-status > .header-league-selector,
.league-status > .header-stat {
  width: 100%;
  min-width: 0;
  height: 40px;
  min-height: 40px;
  max-height: 40px;
  margin: 0;
  box-sizing: border-box;
  border-radius: 13px;
  overflow: hidden;
}
'''
new_header_sizing = '''.league-status > .header-tournament-selector,
.league-status > .header-league-selector,
.league-status > .header-stat {
  width: 100%;
  min-width: 0;
  max-width: none;
  height: 40px;
  min-height: 40px;
  max-height: 40px;
  margin: 0;
  box-sizing: border-box;
  border-radius: 13px;
  overflow: hidden;
  justify-self: stretch;
  align-self: stretch;
  flex: 0 0 auto;
  flex-basis: auto;
}
'''
css = replace_once(css, old_header_sizing, new_header_sizing, 'canonical header sizing reset')

old_header_inner = '''.league-status .header-tournament-selector select,
.league-status .header-league-trigger,
.league-status .header-league-name {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
'''
new_header_inner = '''.league-status .header-tournament-selector select,
.league-status .header-league-trigger,
.league-status .header-league-name {
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.league-status > .header-tournament-selector select,
.league-status > .header-league-selector .header-league-trigger {
  width: 100%;
  min-width: 0;
  flex: 1 1 auto;
}
'''
css = replace_once(css, old_header_inner, new_header_inner, 'header inner controls stretch')

# Club crest: all source aspect ratios must fit inside the square badge.  This
# specifically prevents tall marks such as Liverpool from being cropped.
old_logo_css = '''.club-mark > .club-mark-logo {
  display: block;
  width: 100%;
  height: 100%;
  padding: 9px;
  object-fit: contain;
  border-radius: inherit;
}
'''
new_logo_css = '''.club-mark > .club-mark-logo {
  display: block;
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  padding: 9px;
  object-fit: contain;
  object-position: center;
  border-radius: inherit;
}
'''
css = replace_once(css, old_logo_css, new_logo_css, 'canonical crest contain sizing')

# Country flags are no longer overlays on top of/below the crest. Remove the
# obsolete positioning rules and render them beside the team name instead.
css = re.sub(r'\n\.club-mark-country\s*\{[^{}]*\}\n', '\n', css)
css = re.sub(r'\n\.club-mark-country\s*>\s*img\s*\{[^{}]*\}\n', '\n', css)
css = re.sub(r'\n\.club-mark\.mini\s+\.club-mark-country\s*\{[^{}]*\}\n', '\n', css)
css = re.sub(r'\n\.next-match-team\s+\.club-mark-country\s*\{[^{}]*\}\n', '\n', css)

old_club_mark_overflow = '''  overflow: visible;
  font-size: 0;
}

.club-mark > .club-mark-logo'''
new_club_mark_overflow = '''  overflow: hidden;
  font-size: 0;
}

.club-mark > .club-mark-logo'''
css = replace_once(css, old_club_mark_overflow, new_club_mark_overflow, 'crest container overflow')

identity_css = '''

.team-name-with-country {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 0;
  max-width: 100%;
}

.team-name-with-country > .flag.mini {
  width: 20px;
  min-width: 20px;
  height: 15px;
  flex: 0 0 20px;
  border-radius: 3px;
  overflow: hidden;
  font-size: 14px;
}

.team-name-with-country > .flag.mini > img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.team-name-with-country > strong {
  min-width: 0;
  max-width: 100%;
}

.team-side .team-name-with-country,
.next-match-team .team-name-with-country {
  width: 100%;
}

.ucl-table-club .team-name-with-country,
.hub-club-line .team-name-with-country {
  flex: 1 1 auto;
  justify-content: flex-start;
  overflow: hidden;
}

.hub-club-line {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.match-center-team-options .filter-team-name {
  justify-content: flex-start;
  overflow: hidden;
}
'''
anchor = '''.club-mark.mini > .club-mark-logo {
  padding: 3px;
}
'''
css = replace_once(css, anchor, anchor + identity_css, 'club identity layout CSS')

if 'club-mark-country' in css:
    raise SystemExit('obsolete club-mark-country CSS still exists')

CSS.write_text(css, encoding='utf-8')

package = json.loads(PKG.read_text(encoding='utf-8'))
if package.get('version') != '3.9.16':
    raise SystemExit(f'Unexpected package version: {package.get("version")}')
package['version'] = '3.9.17'
PKG.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

lock = json.loads(LOCK.read_text(encoding='utf-8'))
lock['version'] = '3.9.17'
if '' in lock.get('packages', {}):
    lock['packages']['']['version'] = '3.9.17'
LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

TEST.write_text('''from pathlib import Path\n\n\nROOT = Path(__file__).resolve().parents[1]\nMAIN = (ROOT / "app/miniapp_frontend/src/main.jsx").read_text(encoding="utf-8")\nCSS = (ROOT / "app/miniapp_frontend/src/styles.css").read_text(encoding="utf-8")\n\n\ndef test_header_tracks_are_exact_halves_and_thirds():\n    assert "grid-template-columns: repeat(6, minmax(0, 1fr));" in CSS\n    assert "grid-column: 1 / 4;" in CSS\n    assert "grid-column: 4 / 7;" in CSS\n    assert "grid-column: 1 / 3;" in CSS\n    assert "grid-column: 3 / 5;" in CSS\n    assert "grid-column: 5 / 7;" in CSS\n    canonical = CSS.split("/* Canonical tournament header and club identity (v3.9.15) */", 1)[1]\n    assert "max-width: none;" in canonical\n    assert "justify-self: stretch;" in canonical\n\n\ndef test_country_flag_is_beside_club_name_not_crest_overlay():\n    assert "function TeamNameWithCountry" in MAIN\n    assert "showCountry={Boolean(match.home_logo)}" in MAIN\n    assert "showCountry={Boolean(match.away_logo)}" in MAIN\n    assert "club-mark-country" not in MAIN\n    assert "club-mark-country" not in CSS\n\n\ndef test_club_crest_is_contained_for_tall_and_wide_assets():\n    block = CSS.split(".club-mark > .club-mark-logo {", 1)[1].split("}", 1)[0]\n    assert "object-fit: contain;" in block\n    assert "object-position: center;" in block\n    assert "max-width: 100%;" in block\n    assert "max-height: 100%;" in block\n''', encoding='utf-8')

print(f'patched main.jsx ({stacked_count} stacked identities), styles.css, version 3.9.17 and regression tests')
