
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
}

const TABS = [
  { id: 'matches', label: 'Матч-центр', icon: 'ball' },
  { id: 'predictions', label: 'Прогнозы', icon: 'target' },
  { id: 'tournament', label: 'Турнир', icon: 'cup' },
  { id: 'rating', label: 'Рейтинг', icon: 'rank' },
  { id: 'profile', label: 'Профиль', icon: 'profile' },
];

const QUICK_SCORES = [
  [1, 0],
  [1, 1],
  [2, 1],
  [2, 0],
  [0, 0],
  [0, 1],
];

function Icon({ name, className = '' }) {
  const common = {
    className: `svg-icon ${className}`,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': 'true',
  };

  if (name === 'ball') {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3v18M3 12h18" />
        <path d="M5.6 6.4c4.1 2.6 8.7 2.6 12.8 0M5.6 17.6c4.1-2.6 8.7-2.6 12.8 0" />
      </svg>
    );
  }

  if (name === 'target') {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1.5" />
      </svg>
    );
  }

  if (name === 'cup') {
    return (
      <svg {...common}>
        <path d="M8 4h8v4a4 4 0 0 1-8 0V4Z" />
        <path d="M8 6H5a3 3 0 0 0 3 3M16 6h3a3 3 0 0 1-3 3" />
        <path d="M12 12v5M8 20h8M10 17h4" />
      </svg>
    );
  }

  if (name === 'rank') {
    return (
      <svg {...common}>
        <path d="M5 20V10M12 20V4M19 20v-7" />
        <path d="M3 20h18" />
      </svg>
    );
  }

  if (name === 'more') {
    return (
      <svg {...common}>
        <circle cx="5" cy="12" r="1.5" />
        <circle cx="12" cy="12" r="1.5" />
        <circle cx="19" cy="12" r="1.5" />
      </svg>
    );
  }

  if (name === 'profile') {
    return (
      <svg {...common}>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0" />
      </svg>
    );
  }

  if (name === 'team') {
    return (
      <svg {...common}>
        <circle cx="9" cy="8" r="3" />
        <circle cx="17" cy="9" r="2.5" />
        <path d="M3 21a6 6 0 0 1 12 0" />
        <path d="M14 18a5 5 0 0 1 7 3" />
      </svg>
    );
  }

  if (name === 'fire') {
    return (
      <svg {...common}>
        <path d="M12 22c4 0 7-2.7 7-6.7 0-2.6-1.4-5-4.1-7.2.1 2.3-.8 3.7-2.1 4.5.1-3-1.6-5.7-4.1-7.6.1 3.7-3.7 5.6-3.7 10.2C5 19.2 8 22 12 22Z" />
      </svg>
    );
  }

  if (name === 'shield') {
    return (
      <svg {...common}>
        <path d="M12 3 20 6v6c0 5-3.4 8.2-8 9-4.6-.8-8-4-8-9V6l8-3Z" />
      </svg>
    );
  }

  if (name === 'star') {
    return (
      <svg {...common}>
        <path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1-4.4-4.3 6.1-.9L12 3Z" />
      </svg>
    );
  }

  if (name === 'check') {
    return (
      <svg {...common}>
        <path d="m5 12 4 4L19 6" />
      </svg>
    );
  }

  if (name === 'robot') {
    return (
      <svg {...common}>
        <rect x="5" y="8" width="14" height="10" rx="3" />
        <path d="M12 8V4M9 13h.01M15 13h.01M8 21h8" />
      </svg>
    );
  }

  return null;
}

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

function formatDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDayTitle(value) {
  if (!value) return '';
  const date = new Date(value);
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    weekday: 'long',
  });
}

function formatCountdown(days) {
  if (days === null || days === undefined) return 'до ЧМ';
  const lastTwo = days % 100;
  const last = days % 10;
  let word = 'дней';
  if (lastTwo < 11 || lastTwo > 14) {
    if (last === 1) word = 'день';
    else if ([2, 3, 4].includes(last)) word = 'дня';
  }
  return `до ЧМ ${days} ${word}`;
}

function pluralRu(value, one, few, many) {
  const number = Math.abs(Number(value) || 0);
  const lastTwo = number % 100;
  const last = number % 10;

  if (lastTwo >= 11 && lastTwo <= 14) return many;
  if (last === 1) return one;
  if ([2, 3, 4].includes(last)) return few;
  return many;
}

function getTelegramPhotoUrl() {
  return tg?.initDataUnsafe?.user?.photo_url || '';
}


function useNowTick() {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return now;
}

function formatLiveCountdown(targetValue, now) {
  if (!targetValue) return 'до ЧМ';
  const target = new Date(targetValue).getTime();
  const diff = Math.max(0, target - now);
  const totalSeconds = Math.floor(diff / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const pad = (value) => String(value).padStart(2, '0');

  if (days > 0) {
    return `до ЧМ ${days}д ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  }

  return `до ЧМ ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function compactDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
}

function ErrorCard({ error, onRetry }) {
  return (
    <div className="card error-card">
      <h2>Не удалось открыть портал</h2>
      <p>{error?.message || String(error)}</p>
      <p className="muted small">
        Mini App нужно открывать из Telegram-кнопки бота, чтобы backend получил Telegram initData.
      </p>
      {onRetry && <button onClick={onRetry}>Повторить</button>}
    </div>
  );
}

function LoadingCard({ text = 'Загружаю...' }) {
  return <div className="card muted">{text}</div>;
}

function Header({ dashboard, onRules }) {
  const now = useNowTick();
  const countdownText = formatLiveCountdown(dashboard?.tournament?.starts_at, now);

  return (
    <header className="league-header">
      <div className="league-main">
        <div className="league-logo"><Icon name="cup" /></div>
        <div className="league-text">
          <h1>Отец прогнозов</h1>
          <div className="league-subtitle">ЧМ-2026 · США · Мексика · Канада</div>
        </div>
        <button className="rules-button" onClick={onRules}>Правила</button>
      </div>

      <div className="league-status">
        <span className="status-section live-countdown">{countdownText}</span>
        <span className="divider" />
        <span className="points">{dashboard?.points ?? 0} очков</span>
        <span className="muted">#{dashboard?.rank || '—'}</span>
      </div>
    </header>
  );
}

function HomeHero({ dashboard, tournamentPrediction, onTournamentPick, setTab }) {
  const missing = dashboard?.missing_predictions_count ?? 0;
  const p = tournamentPrediction?.prediction;
  const items = [
    { key: 'champion', label: 'Победитель', value: p?.champion, points: '+15', icon: 'cup' },
    { key: 'runner_up', label: '2-е место', value: p?.runner_up, points: '+10', icon: 'rank' },
    { key: 'third_place', label: '3-е место', value: p?.third_place, points: '+5', icon: 'rank' },
    { key: 'top_scorer', label: 'Бомбардир', value: p?.top_scorer, points: '+15', icon: 'ball' },
  ];

  return (
    <section className="matchcenter-top">
      <button className="compact-action" onClick={() => setTab('predictions')}>
        <span className="compact-action-icon"><Icon name="target" /></span>
        <span>
          <strong>Нужен прогноз для {missing} матчей</strong>
          <small>Перейти к матчам без вашего счета</small>
        </span>
        <b>{missing}</b>
      </button>

      <section className="tournament-mini">
        <div className="tournament-mini-head">
          <h2>Прогнозы на турнир</h2>
          <span>{p ? '4/4' : '0/4'}</span>
        </div>
        <div className="tournament-mini-grid">
          {items.map((item) => (
            <button key={item.key} onClick={() => onTournamentPick(item.key)}>
              <i><Icon name={item.icon} /></i>
              <span>{item.label}</span>
              <strong>{item.value || 'Выбрать'}</strong>
              <small>{item.points}</small>
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}

function PredictionBars({ distribution }) {
  const data = distribution || {};
  const home = data.home_percent || 0;
  const draw = data.draw_percent || 0;
  const away = data.away_percent || 0;
  return (
    <div className="prediction-bars">
      <div className="bar-title">
        <span>Мнение участников</span>
        <span>{data.total || 0} {pluralRu(data.total || 0, 'прогноз', 'прогноза', 'прогнозов')}</span>
      </div>
      <div className="bar-track" aria-label="Распределение прогнозов">
        <span className="bar-home" style={{ width: `${home}%` }} />
        <span className="bar-draw" style={{ width: `${draw}%` }} />
        <span className="bar-away" style={{ width: `${away}%` }} />
      </div>
      <div className="bar-numbers">
        <b>{home}%<small>П1</small></b>
        <b>{draw}%<small>X</small></b>
        <b>{away}%<small>П2</small></b>
      </div>
    </div>
  );
}

function MatchCard({ match, onPredict, onForecast, showDistribution = true }) {
  const locked = match.is_finished || new Date(match.starts_at).getTime() <= Date.now();
  const scoreText = match.is_finished && match.score_home !== null
    ? `${match.score_home}:${match.score_away}`
    : match.prediction
      ? `${match.prediction.pred_home}:${match.prediction.pred_away}`
      : '— : —';

  return (
    <article className="match-card">
      <div className="match-card-top">
        <span className="group-pill">{match.group_code ? `Группа ${match.group_code}` : match.stage}</span>
        <span className={match.is_finished ? 'dot dot-finished' : 'dot'} />
        <span className="muted small">{formatDateTime(match.starts_at)}</span>
      </div>

      <div className="match-teams">
        <div className="team-side">
          <span className="flag">{match.home_flag || '🏳️'}</span>
          <strong>{match.home_team}</strong>
        </div>
        <div className="score-block">
          <strong>{scoreText}</strong>
          {match.prediction && !match.is_finished && <small>мой прогноз</small>}
          {!match.prediction && !locked && <small>прогноза нет</small>}
          {locked && !match.is_finished && <small>закрыт</small>}
        </div>
        <div className="team-side">
          <span className="flag">{match.away_flag || '🏳️'}</span>
          <strong>{match.away_team}</strong>
        </div>
      </div>

      <div className="match-actions">
        {!locked && <button onClick={() => onPredict(match)}>{match.prediction ? 'Изменить прогноз' : 'Сделать прогноз'}</button>}
        <button onClick={() => onForecast(match)}><Icon name="robot" /> Прогноз Отца</button>
      </div>

      {showDistribution && <PredictionBars distribution={match.prediction_distribution} />}
    </article>
  );
}

function groupMatchesByDay(matches) {
  const map = new Map();
  for (const match of matches || []) {
    const key = match.day_key || (match.starts_at || '').slice(0, 10);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(match);
  }
  return [...map.entries()];
}

function GroupTable({ group }) {
  if (!group) return null;
  return (
    <section className={`group-table-card group-color group-${group.group_code}`}>
      <div className="group-header">
        <div className="group-letter">{group.group_code}</div>
        <div>
          <h2>Группа {group.group_code}</h2>
          <p className="muted">1–2 место — 1/8 финала · 3-е — шанс на плей-офф</p>
        </div>
      </div>
      <div className="standings-table">
        <div className="standings-row headings">
          <span>#</span><span>Сборная</span><span>И</span><span>В</span><span>Н</span><span>П</span><span>М</span><span>±</span><span>О</span>
        </div>
        {group.rows.map((row) => (
          <div key={row.team} className={`standings-row zone-${row.qualification_zone}`}>
            <span className="rank-cell">{row.rank}</span>
            <span className="team-name">{row.flag} {row.team}</span>
            <span>{row.played}</span>
            <span>{row.wins}</span>
            <span>{row.draws}</span>
            <span>{row.losses}</span>
            <span>{row.goals_for}:{row.goals_against}</span>
            <span>{row.goal_difference}</span>
            <strong>{row.points}</strong>
          </div>
        ))}
      </div>
      <div className="legend muted small">
        <span><i className="legend-direct" /> 1–2 · 1/8</span>
        <span><i className="legend-playoff" /> 3 · плей-офф</span>
      </div>
    </section>
  );
}

function MatchCenter({ onPredict, onForecast }) {
  const [scope, setScope] = useState('all');
  const [group, setGroup] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ scope });
      if (group) params.set('group_code', group);
      setData(await api(`/api/webapp/match-center?${params.toString()}`));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [scope, group]);

  const grouped = useMemo(() => groupMatchesByDay(data?.matches || []), [data]);
  const selectedStanding = group ? data?.standings?.[0] : null;

  if (error) return <ErrorCard error={error} onRetry={load} />;

  return (
    <main className="screen-content">
      <div className="section-label">Матч-центр</div>

      <div className="filter-strip modern-filters">
        <button className={!group && scope === 'all' ? 'active' : ''} onClick={() => { setGroup(null); setScope('all'); }}>
          <Icon name="star" />
          <span>Все</span>
        </button>
        <button className={scope === 'results' ? 'active result' : ''} onClick={() => { setGroup(null); setScope('results'); }}>
          <Icon name="check" />
          <span>Результаты</span>
        </button>
        {(data?.groups || []).map((item) => (
          <button key={item.group_code} className={`group-color group-${item.group_code} ${group === item.group_code ? 'active group' : ''}`} onClick={() => { setGroup(item.group_code); setScope('all'); }}>
            <b>{item.group_code}</b>
            <span>группа</span>
          </button>
        ))}
      </div>

      <div className="match-center-results">
        {loading && !data ? <LoadingCard /> : (
          <>
            {selectedStanding && <GroupTable group={selectedStanding} />}
            {loading && <LoadingCard text="Обновляю список..." />}
            {!loading && grouped.length === 0 && <EmptyState iconName="ball" title="Нет матчей" text={scope === 'results' ? 'Пока нет завершенных матчей' : 'Матчи не найдены'} />}
            {!loading && grouped.map(([day, matches]) => (
              <section key={day} className="match-day">
                <div className="day-heading">
                  <span>{formatDayTitle(matches[0]?.starts_at)}</span>
                  <b>{matches.length} матч{matches.length === 1 ? '' : 'а'}</b>
                </div>
                {matches.map((match) => <MatchCard key={match.id} match={match} onPredict={onPredict} onForecast={onForecast} />)}
              </section>
            ))}
          </>
        )}
      </div>
    </main>
  );
}

function EmptyState({ iconName = 'ball', title, text }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon name={iconName} /></div>
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}

function ScorePicker({ match, onClose, onSaved }) {
  const [home, setHome] = useState(match?.prediction?.pred_home ?? 1);
  const [away, setAway] = useState(match?.prediction?.pred_away ?? 1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  if (!match) return null;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api('/api/webapp/predictions', {
        method: 'POST',
        body: JSON.stringify({
          match_id: match.id,
          pred_home: home,
          pred_away: away,
          advancement_bet_enabled: false,
          predicted_advancing_side: null,
        }),
      });
      onSaved?.();
      onClose?.();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  function inc(setter, value) { setter(Math.min(20, value + 1)); }
  function dec(setter, value) { setter(Math.max(0, value - 1)); }

  return (
    <div className="modal-backdrop">
      <section className="modal-card score-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>Прогноз на матч</h2>
        <p className="muted match-title-modal">{match.home_team} — {match.away_team}</p>
        <p className="muted small">{formatDateTime(match.starts_at)}</p>

        <div className="score-editor-compact">
          <div className="score-row">
            <span className="score-team"><span className="flag mini">{match.home_flag}</span><strong>{match.home_team}</strong></span>
            <div className="counter compact-counter">
              <button onClick={() => dec(setHome, home)}>−</button>
              <b>{home}</b>
              <button onClick={() => inc(setHome, home)}>+</button>
            </div>
          </div>
          <div className="score-row">
            <span className="score-team"><span className="flag mini">{match.away_flag}</span><strong>{match.away_team}</strong></span>
            <div className="counter compact-counter">
              <button onClick={() => dec(setAway, away)}>−</button>
              <b>{away}</b>
              <button onClick={() => inc(setAway, away)}>+</button>
            </div>
          </div>
        </div>

        <div className="quick-scores">
          {QUICK_SCORES.map(([h, a]) => (
            <button key={`${h}:${a}`} onClick={() => { setHome(h); setAway(a); }}>{h}:{a}</button>
          ))}
        </div>

        {error && <p className="error-text">{error.message}</p>}
        <button className="primary full" disabled={saving} onClick={save}>{saving ? 'Сохраняю...' : 'Сохранить прогноз'}</button>
      </section>
    </div>
  );
}


function TournamentPredictionModal({ currentPrediction, initialField = 'champion', onClose, onSaved }) {
  const [teams, setTeams] = useState([]);
  const [scorers, setScorers] = useState([]);
  const existing = currentPrediction?.prediction || {};
  const [champion, setChampion] = useState(existing.champion || '');
  const [runnerUp, setRunnerUp] = useState(existing.runner_up || '');
  const [thirdPlace, setThirdPlace] = useState(existing.third_place || '');
  const [topScorerSelect, setTopScorerSelect] = useState(existing.top_scorer || '');
  const [customTopScorer, setCustomTopScorer] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api('/api/webapp/tournament-teams')
      .then((result) => setTeams(result.teams || []))
      .catch(setError);
    api('/api/webapp/top-scorer-candidates')
      .then((result) => setScorers(result.candidates || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const node = document.querySelector(`[data-field="${initialField}"]`);
    if (node?.scrollIntoView) {
      window.setTimeout(() => node.scrollIntoView({ block: 'center', behavior: 'smooth' }), 120);
    }
  }, [initialField]);

  const teamOptions = teams.map((team) => team.name);
  const scorerNames = scorers.map((candidate) => candidate.name);
  const selectTopScorerValue = scorerNames.includes(topScorerSelect) ? topScorerSelect : topScorerSelect ? '__custom__' : '';
  const currentTopScorer = selectTopScorerValue === '__custom__' ? customTopScorer.trim() : topScorerSelect;

  useEffect(() => {
    if (existing.top_scorer && scorers.length && !scorerNames.includes(existing.top_scorer)) {
      setTopScorerSelect('__custom__');
      setCustomTopScorer(existing.top_scorer);
    }
  }, [scorers.length]);

  async function save() {
    setSaving(true);
    setError(null);

    if (!champion || !runnerUp || !thirdPlace || !currentTopScorer) {
      setError(new Error('Заполни все 4 поля турнирного прогноза.'));
      setSaving(false);
      return;
    }

    try {
      await api('/api/webapp/tournament-prediction', {
        method: 'POST',
        body: JSON.stringify({
          champion,
          runner_up: runnerUp,
          third_place: thirdPlace,
          top_scorer: currentTopScorer,
        }),
      });
      onSaved?.();
      onClose?.();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  function renderTeamSelect(label, value, setter, field) {
    return (
      <label className="tournament-field" data-field={field}>
        <span>{label}</span>
        <select value={value} onChange={(event) => setter(event.target.value)}>
          <option value="">Выбрать</option>
          {teamOptions.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </label>
    );
  }

  return (
    <div className="modal-backdrop">
      <section className="modal-card tournament-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>Турнирный прогноз</h2>
        <p className="muted">Заполни 4 позиции. До старта турнира прогноз можно менять.</p>

        {renderTeamSelect('Победитель', champion, setChampion, 'champion')}
        {renderTeamSelect('2-е место', runnerUp, setRunnerUp, 'runner_up')}
        {renderTeamSelect('3-е место', thirdPlace, setThirdPlace, 'third_place')}

        <label className="tournament-field" data-field="top_scorer">
          <span>Бомбардир</span>
          <select
            value={selectTopScorerValue}
            onChange={(event) => {
              setTopScorerSelect(event.target.value);
              if (event.target.value !== '__custom__') setCustomTopScorer('');
            }}
          >
            <option value="">Выбрать</option>
            {scorerNames.map((name) => <option key={name} value={name}>{name}</option>)}
            <option value="__custom__">Свой вариант</option>
          </select>
        </label>

        {topScorerSelect === '__custom__' && (
          <input
            className="custom-scorer-input"
            value={customTopScorer}
            onChange={(event) => setCustomTopScorer(event.target.value)}
            placeholder="Введите своего бомбардира"
          />
        )}

        {error && <p className="error-text">{error.message}</p>}
        <button className="primary full" disabled={saving} onClick={save}>{saving ? 'Сохраняю...' : 'Сохранить турнирный прогноз'}</button>
      </section>
    </div>
  );
}

function ForecastModal({ match, onClose }) {
  const [text, setText] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setText('');
    setError(null);

    api(`/api/webapp/forecast/${match.id}`)
      .then((result) => {
        if (active) setText(result.text || 'Прогноз пока не получен.');
      })
      .catch((err) => {
        if (active) setError(err);
      });

    return () => { active = false; };
  }, [match.id]);

  return (
    <div className="modal-backdrop">
      <section className="modal-card forecast-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>🤖 Прогноз Отца</h2>
        <p className="muted">{match.home_team} — {match.away_team}</p>
        {error && <p className="error-text">{error.message}</p>}
        {!error && !text && <LoadingCard text="Отец прогнозов думает..." />}
        {text && <pre className="forecast-text">{text}</pre>}
      </section>
    </div>
  );
}

function Predictions({ onPredict, onForecast }) {
  const [data, setData] = useState(null);
  const [activeSection, setActiveSection] = useState('missing');
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      const result = await api('/api/webapp/matches?scope=all');
      setData(result);
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, []);

  if (error) return <ErrorCard error={error} onRetry={load} />;

  const matches = data?.matches || [];
  const missingMatches = matches.filter((match) => !match.prediction);
  const editableMatches = matches.filter((match) => match.prediction);
  const visibleMatches = activeSection === 'missing' ? missingMatches : editableMatches;

  return (
    <main className="screen-content">
      <div className="section-label">Мои прогнозы</div>
      <div className="stat-grid prediction-tabs">
        <button className={`stat-card ${activeSection === 'missing' ? 'active' : ''}`} onClick={() => setActiveSection('missing')}>
          <b>{data ? missingMatches.length : '—'}</b>
          <span>Нужен прогноз</span>
        </button>
        <button className={`stat-card ${activeSection === 'editable' ? 'active' : ''}`} onClick={() => setActiveSection('editable')}>
          <b>{data ? editableMatches.length : '—'}</b>
          <span>Можно изменить</span>
        </button>
      </div>

      {!data ? <LoadingCard /> : (
        <section className="prediction-section">
          <div className="subsection-title">
            <h2>{activeSection === 'missing' ? 'Нужен прогноз' : 'Можно изменить'}</h2>
            <span>{visibleMatches.length}</span>
          </div>
          {visibleMatches.length === 0 ? (
            <EmptyState
              iconName="target"
              title={activeSection === 'missing' ? 'Все готово' : 'Пока пусто'}
              text={activeSection === 'missing' ? 'Нет матчей без вашего прогноза' : 'Нет будущих матчей с вашим прогнозом'}
            />
          ) : (
            groupMatchesByDay(visibleMatches).map(([day, dayMatches]) => (
              <section key={day} className="match-day">
                <div className="day-heading"><span>{formatDayTitle(dayMatches[0]?.starts_at)}</span><b>{dayMatches.length}</b></div>
                {dayMatches.map((match) => <MatchCard key={match.id} match={match} onPredict={onPredict} onForecast={onForecast} showDistribution={false} />)}
              </section>
            ))
          )}
        </section>
      )}
    </main>
  );
}

function Rating() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api('/api/webapp/table').then(setData).catch(setError);
  }, []);

  if (error) return <ErrorCard error={error} />;
  if (!data) return <LoadingCard />;

  return (
    <main className="screen-content">
      <div className="section-label">Таблица лидеров</div>
      <div className="ranking-list">
        {(data.rows || []).map((row) => (
          <div key={row.name} className={`ranking-row ${row.is_current_user ? 'me' : ''}`}>
            <span className="rank">#{row.rank}</span>
            <strong>{row.name}</strong>
            <span>{row.points} очков</span>
            <small>Матчи: {row.match_points} · Турнир: {row.tournament_points} · 🎯 {row.exact_scores}</small>
          </div>
        ))}
      </div>
    </main>
  );
}

function Tournament({ tournamentPrediction }) {
  const [prediction, setPrediction] = useState(tournamentPrediction);
  const [forecast, setForecast] = useState(null);
  const [scorers, setScorers] = useState(null);
  const [openFather, setOpenFather] = useState(false);
  const [openHelp, setOpenHelp] = useState(false);

  useEffect(() => {
    if (!tournamentPrediction) {
      api('/api/webapp/tournament-prediction/me').then(setPrediction).catch(() => {});
    }
    api('/api/webapp/tournament-forecast').then(setForecast).catch(() => {});
    api('/api/webapp/top-scorer-candidates').then(setScorers).catch(() => {});
  }, [tournamentPrediction]);

  const p = (prediction || tournamentPrediction)?.prediction;
  const father = forecast?.forecast;
  const fatherPicks = father?.forecast || {};

  return (
    <main className="screen-content">
      <div className="section-label">Турнирный прогноз</div>

      <section className="card">
        <h2>Мой турнирный прогноз</h2>
        {p ? (
          <div className="tournament-grid">
            <div>🏆 <b>{p.champion}</b><small>Победитель</small></div>
            <div>🥈 <b>{p.runner_up}</b><small>Финалист</small></div>
            <div>🥉 <b>{p.third_place}</b><small>3 место</small></div>
            <div>⚽ <b>{p.top_scorer}</b><small>Бомбардир</small></div>
          </div>
        ) : (
          <p className="muted">Турнирный прогноз пока не заполнен. Заполни его в боте или предыдущей форме Mini App.</p>
        )}
      </section>

      <section className="card compact-card">
        <button className="wide-toggle" onClick={() => setOpenFather(!openFather)}>🤖 Прогноз Отца прогнозов</button>
        {openFather && (
          <div className="collapsed-panel">
            {father ? (
              <>
                <div className="tournament-grid">
                  <div>🏆 <b>{fatherPicks.champion}</b><small>Победитель</small></div>
                  <div>🥈 <b>{fatherPicks.runner_up}</b><small>Финалист</small></div>
                  <div>🥉 <b>{fatherPicks.third_place}</b><small>3 место</small></div>
                  <div>⚽ <b>{fatherPicks.top_scorer}</b><small>Бомбардир</small></div>
                </div>
                <h3>Почему так</h3>
                <ul className="nice-list">
                  {(father.reasoning || []).map((item) => <li key={item}>{item}</li>)}
                </ul>
                <h3>Альтернативы</h3>
                <p className="muted">🏆 {(father.alternatives?.champion || []).join(', ') || '—'}</p>
                <p className="muted">🥈 {(father.alternatives?.runner_up || []).join(', ') || '—'}</p>
                <p className="muted">🥉 {(father.alternatives?.third_place || []).join(', ') || '—'}</p>
                <p className="muted">⚽ {(father.alternatives?.top_scorer || []).join(', ') || '—'}</p>
                <p className="father-comment">{father.spicy_comment}</p>
              </>
            ) : <LoadingCard />}
          </div>
        )}
      </section>

      <section className="card compact-card">
        <button className="wide-toggle" onClick={() => setOpenHelp(!openHelp)}>⚽ Помощь Отца по бомбардирам</button>
        {openHelp && (
          <div className="collapsed-panel">
            <p>{scorers?.hint || 'Загружаю подсказку...'}</p>
            <div className="scorer-list">
              {(scorers?.candidates || []).map((candidate) => (
                <div className="scorer-card" key={candidate.name}>
                  <strong>{candidate.name}</strong>
                  <span>{candidate.team}</span>
                  <small>{candidate.tier}</small>
                  <p>{candidate.note}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}


function Profile({ tournamentPrediction }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);
  const photoUrl = getTelegramPhotoUrl();

  async function load() {
    setError(null);
    try {
      setProfile(await api('/api/webapp/profile'));
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, []);

  if (error) return <ErrorCard error={error} onRetry={load} />;
  if (!profile) return <LoadingCard />;

  const user = profile.user || {};
  const summary = profile.summary || {};
  const pointsBreakdown = profile.points_breakdown || [];
  const badges = profile.badges || [];
  const tournament = profile.tournament_prediction || tournamentPrediction?.prediction;
  const earnedBadges = badges.filter((badge) => badge.earned);
  const lockedBadges = badges.filter((badge) => !badge.earned);

  return (
    <main className="screen-content profile-screen">
      <div className="section-label">Мой профиль</div>

      <section className="profile-hero-card">
        <div className="avatar-ring">
          {photoUrl ? <img src={photoUrl} alt="" /> : <span>{user.initials || 'ОП'}</span>}
        </div>
        <div className="profile-identity">
          <div className="profile-rank">#{summary.rank || '—'}</div>
          <h2>{user.display_name}</h2>
          {user.username && <p className="muted">@{user.username}</p>}
          <span className="status-pill">{summary.status}</span>
        </div>
        <div className="profile-points">
          <b>{summary.points || 0}</b>
          <span>очков</span>
        </div>
      </section>

      <section className="card team-card">
        <button className="team-support-button" type="button">
          <span className="team-support-flag">⚐</span>
          <span>
            <strong>Укажите, за какую сборную болеете</strong>
            <small>Флаг появится на вашем профиле — его увидят все</small>
          </span>
          <b>→</b>
        </button>
      </section>

      <section className="card">
        <h2>Откуда очки</h2>
        <div className="points-breakdown">
          {pointsBreakdown.map((item) => (
            <div key={item.key} className="points-row">
              <i><Icon name={item.icon} /></i>
              <span>{item.title}</span>
              <b>{item.points} очков</b>
              <em style={{ width: `${Math.min(100, Math.max(4, item.points || 0))}%` }} />
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <div className="profile-section-head">
          <h2>Статистика</h2>
          <span>{summary.total_predictions || 0} {pluralRu(summary.total_predictions || 0, 'прогноз', 'прогноза', 'прогнозов')}</span>
        </div>
        <div className="stats-grid">
          <div><b>{summary.match_points || 0}</b><span>очки за матчи</span></div>
          <div><b>{summary.tournament_points || 0}</b><span>очки за турнир</span></div>
          <div><b>{summary.exact_scores || 0}</b><span>точные счета</span></div>
          <div><b>{summary.outcomes || 0}</b><span>исходы</span></div>
          <div><b>{summary.favorite_score || '—'}</b><span>любимый счет</span></div>
          <div><b>{summary.missing_predictions || 0}</b><span>ждут прогноза</span></div>
        </div>
      </section>

      <section className="card">
        <div className="profile-section-head">
          <h2>Прогнозы на турнир</h2>
          <span>{tournament ? '4/4' : '0/4'}</span>
        </div>
        {tournament ? (
          <div className="profile-tournament-grid">
            <div><Icon name="cup" /><span>Победитель</span><b>{tournament.champion}</b></div>
            <div><Icon name="rank" /><span>2-е место</span><b>{tournament.runner_up}</b></div>
            <div><Icon name="rank" /><span>3-е место</span><b>{tournament.third_place}</b></div>
            <div><Icon name="ball" /><span>Бомбардир</span><b>{tournament.top_scorer}</b></div>
          </div>
        ) : (
          <p className="muted">Турнирный прогноз пока не заполнен.</p>
        )}
      </section>

      <section className="card">
        <div className="profile-section-head">
          <h2>Достижения</h2>
          <span>{earnedBadges.length}/{badges.length}</span>
        </div>
        <div className="badges-grid">
          {badges.map((badge) => (
            <div key={badge.code} className={`badge-card ${badge.earned ? 'earned' : 'locked'}`}>
              <i><Icon name={badge.icon} /></i>
              <strong>{badge.title}</strong>
              <span>{badge.description}</span>
              <div className="badge-progress">
                <em style={{ width: `${Math.round((badge.progress || 0) * 100 / (badge.goal || 1))}%` }} />
              </div>
              <small>{badge.progress}/{badge.goal}</small>
            </div>
          ))}
        </div>
      </section>

      {lockedBadges.length > 0 && (
        <section className="card funny-card">
          <h2>Вердикт Отца</h2>
          <p>
            {summary.missing_predictions > 0
              ? `Еще ${summary.missing_predictions} ${pluralRu(summary.missing_predictions, 'матч', 'матча', 'матчей')} ждут прогноза. Отец прогнозов уже смотрит осуждающе.`
              : 'Все доступные прогнозы сделаны. Теперь остается только молиться футбольным богам.'}
          </p>
        </section>
      )}
    </main>
  );
}


function More() {
  const [fact, setFact] = useState('');
  const [archive, setArchive] = useState('');
  async function loadFact() {
    const result = await api('/api/webapp/facts/random');
    setFact(result.fact?.text || '');
  }
  async function loadArchive() {
    const result = await api('/api/webapp/archive/random');
    setArchive(`${result.card?.title || ''}\n${result.card?.text || ''}`);
  }
  const links = [
    ['Sofascore', 'https://www.sofascore.com/football/tournament/world/world-championship/16#id:58210'],
    ['Flashscore', 'https://www.flashscore.com/football/world/world-championship/'],
    ['FIFA', 'https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures'],
    ['Матч ТВ', 'https://matchtv.ru/football/worldcup/2026'],
    ['Чемпионат', 'https://www.championat.com/news/football/_worldcup/1.html'],
  ];
  return (
    <main className="screen-content">
      <div className="section-label">Еще</div>
      <section className="card actions-card">
        <button onClick={loadFact}>📚 Получить факт</button>
        {fact && <p>{fact}</p>}
      </section>
      <section className="card actions-card">
        <button onClick={loadArchive}>🗂 Карточка архива</button>
        {archive && <pre>{archive}</pre>}
      </section>
      <section className="card">
        <h2>Полезные ссылки</h2>
        <div className="links-list">
          {links.map(([title, url]) => (
            <button key={title} onClick={() => tg?.openLink ? tg.openLink(url) : window.open(url, '_blank')}>{title} ›</button>
          ))}
        </div>
      </section>
    </main>
  );
}

function RulesModal({ onClose }) {
  return (
    <div className="modal-backdrop">
      <section className="modal-card rules-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>📜 Правила начисления очков</h2>

        <div className="rules-section">
          <h3>За каждый матч</h3>
          <div className="rules-score-grid">
            <div><b>🎯 3</b><span>точный счет</span></div>
            <div><b>✅ 1</b><span>угаданный исход</span></div>
            <div><b>❌ 0</b><span>счет и исход не угаданы</span></div>
          </div>
          <p className="muted">
            Пример: прогноз Мексика — ЮАР 2:1. Если матч закончился 2:1 — 3 очка.
            Если 3:1 — 1 очко. Если 2:2 или 0:1 — 0 очков.
          </p>
        </div>

        <div className="rules-section">
          <h3>Плей-офф</h3>
          <ul className="nice-list">
            <li>🟢 +1 очко — если проход дальше угадан.</li>
            <li>🔴 -1 очко — если проход не угадан.</li>
            <li>⚪ 0 очков — если участник решил не ставить на проход.</li>
          </ul>
        </div>

        <div className="rules-section">
          <h3>Прогноз на итоги турнира</h3>
          <div className="rules-score-grid tournament-rules">
            <div><b>🏆 15</b><span>чемпион</span></div>
            <div><b>🥈 10</b><span>финалист</span></div>
            <div><b>🥉 5</b><span>3 место</span></div>
            <div><b>⚽ 15</b><span>бомбардир</span></div>
          </div>
        </div>
      </section>
    </div>
  );
}

function App() {
  const [tab, setTab] = useState('matches');
  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState(null);
  const [predictionMatch, setPredictionMatch] = useState(null);
  const [forecastMatch, setForecastMatch] = useState(null);
  const [tournamentPickField, setTournamentPickField] = useState(null);
  const [tournamentPrediction, setTournamentPrediction] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [rulesOpen, setRulesOpen] = useState(false);

  async function loadDashboard() {
    try {
      const [dashboardResult, tournamentPredictionResult] = await Promise.all([
        api('/api/webapp/dashboard'),
        api('/api/webapp/tournament-prediction/me').catch(() => null),
      ]);
      setDashboard(dashboardResult);
      setTournamentPrediction(tournamentPredictionResult);
    } catch (err) {
      setDashboardError(err);
    }
  }

  useEffect(() => { loadDashboard(); }, [refreshKey]);

  function handleSaved() {
    setRefreshKey((value) => value + 1);
  }

  function handleTournamentSaved() {
    setRefreshKey((value) => value + 1);
  }

  if (dashboardError) {
    return <div className="app"><ErrorCard error={dashboardError} onRetry={loadDashboard} /></div>;
  }

  return (
    <div className="app">
      <Header dashboard={dashboard} onRules={() => setRulesOpen(true)} />

      {tab === 'matches' && (
        <>
          <HomeHero dashboard={dashboard} tournamentPrediction={tournamentPrediction} onTournamentPick={setTournamentPickField} setTab={setTab} />
          <MatchCenter key={`matches-${refreshKey}`} onPredict={setPredictionMatch} onForecast={setForecastMatch} />
        </>
      )}
      {tab === 'predictions' && <Predictions key={`predictions-${refreshKey}`} onPredict={setPredictionMatch} onForecast={setForecastMatch} />}
      {tab === 'tournament' && <Tournament tournamentPrediction={tournamentPrediction} />}
      {tab === 'rating' && <Rating />}
      {tab === 'profile' && <Profile tournamentPrediction={tournamentPrediction} />}

      <nav className="bottom-nav">
        {TABS.map((item) => (
          <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}>
            <Icon name={item.icon} />
            <small>{item.label}</small>
          </button>
        ))}
      </nav>

      {predictionMatch && <ScorePicker match={predictionMatch} onClose={() => setPredictionMatch(null)} onSaved={handleSaved} />}
      {forecastMatch && <ForecastModal match={forecastMatch} onClose={() => setForecastMatch(null)} />}
      {tournamentPickField && <TournamentPredictionModal currentPrediction={tournamentPrediction} initialField={tournamentPickField} onClose={() => setTournamentPickField(null)} onSaved={handleTournamentSaved} />}
      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
