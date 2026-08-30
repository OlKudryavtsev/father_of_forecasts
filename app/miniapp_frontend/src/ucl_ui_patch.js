(() => {
  if (window.__ffUclUiPatchV395) return;
  window.__ffUclUiPatchV395 = true;

  const UCL_CODE = 'ucl_2026_2027';
  const ACTIVE_TOURNAMENT_KEY = 'ff_active_tournament_code';
  const ENGLAND_FLAG = '🏴󠁧󠁢󠁥󠁮󠁧󠁿';

  function apiSportsLogo(id) {
    return id ? `https://media.api-sports.io/football/teams/${id}.png` : '';
  }

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
  ].map(([canonical, ru, flag, logoId, aliases]) => ({
    canonical,
    ru,
    flag,
    logoId,
    aliases: [canonical, ru, ...(aliases || [])]
  }));

  const allAliases = new Map();
  for (const club of CLUBS) {
    for (const alias of club.aliases) {
      allAliases.set(normalize(alias), club);
    }
  }

  function normalize(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/ё/g, 'е')
      .replace(/[«»"'`]/g, '')
      .replace(/\b(fc|cf|sc|sk|fk|kv|sa|club|football|team)\b/g, '')
      .replace(/[^a-zа-я0-9]+/g, ' ')
      .trim();
  }

  function clubFor(value) {
    const direct = allAliases.get(normalize(value));
    if (direct) return direct;
    const text = normalize(value);
    if (!text) return null;
    return CLUBS.find((club) => club.aliases.some((alias) => {
      const key = normalize(alias);
      return key && (text === key || text.includes(key) || key.includes(text));
    })) || null;
  }

  function isUclActive() {
    return localStorage.getItem(ACTIVE_TOURNAMENT_KEY) === UCL_CODE
      || /(?:\?|&)tournament_code=ucl_2026_2027\b/.test(window.location.search);
  }

  function setBodyState() {
    document.body?.classList.toggle('ucl-active', isUclActive());
  }

  function createLogo(club, compact = false) {
    const box = document.createElement('span');
    box.className = compact ? 'ucl-club-logo-inline' : 'ucl-club-logo-large';
    box.title = club?.ru || club?.canonical || '';
    const src = apiSportsLogo(club?.logoId);
    if (src) {
      const img = document.createElement('img');
      img.src = src;
      img.alt = '';
      img.loading = 'lazy';
      img.onerror = () => {
        box.classList.add('fallback');
        box.textContent = initials(club?.ru || club?.canonical || 'ЛЧ');
      };
      box.appendChild(img);
    } else {
      box.classList.add('fallback');
      box.textContent = initials(club?.ru || club?.canonical || 'ЛЧ');
    }
    return box;
  }

  function createCountryFlag(club) {
    const flag = document.createElement('span');
    flag.className = 'ucl-country-flag-inline';
    flag.textContent = club?.flag || '';
    flag.title = club?.ru || club?.canonical || '';
    return flag;
  }

  function initials(value) {
    const parts = String(value || '')
      .replace(/[–—-]/g, ' ')
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return 'ЛЧ';
    return parts.slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  }

  function teamNameElement(block) {
    return block?.querySelector?.('strong, .team-name, .header-league-name');
  }

  function decorateTeamBlock(block) {
    if (!block || block.dataset.uclDecorating === '1') return;
    const nameEl = teamNameElement(block);
    const club = clubFor(nameEl?.textContent || '');
    if (!club) return;

    block.dataset.uclDecorating = '1';
    try {
      nameEl.textContent = club.ru;

      const firstVisual = Array.from(block.children).find((child) => child !== nameEl && !child.classList?.contains('ucl-country-flag-inline'));
      const shouldUseLargeLogo = block.matches('.team-side, .next-match-team, .detail-team, .live-match-team');
      if (shouldUseLargeLogo) {
        if (!block.querySelector('.ucl-club-logo-large')) {
          const logo = createLogo(club, false);
          if (firstVisual) firstVisual.replaceWith(logo);
          else block.insertBefore(logo, nameEl);
        }
        if (!nameEl.previousElementSibling?.classList?.contains('ucl-country-flag-inline')) {
          nameEl.insertAdjacentElement('beforebegin', createCountryFlag(club));
        }
      }
    } finally {
      block.dataset.uclDecorating = '0';
    }
  }

  function decoratePredictionHero() {
    document.querySelectorAll('.next-match-team, .team-side, .detail-team, .live-match-team').forEach(decorateTeamBlock);
  }

  function normalizeVisibleEnglandFlags() {
    if (!isUclActive()) return;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      if (walker.currentNode.nodeValue.includes('🇬🇧') || walker.currentNode.nodeValue.includes('🏴')) nodes.push(walker.currentNode);
    }
    for (const node of nodes) {
      const parentText = node.parentElement?.closest?.('.team-side, .next-match-team, .detail-team, .live-match-team, tr, article, section')?.textContent || '';
      const isEnglishClub = ['Арсенал', 'Астон Вилла', 'Ливерпуль', 'Манчестер Сити', 'Манчестер Юнайтед', 'Тоттенхэм'].some((name) => parentText.includes(name));
      if (isEnglishClub) node.nodeValue = node.nodeValue.replace(/🇬🇧|🏴/g, ENGLAND_FLAG);
    }
  }

  function patchTournamentTabSafety() {
    if (!isUclActive()) return;
    const labels = Array.from(document.querySelectorAll('button, [role="tab"]'));
    const tournamentTab = labels.find((el) => /турнир/i.test(el.textContent || ''));
    if (!tournamentTab || tournamentTab.dataset.uclSafeTab === '1') return;
    tournamentTab.dataset.uclSafeTab = '1';
    tournamentTab.addEventListener('click', () => {
      setTimeout(() => {
        const likelyBroken = document.querySelector('.groups-grid, .standings-section, .tournament-groups, .group-card');
        if (!likelyBroken) return;
        document.body.classList.add('ucl-tournament-tab-open');
      }, 80);
    }, true);
  }

  function patchFetch() {
    if (window.__ffUclFetchPatchV395) return;
    window.__ffUclFetchPatchV395 = true;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function patchedFetch(input, init) {
      const response = await originalFetch(input, init);
      const url = typeof input === 'string' ? input : input?.url || '';
      const shouldPatch = url.includes('/api/webapp/') && (url.includes(`tournament_code=${UCL_CODE}`) || isUclActive());
      if (!shouldPatch) return response;
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) return response;
      try {
        const data = await response.clone().json();
        patchApiPayload(data);
        return new Response(JSON.stringify(data), {
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
        });
      } catch {
        return response;
      }
    };
  }

  function patchApiPayload(data) {
    if (!data || typeof data !== 'object') return data;
    if (Array.isArray(data)) {
      data.forEach(patchApiPayload);
      return data;
    }

    if (Array.isArray(data.matches)) data.matches.forEach(patchMatch);
    if (Array.isArray(data.upcoming_matches)) data.upcoming_matches.forEach(patchMatch);
    if (Array.isArray(data.future_matches)) data.future_matches.forEach(patchMatch);
    if (data.next_match) patchMatch(data.next_match);
    if (data.match) patchMatch(data.match);
    if (data.dashboard?.next_match) patchMatch(data.dashboard.next_match);

    if (data.top_scorers && Array.isArray(data.top_scorers.items)) {
      data.top_scorers.items = [];
      data.top_scorers.message = 'Бомбардиры ЛЧ появятся после первых голов турнира.';
    }
    if (Array.isArray(data.scorers)) data.scorers = [];

    return data;
  }

  function patchMatch(match) {
    if (!match || typeof match !== 'object') return;
    const home = clubFor(match.home_team || match.home_team_api_name);
    const away = clubFor(match.away_team || match.away_team_api_name);
    if (home) {
      match.home_team = home.ru;
      match.home_flag = home.flag;
      match.home_flag_code = home.flag === ENGLAND_FLAG ? 'gb-eng' : String(home.flag || '').toLowerCase();
      match.home_logo = apiSportsLogo(home.logoId);
    }
    if (away) {
      match.away_team = away.ru;
      match.away_flag = away.flag;
      match.away_flag_code = away.flag === ENGLAND_FLAG ? 'gb-eng' : String(away.flag || '').toLowerCase();
      match.away_logo = apiSportsLogo(away.logoId);
    }
  }

  function installStyles() {
    if (document.getElementById('ff-ucl-ui-patch-v395')) return;
    const style = document.createElement('style');
    style.id = 'ff-ucl-ui-patch-v395';
    style.textContent = `
      body.ucl-active .league-status-row { align-items: stretch; }
      body.ucl-active .league-status {
        flex: 1 1 auto;
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
        gap: 8px;
        padding: 0 !important;
        border: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
      }
      body.ucl-active .league-status .divider,
      body.ucl-active .league-status .header-league-divider { display: none !important; }
      body.ucl-active .header-tournament-selector,
      body.ucl-active .header-league-selector,
      body.ucl-active .league-status .status-section,
      body.ucl-active .league-status .points,
      body.ucl-active .league-status > .muted:last-child {
        min-width: 0;
        min-height: 48px;
        display: flex !important;
        align-items: center;
        justify-content: center;
        gap: 8px;
        border: 1px solid rgba(116, 146, 209, .28);
        border-radius: 18px;
        background: rgba(24, 35, 61, .78);
        padding: 10px 12px;
        color: #eef4ff;
        font-weight: 900;
        white-space: nowrap;
        overflow: hidden;
      }
      body.ucl-active .header-tournament-selector select,
      body.ucl-active .header-league-trigger,
      body.ucl-active .header-league-name {
        max-width: 100%;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      body.ucl-active .league-status .status-section {
        color: #ffcf4a;
        background: rgba(91, 68, 18, .44);
        border-color: rgba(255, 207, 74, .22);
      }
      body.ucl-active .league-status .points {
        color: #16d391;
        background: rgba(16, 75, 65, .38);
        border-color: rgba(27, 213, 147, .24);
      }
      body.ucl-active .league-status > .muted:last-child::before {
        content: 'Место ';
        color: #9daacc;
        font-weight: 800;
      }
      body.ucl-active .ucl-club-logo-large {
        width: clamp(86px, 18vw, 124px);
        height: clamp(86px, 18vw, 124px);
        border-radius: 24px;
        background: #f7f8fb;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 18px 36px rgba(0,0,0,.24);
        overflow: hidden;
        margin: 0 auto 8px;
        flex: 0 0 auto;
      }
      body.ucl-active .ucl-club-logo-large img {
        width: 74%;
        height: 74%;
        object-fit: contain;
        display: block;
      }
      body.ucl-active .ucl-club-logo-large.fallback {
        background: linear-gradient(135deg, #172745, #0d1527);
        color: #dbe7ff;
        border: 1px solid rgba(116,146,209,.34);
        font-weight: 1000;
        font-size: 30px;
      }
      body.ucl-active .ucl-country-flag-inline {
        width: 28px;
        height: 28px;
        border-radius: 999px;
        background: rgba(255,255,255,.08);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        line-height: 1;
        flex: 0 0 auto;
        margin-right: 6px;
      }
      body.ucl-active .team-side,
      body.ucl-active .next-match-team,
      body.ucl-active .detail-team,
      body.ucl-active .live-match-team { min-width: 0; }
      body.ucl-active .next-match-team strong,
      body.ucl-active .team-side strong { overflow-wrap: anywhere; }
      body.ucl-active .ucl-league-phase-table,
      body.ucl-active .ucl-standings-scroll,
      body.ucl-active .standings-table,
      body.ucl-active .group-table,
      body.ucl-active table { max-width: 100%; overflow-x: auto; }
      body.ucl-active .ucl-league-phase-table table,
      body.ucl-active .standings-table table,
      body.ucl-active .group-table table { min-width: 720px; }
      @media (max-width: 520px) {
        body.ucl-active .league-status { grid-template-columns: 1fr 1fr; }
        body.ucl-active .header-admin-button { min-height: 48px; }
        body.ucl-active .league-status-row { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: 10px; }
        body.ucl-active .league-status .status-section,
        body.ucl-active .league-status .points,
        body.ucl-active .league-status > .muted:last-child { font-size: 15px; }
      }
    `;
    document.head.appendChild(style);
  }

  let scheduled = false;
  function scheduleDecorate() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      setBodyState();
      if (!isUclActive()) return;
      decoratePredictionHero();
      normalizeVisibleEnglandFlags();
      patchTournamentTabSafety();
    });
  }

  function boot() {
    installStyles();
    patchFetch();
    scheduleDecorate();
    const observer = new MutationObserver(scheduleDecorate);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    window.addEventListener('storage', scheduleDecorate);
    window.addEventListener('click', () => setTimeout(scheduleDecorate, 40), true);
    window.setInterval(scheduleDecorate, 1500);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
