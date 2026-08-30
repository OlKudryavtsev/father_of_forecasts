const UCL_TOURNAMENT_CODE = 'ucl_2026_2027';
const ACTIVE_TOURNAMENT_STORAGE_KEY = 'ff_active_tournament_code';

const UCL_CLUBS = [
  ['AEK Athens','АЕК Афины','🇬🇷','gr','https://logo.clearbit.com/aekfc.gr',['AEK Athens FC']],
  ['Arsenal','Арсенал','🏴','gb-eng','https://logo.clearbit.com/arsenal.com',[]],
  ['Aston Villa','Астон Вилла','🏴','gb-eng','https://logo.clearbit.com/avfc.co.uk',[]],
  ['Atletico Madrid','Атлетико Мадрид','🇪🇸','es','https://logo.clearbit.com/atleticodemadrid.com',['Atlético de Madrid','Atleti','Atl. Madrid']],
  ['Barcelona','Барселона','🇪🇸','es','https://logo.clearbit.com/fcbarcelona.com',['FC Barcelona']],
  ['Bayern Munich','Бавария','🇩🇪','de','https://logo.clearbit.com/fcbayern.com',['Bayern München','FC Bayern Munich','Bayern']],
  ['Bodo/Glimt','Будё-Глимт','🇳🇴','no','https://logo.clearbit.com/glimt.no',['Bodø/Glimt','Bodoe/Glimt','Bodo Glimt']],
  ['Borussia Dortmund','Боруссия Дортмунд','🇩🇪','de','https://logo.clearbit.com/bvb.de',['B. Dortmund','Dortmund']],
  ['Club Brugge','Брюгге','🇧🇪','be','https://logo.clearbit.com/clubbrugge.be',['Club Brugge KV']],
  ['Como','Комо','🇮🇹','it','https://logo.clearbit.com/comofc.com',[]],
  ['Fenerbahce','Фенербахче','🇹🇷','tr','https://logo.clearbit.com/fenerbahce.org',['Fenerbahçe']],
  ['Feyenoord','Фейеноорд','🇳🇱','nl','https://logo.clearbit.com/feyenoord.com',[]],
  ['Galatasaray','Галатасарай','🇹🇷','tr','https://logo.clearbit.com/galatasaray.org',[]],
  ['Inter','Интер','🇮🇹','it','https://logo.clearbit.com/inter.it',['Inter Milan','Internazionale']],
  ['LASK','ЛАСК','🇦🇹','at','https://logo.clearbit.com/lask.at',['Lask Linz','LASK Linz']],
  ['Lens','Ланс','🇫🇷','fr','https://logo.clearbit.com/rclens.fr',['RC Lens']],
  ['Leipzig','Лейпциг','🇩🇪','de','https://logo.clearbit.com/rbleipzig.com',['RB Leipzig','RasenBallsport Leipzig']],
  ['Lille','Лилль','🇫🇷','fr','https://logo.clearbit.com/losc.fr',['LOSC Lille']],
  ['Liverpool','Ливерпуль','🏴','gb-eng','https://logo.clearbit.com/liverpoolfc.com',[]],
  ['Manchester City','Манчестер Сити','🏴','gb-eng','https://logo.clearbit.com/mancity.com',['Man City']],
  ['Manchester United','Манчестер Юнайтед','🏴','gb-eng','https://logo.clearbit.com/manutd.com',['Man Utd','Manchester Utd']],
  ['Napoli','Наполи','🇮🇹','it','https://logo.clearbit.com/sscnapoli.it',['SSC Napoli']],
  ['Paris Saint-Germain','ПСЖ','🇫🇷','fr','https://logo.clearbit.com/psg.fr',['Paris SG','PSG','Paris']],
  ['Porto','Порту','🇵🇹','pt','https://logo.clearbit.com/fcporto.pt',['FC Porto']],
  ['PSV Eindhoven','ПСВ','🇳🇱','nl','https://logo.clearbit.com/psv.nl',['PSV']],
  ['Real Betis','Бетис','🇪🇸','es','https://logo.clearbit.com/realbetisbalompie.es',['Betis']],
  ['Real Madrid','Реал Мадрид','🇪🇸','es','https://logo.clearbit.com/realmadrid.com',[]],
  ['Roma','Рома','🇮🇹','it','https://logo.clearbit.com/asroma.com',['AS Roma']],
  ['Sabah','Сабах','🇦🇿','az','https://logo.clearbit.com/sabahfc.az',['Sabah FK','Sabah FA']],
  ['Shakhtar Donetsk','Шахтёр','🇺🇦','ua','https://logo.clearbit.com/shakhtar.com',['Shakhtar']],
  ['Slavia Praha','Славия Прага','🇨🇿','cz','https://logo.clearbit.com/slavia.cz',['Slavia Prague']],
  ['Slovan Bratislava','Слован Братислава','🇸🇰','sk','https://logo.clearbit.com/skslovan.com',['S. Bratislava']],
  ['Sporting CP','Спортинг','🇵🇹','pt','https://logo.clearbit.com/sporting.pt',['Sporting Lisbon','Sporting']],
  ['Stuttgart','Штутгарт','🇩🇪','de','https://logo.clearbit.com/vfb.de',['VfB Stuttgart']],
  ['Viking','Викинг','🇳🇴','no','https://logo.clearbit.com/vikingfotball.no',['Viking FK']],
  ['Villarreal','Вильярреал','🇪🇸','es','https://logo.clearbit.com/villarrealcf.es',['Villarreal CF']],
];

function normalizeClubName(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/&/g, ' and ').toLowerCase().replace(/[^a-z0-9]+/g, '');
}

const UCL_CLUB_BY_KEY = new Map();
const UCL_CLUB_BY_RU = new Map();
const UCL_CLUB_ALIASES = [];
for (const [canonical, ru, flag, flagCode, logo, aliases] of UCL_CLUBS) {
  const meta = { canonical, ru, flag, flagCode, logo };
  UCL_CLUB_BY_RU.set(ru, meta);
  for (const name of [canonical, ru, ...(aliases || [])]) {
    UCL_CLUB_BY_KEY.set(normalizeClubName(name), meta);
    UCL_CLUB_ALIASES.push({ name, meta });
  }
}
UCL_CLUB_ALIASES.sort((left, right) => right.name.length - left.name.length);

function clubMeta(value) {
  const raw = String(value || '').replace(/[\uD83C-\uDBFF\uDC00-\uDFFF]/g, '').replace(/\s+/g, ' ').trim();
  return UCL_CLUB_BY_RU.get(raw) || UCL_CLUB_BY_KEY.get(normalizeClubName(raw));
}

function translateKnownClubText(value) {
  if (typeof value !== 'string' || !value) return value;
  const exact = clubMeta(value);
  if (exact) return exact.ru;
  let result = value;
  for (const { name, meta } of UCL_CLUB_ALIASES) {
    if (result.includes(name)) result = result.split(name).join(meta.ru);
  }
  return result;
}

function readActiveTournamentCode() {
  const selectorValue = document.querySelector('.header-tournament-selector select')?.value;
  return selectorValue || localStorage.getItem(ACTIVE_TOURNAMENT_STORAGE_KEY) || '';
}
function isUclActive() { return readActiveTournamentCode() === UCL_TOURNAMENT_CODE; }
function isUclTournamentRequest(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.searchParams.get('tournament_code') === UCL_TOURNAMENT_CODE || isUclActive();
  } catch (_) { return isUclActive(); }
}

function decorateTeamObject(target, prefix, value) {
  const meta = clubMeta(value);
  if (!meta) return;
  target[`${prefix}_team`] = meta.ru;
  target[`${prefix}_flag`] = meta.flag;
  target[`${prefix}_flag_code`] = meta.flagCode;
  target[`${prefix}_logo`] = meta.logo;
}

function uclOverviewPayload() {
  const rows = [...UCL_CLUBS]
    .map(([canonical, ru, flag, flagCode, logo], index) => ({
      rank: index + 1, team: ru, flag, flag_code: flagCode, logo,
      played: 0, wins: 0, draws: 0, losses: 0,
      goals_for: 0, goals_against: 0, goal_difference: 0, points: 0,
      qualification_zone: index < 8 ? 'direct' : index < 24 ? 'playoff' : 'out',
    }));
  return {
    groups: [{ group_code: 'ЛЧ', rows }],
    default_group_codes: ['ЛЧ'],
    knockout: { stages: [], bracket: null },
    top_scorers: { source: 'ucl-empty', items: [] },
  };
}

function transformUclPayload(value) {
  if (Array.isArray(value)) return value.map((item) => transformUclPayload(item));
  if (value && typeof value === 'object') {
    const next = {};
    for (const [key, item] of Object.entries(value)) next[key] = transformUclPayload(item);
    if (next.home_team) decorateTeamObject(next, 'home', next.home_team_api_name || next.home_team);
    if (next.away_team) decorateTeamObject(next, 'away', next.away_team_api_name || next.away_team);
    if (next.team?.name) {
      const meta = clubMeta(next.team.api_name || next.team.name);
      if (meta) next.team = { ...next.team, name: meta.ru, flag: meta.flag, flag_code: meta.flagCode, logo: meta.logo };
    }
    for (const key of ['name', 'team_name', 'champion', 'runner_up', 'third_place']) {
      if (typeof next[key] === 'string') next[key] = translateKnownClubText(next[key]);
    }
    return next;
  }
  return typeof value === 'string' ? translateKnownClubText(value) : value;
}

async function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } });
}

async function maybeTransformUclResponse(response, url) {
  if (!isUclTournamentRequest(url)) return response;
  const contentType = response.headers.get('Content-Type') || response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return response;
  try {
    const data = await response.clone().json();
    const headers = new Headers(response.headers);
    headers.set('Content-Type', 'application/json');
    return new Response(JSON.stringify(transformUclPayload(data)), { status: response.status, statusText: response.statusText, headers });
  } catch (_) { return response; }
}

function installUclFetchPatch() {
  const originalFetch = window.fetch?.bind(window);
  if (!originalFetch || window.__ffUclFetchPatchInstalled) return;
  window.__ffUclFetchPatchInstalled = true;
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    let parsed = null;
    try { parsed = new URL(url, window.location.origin); } catch (_) { parsed = null; }

    if (parsed?.pathname === '/api/webapp/tournament/overview' && isUclActive()) {
      return jsonResponse(uclOverviewPayload());
    }
    if (parsed?.pathname === '/api/webapp/top-scorer-candidates' && isUclActive()) {
      return jsonResponse({ candidates: [], hint: 'Для ЛЧ 2026/27 выбери бомбардира вручную: начни вводить имя игрока.' });
    }
    if (parsed?.pathname === '/api/webapp/tournament-prediction' && isUclTournamentRequest(url)) {
      const nextInit = { ...(init || {}) };
      if (typeof nextInit.body === 'string') {
        try { const payload = JSON.parse(nextInit.body); payload.third_place = ''; nextInit.body = JSON.stringify(payload); } catch (_) {}
      }
      return maybeTransformUclResponse(await originalFetch(input, nextInit), url);
    }
    return maybeTransformUclResponse(await originalFetch(input, init), url);
  };
}

function installUclStyles() {
  if (document.getElementById('ff-ucl-style-patch')) return;
  const style = document.createElement('style');
  style.id = 'ff-ucl-style-patch';
  style.textContent = `
    .ff-ucl-tournament .next-match-hero.ff-ucl-hidden-simultaneous { display: none !important; }
    .ff-ucl-schedule-note { margin: 16px 0; padding: 14px 16px; border-radius: 18px; background: rgba(96,165,250,.12); border: 1px solid rgba(96,165,250,.28); color: inherit; }
    .ff-ucl-schedule-note strong { display: block; margin-bottom: 4px; }
    .ff-ucl-tournament .tournament-mini-card, .ff-ucl-tournament .tournament-mini-card-main { min-width: 0; max-width: 100%; }
    .ff-ucl-inline-flag { display:inline-flex; align-items:center; justify-content:center; width:1.45em; height:1.45em; margin-right:.35em; vertical-align:-.15em; border-radius:999px; background:rgba(255,255,255,.08); font-size:.95em; line-height:1; }
    .ff-ucl-club-logo { display:inline-flex; align-items:center; justify-content:center; width:64px; height:64px; border-radius:18px; background:#fff; overflow:hidden; box-shadow:0 8px 26px rgba(0,0,0,.28); }
    .ff-ucl-club-logo img { width:82%; height:82%; object-fit:contain; display:block; }
    .ff-ucl-club-logo .ff-ucl-logo-fallback { display:none; font-size:28px; }
    .ff-ucl-club-logo.logo-failed img { display:none; }
    .ff-ucl-club-logo.logo-failed .ff-ucl-logo-fallback { display:block; }
    .ff-ucl-tournament .standings-table .headings span:nth-child(2)::after { content:' / клуб'; opacity:.65; font-size:.8em; }
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

function addCountryFlag(element, meta) {
  if (!element || element.querySelector?.('.ff-ucl-inline-flag')) return;
  const flag = document.createElement('span');
  flag.className = 'ff-ucl-inline-flag';
  flag.textContent = meta.flag;
  flag.setAttribute('aria-hidden', 'true');
  element.prepend(flag);
}

function logoNode(meta) {
  const logo = document.createElement('span');
  logo.className = 'ff-ucl-club-logo';
  logo.setAttribute('title', meta.ru);
  logo.innerHTML = `<img src="${meta.logo}" alt="" loading="lazy"><span class="ff-ucl-logo-fallback">${meta.flag}</span>`;
  logo.querySelector('img')?.addEventListener('error', () => logo.classList.add('logo-failed'));
  return logo;
}

function replaceBigFlagNear(element, meta) {
  if (!element || element.dataset.ffUclLogoDone === '1') return;
  let candidate = element.previousElementSibling;
  if (!candidate || !candidate.className || !String(candidate.className).includes('flag')) {
    const parent = element.parentElement;
    candidate = parent ? Array.from(parent.children).find((child) => child !== element && String(child.className || '').includes('flag') && !String(child.className || '').includes('ff-ucl-inline-flag')) : null;
  }
  if (!candidate || candidate.classList.contains('ff-ucl-club-logo')) return;
  candidate.replaceWith(logoNode(meta));
  element.dataset.ffUclLogoDone = '1';
}

function decorateVisibleClubPresentation() {
  if (!isUclActive()) return;
  const selectors = ['.next-match-hero strong','.next-match-slide strong','.live-match-team strong','.match-card strong','.match-team strong','.match-row strong','.prediction-match strong','.modal-card strong','.team-name'].join(',');
  document.querySelectorAll(selectors).forEach((element) => {
    const meta = clubMeta(element.textContent);
    if (!meta) return;
    addCountryFlag(element, meta);
    replaceBigFlagNear(element, meta);
  });
}

function replaceExactText(root, from, to) {
  root.querySelectorAll('*').forEach((element) => {
    for (const node of element.childNodes) {
      if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim() === from) node.nodeValue = node.nodeValue.replace(from, to);
    }
  });
}

function patchUclTournamentHubText() {
  if (!isUclActive()) return;
  const hub = document.querySelector('.tournament-hub');
  if (!hub) return;
  replaceExactText(hub, 'Группы', 'Общий этап');
  replaceExactText(hub, 'Группа ЛЧ', 'Общий этап ЛЧ');
  replaceExactText(hub, 'Сборная', 'Клуб');
  hub.querySelectorAll('p, small, span').forEach((element) => {
    if ((element.textContent || '').includes('1–2 место — 1/8 финала')) {
      element.textContent = '1–8 — 1/8 финала · 9–24 — стыковые матчи · 25–36 — вылет';
    }
    if ((element.textContent || '').includes('По умолчанию выбраны группы')) {
      element.textContent = 'Общий этап ЛЧ: 36 клубов, 8 туров. Таблица обновится после первых матчей.';
    }
    if ((element.textContent || '').includes('обновляется из статистики')) {
      element.textContent = 'по матчам ЛЧ';
    }
  });
}

function hideThirdPlaceElementsForUcl() {
  const active = isUclActive();
  document.documentElement.classList.toggle('ff-ucl-tournament', active);
  const candidates = document.querySelectorAll(['.tournament-mini-card','.tournament-mini-card-edit','.modal-card article','.modal-card button','.modal-card label','.modal-card .form-row','.modal-card .field','.modal-card .picker-section'].join(','));
  candidates.forEach((element) => {
    const text = (element.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const aria = (element.getAttribute('aria-label') || '').toLowerCase();
    const isThirdPlace = text.includes('3-е место') || text.includes('3 место') || aria.includes('third_place') || aria.includes('3-е место');
    if (!isThirdPlace) return;
    if (active) { element.dataset.ffUclHiddenThirdPlace = '1'; element.setAttribute('hidden', ''); }
    else if (element.dataset.ffUclHiddenThirdPlace === '1') { element.removeAttribute('hidden'); delete element.dataset.ffUclHiddenThirdPlace; }
  });
  if (active) {
    document.querySelectorAll('.tournament-mini-actions span').forEach((element) => {
      const match = String(element.textContent || '').trim().match(/^(\d+)\/4$/);
      if (!match) return;
      element.textContent = `${Math.min(Number(match[1] || 0), 3)}/3`;
    });
  }
}

function installUclDomPatch() {
  installUclStyles();
  const run = () => {
    hideThirdPlaceElementsForUcl();
    patchSimultaneousHeroForUcl();
    decorateVisibleClubPresentation();
    patchUclTournamentHubText();
  };
  run();
  document.addEventListener('change', (event) => {
    if (event.target?.matches?.('.header-tournament-selector select')) {
      window.setTimeout(run, 0);
      window.setTimeout(run, 250);
    }
  }, true);
  new MutationObserver(() => run()).observe(document.documentElement, { childList: true, subtree: true });
}

installUclFetchPatch();
installUclDomPatch();
