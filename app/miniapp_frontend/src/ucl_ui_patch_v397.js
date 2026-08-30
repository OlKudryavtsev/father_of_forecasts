(() => {
  if (window.__ffUclUiPatchV398) return;
  window.__ffUclUiPatchV398 = true;

  const UCL_CODE = 'ucl_2026_2027';
  const ACTIVE_TOURNAMENT_KEY = 'ff_active_tournament_code';
  const FALLBACK_START = '2026-09-08T16:45:00Z';

  function isUclActive() {
    return localStorage.getItem(ACTIVE_TOURNAMENT_KEY) === UCL_CODE
      || /(?:\?|&)tournament_code=ucl_2026_2027\b/.test(window.location.search);
  }

  function formatCountdown(value) {
    const target = new Date(value || FALLBACK_START).getTime();
    const diff = target - Date.now();
    if (!Number.isFinite(diff) || diff <= 0) return 'Общий этап';
    const h = Math.floor(diff / 3600000);
    return `До старта ${Math.floor(h / 24)}д ${h % 24}ч`;
  }

  function fixHeader() {
    if (!isUclActive()) return;
    const stage = document.querySelector('.league-status .status-section');
    if (stage && /до старта/i.test(stage.textContent || '')) {
      stage.textContent = formatCountdown(stage.dataset.startsAt || FALLBACK_START);
    }
  }

  function markStandings() {
    if (!isUclActive()) return;
    const table = document.querySelector('#ucl-league-phase-panel .ucl-phase-table');
    if (!table) return;

    Array.from(table.querySelectorAll('tbody tr')).forEach((row, index) => {
      row.classList.remove('ucl-direct', 'ucl-playoff', 'ucl-out');
      row.classList.add(index < 8 ? 'ucl-direct' : index < 24 ? 'ucl-playoff' : 'ucl-out');
      const club = row.querySelector('td:nth-child(2) .ucl-table-club strong');
      if (club) {
        club.style.setProperty('display', 'inline', 'important');
        club.style.setProperty('visibility', 'visible', 'important');
        club.style.setProperty('opacity', '1', 'important');
      }
    });

    const note = document.querySelector('#ucl-league-phase-panel .ucl-phase-note');
    if (note && !note.dataset.v398) {
      note.dataset.v398 = '1';
      note.innerHTML = '<span class="ucl-legend direct"></span>1–8 — 1/8 <span class="ucl-legend playoff"></span>9–24 — стыки <span class="ucl-legend out"></span>25–36 — вылет';
    }
  }

  function installStyles() {
    if (document.getElementById('ff-ucl-ui-patch-v398')) return;
    const style = document.createElement('style');
    style.id = 'ff-ucl-ui-patch-v398';
    style.textContent = `
      body.ucl-active .header-admin-button {
        width: 40px !important;
        height: 40px !important;
        min-width: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        padding: 0 !important;
        border-radius: 12px !important;
        align-self: flex-start !important;
      }

      body.ucl-active .ucl-league-phase-panel { padding: 10px !important; }
      body.ucl-active .ucl-table-scroll { width: 100% !important; overflow: hidden !important; }
      body.ucl-active .ucl-phase-table {
        width: 100% !important;
        min-width: 0 !important;
        table-layout: fixed !important;
        border-collapse: collapse !important;
        font-size: 10px !important;
      }
      body.ucl-active .ucl-phase-table th,
      body.ucl-active .ucl-phase-table td {
        padding: 6px 2px !important;
        min-width: 0 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
      }
      body.ucl-active .ucl-phase-table th:nth-child(1),
      body.ucl-active .ucl-phase-table td:nth-child(1) { width: 24px !important; }
      body.ucl-active .ucl-phase-table th:nth-child(2),
      body.ucl-active .ucl-phase-table td:nth-child(2) { width: 128px !important; text-align: left !important; }
      body.ucl-active .ucl-phase-table th:nth-child(3),
      body.ucl-active .ucl-phase-table td:nth-child(3),
      body.ucl-active .ucl-phase-table th:nth-child(4),
      body.ucl-active .ucl-phase-table td:nth-child(4),
      body.ucl-active .ucl-phase-table th:nth-child(5),
      body.ucl-active .ucl-phase-table td:nth-child(5),
      body.ucl-active .ucl-phase-table th:nth-child(6),
      body.ucl-active .ucl-phase-table td:nth-child(6) { width: 22px !important; }
      body.ucl-active .ucl-phase-table th:nth-child(7),
      body.ucl-active .ucl-phase-table td:nth-child(7) { width: 34px !important; }
      body.ucl-active .ucl-phase-table th:nth-child(8),
      body.ucl-active .ucl-phase-table td:nth-child(8),
      body.ucl-active .ucl-phase-table th:nth-child(9),
      body.ucl-active .ucl-phase-table td:nth-child(9) { width: 24px !important; }
      body.ucl-active .ucl-table-club {
        display: flex !important;
        align-items: center !important;
        gap: 4px !important;
        min-width: 0 !important;
        width: 100% !important;
        overflow: hidden !important;
      }
      body.ucl-active .ucl-table-club strong {
        display: inline !important;
        visibility: visible !important;
        opacity: 1 !important;
        color: #f4f7ff !important;
        font-size: 10px !important;
        font-weight: 800 !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
        min-width: 0 !important;
      }
      body.ucl-active .ucl-table-club .ucl-country-flag-inline {
        width: 18px !important;
        height: 18px !important;
        font-size: 13px !important;
        flex: 0 0 18px !important;
      }
      body.ucl-active .ucl-phase-table tbody tr.ucl-direct td:first-child {
        border-left: 4px solid #16d391 !important;
        background: rgba(22,211,145,.08) !important;
      }
      body.ucl-active .ucl-phase-table tbody tr.ucl-playoff td:first-child {
        border-left: 4px solid #ffbf35 !important;
        background: rgba(255,191,53,.08) !important;
      }
      body.ucl-active .ucl-phase-table tbody tr.ucl-out td:first-child {
        border-left: 4px solid #657089 !important;
        background: rgba(101,112,137,.08) !important;
      }
      body.ucl-active .ucl-phase-table tbody tr.ucl-direct { background: rgba(22,211,145,.035) !important; }
      body.ucl-active .ucl-phase-table tbody tr.ucl-playoff { background: rgba(255,191,53,.025) !important; }
      body.ucl-active .ucl-phase-table tbody tr.ucl-out { opacity: .74 !important; }
      body.ucl-active .ucl-phase-note {
        display: flex !important;
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 4px 7px !important;
        font-size: 10px !important;
      }
      body.ucl-active .ucl-legend {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        display: inline-block;
      }
      .ucl-legend.direct { background: #16d391; }
      .ucl-legend.playoff { background: #ffbf35; }
      .ucl-legend.out { background: #657089; }

      @media (max-width: 390px) {
        body.ucl-active .ucl-phase-table th:nth-child(2),
        body.ucl-active .ucl-phase-table td:nth-child(2) { width: 112px !important; }
        body.ucl-active .ucl-table-club strong { font-size: 9.5px !important; }
      }
    `;
    document.head.appendChild(style);
  }

  let scheduled = false;
  function render() {
    scheduled = false;
    if (!isUclActive()) return;
    fixHeader();
    markStandings();
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
