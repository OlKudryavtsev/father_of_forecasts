(() => {
  if (window.__ffUclUiPatchV396) return;
  window.__ffUclUiPatchV396 = true;

  const UCL_CODE = 'ucl_2026_2027';
  const ACTIVE_TOURNAMENT_KEY = 'ff_active_tournament_code';
  const ENGLAND_FLAG = '🏴󠁧󠁢󠁥󠁮󠁧󠁿';

  const CLUBS = [
    ['AEK Athens', 'АЕК Афины', '🇬🇷', 338, ['AEK', 'AEK Athens FC']],
    ['Arsenal', 'Арсенал', ENGLAND_FLAG, 42, ['Arsenal FC']],
    ['Aston Villa', 'Астон Вилла', ENGLAND_FLAG, 66, ['Aston Villa FC']],
    ['Atletico Madrid', 'Атлетико Мадрид', '🇪🇸', 530, ['Atlético Madrid', 'Atleti', 'Atl. Madrid']],
    ['Barcelona', 'Барселона', '🇪🇸', 529, ['FC Barcelona']],
    ['Bayern Munich', 'Бавария', '🇩🇪', 157, ['Bayern München', 'FC Bayern Munich', 'Bayern']],
    ['Bodo/Glimt', 'Будё-Глимт', '🇳🇴', 727, ['Bodø/Glimt', 'Bodoe/Glimt', 'Bodo Glimt']],
    ['Borussia Dortmund', 'Боруссия Дортмунд', '🇩🇪', 165, ['Dortmund', 'B. Dortmund']],
    ['Club Brugge', 'Брюгге', '🇧🇪', 569, ['Club Brugge KV', 'Brugge']],
    ['Como', 'Комо', '🇮🇹', 895, ['Como 1907']],
    ['Fenerbahce', 'Фенербахче', '🇹🇷', 611, ['Fenerbahçe', 'Fenerbahce SK']],
    ['Feyenoord', 'Фейеноорд', '🇳🇱', 209, ['Feyenoord Rotterdam']],
    ['Galatasaray', 'Галатасарай', '🇹🇷', 645, ['Galatasaray SK']],
    ['Inter', 'Интер', '🇮🇹', 505, ['Inter Milan', 'Internazionale']],
    ['LASK', 'ЛАСК', '🇦🇹', 102, ['Lask Linz', 'LASK Linz']],
    ['Lens', 'Ланс', '🇫🇷', 116, ['RC Lens']],
    ['Leipzig', 'Лейпциг', '🇩🇪', 173, ['RB Leipzig', 'RasenBallsport Leipzig']],
    ['Lille', 'Лилль', '🇫🇷', 79, ['LOSC Lille']],
    ['Liverpool', 'Ливерпуль', ENGLAND_FLAG, 40, ['Liverpool FC']],
    ['Manchester City', 'Манчестер Сити', ENGLAND_FLAG, 50, ['Man City']],
    ['Manchester United', 'Манчестер Юнайтед', ENGLAND_FLAG, 33, ['Man Utd', 'Manchester Utd']],
    ['Napoli', 'Наполи', '🇮🇹', 492, ['SSC Napoli']],
    ['Nancy', 'Нанси', '🇫🇷', 100, ['AS Nancy', 'Nancy Lorraine']],
    ['Paris Saint-Germain', 'ПСЖ', '🇫🇷', 85, ['Paris SG', 'PSG', 'Paris']],
    ['Porto', 'Порту', '🇵🇹', 212, ['FC Porto']],
    ['PSV Eindhoven', 'ПСВ', '🇳🇱', 197, ['PSV']],
    ['Real Betis', 'Бетис', '🇪🇸', 543, ['Betis']],
    ['Real Madrid', 'Реал Мадрид', '🇪🇸', 541, ['Real Madrid CF']],
    ['Roma', 'Рома', '🇮🇹', 497, ['AS Roma']],
    ['Sabah', 'Сабах', '🇦🇿', 1083, ['Sabah FA', 'Sabah FK']],
    ['Slavia Praha', 'Славия Прага', '🇨🇿', 560, ['Slavia Prague', 'SK Slavia Praha']],
    ['Sporting CP', 'Спортинг', '🇵🇹', 228, ['Sporting Lisbon', 'Sporting']],
    ['Tottenham', 'Тоттенхэм', ENGLAND_FLAG, 47, ['Tottenham Hotspur', 'Spurs']],
    ['Viking', 'Викинг', '🇳🇴', 1074, ['Viking FK']],
    ['Villarreal', 'Вильярреал', '🇪🇸', 533, ['Villarreal CF']],
    ['Wisla Krakow', 'Висла Краков', '🇵🇱', 349, ['Wisła Kraków', 'Wisla Kraków', 'Wisla Krakow SA']]
  ].map(([canonical, ru, flag, logoId, aliases]) => ({ canonical, ru, flag, logoId, aliases: [canonical, ru, ...(aliases || [])] }));

  function normalize(value) {
    return String(value || '')
      .toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
      .replace(/ё/g, 'е').replace(/[«»"'`]/g, '')
      .replace(/\b(fc|cf|sc|sk|fk|kv|sa|club|football|team)\b/g, '')
      .replace(/[^a-zа-я0-9]+/g, ' ').trim();
  }

  const aliases = new Map();
  CLUBS.forEach((club) => club.aliases.forEach((alias) => aliases.set(normalize(alias), club)));

  function clubFor(value) {
    const key = normalize(value);
    if (!key) return null;
    return aliases.get(key) || CLUBS.find((club) => club.aliases.some((alias) => {
      const candidate = normalize(alias);
      return candidate && (key === candidate || key.includes(candidate) || candidate.includes(key));
    })) || null;
  }

  function isUclActive() {
    return localStorage.getItem(ACTIVE_TOURNAMENT_KEY) === UCL_CODE
      || /(?:\?|&)tournament_code=ucl_2026_2027\b/.test(window.location.search);
  }

  function apiSportsLogo(id) {
    return id ? `https://media.api-sports.io/football/teams/${id}.png` : '';
  }

  function initials(value) {
    const parts = String(value || '').replace(/[–—-]/g, ' ').split(/\s+/).filter(Boolean);
    return (parts.slice(0, 2).map((part) => part[0]).join('') || 'ЛЧ').toUpperCase();
  }

  function createLogo(club) {
    const box = document.createElement('span');
    box.className = 'ucl-club-logo-large';
    const img = document.createElement('img');
    img.src = apiSportsLogo(club?.logoId);
    img.alt = '';
    img.loading = 'lazy';
    img.onerror = () => {
      box.classList.add('fallback');
      box.textContent = initials(club?.ru || club?.canonical || 'ЛЧ');
    };
    box.appendChild(img);
    return box;
  }

  function createFlag(club) {
    const flag = document.createElement('span');
    flag.className = 'ucl-country-flag-inline';
    flag.textContent = club?.flag || '';
    return flag;
  }

  function decorateTeamBlock(block) {
    if (!block || block.dataset.uclDecorating === '1') return;
    const nameEl = block.querySelector('.ucl-team-name-row strong, :scope > strong, strong');
    const club = clubFor(nameEl?.textContent || '');
    if (!club || !nameEl) return;

    block.dataset.uclDecorating = '1';
    try {
      nameEl.textContent = club.ru;

      let logo = block.querySelector(':scope > .ucl-club-logo-large');
      if (!logo) {
        const candidates = Array.from(block.children).filter((child) => child !== nameEl && !child.classList?.contains('ucl-team-name-row'));
        const oldVisual = candidates.find((child) => child.matches?.('.team-flag, .flag, img, span'));
        logo = createLogo(club);
        if (oldVisual) oldVisual.replaceWith(logo);
        else block.insertBefore(logo, block.firstChild);
      }

      let row = block.querySelector(':scope > .ucl-team-name-row');
      if (!row) {
        row = document.createElement('span');
        row.className = 'ucl-team-name-row';
        nameEl.parentElement === block ? nameEl.replaceWith(row) : block.appendChild(row);
        row.appendChild(createFlag(club));
        row.appendChild(nameEl);
      } else {
        const flag = row.querySelector('.ucl-country-flag-inline');
        if (flag) flag.textContent = club.flag;
        else row.insertBefore(createFlag(club), row.firstChild);
      }
    } finally {
      block.dataset.uclDecorating = '0';
    }
  }

  function decorateTeams() {
    document.querySelectorAll('.team-side, .next-match-team, .detail-team, .live-match-team').forEach(decorateTeamBlock);
  }

  function patchMatch(match) {
    if (!match || typeof match !== 'object') return;
    const home = clubFor(match.home_team || match.home_team_api_name);
    const away = clubFor(match.away_team || match.away_team_api_name);
    if (home) {
      match.home_team = home.ru;
      match.home_flag = home.flag;
      if (home.flag === ENGLAND_FLAG) match.home_flag_code = '';
      match.home_logo = apiSportsLogo(home.logoId);
    }
    if (away) {
      match.away_team = away.ru;
      match.away_flag = away.flag;
      if (away.flag === ENGLAND_FLAG) match.away_flag_code = '';
      match.away_logo = apiSportsLogo(away.logoId);
    }
  }

  function patchApiPayload(data) {
    if (!data || typeof data !== 'object') return data;
    if (Array.isArray(data)) { data.forEach(patchApiPayload); return data; }
    ['matches', 'upcoming_matches', 'future_matches'].forEach((key) => Array.isArray(data[key]) && data[key].forEach(patchMatch));
    ['next_match', 'match'].forEach((key) => data[key] && patchMatch(data[key]));
    if (data.dashboard?.next_match) patchMatch(data.dashboard.next_match);
    if (data.top_scorers && Array.isArray(data.top_scorers.items)) {
      data.top_scorers.items = [];
      data.top_scorers.message = 'Бомбардиры ЛЧ появятся после первых голов турнира.';
    }
    if (Array.isArray(data.scorers)) data.scorers = [];
    return data;
  }

  function installFetchPatch() {
    if (window.__ffUclFetchPatchV396) return;
    window.__ffUclFetchPatchV396 = true;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function patchedFetch(input, init) {
      const response = await originalFetch(input, init);
      const url = typeof input === 'string' ? input : input?.url || '';
      if (!isUclActive() || !url.includes('/api/webapp/')) return response;
      if (!(response.headers.get('content-type') || '').includes('application/json')) return response;
      try {
        const data = await response.clone().json();
        patchApiPayload(data);
        return new Response(JSON.stringify(data), { status: response.status, statusText: response.statusText, headers: response.headers });
      } catch {
        return response;
      }
    };
  }

  function textButton(label) {
    return Array.from(document.querySelectorAll('button, [role="tab"]')).find((el) => String(el.textContent || '').trim() === label);
  }

  function isActiveTab(button) {
    return Boolean(button && (button.classList.contains('active') || button.getAttribute('aria-selected') === 'true'));
  }

  function cleanupTournamentView() {
    document.querySelectorAll('[data-ucl-native-hidden="1"]').forEach((node) => {
      node.style.removeProperty('display');
      delete node.dataset.uclNativeHidden;
    });
    document.getElementById('ucl-league-phase-panel')?.remove();
  }

  function buildLeaguePhasePanel() {
    const panel = document.createElement('section');
    panel.id = 'ucl-league-phase-panel';
    panel.className = 'ucl-league-phase-panel';
    panel.innerHTML = `
      <div class="ucl-phase-head">
        <div><span>Лига чемпионов 2026/27</span><h3>Общий этап</h3></div>
        <small>36 клубов · 8 туров</small>
      </div>
      <p class="ucl-phase-note">1–8 — 1/8 финала · 9–24 — стыковые матчи · 25–36 — вылет</p>
      <div class="ucl-table-scroll">
        <table class="ucl-phase-table">
          <thead><tr><th>#</th><th>Клуб</th><th>И</th><th>В</th><th>Н</th><th>П</th><th>М</th><th>±</th><th>О</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>`;

    const body = panel.querySelector('tbody');
    [...CLUBS].sort((a, b) => a.ru.localeCompare(b.ru, 'ru')).forEach((club, index) => {
      const row = document.createElement('tr');
      row.innerHTML = `<td>${index + 1}</td><td><span class="ucl-table-club"><span class="ucl-country-flag-inline">${club.flag}</span><strong>${club.ru}</strong></span></td><td>0</td><td>0</td><td>0</td><td>0</td><td>0:0</td><td>0</td><td>0</td>`;
      body.appendChild(row);
    });
    return panel;
  }

  function renderTournamentView() {
    if (!isUclActive()) { cleanupTournamentView(); return; }
    const tournamentTab = textButton('Турнир');
    if (!isActiveTab(tournamentTab)) { cleanupTournamentView(); return; }

    const stageButton = textButton('Группы') || textButton('Общий этап');
    const anchor = stageButton?.parentElement || tournamentTab?.parentElement;
    if (!anchor) return;

    const host = anchor.parentElement;
    if (!host) return;

    if (!document.getElementById('ucl-league-phase-panel')) {
      const panel = buildLeaguePhasePanel();
      anchor.insertAdjacentElement('afterend', panel);
    }

    let sibling = anchor.nextElementSibling;
    while (sibling) {
      const next = sibling.nextElementSibling;
      if (sibling.id !== 'ucl-league-phase-panel' && !sibling.matches('nav, .bottom-nav')) {
        sibling.dataset.uclNativeHidden = '1';
        sibling.style.setProperty('display', 'none', 'important');
      }
      sibling = next;
    }
  }

  function installStyles() {
    if (document.getElementById('ff-ucl-ui-patch-v396')) return;
    const style = document.createElement('style');
    style.id = 'ff-ucl-ui-patch-v396';
    style.textContent = `
      body.ucl-active .league-status-row { display:flex !important; align-items:flex-start !important; gap:8px !important; }
      body.ucl-active .header-admin-button { flex:0 0 44px !important; width:44px !important; height:44px !important; min-width:44px !important; min-height:44px !important; align-self:flex-start !important; padding:0 !important; border-radius:14px !important; font-size:0 !important; }
      body.ucl-active .header-admin-button svg { width:21px !important; height:21px !important; margin:0 !important; }
      body.ucl-active .league-status { flex:1 1 auto !important; min-width:0 !important; display:grid !important; grid-template-columns:repeat(6,minmax(0,1fr)) !important; gap:8px !important; padding:0 !important; border:0 !important; background:transparent !important; box-shadow:none !important; }
      body.ucl-active .league-status .divider { display:none !important; }
      body.ucl-active .header-tournament-selector, body.ucl-active .header-league-selector { grid-column:span 3 !important; min-width:0 !important; min-height:44px !important; border:1px solid rgba(116,146,209,.28) !important; border-radius:15px !important; background:rgba(24,35,61,.86) !important; padding:8px 10px !important; }
      body.ucl-active .league-status .status-section, body.ucl-active .league-status .points, body.ucl-active .league-status > .muted:last-child { grid-column:span 2 !important; min-width:0 !important; min-height:40px !important; display:flex !important; align-items:center !important; justify-content:center !important; border:1px solid rgba(116,146,209,.22) !important; border-radius:13px !important; background:rgba(19,29,49,.8) !important; padding:7px 8px !important; font-size:14px !important; font-weight:900 !important; white-space:nowrap !important; }
      body.ucl-active .league-status .status-section { color:#ffcf4a !important; background:rgba(96,70,18,.42) !important; }
      body.ucl-active .league-status .points { color:#17d494 !important; background:rgba(13,72,62,.42) !important; }
      body.ucl-active .league-status > .muted:last-child::before { content:'Место '; color:#9daacc; margin-right:4px; }
      body.ucl-active .header-tournament-selector select, body.ucl-active .header-league-trigger, body.ucl-active .header-league-name { min-width:0 !important; max-width:100% !important; overflow:hidden !important; text-overflow:ellipsis !important; white-space:nowrap !important; }

      body.ucl-active .ucl-club-logo-large { width:clamp(86px,18vw,124px); height:clamp(86px,18vw,124px); border-radius:24px; background:#f7f8fb; display:inline-flex; align-items:center; justify-content:center; overflow:hidden; margin:0 auto 8px; flex:0 0 auto; box-shadow:0 16px 32px rgba(0,0,0,.24); }
      body.ucl-active .ucl-club-logo-large img { width:74%; height:74%; object-fit:contain; display:block; }
      body.ucl-active .ucl-club-logo-large.fallback { background:linear-gradient(135deg,#172745,#0d1527); color:#dbe7ff; border:1px solid rgba(116,146,209,.34); font-weight:1000; font-size:30px; }
      body.ucl-active .ucl-team-name-row { display:inline-flex !important; align-items:center !important; justify-content:center !important; gap:7px !important; max-width:100%; }
      body.ucl-active .ucl-team-name-row strong { display:inline !important; margin:0 !important; }
      body.ucl-active .ucl-country-flag-inline { width:28px; height:28px; border-radius:999px; background:rgba(255,255,255,.08); display:inline-flex; align-items:center; justify-content:center; font-size:18px; line-height:1; flex:0 0 auto; }

      body.ucl-active .ucl-league-phase-panel { margin-top:14px; border:1px solid rgba(70,143,255,.34); border-radius:22px; background:linear-gradient(180deg,rgba(18,34,59,.96),rgba(10,20,36,.96)); padding:16px; }
      body.ucl-active .ucl-phase-head { display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin-bottom:6px; }
      body.ucl-active .ucl-phase-head span { color:#7da8ff; font-size:12px; font-weight:900; text-transform:uppercase; letter-spacing:.08em; }
      body.ucl-active .ucl-phase-head h3 { margin:3px 0 0; font-size:24px; }
      body.ucl-active .ucl-phase-head small, body.ucl-active .ucl-phase-note { color:#9ba9c6; }
      body.ucl-active .ucl-phase-note { margin:0 0 14px; font-size:13px; }
      body.ucl-active .ucl-table-scroll { width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:16px; }
      body.ucl-active .ucl-phase-table { width:100%; min-width:660px; border-collapse:collapse; background:rgba(6,13,25,.42); }
      body.ucl-active .ucl-phase-table th, body.ucl-active .ucl-phase-table td { padding:10px 9px; border-bottom:1px solid rgba(123,149,194,.16); text-align:center; white-space:nowrap; }
      body.ucl-active .ucl-phase-table th { color:#9daacc; font-size:11px; text-transform:uppercase; }
      body.ucl-active .ucl-phase-table th:nth-child(2), body.ucl-active .ucl-phase-table td:nth-child(2) { text-align:left; min-width:210px; }
      body.ucl-active .ucl-table-club { display:inline-flex; align-items:center; gap:8px; }
      body.ucl-active .ucl-table-club .ucl-country-flag-inline { width:24px; height:24px; font-size:16px; }

      @media (max-width:520px) {
        body.ucl-active .league-status-row { gap:7px !important; }
        body.ucl-active .header-admin-button { width:40px !important; height:40px !important; min-width:40px !important; min-height:40px !important; }
        body.ucl-active .league-status { gap:7px !important; }
        body.ucl-active .header-tournament-selector, body.ucl-active .header-league-selector { min-height:40px !important; padding:7px 8px !important; }
        body.ucl-active .league-status .status-section, body.ucl-active .league-status .points, body.ucl-active .league-status > .muted:last-child { min-height:36px !important; font-size:13px !important; padding:6px !important; }
      }
    `;
    document.head.appendChild(style);
  }

  let scheduled = false;
  function render() {
    scheduled = false;
    document.body?.classList.toggle('ucl-active', isUclActive());
    if (!isUclActive()) { cleanupTournamentView(); return; }
    decorateTeams();
    renderTournamentView();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(render);
  }

  function boot() {
    installStyles();
    installFetchPatch();
    schedule();
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList:true, subtree:true });
    document.addEventListener('click', () => setTimeout(schedule, 50), true);
    window.addEventListener('storage', schedule);
    window.setInterval(schedule, 1800);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once:true });
  else boot();
})();