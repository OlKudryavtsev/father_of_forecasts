const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  tab: 'home',
  currentMatch: null,
  scoreHome: 1,
  scoreAway: 1,
  quickQuizQuestion: null,
  tournamentTeams: [],
  topScorerCandidates: [],
  topScorerHint: '',
};

function initData() {
  return tg?.initData || '';
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData(),
      ...(options.headers || {}),
    },
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || 'Ошибка запроса');
  }

  return payload;
}

function showStatus(text, isError = false) {
  const status = document.querySelector('#status');
  status.textContent = text;
  status.classList.toggle('error', isError);
  status.classList.remove('hidden');
  setTimeout(() => status.classList.add('hidden'), 4500);
}

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.tab').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === tab);
  });
  document.querySelectorAll('.screen').forEach((screen) => {
    screen.classList.toggle('active', screen.id === tab);
  });
  loadCurrentTab();
}

function activateTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.tab').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === tab);
  });
  document.querySelectorAll('.screen').forEach((screen) => {
    screen.classList.toggle('active', screen.id === tab);
  });
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDaysLeft(days) {
  const lastTwo = days % 100;
  const last = days % 10;

  if (lastTwo >= 11 && lastTwo <= 14) return `${days} дней`;
  if (last === 1) return `${days} день`;
  if (last >= 2 && last <= 4) return `${days} дня`;
  return `${days} дней`;
}

function navigateToTournament() {
  setTab('tournament');
}

function navigateToNearestPredictions() {
  activateTab('predictions');
  loadPredictions('nearest');
}

function escapeForAttribute(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}

function renderLoading(container, text = 'Загружаю...') {
  container.innerHTML = `<div class="card muted">${text}</div>`;
}

function predictionBadge(match) {
  if (!match.prediction) {
    return '<span class="badge warning">прогноза нет</span>';
  }
  const p = match.prediction;
  return `<span class="badge success">мой прогноз ${p.pred_home}:${p.pred_away}</span>`;
}

function matchCard(match, includePredictButton = true) {
  return `
    <article class="card compact">
      <div class="match-title">${match.label}</div>
      <div class="match-meta">
        Старт: ${formatDate(match.starts_at)}<br>
        ${match.venue || match.city ? `Стадион: ${[match.venue, match.city].filter(Boolean).join(', ')}<br>` : ''}
        ${predictionBadge(match)}
        ${match.is_playoff ? '<span class="badge">плей-офф</span>' : ''}
      </div>
      ${includePredictButton ? `
        <div class="actions">
          <button class="primary" onclick="openPrediction(${match.id})">Сделать прогноз</button>
          <button onclick="openForecast(${match.id})">🤖 Прогноз Отца</button>
        </div>
      ` : ''}
    </article>
  `;
}

async function loadHome() {
  const container = document.querySelector('#home');
  renderLoading(container);

  try {
    const dashboard = await api('/api/webapp/dashboard');
    const tournamentNotice = dashboard.tournament && !dashboard.tournament.is_started && !dashboard.tournament.has_prediction
      ? `
        <div class="card notice-card">
          <div class="badge warning">Турнирный прогноз не сделан</div>
          <h2>До старта ЧМ-2026 — ${formatDaysLeft(dashboard.tournament.days_until_start)}</h2>
          <p class="muted">Пока не поздно, внеси долгосрочный прогноз: чемпион, финалист, 3 место и бомбардир.</p>
          <button class="primary" onclick="navigateToTournament()">Перейти к турнирному прогнозу</button>
        </div>
      `
      : '';

    const nearestNotice = dashboard.nearest_missing_predictions_count > 0
      ? `
        <div class="card notice-card">
          <div class="badge warning">Ближайший игровой день</div>
          <h2>Нет прогнозов на ${dashboard.nearest_missing_predictions_count} матч(а)</h2>
          <p class="muted">Сделай прогнозы заранее — после стартового свистка Отец прогнозов уже ничего не примет.</p>
          <button class="primary" onclick="navigateToNearestPredictions()">Сделать прогнозы на ближайшие матчи</button>
        </div>
      `
      : '';

    container.innerHTML = `
      ${tournamentNotice}
      ${nearestNotice}

      <section class="grid">
        <div class="card">
          <h2>Привет, ${dashboard.user.display_name}</h2>
          <p class="muted">Очки: <strong>${dashboard.points}</strong>${dashboard.rank ? ` · место: <strong>${dashboard.rank}</strong>` : ''}</p>
        </div>
        <div class="card">
          <h2>Пропущенные прогнозы</h2>
          <p class="muted">Всего матчей без прогноза: <strong>${dashboard.missing_predictions_count}</strong></p>
          <button class="primary" onclick="setTab('predictions')">Сделать прогноз</button>
        </div>
      </section>

      <h2>Ближайшие матчи</h2>
      ${dashboard.nearest_matches.length ? dashboard.nearest_matches.map((match) => matchCard(match)).join('') : '<div class="card muted">Ближайших матчей нет.</div>'}

      <h2>Где нет прогноза</h2>
      ${dashboard.missing_matches_preview.length ? dashboard.missing_matches_preview.map((match) => matchCard(match)).join('') : '<div class="card muted">Все ближайшие прогнозы сделаны.</div>'}
    `;
  } catch (error) {
    container.innerHTML = authErrorBlock(error);
  }
}

async function loadPredictions(scope = 'all') {
  const container = document.querySelector('#predictions');
  renderLoading(container);

  try {
    const result = await api(`/api/webapp/matches?scope=${scope}`);
    container.innerHTML = `
      <div class="filter-bar">
        <button onclick="loadPredictions('nearest')">Ближайший день</button>
        <button onclick="loadPredictions('missing')">Без прогноза</button>
        <button onclick="loadPredictions('all')">Все будущие</button>
      </div>
      ${result.matches.length ? result.matches.map((match) => matchCard(match)).join('') : '<div class="card muted">Матчей не найдено.</div>'}
    `;
  } catch (error) {
    container.innerHTML = authErrorBlock(error);
  }
}

async function openPrediction(matchId) {
  activateTab('predictions');
  const container = document.querySelector('#predictions');
  renderLoading(container, 'Открываю матч...');

  try {
    const result = await api(`/api/webapp/matches/${matchId}`);
    const match = result.match;
    state.currentMatch = match;
    state.scoreHome = match.prediction?.pred_home ?? 1;
    state.scoreAway = match.prediction?.pred_away ?? 1;

    container.innerHTML = `
      <button class="back-button" onclick="loadPredictions('all')">← Назад к матчам</button>
      <article class="card">
        <h2>${match.label}</h2>
        <p class="muted">Старт: ${formatDate(match.starts_at)}</p>
        ${renderScoreEditor()}
        ${match.is_playoff ? renderAdvancement(match) : ''}
        <div class="actions">
          <button class="primary" onclick="savePrediction()">Сохранить прогноз</button>
          <button onclick="loadForecastInline(${match.id})">🤖 Получить прогноз Отца прогнозов</button>
        </div>
        <div id="forecastBox" class="forecast-box"></div>
      </article>
    `;
    bindScoreButtons();
  } catch (error) {
    showStatus(error.message, true);
  }
}


async function openForecast(matchId) {
  activateTab('predictions');
  const container = document.querySelector('#predictions');
  renderLoading(container, 'Отец прогнозов изучает форму, рейтинги и личные встречи...');

  try {
    const result = await api(`/api/webapp/forecast/${matchId}`);
    container.innerHTML = `
      <button class="back-button" onclick="loadPredictions('all')">← Назад к матчам</button>
      <article class="card">
        <h2>🤖 Прогноз Отца прогнозов</h2>
        <pre class="forecast-text">${escapeHtml(result.text)}</pre>
        <div class="actions">
          <button class="primary" onclick="openPrediction(${matchId})">Сделать прогноз на этот матч</button>
        </div>
      </article>
    `;
  } catch (error) {
    container.innerHTML = `
      <button class="back-button" onclick="loadPredictions('all')">← Назад к матчам</button>
      <div class="card"><h2>Не удалось получить прогноз</h2><p class="muted">${escapeHtml(error.message)}</p></div>
    `;
  }
}

async function loadForecastInline(matchId) {
  const box = document.querySelector('#forecastBox');
  if (!box) return;

  box.innerHTML = '<div class="card compact muted">Отец прогнозов готовит AI-прогноз...</div>';

  try {
    const result = await api(`/api/webapp/forecast/${matchId}`);
    box.innerHTML = `<pre class="forecast-text">${escapeHtml(result.text)}</pre>`;
  } catch (error) {
    box.innerHTML = `<div class="card compact muted">${escapeHtml(error.message)}</div>`;
  }
}

function renderScoreEditor() {
  return `
    <h3>Счет</h3>
    <div class="score-editor">
      <div class="score-side" aria-label="Голы первой команды">
        <button type="button" data-action="minus-home">−</button>
        <strong data-field="home">${state.scoreHome}</strong>
        <button type="button" data-action="plus-home">+</button>
      </div>
      <div class="score-separator">:</div>
      <div class="score-side" aria-label="Голы второй команды">
        <button type="button" data-action="minus-away">−</button>
        <strong data-field="away">${state.scoreAway}</strong>
        <button type="button" data-action="plus-away">+</button>
      </div>
    </div>
  `;
}

function bindScoreButtons() {
  document.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.dataset.action;
      if (action === 'plus-home') state.scoreHome += 1;
      if (action === 'plus-away') state.scoreAway += 1;
      if (action === 'minus-home') state.scoreHome = Math.max(0, state.scoreHome - 1);
      if (action === 'minus-away') state.scoreAway = Math.max(0, state.scoreAway - 1);
      document.querySelector('[data-field="home"]').textContent = state.scoreHome;
      document.querySelector('[data-field="away"]').textContent = state.scoreAway;
    });
  });
}

function renderAdvancement(match) {
  return `
    <h3>Кто пройдет дальше?</h3>
    <div class="radio-row">
      <label><input type="radio" name="advance" value="none" checked /> Не ставить на проход</label>
      <label><input type="radio" name="advance" value="home" /> ${match.home_team}</label>
      <label><input type="radio" name="advance" value="away" /> ${match.away_team}</label>
    </div>
  `;
}

async function savePrediction() {
  const match = state.currentMatch;
  const selectedAdvance = document.querySelector('input[name="advance"]:checked')?.value || null;
  const isAdvanceEnabled = match.is_playoff && selectedAdvance && selectedAdvance !== 'none';

  try {
    const result = await api('/api/webapp/predictions', {
      method: 'POST',
      body: JSON.stringify({
        match_id: match.id,
        pred_home: state.scoreHome,
        pred_away: state.scoreAway,
        advancement_bet_enabled: isAdvanceEnabled,
        predicted_advancing_side: isAdvanceEnabled ? selectedAdvance : null,
      }),
    });
    showStatus(result.message || 'Прогноз сохранен');
    await openPrediction(match.id);
  } catch (error) {
    showStatus(error.message, true);
  }
}

async function loadTable() {
  const container = document.querySelector('#table');
  renderLoading(container);

  try {
    const result = await api('/api/webapp/table');
    const tableRows = result.rows.map((row) => `
      <tr class="${row.is_current_user ? 'current' : ''}">
        <td>${row.rank}</td>
        <td>${row.name}</td>
        <td><strong>${row.points}</strong></td>
        <td>${row.match_points}</td>
        <td>${row.tournament_points}</td>
        <td>${row.exact_scores}</td>
        <td>${row.outcomes}</td>
      </tr>
    `).join('');

    const cardRows = result.rows.map((row) => `
      <article class="card compact table-player-card ${row.is_current_user ? 'current' : ''}">
        <div class="rank-pill">${row.rank}</div>
        <div>
          <div class="player-name">${row.name}</div>
          <div class="muted small">Матчи: ${row.match_points} · Турнир: ${row.tournament_points}</div>
        </div>
        <div class="points-big">${row.points}</div>
        <div class="stat-row">
          <div class="stat-mini"><strong>${row.match_points}</strong>матчи</div>
          <div class="stat-mini"><strong>${row.tournament_points}</strong>турнир</div>
          <div class="stat-mini"><strong>${row.exact_scores}</strong>🎯 счет</div>
          <div class="stat-mini"><strong>${row.outcomes}</strong>✅ исход</div>
        </div>
      </article>
    `).join('');

    container.innerHTML = `
      <h2>Таблица участников</h2>

      <div class="table-cards">
        ${cardRows || '<div class="card muted">Таблица пока пустая.</div>'}
      </div>

      <div class="table-wrap card">
        <table>
          <thead><tr><th>№</th><th>Игрок</th><th>Очки</th><th>Матчи</th><th>Турнир</th><th>🎯</th><th>✅</th></tr></thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>
    `;
  } catch (error) {
    container.innerHTML = authErrorBlock(error);
  }
}


function renderTeamAutocompleteInput(id, label, value, placeholder, disabled) {
  return `
    <div class="autocomplete-field">
      <label>${label}</label>
      <input
        id="${id}"
        class="team-autocomplete"
        data-autocomplete="team"
        autocomplete="off"
        value="${escapeForAttribute(value)}"
        placeholder="${placeholder}"
        ${disabled ? 'disabled' : ''}
      />
      <div class="autocomplete-list hidden" data-autocomplete-list="${id}"></div>
    </div>
  `;
}

function bindTeamAutocomplete() {
  document.querySelectorAll('[data-autocomplete="team"]').forEach((input) => {
    const list = document.querySelector(`[data-autocomplete-list="${input.id}"]`);
    if (!list) return;

    const render = () => {
      const query = input.value.trim().toLowerCase();
      const teams = state.tournamentTeams
        .filter((team) => !query || team.name.toLowerCase().includes(query))
        .slice(0, 8);

      if (!teams.length || input.disabled) {
        list.classList.add('hidden');
        list.innerHTML = '';
        return;
      }

      list.innerHTML = teams.map((team) => `
        <button type="button" class="autocomplete-item" data-team-name="${escapeForAttribute(team.name)}">
          <span>${team.flag || '🏳️'}</span><span>${team.name}</span>
        </button>
      `).join('');
      list.classList.remove('hidden');
    };

    input.addEventListener('input', render);
    input.addEventListener('focus', render);

    list.addEventListener('click', (event) => {
      const item = event.target.closest('[data-team-name]');
      if (!item) return;

      input.value = item.datasetTeamName || item.dataset.teamName;
      list.classList.add('hidden');
      list.innerHTML = '';
    });
  });

  document.addEventListener('click', (event) => {
    if (event.target.closest('.autocomplete-field')) return;
    document.querySelectorAll('.autocomplete-list').forEach((list) => list.classList.add('hidden'));
  }, { once: true });
}

function renderFatherTournamentForecastCard(forecastData) {
  const forecast = forecastData?.forecast || {};
  const alternatives = forecastData?.alternatives || {};
  const reasoning = forecastData?.reasoning || [];

  return `
    <section class="card father-forecast-card">
      <div class="badge">Прогноз Отца · ${forecastData?.version || 'v1'}</div>
      <h2>🤖 Прогноз Отца на турнир</h2>
      <div class="forecast-picks-grid">
        <div><span>🏆</span><strong>${forecast.champion || '—'}</strong><small>чемпион</small></div>
        <div><span>🥈</span><strong>${forecast.runner_up || '—'}</strong><small>финалист</small></div>
        <div><span>🥉</span><strong>${forecast.third_place || '—'}</strong><small>3 место</small></div>
        <div><span>⚽</span><strong>${forecast.top_scorer || '—'}</strong><small>бомбардир</small></div>
      </div>
      <button type="button" onclick="toggleBlock('fatherForecastDetails')">Показать объяснение</button>
      <div id="fatherForecastDetails" class="hidden forecast-details">
        <h3>Почему так</h3>
        <ul>${reasoning.map((item) => `<li>${item}</li>`).join('')}</ul>
        <h3>Альтернативы</h3>
        <p class="muted">🏆 ${alternatives.champion?.join(', ') || '—'}</p>
        <p class="muted">🥈 ${alternatives.runner_up?.join(', ') || '—'}</p>
        <p class="muted">🥉 ${alternatives.third_place?.join(', ') || '—'}</p>
        <p class="muted">⚽ ${alternatives.top_scorer?.join(', ') || '—'}</p>
        <h3>Качество данных</h3>
        <p class="muted">${forecastData?.data_quality || '—'}</p>
        <h3>Вердикт Отца</h3>
        <p>${forecastData?.spicy_comment || '—'}</p>
      </div>
    </section>
  `;
}

function toggleBlock(id) {
  const block = document.querySelector(`#${id}`);
  if (!block) return;
  block.classList.toggle('hidden');
}

function renderTopScorerPicker(currentValue, disabled) {
  const candidates = state.topScorerCandidates || [];
  const normalized = (currentValue || '').trim().toLowerCase();
  const knownCandidate = candidates.find((candidate) => candidate.name.toLowerCase() === normalized);
  const useCustom = Boolean(currentValue && !knownCandidate);

  return `
    <div class="top-scorer-picker">
      <label>Бомбардир</label>
      <select id="topScorerSelect" ${disabled ? 'disabled' : ''} onchange="handleTopScorerSelectChange()">
        <option value="">Выбери кандидата</option>
        ${candidates.map((candidate) => `
          <option value="${escapeForAttribute(candidate.name)}" ${candidate.name === currentValue ? 'selected' : ''}>
            ${candidate.name} — ${candidate.team}
          </option>
        `).join('')}
        <option value="__custom__" ${useCustom ? 'selected' : ''}>Свой вариант</option>
      </select>
      <input
        id="topScorerCustom"
        class="${useCustom ? '' : 'hidden'}"
        value="${useCustom ? escapeForAttribute(currentValue) : ''}"
        placeholder="Введи своего бомбардира"
        ${disabled ? 'disabled' : ''}
      />
      <div class="actions">
        <button type="button" onclick="toggleBlock('topScorerHint')">Подсказка по бомбардирам</button>
      </div>
      <div id="topScorerHint" class="hidden hint-box">
        <p>${state.topScorerHint || ''}</p>
        <div class="candidate-list">
          ${candidates.slice(0, 10).map((candidate) => `
            <div class="candidate-card">
              <strong>${candidate.name}</strong>
              <span class="badge">${candidate.team}</span>
              <div class="muted small">${candidate.tier || ''}</div>
              <div class="small">${candidate.note || ''}</div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function handleTopScorerSelectChange() {
  const select = document.querySelector('#topScorerSelect');
  const custom = document.querySelector('#topScorerCustom');
  if (!select || !custom) return;
  custom.classList.toggle('hidden', select.value !== '__custom__');
  if (select.value === '__custom__') {
    custom.focus();
  } else {
    custom.value = '';
  }
}

function getTopScorerValue() {
  const select = document.querySelector('#topScorerSelect');
  const custom = document.querySelector('#topScorerCustom');
  if (!select) return '';
  if (select.value === '__custom__') return (custom?.value || '').trim();
  return select.value.trim();
}

async function loadTournament() {
  const container = document.querySelector('#tournament');
  renderLoading(container);

  try {
    const [result, teamsResult, fatherResult, scorersResult] = await Promise.all([
      api('/api/webapp/tournament-prediction/me'),
      api('/api/webapp/tournament-teams'),
      api('/api/webapp/tournament-forecast'),
      api('/api/webapp/top-scorer-candidates'),
    ]);
    state.tournamentTeams = teamsResult.teams || [];
    state.topScorerCandidates = scorersResult.candidates || [];
    state.topScorerHint = scorersResult.hint || '';
    const p = result.prediction || {};
    container.innerHTML = `
      ${renderFatherTournamentForecastCard(fatherResult.forecast)}
      <section class="card">
        <h2>Мой турнирный прогноз</h2>
        ${result.is_closed ? '<p class="badge danger">Прогнозы закрыты</p>' : '<p class="muted">До старта турнира прогноз можно менять. Названия сборных выбираются из списка участников ЧМ-2026.</p>'}
        ${renderTeamAutocompleteInput('champion', 'Чемпион', p.champion || '', 'Начни вводить страну', result.is_closed)}
        ${renderTeamAutocompleteInput('runnerUp', 'Финалист', p.runner_up || '', 'Начни вводить страну', result.is_closed)}
        ${renderTeamAutocompleteInput('thirdPlace', '3 место', p.third_place || '', 'Начни вводить страну', result.is_closed)}
        ${renderTopScorerPicker(p.top_scorer || '', result.is_closed)}
        ${result.is_closed ? '' : '<button class="primary" onclick="saveTournamentPrediction()">Сохранить</button>'}
      </section>
      <section class="card">
        <h2>Прогнозы участников</h2>
        <button onclick="loadTournamentPredictions()">Показать список</button>
        <div id="tournamentPredictions"></div>
      </section>
    `;
    bindTeamAutocomplete();
  } catch (error) {
    container.innerHTML = authErrorBlock(error);
  }
}

async function saveTournamentPrediction() {
  try {
    const topScorer = getTopScorerValue();
    if (!topScorer) {
      showStatus('Выбери бомбардира или укажи свой вариант', true);
      return;
    }

    const result = await api('/api/webapp/tournament-prediction', {
      method: 'POST',
      body: JSON.stringify({
        champion: document.querySelector('#champion').value,
        runner_up: document.querySelector('#runnerUp').value,
        third_place: document.querySelector('#thirdPlace').value,
        top_scorer: topScorer,
      }),
    });
    showStatus(result.message || 'Турнирный прогноз сохранен');
    await loadTournament();
  } catch (error) {
    showStatus(error.message, true);
  }
}

async function loadTournamentPredictions() {
  const target = document.querySelector('#tournamentPredictions');
  target.innerHTML = '<p class="muted">Загружаю...</p>';
  try {
    const result = await api('/api/webapp/tournament-predictions');
    target.innerHTML = result.rows.map((row) => {
      if (!row.has_prediction) return `<p>${row.user_name}: ❌ прогноза нет</p>`;
      if (!result.revealed) return `<p>${row.user_name}: ✅ прогноз сделан</p>`;
      const p = row.prediction;
      return `<p><strong>${row.user_name}</strong><br>🏆 ${p.champion}<br>🥈 ${p.runner_up}<br>🥉 ${p.third_place}<br>⚽ ${p.top_scorer}</p>`;
    }).join('');
  } catch (error) {
    target.innerHTML = `<p class="muted">${error.message}</p>`;
  }
}

async function loadFun() {
  const container = document.querySelector('#fun');
  container.innerHTML = `
    <section class="grid">
      <div class="card">
        <h2>📚 Факт о ЧМ</h2>
        <div id="factBox" class="muted fun-box">Нажми кнопку, чтобы получить факт.</div>
        <div class="actions"><button onclick="loadRandomFact()">Получить факт</button></div>
      </div>
      <div class="card">
        <h2>❓ Квиз</h2>
        <div id="quizBox" class="muted fun-box">Нажми кнопку, чтобы получить вопрос.</div>
        <div class="actions"><button onclick="loadRandomQuiz()">Запустить вопрос</button></div>
      </div>
      <div class="card">
        <h2>🗂 Архив</h2>
        <div id="archiveBox" class="muted fun-box">Нажми кнопку, чтобы открыть карточку архива.</div>
        <div class="actions"><button onclick="loadRandomArchive()">Карточка архива</button></div>
      </div>
    </section>
  `;
}

async function loadRandomFact() {
  const box = document.querySelector('#factBox');
  box.textContent = 'Загружаю...';
  try {
    const result = await api('/api/webapp/facts/random');
    const fact = result.fact;
    box.innerHTML = `<h3>${fact.title}</h3><p>${fact.text}</p>${fact.spicy_comment ? `<p class="muted">🔥 ${fact.spicy_comment}</p>` : ''}`;
  } catch (error) { box.textContent = error.message; }
}

async function loadRandomQuiz() {
  const box = document.querySelector('#quizBox');
  box.textContent = 'Загружаю...';
  try {
    const result = await api('/api/webapp/quiz/random');
    state.quickQuizQuestion = result.question;
    box.innerHTML = `
      <h3>${result.question.text}</h3>
      ${Object.entries(result.question.options).map(([key, value]) => `<button class="option-button" onclick="answerQuickQuiz('${key}')">${key}) ${value}</button>`).join('')}
      <div id="quizAnswerBox"></div>
    `;
  } catch (error) { box.textContent = error.message; }
}

async function answerQuickQuiz(option) {
  const answerBox = document.querySelector('#quizAnswerBox');
  try {
    const result = await api('/api/webapp/quiz/answer', {
      method: 'POST',
      body: JSON.stringify({ question_id: state.quickQuizQuestion.id, selected_option: option }),
    });
    answerBox.innerHTML = `<p class="${result.is_correct ? 'badge success' : 'badge danger'}">${result.is_correct ? 'Верно' : 'Мимо'}</p><p>Правильный ответ: ${result.correct_option}) ${result.correct_text}</p>${result.explanation ? `<p class="muted">${result.explanation}</p>` : ''}`;
  } catch (error) { answerBox.textContent = error.message; }
}

async function loadRandomArchive() {
  const box = document.querySelector('#archiveBox');
  box.textContent = 'Загружаю...';
  try {
    const result = await api('/api/webapp/archive/random');
    const card = result.card;
    box.innerHTML = `<h3>${card.title}</h3><p>${card.text}</p>${card.related_name ? `<p class="muted">Герой карточки: ${card.related_name}</p>` : ''}`;
  } catch (error) { box.textContent = error.message; }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
}

function authErrorBlock(error) {
  return `
    <div class="card">
      <h2>Не удалось открыть портал</h2>
      <p class="muted">${error.message}</p>
      <p class="muted small">Mini App нужно открывать из Telegram-кнопки бота, чтобы backend получил Telegram initData.</p>
    </div>
  `;
}

const RESOURCE_GROUPS = [
  {
    title: 'Матч-центры и статистика',
    description: 'Быстро смотреть расписание, live-счет, составы, форму и статистику по матчам.',
    items: [
      {
        title: 'Sofascore',
        url: 'https://www.sofascore.com/football/tournament/world/world-championship/16#id:58210',
        emoji: '📊',
        text: 'Live-матчи, рейтинги игроков, составы, форма и расширенная статистика.',
        tag: 'статистика',
      },
      {
        title: 'Flashscore',
        url: 'https://www.flashscore.com/football/world/world-championship/',
        emoji: '⚡',
        text: 'Быстрый live-счет, календарь, таблицы, форма команд и уведомления.',
        tag: 'live',
      },
      {
        title: 'FIFA — Scores & Fixtures',
        url: 'https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures',
        emoji: '🌍',
        text: 'Официальное расписание, результаты и матч-центр FIFA.',
        tag: 'официально',
      },
    ],
  },
  {
    title: 'Новости на русском',
    description: 'Русскоязычные новости, составы, интервью, травмы и контекст вокруг сборных.',
    items: [
      {
        title: 'Матч ТВ',
        url: 'https://matchtv.ru/football/worldcup/2026',
        emoji: '📺',
        text: 'Новости ЧМ-2026, материалы, видео и эфирный футбольный контекст.',
        tag: 'медиа',
      },
      {
        title: 'Чемпионат.com',
        url: 'https://www.championat.com/news/football/_worldcup/1.html',
        emoji: '📰',
        text: 'Лента новостей по чемпионату мира и сборным.',
        tag: 'новости',
      },
      {
        title: 'Sports.ru — Футбол',
        url: 'https://www.sports.ru/football/',
        emoji: '💬',
        text: 'Новости, обсуждения, блоги и фанатский контекст вокруг турнира.',
        tag: 'комьюнити',
      },
    ],
  },
  {
    title: 'Официальное и справочное',
    description: 'Проверять первоисточник, формат турнира, стадионы и базовую справку.',
    items: [
      {
        title: 'FIFA World Cup 2026',
        url: 'https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026',
        emoji: '🏆',
        text: 'Официальная страница турнира: расписание, команды, новости, стадионы.',
        tag: 'FIFA',
      },
      {
        title: 'Wikipedia: 2026 FIFA World Cup',
        url: 'https://en.wikipedia.org/wiki/2026_FIFA_World_Cup',
        emoji: '📚',
        text: 'Справка по формату, городам, группам, расписанию и истории изменений.',
        tag: 'справка',
      },
    ],
  },
];

function openExternalLink(url) {
  if (tg?.openLink) {
    tg.openLink(url);
    return;
  }

  window.open(url, '_blank', 'noopener,noreferrer');
}

function renderResourceItem(item) {
  return `
    <button class="resource-item" type="button" onclick="openExternalLink('${item.url}')">
      <div class="resource-icon">${item.emoji}</div>
      <div class="resource-body">
        <div class="resource-title-row">
          <strong>${item.title}</strong>
          <span class="badge">${item.tag}</span>
        </div>
        <div class="muted small">${item.text}</div>
      </div>
      <div class="resource-arrow">›</div>
    </button>
  `;
}

async function loadResources() {
  const container = document.querySelector('#resources');

  container.innerHTML = `
    ${RESOURCE_GROUPS.map((group) => `
      <section class="resource-section">
        <h3>${group.title}</h3>
        <p class="muted small">${group.description}</p>
        <div class="resource-list">
          ${group.items.map(renderResourceItem).join('')}
        </div>
      </section>
    `).join('')}

  `;
}

function loadCurrentTab() {
  if (state.tab === 'home') return loadHome();
  if (state.tab === 'predictions') return loadPredictions('all');
  if (state.tab === 'table') return loadTable();
  if (state.tab === 'tournament') return loadTournament();
  if (state.tab === 'fun') return loadFun();
  if (state.tab === 'resources') return loadResources();
}

document.querySelectorAll('.tab').forEach((button) => {
  button.addEventListener('click', () => setTab(button.dataset.tab));
});

document.querySelector('#refreshButton').addEventListener('click', loadCurrentTab);

loadCurrentTab();
