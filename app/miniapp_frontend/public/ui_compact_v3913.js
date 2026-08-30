(() => {
  if (window.__ffUiCompactV3913) return;
  window.__ffUiCompactV3913 = true;

  const nativeFetch = window.fetch.bind(window);

  function requestUrl(input) {
    try {
      if (typeof input === 'string') return new URL(input, window.location.origin);
      if (input?.url) return new URL(input.url, window.location.origin);
    } catch (_) {}
    return null;
  }

  function rowsFromPayload(payload) {
    if (!payload || typeof payload !== 'object') return [];
    const candidates = [payload.rows, payload.table, payload.items, payload.participants, payload.rating];
    return candidates.find(Array.isArray) || [];
  }

  function findUserRow(rows, user) {
    if (!Array.isArray(rows) || !user) return null;
    const userId = Number(user.id || user.user_id || 0);
    if (userId) {
      const byId = rows.find((row) => Number(row?.user_id || row?.id || 0) === userId);
      if (byId) return byId;
    }
    const displayName = String(user.display_name || user.name || '').trim();
    return displayName ? rows.find((row) => String(row?.name || row?.display_name || '').trim() === displayName) : null;
  }

  // Dashboard can return rank=null for an archived/completed tournament even though
  // the league table still contains the participant. Reuse the already existing
  // /table API as a deterministic fallback before React receives the dashboard.
  window.fetch = async function patchedFetch(input, init) {
    const response = await nativeFetch(input, init);
    const url = requestUrl(input);
    if (!url || url.origin !== window.location.origin || url.pathname !== '/api/webapp/dashboard' || !response.ok) {
      return response;
    }

    try {
      const dashboard = await response.clone().json();
      if (dashboard?.rank) return response;

      const params = new URLSearchParams(url.search);
      const tableUrl = `/api/webapp/table${params.toString() ? `?${params.toString()}` : ''}`;
      const tableResponse = await nativeFetch(tableUrl, init);
      if (!tableResponse.ok) return response;

      const tablePayload = await tableResponse.json();
      const row = findUserRow(rowsFromPayload(tablePayload), dashboard?.user);
      if (!row) return response;

      const rowRank = Number(row.rank || row.position || 0);
      if (!rowRank) {
        const rows = rowsFromPayload(tablePayload);
        const index = rows.indexOf(row);
        if (index >= 0) dashboard.rank = index + 1;
      } else {
        dashboard.rank = rowRank;
      }
      if (!dashboard.rank) return response;

      return new Response(JSON.stringify(dashboard), {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    } catch (_) {
      return response;
    }
  };

  function moveAdminButton() {
    const main = document.querySelector('.league-main');
    const rules = main?.querySelector('.rules-button');
    const admin = document.querySelector('.header-admin-button');
    if (!main || !rules || !admin) return;
    if (admin.parentElement !== main || admin.nextElementSibling !== rules) {
      main.insertBefore(admin, rules);
    }
    admin.classList.add('ff-admin-icon-v3913');
    admin.setAttribute('aria-label', 'Администрирование');
    admin.setAttribute('title', 'Администрирование');
  }

  function normalizeHeader() {
    const status = document.querySelector('.league-status');
    if (!status) return;
    status.classList.add('ff-compact-header-v3913');
    const stage = status.querySelector(':scope > .status-section');
    const points = status.querySelector(':scope > .points');
    const rank = status.querySelector(':scope > .ff-header-rank-v3912')
      || Array.from(status.querySelectorAll(':scope > .muted')).find((el) => /#|—|\d/.test(String(el.textContent || '')));
    stage?.classList.add('ff-stat-v3913');
    points?.classList.add('ff-stat-v3913');
    rank?.classList.add('ff-stat-v3913', 'ff-rank-v3913');
  }

  function installStyles() {
    if (document.getElementById('ff-ui-compact-v3913-style')) return;
    const style = document.createElement('style');
    style.id = 'ff-ui-compact-v3913-style';
    style.textContent = `
      .league-header {
        padding-bottom: 8px !important;
        margin-bottom: 8px !important;
      }
      .league-main {
        grid-template-columns: auto minmax(0,1fr) 40px auto !important;
        gap: 8px !important;
      }
      .league-main .rules-button,
      .league-main .header-admin-button.ff-admin-icon-v3913 {
        height: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        border-radius: 13px !important;
        transition: transform .2s ease, border-color .2s ease, background .2s ease !important;
      }
      .league-main .rules-button {
        padding: 0 14px !important;
      }
      .league-main .header-admin-button.ff-admin-icon-v3913 {
        width: 40px !important;
        min-width: 40px !important;
        max-width: 40px !important;
        padding: 0 !important;
        margin: 0 !important;
        display: grid !important;
        place-items: center !important;
        font-size: 0 !important;
        color: #70a2ff !important;
        background: rgba(35,53,91,.88) !important;
        border: 1px solid rgba(90,141,255,.40) !important;
      }
      .league-main .header-admin-button.ff-admin-icon-v3913 .svg-icon {
        width: 21px !important;
        height: 21px !important;
      }
      @media (hover:hover) {
        .league-main .rules-button:hover,
        .league-main .header-admin-button.ff-admin-icon-v3913:hover,
        .league-status.ff-compact-header-v3913 > .header-tournament-selector:hover,
        .league-status.ff-compact-header-v3913 > .header-league-selector:hover,
        .next-match-cta:hover {
          transform: translateY(-1px) !important;
        }
      }

      .league-status-row {
        margin-top: 10px !important;
        width: 100% !important;
      }
      .league-status.ff-compact-header-v3913 {
        width: 100% !important;
        display: grid !important;
        grid-template-columns: repeat(6,minmax(0,1fr)) !important;
        grid-template-rows: 40px 40px !important;
        gap: 7px !important;
      }
      .league-status.ff-compact-header-v3913 > .header-tournament-selector {
        grid-column: 1 / 4 !important;
        grid-row: 1 !important;
      }
      .league-status.ff-compact-header-v3913 > .header-league-selector {
        grid-column: 4 / 7 !important;
        grid-row: 1 !important;
      }
      .league-status.ff-compact-header-v3913 > .status-section {
        grid-column: 1 / 3 !important;
        grid-row: 2 !important;
      }
      .league-status.ff-compact-header-v3913 > .points {
        grid-column: 3 / 5 !important;
        grid-row: 2 !important;
      }
      .league-status.ff-compact-header-v3913 > .ff-rank-v3913 {
        grid-column: 5 / 7 !important;
        grid-row: 2 !important;
      }
      .league-status.ff-compact-header-v3913 > .header-tournament-selector,
      .league-status.ff-compact-header-v3913 > .header-league-selector,
      .league-status.ff-compact-header-v3913 > .ff-stat-v3913 {
        width: 100% !important;
        height: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        margin: 0 !important;
        box-sizing: border-box !important;
        border-radius: 13px !important;
        overflow: hidden !important;
        transition: transform .2s ease, border-color .2s ease, background .2s ease !important;
      }
      .league-status.ff-compact-header-v3913 > .header-tournament-selector,
      .league-status.ff-compact-header-v3913 > .header-league-selector {
        padding: 0 10px !important;
      }
      .league-status.ff-compact-header-v3913 > .ff-stat-v3913 {
        padding: 0 7px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 12.5px !important;
        line-height: 1 !important;
        white-space: nowrap !important;
        text-overflow: ellipsis !important;
      }
      .league-status.ff-compact-header-v3913 > .ff-rank-v3913::before {
        content: 'Место ' !important;
        margin-right: 2px !important;
        font-size: 10px !important;
      }
      .league-status.ff-compact-header-v3913 > .divider { display: none !important; }

      /* Compact quick-prediction hero: same information, substantially less vertical chrome. */
      .next-match-hero {
        padding: 11px !important;
        border-radius: 20px !important;
      }
      .next-match-hero-top {
        margin-bottom: 8px !important;
        gap: 8px !important;
      }
      .next-match-kicker { font-size: 12px !important; }
      .next-match-countdown {
        padding: 4px 8px !important;
        font-size: 11px !important;
      }
      .next-match-teams {
        margin-bottom: 8px !important;
        gap: 6px !important;
      }
      .next-match-team { gap: 4px !important; }
      .next-match-team strong { font-size: 13px !important; }
      .next-match-team .flag {
        width: 44px !important;
        height: 32px !important;
      }
      body.ucl-active .next-match-team .flag {
        width: 66px !important;
        height: 66px !important;
        border-radius: 14px !important;
      }
      .next-match-versus { gap: 3px !important; }
      .next-match-versus b { font-size: 20px !important; }
      .next-match-versus small { font-size: 10px !important; }
      .next-match-status {
        min-height: 34px !important;
        margin-bottom: 8px !important;
        padding: 6px 9px !important;
        border-radius: 12px !important;
        gap: 6px !important;
      }
      .next-match-status > span {
        width: 18px !important;
        height: 18px !important;
      }
      .next-match-status strong { font-size: 12.5px !important; }
      .next-match-status small { font-size: 10px !important; padding-left: 24px !important; }
      .next-match-cta {
        min-height: 40px !important;
        height: 40px !important;
        border-radius: 13px !important;
        font-size: 13px !important;
        transition: transform .2s ease, filter .2s ease !important;
      }

      @media (max-width: 390px) {
        .league-main { grid-template-columns: auto minmax(0,1fr) 38px auto !important; gap: 7px !important; }
        .league-main .rules-button,
        .league-main .header-admin-button.ff-admin-icon-v3913 {
          height: 38px !important;
          min-height: 38px !important;
          max-height: 38px !important;
        }
        .league-main .header-admin-button.ff-admin-icon-v3913 { width: 38px !important; min-width: 38px !important; max-width: 38px !important; }
        .league-main .rules-button { padding: 0 12px !important; }
        .league-status.ff-compact-header-v3913 {
          grid-template-rows: 38px 38px !important;
          gap: 6px !important;
        }
        .league-status.ff-compact-header-v3913 > .header-tournament-selector,
        .league-status.ff-compact-header-v3913 > .header-league-selector,
        .league-status.ff-compact-header-v3913 > .ff-stat-v3913 {
          height: 38px !important;
          min-height: 38px !important;
          max-height: 38px !important;
          border-radius: 12px !important;
        }
        .league-status.ff-compact-header-v3913 > .header-tournament-selector,
        .league-status.ff-compact-header-v3913 > .header-league-selector { padding: 0 8px !important; }
        .league-status.ff-compact-header-v3913 > .ff-stat-v3913 { font-size: 11.5px !important; padding: 0 5px !important; }
        .league-status.ff-compact-header-v3913 > .ff-rank-v3913::before { content: '№' !important; font-size: 10px !important; }
        .next-match-hero { padding: 10px !important; }
        body.ucl-active .next-match-team .flag { width: 58px !important; height: 58px !important; }
      }
    `;
    document.head.appendChild(style);
  }

  let scheduled = false;
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      moveAdminButton();
      normalizeHeader();
    });
  }

  function boot() {
    installStyles();
    schedule();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    document.addEventListener('click', () => setTimeout(schedule, 30), true);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
