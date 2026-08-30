const UCL_TOURNAMENT_CODE = 'ucl_2026_2027';
const ACTIVE_TOURNAMENT_STORAGE_KEY = 'ff_active_tournament_code';
const UCL_EMPTY_SCORERS = {
  source: 'ucl-pending',
  items: [],
  message: 'Бомбардиры ЛЧ появятся после первых голов турнира.',
};

function apiSportsLogo(id) {
  return id ? `https://media.api-sports.io/football/teams/${id}.png` : '';
}

const UCL_CLUBS = [
  { canonical: 'AEK Athens', ru: 'АЕК Афины', flag: '🇬🇷', flagCode: 'gr', logoId: 338, aliases: ['AEK Athens FC', 'AEK'] },
  { canonical: 'Arsenal', ru: 'Арсенал', flag: '🇬🇧', flagCode: 'gb', logoId: 42, aliases: ['Arsenal FC'] },
  { canonical: 'Aston Villa', ru: 'Астон Вилла', flag: '🇬🇧', flagCode: 'gb', logoId: 66, aliases: ['Aston Villa FC'] },
  { canonical: 'Atletico Madrid', ru: 'Атлетико Мадрид', flag: '🇪🇸', flagCode: 'es', logoId: 530, aliases: ['Atlético de Madrid', 'Atleti', 'Atl. Madrid'] },
  { canonical: 'Barcelona', ru: 'Барселона', flag: '🇪🇸', flagCode: 'es', logoId: 529, aliases: ['FC Barcelona'] },
  { canonical: 'Bayern Munich', ru: 'Бавария', flag: '🇩🇪', flagCode: 'de', logoId: 157, aliases: ['Bayern München', 'FC Bayern Munich', 'Bayern'] },
  { canonical: 'Bodo/Glimt', ru: 'Будё-Глимт', flag: '🇳🇴', flagCode: 'no', logoId: 727, aliases: ['Bodø/Glimt', 'Bodoe/Glimt', 'Bodo Glimt'] },
  { canonical: 'Borussia Dortmund', ru: 'Боруссия Дортмунд', flag: '🇩🇪', flagCode: 'de', logoId: 165, aliases: ['B. Dortmund', 'Dortmund'] },
  { canonical: 'Club Brugge', ru: 'Брюгге', flag: '🇧🇪', flagCode: 'be', logoId: 569, aliases: ['Club Brugge KV', 'Brugge'] },
  { canonical: 'Como', ru: 'Комо', flag: '🇮🇹', flagCode: 'it', logoId: 895, aliases: ['Como 1907'] },
  { canonical: 'Fenerbahce', ru: 'Фенербахче', flag: '🇹🇷', flagCode: 'tr', logoId: 611, aliases: ['Fenerbahçe', 'Fenerbahce SK'] },
  { canonical: 'Feyenoord', ru: 'Фейеноорд', flag: '🇳🇱', flagCode: 'nl', logoId: 209, aliases: ['Feyenoord Rotterdam'] },
  { canonical: 'Galatasaray', ru: 'Галатасарай', flag: '🇹🇷', flagCode: 'tr', logoId: 645, aliases: ['Galatasaray SK'] },
  { canonical: 'Inter', ru: 'Интер', flag: '🇮🇹', flagCode: 'it', logoId: 505, aliases: ['Inter Milan', 'Internazionale'] },
  { canonical: 'LASK', ru: 'ЛАСК', flag: '🇦🇹', flagCode: 'at', logoId: 102, aliases: ['Lask Linz', 'LASK Linz'] },
  { canonical: 'Lens', ru: 'Ланс', flag: '🇫🇷', flagCode: 'fr', logoId: 116, aliases: ['RC Lens'] },
  { canonical: 'Leipzig', ru: 'Лейпциг', flag: '🇩🇪', flagCode: 'de', logoId: 173, aliases: ['RB Leipzig', 'RasenBallsport Leipzig'] },
  { canonical: 'Lille', ru: 'Лилль', flag: '🇫🇷', flagCode: 'fr', logoId: 79, aliases: ['LOSC Lille'] },
  { canonical: 'Liverpool', ru: 'Ливерпуль', flag: '🇬🇧', flagCode: 'gb', logoId: 40, aliases: ['Liverpool FC'] },
  { canonical: 'Manchester City', ru: 'Манчестер Сити', flag: '🇬🇧', flagCode: 'gb', logoId: 50, aliases: ['Man City'] },
  { canonical: 'Manchester United', ru: 'Манчестер Юнайтед', flag: '🇬🇧', flagCode: 'gb', logoId: 33, aliases: ['Man Utd', 'Manchester Utd'] },
  { canonical: 'Napoli', ru: 'Наполи', flag: '🇮🇹', flagCode: 'it', logoId: 492, aliases: ['SSC Napoli'] },
  { canonical: 'Paris Saint-Germain', ru: 'ПСЖ', flag: '🇫🇷', flagCode: 'fr', logoId: 85, aliases: ['Paris SG', 'PSG', 'Paris'] },
  { canonical: 'Porto', ru: 'Порту', flag: '🇵🇹', flagCode: 'pt', logoId: 212, aliases: ['FC Porto'] },
  { canonical: 'PSV Eindhoven', ru: 'ПСВ', flag: '🇳🇱', flagCode: 'nl', logoId: 197, aliases: ['PSV'] },
  { canonical: 'Real Betis', ru: 'Бетис', flag: '🇪🇸', flagCode: 'es', logoId: 543, aliases: ['Betis'] },
  { canonical: 'Real Madrid', ru: 'Реал Мадрид', flag: '🇪🇸', flagCode: 'es', logoId: 541, aliases: ['Real Madrid CF'] },
  { canonical: 'Roma', ru: 'Рома', flag: '🇮🇹', flagCode: 'it', logoId: 497, aliases: ['AS Roma'] },
  { canonical: 'Sabah', ru: 'Сабах', flag: '🇦🇿', flagCode: 'az', logoId: null, aliases: ['Sabah FK', 'Sabah FA'] },
  { canonical: 'Shakhtar Donetsk', ru: 'Шахтёр', flag: '🇺🇦', flagCode: 'ua', logoId: 550, aliases: ['Shakhtar'] },
  { canonical: 'Slavia Praha', ru: 'Славия Прага', flag: '🇨🇿', flagCode: 'cz', logoId: 558, aliases: ['Slavia Prague'] },
  { canonical: 'Slovan Bratislava', ru: 'Слован Братислава', flag: '🇸🇰', flagCode: 'sk', logoId: 447, aliases: ['S. Bratislava'] },
  { canonical: 'Sporting CP', ru: 'Спортинг', flag: '🇵🇹', flagCode: 'pt', logoId: 228, aliases: ['Sporting Lisbon', 'Sporting'] },
  { canonical: 'Stuttgart', ru: 'Штутгарт', flag: '🇩🇪', flagCode: 'de', logoId: 172, aliases: ['VfB Stuttgart'] },
  { canonical: 'Viking', ru: 'Викинг', flag: '🇳🇴', flagCode: 'no', logoId: null, aliases: ['Viking FK'] },
  { canonical: 'Villarreal', ru: 'Вильярреал', flag: '🇪🇸', flagCode: 'es', logoId: 533, aliases: ['Villarreal CF'] },
].map((club) => ({
  ...club,
  logo: club.logo || apiSportsLogo(club.logoId),
  short: (club.ru || club.canonical).split(/\s+/).map((part) => part[0]).join('').slice(0, 3).toUpperCase(),
}));

function normalizeClubName(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, ' and ')
    .toLowerCase()
    .replace(/[^a-zа-яё0-9]+/gi, '');
}

const UCL_CLUB_BY_KEY = new Map();
for (const meta of UCL_CLUBS) {
  [meta.canonical, meta.ru, ...(meta.aliases || [])].forEach((name) => {
    UCL_CLUB_BY_KEY.set(normalizeClubName(name), meta);
  });
}

function clubMeta(value) {
  const raw = String(value || '').replace(/\s+/g, ' ').trim();
  if (!raw) return null;
  const exact = UCL_CLUB_BY_KEY.get(normalizeClubName(raw));
  if (exact) return exact;
  const normalized = normalizeClubName(raw);
  return UCL_CLUBS.find((meta) => {
    const values = [meta.canonical, meta.ru, ...(meta.aliases || [])].map(normalizeClubName);
    return values.some((value) => value && normalized.includes(value));
  }) || null;
}

function readActiveTournamentCode() {
  const selectorValue = document.querySelector('.header-tournament-selector select')?.value;
  return selectorValue || localStorage.getItem(ACTIVE_TOURNAMENT_STORAGE_KEY) || '';
}

function isUclActive() {
  return readActiveTournamentCode() === UCL_TOURNAMENT_CODE;
}

function isUclTournamentRequest(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.searchParams.get('tournament_code') === UCL_TOURNAMENT_CODE || isUclActive();
  } catch (_) {
    return isUclActive();
  }
}

function decorateTeamObject(target, prefix, value, externalId) {
  const meta = clubMeta(value);
  if (!meta) return;
  target[`${prefix}_team`] = meta.ru;
  target[`${prefix}_flag`] = meta.flag;
  target[`${prefix}_flag_code`] = meta.flagCode;
  target[`${prefix}_club_logo`] = externalId ? apiSportsLogo(externalId) : meta.logo;
  target[`${prefix}_club_short`] = meta.short;
}

function transformUclPayload(value) {
  if (Array.isArray(value)) return value.map((item) => transformUclPayload(item));
  if (!value || typeof value !== 'object') return value;

  const next = {};
  for (const [key, item] of Object.entries(value)) {
    next[key] = transformUclPayload(item);
  }

  if (next.home_team) {
    decorateTeamObject(next, 'home', next.home_team_api_name || next.home_team, next.home_external_team_id);
  }
  if (next.away_team) {
    decorateTeamObject(next, 'away', next.away_team_api_name || next.away_team, next.away_external_team_id);
  }
  if (next.team && typeof next.team === 'string') {
    const meta = clubMeta(next.team);
    if (meta) next.team = meta.ru;
  }
  if (next.team?.name) {
    const meta = clubMeta(next.team.api_name || next.team.name);
    if (meta) {
      next.team = {
        ...next.team,
        name: meta.ru,
        flag: meta.flag,
        flag_code: meta.flagCode,
        logo: next.team.logo || meta.logo,
      };
    }
  }

  return next;
}

function buildUclOverviewPayload() {
  return {
    ok: true,
    tournament_code: UCL_TOURNAMENT_CODE,
    groups: [
      {
        group_code: 'ЛЧ',
        rows: UCL_CLUBS.map((meta, index) => ({
          rank: index + 1,
          team: meta.ru,
          team_id: null,
          flag: meta.flag,
          flag_code: meta.flagCode,
          played: 0,
          wins: 0,
          draws: 0,
          losses: 0,
          goals_for: 0,
          goals_against: 0,
          goal_difference: 0,
          points: 0,
          qualification_zone: index < 8 ? 'direct' : index < 24 ? 'playoff' : 'out',
        })),
      },
    ],
    default_group_codes: ['ЛЧ'],
    knockout: { stages: [], bracket: null },
    top_scorers: UCL_EMPTY_SCORERS,
  };
}

async function maybeTransformUclResponse(response, url) {
  const contentType = response.headers.get('Content-Type') || response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return response;

  try {
    const parsed = new URL(url, window.location.origin);
    const isOverview = parsed.pathname === '/api/webapp/tournament/overview';
    const isUcl = isUclTournamentRequest(url);
    if (isOverview && isUcl) {
      return new Response(JSON.stringify(buildUclOverviewPayload()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (!isUcl) return response;

    const data = await response.clone().json();
    const transformed = transformUclPayload(data);
    const headers = new Headers(response.headers);
    headers.set('Content-Type', 'application/json');
    return new Response(JSON.stringify(transformed), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  } catch (_) {
    return response;
  }
}

function installUclFetchPatch() {
  const originalFetch = window.fetch?.bind(window);
  if (!originalFetch || window.__ffUclFetchPatchInstalledV394) return;
  window.__ffUclFetchPatchInstalledV394 = true;

  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    let parsed = null;
    try {
      parsed = new URL(url, window.location.origin);
    } catch (_) {
      parsed = null;
    }

    if (parsed?.pathname === '/api/webapp/top-scorer-candidates' && isUclActive()) {
      return new Response(JSON.stringify({
        candidates: [],
        hint: 'Для ЛЧ 2026/27 выбери бомбардира вручную: начни вводить имя игрока.',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (parsed?.pathname === '/api/webapp/tournament-prediction' && isUclTournamentRequest(url)) {
      const nextInit = { ...(init || {}) };
      if (typeof nextInit.body === 'string') {
        try {
          const payload = JSON.parse(nextInit.body);
          payload.third_place = '';
          nextInit.body = JSON.stringify(payload);
        } catch (_) {
          // Leave malformed or non-JSON bodies untouched.
        }
      }
      const response = await originalFetch(input, nextInit);
      return maybeTransformUclResponse(response, url);
    }

    const response = await originalFetch(input, init);
    return maybeTransformUclResponse(response, url);
  };
}

function installUclStyles() {
  if (document.getElementById('ff-ucl-style-patch-v394')) return;
  const style = document.createElement('style');
  style.id = 'ff-ucl-style-patch-v394';
  style.textContent = `
    .ff-ucl-tournament .next-match-hero.ff-ucl-hidden-simultaneous { display: none !important; }

    .ff-ucl-inline-flag {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1.35em;
      height: 1.35em;
      margin-right: 0.35em;
      vertical-align: -0.16em;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      font-size: 0.95em;
      line-height: 1;
      flex: 0 0 auto;
    }

    .ff-ucl-club-logo {
      width: 86px;
      height: 86px;
      border-radius: 24px;
      background: rgba(255,255,255,0.96);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 14px 32px rgba(0,0,0,.24);
      overflow: hidden;
      flex: 0 0 auto;
    }
    .ff-ucl-club-logo img {
      width: 72%;
      height: 72%;
      object-fit: contain;
      display: block;
    }
    .ff-ucl-club-logo span {
      color: #0f172a;
      font-weight: 900;
      font-size: 24px;
      letter-spacing: -0.04em;
    }
    .ff-ucl-club-logo.logo-failed img { display: none; }
    .ff-ucl-club-logo.logo-failed span { display: inline !important; }

    .ff-ucl-tournament .match-teams .team-side > .flag,
    .ff-ucl-tournament .detail-team > .flag,
    .ff-ucl-tournament .live-match-team > .flag {
      display: none !important;
    }

    .ff-ucl-tournament .group-table-card.group-ЛЧ {
      overflow: hidden;
      border-color: rgba(96, 165, 250, .55);
    }
    .ff-ucl-tournament .group-table-card.group-ЛЧ .group-header p {
      font-size: 13px;
      line-height: 1.35;
    }
    .ff-ucl-tournament .group-table-card.group-ЛЧ .standings-table {
      display: block;
      width: 100%;
      overflow-x: auto;
      padding-bottom: 4px;
      -webkit-overflow-scrolling: touch;
    }
    .ff-ucl-tournament .group-table-card.group-ЛЧ .standings-row {
      display: grid !important;
      grid-template-columns: 40px minmax(190px, 1.6fr) 40px 40px 40px 40px 58px 42px 42px !important;
      min-width: 620px;
      align-items: center;
      column-gap: 8px;
    }
    .ff-ucl-tournament .group-table-card.group-ЛЧ .standings-row .team-name {
      min-width: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .ff-ucl-tournament .group-table-card.group-ЛЧ .standings-row .team-name .ff-ucl-inline-flag {
      display: none;
    }

    .league-status-row {
      gap: 8px;
    }
    .league-status {
      flex-wrap: wrap;
      row-gap: 8px;
      max-width: 100%;
      align-items: center;
    }
    .header-tournament-selector,
    .header-league-selector {
      min-width: 0;
      max-width: min(46vw, 220px);
    }
    .header-tournament-selector select,
    .header-league-name {
      max-width: 150px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .league-status .divider {
      opacity: .35;
    }
    @media (max-width: 720px) {
      .league-status-row {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        align-items: start;
      }
      .league-status {
        padding: 7px 9px;
        border-radius: 22px;
      }
      .header-league-divider {
        display: none !important;
      }
      .league-status .live-countdown {
        order: 20;
        flex-basis: auto;
      }
      .league-status .points {
        order: 21;
      }
      .league-status .muted {
        order: 22;
      }
    }
  `;
  document.head.appendChild(style);
}

function patchSimultaneousHeroForUcl() {
  const oldNote = document.querySelector('.ff-ucl-schedule-note');
  if (oldNote && !isUclActive()) oldNote.remove();
  if (!isUclActive()) return;

  const hero = document.querySelector('.next-match-hero');
  if (!hero) return;
  const text = (hero.textContent || '').replace(/\s+/g, ' ');
  const match = text.match(/(\d+)\s+матч[а-я]*\s+стартуют\s+одновременно/i);
  const count = match ? Number(match[1]) : 0;
  if (count <= 12) return;

  hero.classList.add('ff-ucl-hidden-simultaneous');
}

function elementTextWithoutPatch(element) {
  if (!element) return '';
  const clone = element.cloneNode(true);
  clone.querySelectorAll?.('.ff-ucl-inline-flag,.ff-ucl-club-logo').forEach((node) => node.remove());
  return (clone.textContent || '')
    .replace(/[🇦-🇿]{2}/gu, '')
    .replace(/🏴/gu, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function metaFromElement(element) {
  const text = elementTextWithoutPatch(element);
  return clubMeta(text);
}

function makeClubLogo(meta) {
  const logo = document.createElement('span');
  logo.className = 'ff-ucl-club-logo';
  logo.title = meta.ru;
  logo.setAttribute('aria-label', `Эмблема: ${meta.ru}`);

  if (meta.logo) {
    const img = document.createElement('img');
    img.src = meta.logo;
    img.alt = '';
    img.loading = 'lazy';
    img.onerror = () => {
      logo.classList.add('logo-failed');
    };
    logo.appendChild(img);
  }

  const fallback = document.createElement('span');
  fallback.textContent = meta.short || meta.flag;
  fallback.style.display = meta.logo ? 'none' : 'inline';
  logo.appendChild(fallback);

  return logo;
}

function addCountryFlagToLabel(label, meta) {
  if (!label || label.querySelector?.('.ff-ucl-inline-flag')) return;
  const flag = document.createElement('span');
  flag.className = 'ff-ucl-inline-flag';
  flag.textContent = meta.flag;
  flag.setAttribute('aria-hidden', 'true');
  label.prepend(flag);
}

function decorateTeamSide(side) {
  if (!side || side.dataset.ffUclLogoDecorated === '1') return;
  const label = side.querySelector('strong') || side.querySelector('.team-name') || side;
  const meta = metaFromElement(label);
  if (!meta) return;

  addCountryFlagToLabel(label, meta);

  const directFlag = Array.from(side.children || []).find((node) => node.classList?.contains('flag'));
  if (directFlag) {
    directFlag.replaceWith(makeClubLogo(meta));
  } else if (!side.querySelector('.ff-ucl-club-logo') && (side.classList.contains('team-side') || side.classList.contains('detail-team') || side.classList.contains('live-match-team'))) {
    side.insertBefore(makeClubLogo(meta), side.firstChild);
  }

  side.dataset.ffUclLogoDecorated = '1';
}

function decorateVisibleClubFlagsAndLogos() {
  if (!isUclActive()) return;

  document.querySelectorAll([
    '.match-teams .team-side',
    '.next-match-hero .team-side',
    '.match-details-hero .detail-team',
    '.live-match-team',
  ].join(',')).forEach((side) => decorateTeamSide(side));

  document.querySelectorAll([
    '.team-name',
    '.match-row strong',
    '.prediction-match strong',
    '.modal-card strong',
  ].join(',')).forEach((element) => {
    const meta = metaFromElement(element);
    if (meta) addCountryFlagToLabel(element, meta);
  });
}

function patchUclTournamentTexts() {
  if (!isUclActive()) return;
  document.querySelectorAll('.group-table-card.group-ЛЧ .group-header h2').forEach((element) => {
    if ((element.textContent || '').includes('Группа')) element.textContent = 'Общий этап ЛЧ';
  });
  document.querySelectorAll('.group-table-card.group-ЛЧ .group-header p').forEach((element) => {
    element.textContent = '1–8 — 1/8 финала · 9–24 — стыковые матчи · 25–36 — вылет';
  });
  document.querySelectorAll('.group-table-card.group-ЛЧ .standings-row.headings span').forEach((element) => {
    if ((element.textContent || '').trim().toLowerCase() === 'сборная') element.textContent = 'Клуб';
  });
}

function hideThirdPlaceElementsForUcl() {
  const active = isUclActive();
  document.documentElement.classList.toggle('ff-ucl-tournament', active);
  if (!active) return;

  const candidates = document.querySelectorAll([
    '.tournament-mini-card',
    '.tournament-mini-card-edit',
    '.modal-card article',
    '.modal-card button',
    '.modal-card label',
    '.modal-card .form-row',
    '.modal-card .field',
    '.modal-card .picker-section',
  ].join(','));

  candidates.forEach((element) => {
    const text = (element.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const aria = (element.getAttribute('aria-label') || '').toLowerCase();
    const isThirdPlace = text.includes('3-е место') || text.includes('3 место') || aria.includes('third_place') || aria.includes('3-е место');
    if (!isThirdPlace) return;
    element.dataset.ffUclHiddenThirdPlace = '1';
    element.setAttribute('hidden', '');
  });

  document.querySelectorAll('.tournament-mini-actions span').forEach((element) => {
    const match = String(element.textContent || '').trim().match(/^(\d+)\/4$/);
    if (!match) return;
    const value = Math.min(Number(match[1] || 0), 3);
    element.textContent = `${value}/3`;
  });
}

function installUclDomPatch() {
  installUclStyles();
  const run = () => {
    hideThirdPlaceElementsForUcl();
    patchSimultaneousHeroForUcl();
    decorateVisibleClubFlagsAndLogos();
    patchUclTournamentTexts();
  };
  run();

  document.addEventListener('change', (event) => {
    if (event.target?.matches?.('.header-tournament-selector select')) {
      window.setTimeout(run, 0);
      window.setTimeout(run, 250);
      window.setTimeout(run, 900);
    }
  }, true);

  const observer = new MutationObserver(() => run());
  observer.observe(document.documentElement, { childList: true, subtree: true });
}

installUclFetchPatch();
installUclDomPatch();
