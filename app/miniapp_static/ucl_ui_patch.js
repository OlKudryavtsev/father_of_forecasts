const UCL_TOURNAMENT_CODE = 'ucl_2026_2027';
const ACTIVE_TOURNAMENT_STORAGE_KEY = 'ff_active_tournament_code';

const UCL_CLUBS = [
  ['AEK Athens', 'АЕК Афины', '🇬🇷', 'gr', ['AEK Athens FC']],
  ['Arsenal', 'Арсенал', '🏴', 'gb-eng', []],
  ['Aston Villa', 'Астон Вилла', '🏴', 'gb-eng', []],
  ['Atletico Madrid', 'Атлетико Мадрид', '🇪🇸', 'es', ['Atlético de Madrid', 'Atleti', 'Atl. Madrid']],
  ['Barcelona', 'Барселона', '🇪🇸', 'es', ['FC Barcelona']],
  ['Bayern Munich', 'Бавария', '🇩🇪', 'de', ['Bayern München', 'FC Bayern Munich', 'Bayern']],
  ['Bodo/Glimt', 'Будё-Глимт', '🇳🇴', 'no', ['Bodø/Glimt', 'Bodoe/Glimt', 'Bodo Glimt']],
  ['Borussia Dortmund', 'Боруссия Дортмунд', '🇩🇪', 'de', ['B. Dortmund', 'Dortmund']],
  ['Club Brugge', 'Брюгге', '🇧🇪', 'be', ['Club Brugge KV']],
  ['Como', 'Комо', '🇮🇹', 'it', []],
  ['Fenerbahce', 'Фенербахче', '🇹🇷', 'tr', ['Fenerbahçe']],
  ['Feyenoord', 'Фейеноорд', '🇳🇱', 'nl', []],
  ['Galatasaray', 'Галатасарай', '🇹🇷', 'tr', []],
  ['Inter', 'Интер', '🇮🇹', 'it', ['Inter Milan', 'Internazionale']],
  ['LASK', 'ЛАСК', '🇦🇹', 'at', ['Lask Linz', 'LASK Linz']],
  ['Lens', 'Ланс', '🇫🇷', 'fr', ['RC Lens']],
  ['Leipzig', 'Лейпциг', '🇩🇪', 'de', ['RB Leipzig', 'RasenBallsport Leipzig']],
  ['Lille', 'Лилль', '🇫🇷', 'fr', ['LOSC Lille']],
  ['Liverpool', 'Ливерпуль', '🏴', 'gb-eng', []],
  ['Manchester City', 'Манчестер Сити', '🏴', 'gb-eng', ['Man City']],
  ['Manchester United', 'Манчестер Юнайтед', '🏴', 'gb-eng', ['Man Utd', 'Manchester Utd']],
  ['Napoli', 'Наполи', '🇮🇹', 'it', ['SSC Napoli']],
  ['Paris Saint-Germain', 'ПСЖ', '🇫🇷', 'fr', ['Paris SG', 'PSG', 'Paris']],
  ['Porto', 'Порту', '🇵🇹', 'pt', ['FC Porto']],
  ['PSV Eindhoven', 'ПСВ', '🇳🇱', 'nl', ['PSV']],
  ['Real Betis', 'Бетис', '🇪🇸', 'es', ['Betis']],
  ['Real Madrid', 'Реал Мадрид', '🇪🇸', 'es', []],
  ['Roma', 'Рома', '🇮🇹', 'it', ['AS Roma']],
  ['Sabah', 'Сабах', '🇦🇿', 'az', ['Sabah FK', 'Sabah FA']],
  ['Shakhtar Donetsk', 'Шахтёр', '🇺🇦', 'ua', ['Shakhtar']],
  ['Slavia Praha', 'Славия Прага', '🇨🇿', 'cz', ['Slavia Prague']],
  ['Slovan Bratislava', 'Слован Братислава', '🇸🇰', 'sk', ['S. Bratislava']],
  ['Sporting CP', 'Спортинг', '🇵🇹', 'pt', ['Sporting Lisbon', 'Sporting']],
  ['Stuttgart', 'Штутгарт', '🇩🇪', 'de', ['VfB Stuttgart']],
  ['Viking', 'Викинг', '🇳🇴', 'no', ['Viking FK']],
  ['Villarreal', 'Вильярреал', '🇪🇸', 'es', ['Villarreal CF']],
];

function normalizeClubName(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, ' and ')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '');
}

const UCL_CLUB_BY_KEY = new Map();
const UCL_CLUB_BY_RU = new Map();
for (const [canonical, ru, flag, flagCode, aliases] of UCL_CLUBS) {
  const meta = { canonical, ru, flag, flagCode };
  UCL_CLUB_BY_RU.set(ru, meta);
  [canonical, ...(aliases || [])].forEach((name) => UCL_CLUB_BY_KEY.set(normalizeClubName(name), meta));
}
const UCL_CLUB_ALIASES = [...UCL_CLUBS.flatMap(([canonical, ru, flag, flagCode, aliases]) => {
  const meta = { canonical, ru, flag, flagCode };
  return [canonical, ru, ...(aliases || [])].map((name) => ({ name, meta }));
})].sort((left, right) => right.name.length - left.name.length);

function clubMeta(value) {
  const raw = String(value || '').trim();
  return UCL_CLUB_BY_RU.get(raw) || UCL_CLUB_BY_KEY.get(normalizeClubName(raw));
}

function translateKnownClubText(value) {
  if (typeof value !== 'string' || !value) return value;
  const exact = clubMeta(value);
  if (exact) return exact.ru;
  let result = value;
  for (const { name, meta } of UCL_CLUB_ALIASES) {
    if (!result.includes(name)) continue;
    result = result.split(name).join(meta.ru);
  }
  return result;
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

function decorateTeamObject(target, prefix, value) {
  const meta = clubMeta(value);
  if (!meta) return;
  target[`${prefix}_team`] = meta.ru;
  target[`${prefix}_flag`] = meta.flag;
  target[`${prefix}_flag_code`] = meta.flagCode;
}

function transformUclPayload(value) {
  if (Array.isArray(value)) return value.map((item) => transformUclPayload(item));
  if (value && typeof value === 'object') {
    const next = {};
    for (const [key, item] of Object.entries(value)) {
      next[key] = transformUclPayload(item);
    }

    if (next.home_team) decorateTeamObject(next, 'home', next.home_team_api_name || next.home_team);
    if (next.away_team) decorateTeamObject(next, 'away', next.away_team_api_name || next.away_team);
    if (next.team?.name) {
      const meta = clubMeta(next.team.api_name || next.team.name);
      if (meta) next.team = { ...next.team, name: meta.ru, flag: meta.flag, flag_code: meta.flagCode };
    }

    for (const key of ['name', 'team_name', 'champion', 'runner_up', 'third_place']) {
      if (typeof next[key] === 'string') next[key] = translateKnownClubText(next[key]);
    }
    return next;
  }
  return typeof value === 'string' ? translateKnownClubText(value) : value;
}

async function maybeTransformUclResponse(response, url) {
  if (!isUclTournamentRequest(url)) return response;
  const contentType = response.headers.get('Content-Type') || response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return response;

  try {
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
  if (!originalFetch || window.__ffUclFetchPatchInstalled) return;
  window.__ffUclFetchPatchInstalled = true;

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
        hint: 'Для ЛЧ 2026/27 выбери бомбардира вручную: начни вводить имя игрока.'
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
  if (document.getElementById('ff-ucl-style-patch')) return;
  const style = document.createElement('style');
  style.id = 'ff-ucl-style-patch';
  style.textContent = `
    .ff-ucl-tournament .next-match-hero.ff-ucl-hidden-simultaneous { display: none !important; }
    .ff-ucl-schedule-note { margin: 16px 0; padding: 14px 16px; border-radius: 18px; background: rgba(96, 165, 250, 0.12); border: 1px solid rgba(96, 165, 250, 0.28); color: inherit; }
    .ff-ucl-schedule-note strong { display: block; margin-bottom: 4px; }
    .ff-ucl-schedule-note small { color: rgba(203, 213, 225, 0.78); }
    .ff-ucl-tournament .tournament-mini-card,
    .ff-ucl-tournament .tournament-mini-card-main { min-width: 0; max-width: 100%; }
    .ff-ucl-inline-flag { display: inline-flex; align-items: center; justify-content: center; width: 1.45em; height: 1.45em; margin-right: 0.35em; vertical-align: -0.15em; border-radius: 999px; background: rgba(255,255,255,0.08); font-size: 0.95em; line-height: 1; }
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
  if (document.querySelector('.ff-ucl-schedule-note')) return;
  const note = document.createElement('section');
  note.className = 'ff-ucl-schedule-note';
  note.innerHTML = '<strong>Календарь ЛЧ загружен</strong><small>Показываю матчи по турам. Блок массового прогноза скрыт, потому что провайдер сначала отдал общий placeholder для всех матчей.</small>';
  hero.parentNode?.insertBefore(note, hero);
}

function visibleClubMeta(text) {
  const trimmed = String(text || '').replace(/\s+/g, ' ').trim();
  if (!trimmed) return null;
  if (/^[\u{1F1E6}-\u{1F1FF}\u{1F3F4}]/u.test(trimmed)) return null;
  const exact = clubMeta(trimmed);
  if (exact) return exact;
  return null;
}

function decorateVisibleClubFlags() {
  if (!isUclActive()) return;
  const selectors = [
    '.next-match-hero strong',
    '.next-match-slide strong',
    '.live-match-team strong',
    '.match-card strong',
    '.match-team strong',
    '.match-row strong',
    '.prediction-match strong',
    '.modal-card strong',
    '.team-name',
  ].join(',');

  document.querySelectorAll(selectors).forEach((element) => {
    if (element.querySelector?.('.ff-ucl-inline-flag')) return;
    const meta = visibleClubMeta(element.textContent);
    if (!meta) return;
    const flag = document.createElement('span');
    flag.className = 'ff-ucl-inline-flag';
    flag.textContent = meta.flag;
    flag.setAttribute('aria-hidden', 'true');
    element.prepend(flag);
  });
}

function hideThirdPlaceElementsForUcl() {
  const active = isUclActive();
  document.documentElement.classList.toggle('ff-ucl-tournament', active);

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

    if (active) {
      element.dataset.ffUclHiddenThirdPlace = '1';
      element.setAttribute('hidden', '');
    } else if (element.dataset.ffUclHiddenThirdPlace === '1') {
      element.removeAttribute('hidden');
      delete element.dataset.ffUclHiddenThirdPlace;
    }
  });

  if (active) {
    document.querySelectorAll('.tournament-mini-actions span').forEach((element) => {
      const match = String(element.textContent || '').trim().match(/^(\d+)\/4$/);
      if (!match) return;
      const value = Math.min(Number(match[1] || 0), 3);
      element.textContent = `${value}/3`;
    });
  }
}

function installUclDomPatch() {
  installUclStyles();
  const run = () => {
    hideThirdPlaceElementsForUcl();
    patchSimultaneousHeroForUcl();
    decorateVisibleClubFlags();
  };
  run();

  document.addEventListener('change', (event) => {
    if (event.target?.matches?.('.header-tournament-selector select')) {
      window.setTimeout(run, 0);
      window.setTimeout(run, 250);
    }
  }, true);

  const observer = new MutationObserver(() => run());
  observer.observe(document.documentElement, { childList: true, subtree: true });
}

installUclFetchPatch();
installUclDomPatch();
