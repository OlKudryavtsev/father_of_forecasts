(() => {
  if (window.__ffUnifiedHeaderV3914) return;
  window.__ffUnifiedHeaderV3914 = true;

  function restoreDirectChildren(status) {
    if (!status) return;
    ['.ff-header-score', '.ucl-score-rank'].forEach((selector) => {
      const wrapper = status.querySelector(`:scope > ${selector}`);
      if (!wrapper) return;
      Array.from(wrapper.children).forEach((child) => status.insertBefore(child, wrapper));
      wrapper.remove();
    });
  }

  function findRank(status) {
    return Array.from(status.querySelectorAll(':scope > .muted')).find((el) => /#|\d|—/.test(String(el.textContent || ''))) || null;
  }

  function normalizeHeader() {
    const status = document.querySelector('.league-status');
    if (!status) return;

    restoreDirectChildren(status);

    const tournament = status.querySelector(':scope > .header-tournament-selector');
    const league = status.querySelector(':scope > .header-league-selector');
    const stage = status.querySelector(':scope > .status-section');
    const points = status.querySelector(':scope > .points');
    const rank = findRank(status);
    if (!tournament || !league || !stage || !points || !rank) return;

    status.classList.add('ff-header-unified-v3914');
    status.dataset.ffUnifiedHeader = '4';

    tournament.classList.add('ff-header-control-v3914');
    league.classList.add('ff-header-control-v3914');
    stage.classList.add('ff-header-stat-v3914', 'ff-header-stage-v3914');
    points.classList.add('ff-header-stat-v3914', 'ff-header-points-v3914');
    rank.classList.add('ff-header-stat-v3914', 'ff-header-rank-v3914');

    const text = String(rank.textContent || '').trim();
    const match = text.match(/(\d+)/);
    const normalized = match ? `#${match[1]}` : '#—';
    if (rank.textContent !== normalized) rank.textContent = normalized;
  }

  function installStyles() {
    if (document.getElementById('ff-header-unified-v3914-style')) return;

    const style = document.createElement('style');
    style.id = 'ff-header-unified-v3914-style';
    style.textContent = `
      html body .league-status-row {
        width: 100% !important;
        margin-top: 10px !important;
        padding: 0 !important;
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        overflow: visible !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] {
        --ff-header-tile-height: 40px;
        width: 100% !important;
        min-width: 0 !important;
        flex: 1 1 auto !important;
        display: grid !important;
        grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
        grid-template-rows: var(--ff-header-tile-height) var(--ff-header-tile-height) !important;
        gap: 7px !important;
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        clip-path: none !important;
        mask: none !important;
        overflow: visible !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .header-tournament-selector {
        grid-column: 1 / 4 !important;
        grid-row: 1 !important;
      }
      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .header-league-selector {
        grid-column: 4 / 7 !important;
        grid-row: 1 !important;
      }
      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .status-section {
        grid-column: 1 / 3 !important;
        grid-row: 2 !important;
      }
      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .points {
        grid-column: 3 / 5 !important;
        grid-row: 2 !important;
      }
      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-rank-v3914 {
        grid-column: 5 / 7 !important;
        grid-row: 2 !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-control-v3914,
      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-stat-v3914 {
        width: 100% !important;
        min-width: 0 !important;
        height: var(--ff-header-tile-height) !important;
        min-height: var(--ff-header-tile-height) !important;
        max-height: var(--ff-header-tile-height) !important;
        margin: 0 !important;
        box-sizing: border-box !important;
        border-radius: 13px !important;
        clip-path: none !important;
        mask: none !important;
        transform: none !important;
        overflow: hidden !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-control-v3914 {
        padding: 0 10px !important;
        display: flex !important;
        align-items: center !important;
        background: rgba(24,35,61,.92) !important;
        border: 1px solid rgba(116,146,209,.34) !important;
        box-shadow: inset 0 0 0 1px rgba(116,146,209,.05) !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-stat-v3914 {
        padding: 0 7px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 12.5px !important;
        font-weight: 900 !important;
        line-height: 1 !important;
        white-space: nowrap !important;
        text-overflow: ellipsis !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-stage-v3914 {
        color: #ffd047 !important;
        background: linear-gradient(180deg, rgba(92,66,18,.72), rgba(58,43,17,.72)) !important;
        border: 1px solid rgba(255,196,58,.24) !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-points-v3914 {
        color: #1bd394 !important;
        background: rgba(8,66,57,.56) !important;
        border: 1px solid rgba(24,209,146,.36) !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-rank-v3914 {
        color: #f4f7ff !important;
        background: linear-gradient(180deg, rgba(95,108,196,.40), rgba(44,56,120,.40)) !important;
        border: 1px solid rgba(117,151,255,.38) !important;
        opacity: 1 !important;
        visibility: visible !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-rank-v3914::before {
        content: 'Место ' !important;
        margin-right: 3px !important;
        color: #b9c7f3 !important;
        font-size: 10px !important;
        font-weight: 850 !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .divider {
        display: none !important;
      }

      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] .header-tournament-selector select,
      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] .header-league-trigger,
      html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] .header-league-name {
        min-width: 0 !important;
        max-width: 100% !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
      }

      @media (max-width: 390px) {
        html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] {
          --ff-header-tile-height: 38px;
          gap: 6px !important;
        }
        html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-control-v3914,
        html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-stat-v3914 {
          border-radius: 12px !important;
        }
        html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-control-v3914 {
          padding-left: 8px !important;
          padding-right: 8px !important;
        }
        html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-stat-v3914 {
          padding-left: 5px !important;
          padding-right: 5px !important;
          font-size: 11.5px !important;
        }
        html body .league-status.ff-header-unified-v3914[data-ff-unified-header="4"] > .ff-header-rank-v3914::before {
          content: '' !important;
          margin-right: 0 !important;
        }
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
      normalizeHeader();
    });
  }

  function boot() {
    installStyles();
    schedule();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    document.addEventListener('click', () => setTimeout(schedule, 30), true);
    window.addEventListener('storage', schedule);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
