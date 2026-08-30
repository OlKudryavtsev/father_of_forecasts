(() => {
  if (window.__ffUclUiPatchV399) return;
  window.__ffUclUiPatchV399 = true;

  function install() {
    if (document.getElementById('ff-ucl-ui-patch-v399')) return;
    const style = document.createElement('style');
    style.id = 'ff-ucl-ui-patch-v399';
    style.textContent = `
      body.ucl-active .league-status.ucl-status-v398 {
        grid-template-columns: minmax(0,1fr) minmax(0,1fr) !important;
        column-gap: 8px !important;
      }
      body.ucl-active .league-status.ucl-status-v398 .header-tournament-selector,
      body.ucl-active .league-status.ucl-status-v398 .header-league-selector {
        width: 100% !important; max-width: none !important; min-width: 0 !important;
        justify-self: stretch !important; box-sizing: border-box !important;
      }
      body.ucl-active .league-status.ucl-status-v398 .header-tournament-selector { grid-column: 1 / 2 !important; }
      body.ucl-active .league-status.ucl-status-v398 .header-league-selector { grid-column: 2 / 3 !important; }
      body.ucl-active .league-status.ucl-status-v398 .status-section {
        grid-column: 1 / 2 !important; width: 100% !important; max-width: none !important;
        min-width: 0 !important; justify-self: stretch !important; box-sizing: border-box !important;
      }
      body.ucl-active .league-status.ucl-status-v398 .ucl-score-rank {
        grid-column: 2 / 3 !important; width: 100% !important; max-width: none !important;
        min-width: 0 !important; justify-self: stretch !important; box-sizing: border-box !important;
        display: grid !important; grid-template-columns: minmax(0,1fr) minmax(0,.72fr) !important;
      }
      body.ucl-active .league-status.ucl-status-v398 .ucl-score-rank .points { min-width: 0 !important; font-weight: 900 !important; }
      body.ucl-active .league-status.ucl-status-v398 .ucl-score-rank > .muted {
        min-width: 0 !important; color: #f5f7ff !important; font-weight: 950 !important;
        background: rgba(89,122,255,.18) !important; border-left: 1px solid rgba(117,151,255,.40) !important;
        text-shadow: 0 0 12px rgba(117,151,255,.22) !important;
      }
      body.ucl-active .league-status.ucl-status-v398 .ucl-score-rank > .muted::before {
        content: 'Место ' !important; color: #aab9dd !important; font-weight: 800 !important; margin-right: 3px !important;
      }
      @media (max-width:390px) {
        body.ucl-active .league-status.ucl-status-v398 { column-gap: 7px !important; }
        body.ucl-active .league-status.ucl-status-v398 .ucl-score-rank { grid-template-columns:minmax(0,1fr) minmax(0,.68fr) !important; }
        body.ucl-active .league-status.ucl-status-v398 .ucl-score-rank > .muted::before { content:'№' !important; margin-right:1px !important; }
      }
    `;
    document.head.appendChild(style);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
})();
