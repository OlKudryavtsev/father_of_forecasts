(() => {
  if (window.__ffUclTournamentViewV400) return;
  window.__ffUclTournamentViewV400 = true;

  const UCL_CODE = 'ucl_2026_2027';
  const ACTIVE_TOURNAMENT_KEY = 'ff_active_tournament_code';
  const WEB_SESSION_KEY = 'ff-web-session-token';
  let payloadPromise = null;
  let scheduled = false;

  function isUclActive() {
    return localStorage.getItem(ACTIVE_TOURNAMENT_KEY) === UCL_CODE;
  }

  function getCookieValue(name) {
    return document.cookie.split('; ').find((row) => row.startsWith(`${name}=`))?.split('=').slice(1).join('=') || '';
  }

  function authHeaders() {
    const headers = {};
    const initData = window.Telegram?.WebApp?.initData || '';
    const webToken = localStorage.getItem(WEB_SESSION_KEY) || decodeURIComponent(getCookieValue('ff_web_session') || '');
    if (initData) headers['X-Telegram-Init-Data'] = initData;
    else if (webToken) headers['X-Web-Session-Token'] = webToken;
    return headers;
  }

  async function loadMatches() {
    if (!payloadPromise) {
      payloadPromise = fetch(`/api/webapp/matches?scope=all&tournament_code=${encodeURIComponent(UCL_CODE)}`, {
        cache: 'no-store',
        headers: authHeaders(),
      }).then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      }).catch((error) => {
        payloadPromise = null;
        throw error;
      });
    }
    return payloadPromise;
  }

  function teamKey(id, name) {
    return id ? `id:${id}` : `name:${String(name || '').toLowerCase()}`;
  }

  function buildStandings(matches) {
    const leagueMatches = (matches || []).filter((match) => {
      const stage = String(match.stage || '').toLowerCase();
      const round = String(match.match_round || '').toLowerCase();
      return stage === 'league' || stage === 'group' || stage === 'league_phase' || round.includes('matchday');
    });
    const source = leagueMatches.length ? leagueMatches : (matches || []);
    const rows = new Map();

    function ensure(id, name, flag, flagCode) {
      const key = teamKey(id, name);
      if (!rows.has(key)) rows.set(key, { key, name, flag, flagCode, played: 0, wins: 0, draws: 0, losses: 0, gf: 0, ga: 0, points: 0 });
      return rows.get(key);
    }

    source.forEach((match) => {
      const home = ensure(match.home_team_id, match.home_team, match.home_flag, match.home_flag_code);
      const away = ensure(match.away_team_id, match.away_team, match.away_flag, match.away_flag_code);
      if (!match.is_finished || match.score_home === null || match.score_home === undefined || match.score_away === null || match.score_away === undefined) return;
      const hs = Number(match.score_home);
      const as = Number(match.score_away);
      home.played += 1; away.played += 1;
      home.gf += hs; home.ga += as; away.gf += as; away.ga += hs;
      if (hs > as) { home.wins += 1; away.losses += 1; home.points += 3; }
      else if (as > hs) { away.wins += 1; home.losses += 1; away.points += 3; }
      else { home.draws += 1; away.draws += 1; home.points += 1; away.points += 1; }
    });

    return [...rows.values()].sort((a, b) =>
      b.points - a.points ||
      (b.gf - b.ga) - (a.gf - a.ga) ||
      b.gf - a.gf ||
      a.name.localeCompare(b.name, 'ru')
    );
  }

  function flagMarkup(row) {
    if (row.flagCode) return `<img src="https://flagcdn.com/${row.flagCode}.svg" alt="" loading="lazy">`;
    return `<span>${row.flag || '⚽'}</span>`;
  }

  function panelMarkup(rows) {
    const body = rows.map((row, index) => {
      const gd = row.gf - row.ga;
      const zone = index < 8 ? 'direct' : index < 24 ? 'playoff' : 'out';
      return `<tr class="ucl-${zone}"><td>${index + 1}</td><td><span class="ucl-table-club"><i>${flagMarkup(row)}</i><strong>${row.name}</strong></span></td><td>${row.played}</td><td>${row.wins}</td><td>${row.draws}</td><td>${row.losses}</td><td>${row.gf}:${row.ga}</td><td>${gd > 0 ? '+' : ''}${gd}</td><td><b>${row.points}</b></td></tr>`;
    }).join('');
    return `<section id="ucl-league-phase-panel" class="ucl-league-phase-panel"><div class="ucl-phase-head"><div><span>Лига чемпионов 2026/27</span><h3>Общий этап</h3></div><small>${rows.length} клубов · 8 туров</small></div><p class="ucl-phase-note"><span class="ucl-legend direct"></span>1–8 — 1/8 <span class="ucl-legend playoff"></span>9–24 — стыки <span class="ucl-legend out"></span>25–36 — вылет</p><div class="ucl-table-scroll"><table class="ucl-phase-table"><thead><tr><th>#</th><th>Клуб</th><th>И</th><th>В</th><th>Н</th><th>П</th><th>М</th><th>±</th><th>О</th></tr></thead><tbody>${body}</tbody></table></div></section>`;
  }

  function textButton(label) {
    return Array.from(document.querySelectorAll('button, [role="tab"]')).find((el) => String(el.textContent || '').trim() === label);
  }

  function cleanup() {
    document.querySelectorAll('[data-ucl-native-hidden="1"]').forEach((node) => {
      node.style.removeProperty('display');
      delete node.dataset.uclNativeHidden;
    });
    document.getElementById('ucl-league-phase-panel')?.remove();
  }

  async function render() {
    scheduled = false;
    if (!isUclActive()) { cleanup(); return; }
    const tournamentTab = textButton('Турнир');
    if (!tournamentTab || !(tournamentTab.classList.contains('active') || tournamentTab.getAttribute('aria-selected') === 'true')) { cleanup(); return; }
    const stageButton = textButton('Группы') || textButton('Общий этап');
    const anchor = stageButton?.parentElement || tournamentTab.parentElement;
    if (!anchor || document.getElementById('ucl-league-phase-panel')) return;
    try {
      const payload = await loadMatches();
      if (!isUclActive()) return;
      const rows = buildStandings(payload.matches || []);
      anchor.insertAdjacentHTML('afterend', panelMarkup(rows));
      let sibling = anchor.nextElementSibling;
      while (sibling) {
        const next = sibling.nextElementSibling;
        if (sibling.id !== 'ucl-league-phase-panel' && !sibling.matches('nav, .bottom-nav')) {
          sibling.dataset.uclNativeHidden = '1';
          sibling.style.display = 'none';
        }
        sibling = next;
      }
    } catch (error) {
      console.warn('UCL standings unavailable', error);
    }
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(render);
  }

  function installStyles() {
    const style = document.createElement('style');
    style.textContent = `.ucl-league-phase-panel{padding:12px;border:1px solid rgba(116,146,209,.25);border-radius:18px;background:#121a2c}.ucl-phase-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-end}.ucl-phase-head span,.ucl-phase-head small{color:#96a2bc;font-size:11px}.ucl-phase-head h3{margin:2px 0 0}.ucl-phase-note{display:flex;flex-wrap:wrap;gap:5px 8px;align-items:center;color:#96a2bc;font-size:10px}.ucl-legend{width:8px;height:8px;border-radius:50%}.ucl-legend.direct{background:#16d391}.ucl-legend.playoff{background:#ffbf35}.ucl-legend.out{background:#657089}.ucl-table-scroll{overflow-x:auto}.ucl-phase-table{width:100%;min-width:520px;border-collapse:collapse;font-size:11px}.ucl-phase-table th,.ucl-phase-table td{padding:7px 4px;text-align:center;border-bottom:1px solid rgba(148,163,184,.12)}.ucl-phase-table th:nth-child(2),.ucl-phase-table td:nth-child(2){text-align:left}.ucl-table-club{display:flex;align-items:center;gap:6px;min-width:0}.ucl-table-club i{width:21px;height:17px;display:grid;place-items:center;flex:0 0 21px}.ucl-table-club i img{width:21px;height:15px;object-fit:cover;border-radius:3px}.ucl-table-club strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ucl-phase-table tr.ucl-direct td:first-child{border-left:3px solid #16d391}.ucl-phase-table tr.ucl-playoff td:first-child{border-left:3px solid #ffbf35}.ucl-phase-table tr.ucl-out{opacity:.72}`;
    document.head.appendChild(style);
  }

  installStyles();
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  document.addEventListener('click', () => setTimeout(schedule, 30), true);
  window.addEventListener('storage', () => { payloadPromise = null; schedule(); });
  schedule();
})();
