const UCL_TOURNAMENT_CODE = 'ucl_2026_2027';
const ACTIVE_TOURNAMENT_STORAGE_KEY = 'ff_active_tournament_code';

function readActiveTournamentCode() {
  const selectorValue = document.querySelector('.header-tournament-selector select')?.value;
  return selectorValue || localStorage.getItem(ACTIVE_TOURNAMENT_STORAGE_KEY) || '';
}

function isUclActive() {
  return readActiveTournamentCode() === UCL_TOURNAMENT_CODE;
}

function isUclTournamentRequest(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.searchParams.get('tournament_code') === UCL_TOURNAMENT_CODE || isUclActive();
  } catch (_) {
    return isUclActive();
  }
}

function installUclFetchPatch() {
  const originalFetch = window.fetch?.bind(window);
  if (!originalFetch || window.__ffUclFetchPatchInstalled) return;
  window.__ffUclFetchPatchInstalled = true;

  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';
    let parsed = null;
    try {
      parsed = new URL(url, window.location.origin);
    } catch (_) {
      parsed = null;
    }

    if (parsed?.pathname === '/api/webapp/top-scorer-candidates' && isUclActive()) {
      return new Response(JSON.stringify({
        candidates: [],
        hint: 'Для ЛЧ 2026/27 выбери бомбардира вручную: начни вводить имя игрока.'
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (parsed?.pathname === '/api/webapp/tournament-prediction' && isUclTournamentRequest(url)) {
      const nextInit = { ...(init || {}) };
      if (typeof nextInit.body === 'string') {
        try {
          const payload = JSON.parse(nextInit.body);
          payload.third_place = '';
          nextInit.body = JSON.stringify(payload);
        } catch (_) {
        }
      }
      return originalFetch(input, nextInit);
    }

    return originalFetch(input, init);
  };
}

function hideThirdPlaceElementsForUcl() {
  const active = isUclActive();
  document.documentElement.classList.toggle('ff-ucl-tournament', active);

  const candidates = document.querySelectorAll([
    '.tournament-mini-card',
    '.tournament-mini-card-edit',
    '.modal-card article',
    '.modal-card button',
    '.modal-card label',
    '.modal-card .form-row',
    '.modal-card .field',
    '.modal-card .picker-section',
  ].join(','));

  candidates.forEach((element) => {
    const text = (element.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const aria = (element.getAttribute('aria-label') || '').toLowerCase();
    const isThirdPlace = text.includes('3-е место') || text.includes('3 место') || aria.includes('third_place') || aria.includes('3-е место');
    if (!isThirdPlace) return;

    if (active) {
      element.dataset.ffUclHiddenThirdPlace = '1';
      element.setAttribute('hidden', '');
    } else if (element.dataset.ffUclHiddenThirdPlace === '1') {
      element.removeAttribute('hidden');
      delete element.dataset.ffUclHiddenThirdPlace;
    }
  });

  if (active) {
    document.querySelectorAll('.tournament-mini-actions span').forEach((element) => {
      const match = String(element.textContent || '').trim().match(/^(\d+)\/4$/);
      if (!match) return;
      const value = Math.min(Number(match[1] || 0), 3);
      element.textContent = `${value}/3`;
    });
  }
}

function installUclDomPatch() {
  const run = () => hideThirdPlaceElementsForUcl();
  run();

  document.addEventListener('change', (event) => {
    if (event.target?.matches?.('.header-tournament-selector select')) {
      window.setTimeout(run, 0);
      window.setTimeout(run, 250);
    }
  }, true);

  const observer = new MutationObserver(() => run());
  observer.observe(document.documentElement, { childList: true, subtree: true });
}

installUclFetchPatch();
installUclDomPatch();
