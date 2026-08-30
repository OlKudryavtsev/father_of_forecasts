(() => {
  if (window.__ffUnifiedHeaderV3912) return;
  window.__ffUnifiedHeaderV3912 = true;

  function restoreDirectChildren(status) {
    if (!status) return;
    ['.ff-header-score', '.ucl-score-rank'].forEach((selector) => {
      const wrapper = status.querySelector(`:scope > ${selector}`);
      if (!wrapper) return;
      Array.from(wrapper.children).forEach((child) => status.insertBefore(child, wrapper));
      wrapper.remove();
    });
  }

  function normalizeHeader() {
    const status = document.querySelector('.league-status');
    if (!status) return;
    restoreDirectChildren(status);

    const tournament = status.querySelector(':scope > .header-tournament-selector');
    const league = status.querySelector(':scope > .header-league-selector');
    const stage = status.querySelector(':scope > .status-section');
    const points = status.querySelector(':scope > .points');
    const rank = Array.from(status.querySelectorAll(':scope > .muted')).find((el) => /#|\d|—/.test(String(el.textContent || '')));
    if (!tournament || !league || !stage || !points || !rank) return;

    status.classList.add('ff-header-unified-v3912');
    status.dataset.ffUnifiedHeader = '2';
    tournament.classList.add('ff-header-selector-v3912');
    league.classList.add('ff-header-selector-v3912');
    stage.classList.add('ff-header-stat-v3912', 'ff-header-stage-v3912');
    points.classList.add('ff-header-stat-v3912', 'ff-header-points-v3912');
    rank.classList.add('ff-header-stat-v3912', 'ff-header-rank-v3912');

    const text = String(rank.textContent || '').trim();
    const match = text.match(/(\d+)/);
    rank.textContent = match ? `#${match[1]}` : '#—';
  }

  function installStyles() {
    if (document.getElementById('ff-header-unified-v3912-style')) return;
    const style = document.createElement('style');
    style.id = 'ff-header-unified-v3912-style';
    style.textContent = `
      .league-status-row {
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        clip-path: none !important;
        mask: none !important;
        padding: 0 !important;
        overflow: visible !important;
        align-items: flex-start !important;
      }
      .league-status.ff-header-unified-v3912[data-ff-unified-header="2"] {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        display: grid !important;
        grid-template-columns: minmax(0,1fr) minmax(0,1fr) minmax(0,1.2fr) minmax(0,.8fr) !important;
        grid-template-rows: 54px 44px !important;
        gap: 8px !important;
        padding: 0 !important;
        margin: 0 !important;
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        clip-path: none !important;
        mask: none !important;
        overflow: visible !important;
      }
      .league-status.ff-header-unified-v3912 > .header-tournament-selector { grid-column: 1 / 3 !important; grid-row: 1 !important; }
      .league-status.ff-header-unified-v3912 > .header-league-selector { grid-column: 3 / 5 !important; grid-row: 1 !important; }
      .league-status.ff-header-unified-v3912 > .status-section { grid-column: 1 / 3 !important; grid-row: 2 !important; }
      .league-status.ff-header-unified-v3912 > .points { grid-column: 3 !important; grid-row: 2 !important; }
      .league-status.ff-header-unified-v3912 > .ff-header-rank-v3912 { grid-column: 4 !important; grid-row: 2 !important; }

      .league-status.ff-header-unified-v3912 > .ff-header-selector-v3912 {
        width: 100% !important;
        max-width: none !important;
        min-width: 0 !important;
        height: 54px !important;
        min-height: 54px !important;
        max-height: 54px !important;
        margin: 0 !important;
        padding: 0 14px !important;
        display: flex !important;
        align-items: center !important;
        box-sizing: border-box !important;
        background: rgba(24,35,61,.92) !important;
        border: 1px solid rgba(116,146,209,.34) !important;
        border-radius: 17px !important;
        box-shadow: inset 0 0 0 1px rgba(116,146,209,.05) !important;
        clip-path: none !important;
        mask: none !important;
        transform: none !important;
        overflow: hidden !important;
      }
      .league-status.ff-header-unified-v3912 > .ff-header-stat-v3912 {
        width: 100% !important;
        min-width: 0 !important;
        height: 44px !important;
        min-height: 44px !important;
        max-height: 44px !important;
        margin: 0 !important;
        padding: 4px 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-sizing: border-box !important;
        border-radius: 13px !important;
        line-height: 1 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        clip-path: none !important;
        mask: none !important;
        transform: none !important;
      }
      .league-status.ff-header-unified-v3912 > .ff-header-stage-v3912 {
        background: linear-gradient(180deg, rgba(92,66,18,.72), rgba(58,43,17,.72)) !important;
        border: 1px solid rgba(255,196,58,.24) !important;
        color: #ffd047 !important;
        font-size: 15px !important;
        font-weight: 950 !important;
        padding-left: 10px !important;
        padding-right: 10px !important;
      }
      .league-status.ff-header-unified-v3912 > .ff-header-points-v3912 {
        background: rgba(8,66,57,.56) !important;
        border: 1px solid rgba(24,209,146,.36) !important;
        color: #1bd394 !important;
        font-size: 15px !important;
        font-weight: 950 !important;
      }
      .league-status.ff-header-unified-v3912 > .ff-header-rank-v3912 {
        background: linear-gradient(180deg, rgba(95,108,196,.40), rgba(44,56,120,.40)) !important;
        border: 1px solid rgba(117,151,255,.38) !important;
        color: #f4f7ff !important;
        font-size: 14px !important;
        font-weight: 1000 !important;
        opacity: 1 !important;
        visibility: visible !important;
      }
      .league-status.ff-header-unified-v3912 > .ff-header-rank-v3912::before {
        content: 'Место ';
        margin-right: 3px;
        color: #b9c7f3 !important;
        font-size: 11px !important;
        font-weight: 850 !important;
      }
      .league-status.ff-header-unified-v3912 > .divider { display: none !important; }
      .league-status.ff-header-unified-v3912 .header-tournament-selector select,
      .league-status.ff-header-unified-v3912 .header-league-trigger,
      .league-status.ff-header-unified-v3912 .header-league-name {
        min-width: 0 !important;
        max-width: 100% !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
      }
      @media (max-width: 390px) {
        .league-status.ff-header-unified-v3912[data-ff-unified-header="2"] {
          grid-template-rows: 50px 40px !important;
          gap: 7px !important;
        }
        .league-status.ff-header-unified-v3912 > .ff-header-selector-v3912 {
          height: 50px !important;
          min-height: 50px !important;
          max-height: 50px !important;
          padding-left: 11px !important;
          padding-right: 11px !important;
          border-radius: 15px !important;
        }
        .league-status.ff-header-unified-v3912 > .ff-header-stat-v3912 {
          height: 40px !important;
          min-height: 40px !important;
          max-height: 40px !important;
          border-radius: 11px !important;
          font-size: 13px !important;
        }
        .league-status.ff-header-unified-v3912 > .ff-header-rank-v3912::before {
          content: '№';
          margin-right: 1px;
          font-size: 11px !important;
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
    document.addEventListener('click', () => setTimeout(schedule, 40), true);
    window.addEventListener('storage', schedule);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
