(() => {
  if (window.__ffUclUiPatchV397) return;
  window.__ffUclUiPatchV397 = true;

  const UCL_CODE = 'ucl_2026_2027';
  const ACTIVE_TOURNAMENT_KEY = 'ff_active_tournament_code';
  const FALLBACK_START = '2026-09-08T16:45:00Z';

  function isUclActive() {
    return localStorage.getItem(ACTIVE_TOURNAMENT_KEY) === UCL_CODE
      || /(?:\?|&)tournament_code=ucl_2026_2027\b/.test(window.location.search);
  }

  function formatCountdown(targetValue) {
    const target = new Date(targetValue || FALLBACK_START).getTime();
    const diff = target - Date.now();
    if (!Number.isFinite(diff) || diff <= 0) return 'Общий этап';
    const totalHours = Math.floor(diff / 3600000);
    const days = Math.floor(totalHours / 24);
    const hours = totalHours % 24;
    return `До старта ${days}д ${hours}ч`;
  }

  function fixHeader() {
    if (!isUclActive()) return;
    const status = document.querySelector('.league-status');
    if (!status) return;

    status.classList.add('ucl-status-v397');
    const stage = status.querySelector('.status-section');
    const points = status.querySelector('.points');
    const rank = status.querySelector(':scope > .muted:last-child');

    if (stage && /до старта/i.test(stage.textContent || '')) {
      stage.textContent = formatCountdown(stage.dataset.startsAt || FALLBACK_START);
    }

    if (points && rank && !status.querySelector('.ucl-score-rank')) {
      const wrap = document.createElement('div');
      wrap.className = 'ucl-score-rank';
      points.parentNode.insertBefore(wrap, points);
      wrap.append(points, rank);
    }
  }

  function markStandingsZones() {
    if (!isUclActive()) return;
    const table = document.querySelector('#ucl-league-phase-panel .ucl-phase-table');
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    rows.forEach((row, index) => {
      row.classList.remove('ucl-direct', 'ucl-playoff', 'ucl-out');
      const pos = index + 1;
      if (pos <= 8) row.classList.add('ucl-direct');
      else if (pos <= 24) row.classList.add('ucl-playoff');
      else row.classList.add('ucl-out');
    });

    const note = document.querySelector('#ucl-league-phase-panel .ucl-phase-note');
    if (note && !note.dataset.v397) {
      note.dataset.v397 = '1';
      note.innerHTML = '<span class="ucl-legend direct"></span>1–8 — 1/8 финала <span class="ucl-legend playoff"></span>9–24 — стыки <span class="ucl-legend out"></span>25–36 — вылет';
    }
  }

  function installStyles() {
    if (document.getElementById('ff-ucl-ui-patch-v397')) return;
    const style = document.createElement('style');
    style.id = 'ff-ucl-ui-patch-v397';
    style.textContent = `
      body.ucl-active .league-status-row {
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        padding: 0 !important;
      }
      body.ucl-active .league-status.ucl-status-v397 {
        display: grid !important;
        grid-template-columns: minmax(0,1fr) minmax(0,1fr) !important;
        gap: 8px !important;
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        padding: 0 !important;
      }
      body.ucl-active .league-status.ucl-status-v397 .header-tournament-selector,
      body.ucl-active .league-status.ucl-status-v397 .header-league-selector {
        grid-column: span 1 !important;
      }
      body.ucl-active .league-status.ucl-status-v397 .status-section {
        grid-column: 1 / 2 !important;
        min-height: 42px !important;
        border-radius: 14px !important;
        font-size: 14px !important;
      }
      body.ucl-active .league-status.ucl-status-v397 .ucl-score-rank {
        grid-column: 2 / 3 !important;
        display: grid !important;
        grid-template-columns: 1fr auto !important;
        align-items: center !important;
        min-height: 42px !important;
        border: 1px solid rgba(27,213,147,.24) !important;
        border-radius: 14px !important;
        background: rgba(13,72,62,.42) !important;
        overflow: hidden !important;
      }
      body.ucl-active .league-status.ucl-status-v397 .ucl-score-rank .points,
      body.ucl-active .league-status.ucl-status-v397 .ucl-score-rank > .muted {
        min-height: 40px !important;
        border: 0 !important;
        background: transparent !important;
        border-radius: 0 !important;
        padding: 8px 10px !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
      }
      body.ucl-active .league-status.ucl-status-v397 .ucl-score-rank > .muted {
        border-left: 1px solid rgba(27,213,147,.18) !important;
        color: #c4cee2 !important;
      }
      body.ucl-active .league-status.ucl-status-v397 .ucl-score-rank > .muted::before {
        content: '#';
        margin-right: 1px;
        color: #9daacc;
      }

      body.ucl-active .ucl-league-phase-panel { padding: 12px !important; }
      body.ucl-active .ucl-table-scroll { overflow: visible !important; width: 100% !important; }
      body.ucl-active .ucl-phase-table {
        width: 100% !important;
        min-width: 0 !important;
        table-layout: fixed !important;
        font-size: 11px !important;
      }
      body.ucl-active .ucl-phase-table th,
      body.ucl-active .ucl-phase-table td {
        padding: 7px 3px !important;
        min-width: 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
      }
      body.ucl-active .ucl-phase-table th:nth-child(1), body.ucl-active .ucl-phase-table td:nth-child(1) { width: 28px !important; }
      body.ucl-active .ucl-phase-table th:nth-child(2), body.ucl-active .ucl-phase-table td:nth-child(2) { width: auto !important; min-width: 0 !important; }
      body.ucl-active .ucl-phase-table th:nth-child(n+3):not(:nth-child(7)),
      body.ucl-active .ucl-phase-table td:nth-child(n+3):not(:nth-child(7)) { width: 28px !important; }
      body.ucl-active .ucl-phase-table th:nth-child(7), body.ucl-active .ucl-phase-table td:nth-child(7) { width: 40px !important; }
      body.ucl-active .ucl-table-club { min-width: 0 !important; max-width: 100% !important; gap: 4px !important; }
      body.ucl-active .ucl-table-club strong { overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important; }
      body.ucl-active .ucl-table-club .ucl-country-flag-inline { width: 20px !important; height: 20px !important; font-size: 14px !important; }

      body.ucl-active .ucl-phase-table tbody tr { position: relative; }
      body.ucl-active .ucl-phase-table tbody tr::before {
        content: '';
        position: absolute;
        left: 0;
        top: 5px;
        bottom: 5px;
        width: 3px;
        border-radius: 3px;
      }
      body.ucl-active .ucl-phase-table tbody tr.ucl-direct::before { background:#16d391; }
      body.ucl-active .ucl-phase-table tbody tr.ucl-playoff::before { background:#ffbf35; }
      body.ucl-active .ucl-phase-table tbody tr.ucl-out::before { background:#657089; }
      body.ucl-active .ucl-phase-table tbody tr.ucl-direct { background:rgba(22,211,145,.045); }
      body.ucl-active .ucl-phase-table tbody tr.ucl-playoff { background:rgba(255,191,53,.035); }
      body.ucl-active .ucl-phase-table tbody tr.ucl-out { opacity:.72; }
      body.ucl-active .ucl-phase-note { display:flex; flex-wrap:wrap; align-items:center; gap:5px 8px; font-size:11px !important; }
      body.ucl-active .ucl-legend { width:9px; height:9px; border-radius:999px; display:inline-block; }
      body.ucl-active .ucl-legend.direct { background:#16d391; }
      body.ucl-active .ucl-legend.playoff { background:#ffbf35; }
      body.ucl-active .ucl-legend.out { background:#657089; }

      @media (max-width: 390px) {
        body.ucl-active .ucl-phase-table { font-size: 10px !important; }
        body.ucl-active .ucl-phase-table th, body.ucl-active .ucl-phase-table td { padding: 6px 2px !important; }
        body.ucl-active .ucl-phase-table th:nth-child(n+3):not(:nth-child(7)),
        body.ucl-active .ucl-phase-table td:nth-child(n+3):not(:nth-child(7)) { width: 25px !important; }
        body.ucl-active .ucl-phase-table th:nth-child(7), body.ucl-active .ucl-phase-table td:nth-child(7) { width: 36px !important; }
        body.ucl-active .ucl-table-club .ucl-country-flag-inline { width:18px !important; height:18px !important; font-size:13px !important; }
      }
    `;
    document.head.appendChild(style);
  }

  let scheduled = false;
  function render() {
    scheduled = false;
    if (!isUclActive()) return;
    fixHeader();
    markStandingsZones();
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(render);
  }
  function boot() {
    installStyles();
    schedule();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    document.addEventListener('click', () => setTimeout(schedule, 40), true);
    window.setInterval(schedule, 60000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
