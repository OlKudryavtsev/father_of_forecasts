
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
  { id: 'fantasy', label: 'Fantasy-футбол', icon: 'team' },
  { id: 'rating', label: 'Рейтинг', icon: 'rank' },
  { id: 'resources', label: 'Ресурсы', icon: 'link' },
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

  if (name === 'link') {
    return (
      <svg {...common}>
        <path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1" />
        <path d="M14 11a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 20.1l1.1-1.1" />
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

  if (name === 'arrowDown') {
    return (
      <svg {...common} fill="currentColor" stroke="none">
        <path d="M12 20 5 9h14l-7 11Z" />
      </svg>
    );
  }

  if (name === 'arrowUp') {
    return (
      <svg {...common} fill="currentColor" stroke="none">
        <path d="M12 4 19 15H5L12 4Z" />
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

function formatRoundLabel(match) {
  if (!match) return '';

  if (match.stage === 'group') {
    if (match.match_round) {
      const value = String(match.match_round).replace(/^тур\s*/i, '').trim();
      return `Тур ${value}`;
    }

    return 'Группа';
  }

  const round = match.match_round || match.stage || '';

  if (!round) return 'Плей-офф';

  const normalized = String(round).toLowerCase();

  if (normalized.includes('round of 16') || normalized.includes('1/8')) return '1/8 финала';
  if (normalized.includes('quarter') || normalized.includes('1/4')) return '1/4 финала';
  if (normalized.includes('semi') || normalized.includes('1/2')) return '1/2 финала';
  if (normalized.includes('third') || normalized.includes('3')) return 'Матч за 3 место';
  if (normalized.includes('final')) return 'Финал';

  return round;
}

function predictionResultClass(match) {
  if (!match?.is_finished || !match?.prediction) return '';

  const points = match.prediction.score_points ?? match.prediction.points ?? 0;

  if (points >= 3) return 'prediction-exact';
  if (points >= 1) return 'prediction-outcome';

  return 'prediction-miss';
}

function formatPredictionScore(prediction) {
  if (!prediction) return '— : —';
  return `${prediction.pred_home}:${prediction.pred_away}`;
}

function formatActualScore(match) {
  if (!match?.is_finished || match.score_home === null || match.score_home === undefined) return '— : —';
  return `${match.score_home}:${match.score_away}`;
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

const FANTASY_FORMATIONS = [
  { value: '4-3-3', label: '4-3-3', defenders: 4, midfielders: 3, attackers: 3 },
  { value: '4-4-2', label: '4-4-2', defenders: 4, midfielders: 4, attackers: 2 },
  { value: '4-2-2', label: '4-2-2-2', defenders: 4, midfielders: 4, attackers: 2 },
  { value: '5-4-1', label: '5-4-1', defenders: 5, midfielders: 4, attackers: 1 },
  { value: '4-5-1', label: '4-5-1', defenders: 4, midfielders: 5, attackers: 1 },
  { value: '3-5-2', label: '3-5-2', defenders: 3, midfielders: 5, attackers: 2 },
  { value: '3-4-3', label: '3-4-3', defenders: 3, midfielders: 4, attackers: 3 },
  { value: '5-3-2', label: '5-3-2', defenders: 5, midfielders: 3, attackers: 2 },
  { value: '4-1-4-1', label: '4-1-4-1', defenders: 4, midfielders: 5, attackers: 1 },
];

const FANTASY_STARTER_SLOTS = buildFormationSlots('4-3-3');

const FANTASY_BENCH_SLOTS = [
  { slot: 'ЗАП1', position: 'Goalkeeper', label: 'ВР запас', isStarter: false },
  { slot: 'ЗАП2', position: 'Defender', label: 'ЗЩ запас', isStarter: false },
  { slot: 'ЗАП3', position: 'Midfielder', label: 'ПЗ запас', isStarter: false },
  { slot: 'ЗАП4', position: 'Midfielder', label: 'ПЗ запас', isStarter: false },
];

const FANTASY_SLOTS = [...FANTASY_STARTER_SLOTS, ...FANTASY_BENCH_SLOTS];

function getFormationConfig(formation) {
  return FANTASY_FORMATIONS.find((item) => item.value === formation) || FANTASY_FORMATIONS[0];
}

function spreadPositions(count, top, minLeft = 12, maxLeft = 88) {
  if (count === 1) return [{ top, left: 50 }];
  const step = (maxLeft - minLeft) / (count - 1);
  return Array.from({ length: count }, (_, index) => ({ top, left: Math.round(minLeft + step * index) }));
}

function buildFormationSlots(formation) {
  const config = getFormationConfig(formation);
  const attackerPositions = spreadPositions(config.attackers, 8, config.attackers === 1 ? 50 : 20, config.attackers === 1 ? 50 : 80);
  const midfieldPositions = spreadPositions(config.midfielders, 42, 10, 90);
  const defenderPositions = spreadPositions(config.defenders, 70, 8, 92);

  return [
    ...attackerPositions.map((position, index) => ({
      slot: `НП${index + 1}`,
      position: 'Attacker',
      label: 'НП',
      isStarter: true,
      ...position,
    })),
    ...midfieldPositions.map((position, index) => ({
      slot: `ПЗ${index + 1}`,
      position: 'Midfielder',
      label: 'ПЗ',
      isStarter: true,
      ...position,
    })),
    ...defenderPositions.map((position, index) => ({
      slot: `ЗЩ${index + 1}`,
      position: 'Defender',
      label: 'ЗЩ',
      isStarter: true,
      ...position,
    })),
    { slot: 'ВР1', position: 'Goalkeeper', label: 'ВР', isStarter: true, top: 90, left: 50 },
  ];
}

function formatDeadlineCountdown(targetValue, now) {
  if (!targetValue) return 'дедлайн не определен';
  const target = new Date(targetValue).getTime();
  const diff = Math.max(0, target - now);
  const totalSeconds = Math.floor(diff / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (value) => String(value).padStart(2, '0');
  return days > 0 ? `${days}д ${pad(hours)}:${pad(minutes)}:${pad(seconds)}` : `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function positionOrder(position) {
  return { Goalkeeper: 0, Defender: 1, Midfielder: 2, Attacker: 3 }[position] ?? 9;
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

function MatchCard({ match, onPredict, onForecast, onParticipants, showDistribution = true }) {
  const locked = match.is_finished || new Date(match.starts_at).getTime() <= Date.now();
  const predictionScoreClass = predictionResultClass(match);

  return (
    <article className="match-card">
      <div className="match-card-top">
        <span className="group-pill">{match.group_code ? `Группа ${match.group_code}` : match.stage}</span>
        <span className="round-pill">{formatRoundLabel(match)}</span>
        <span className={match.is_finished ? 'dot dot-finished' : 'dot'} />
        <span className="muted small match-date">{formatDateTime(match.starts_at)}</span>
      </div>

      <div className="match-teams">
        <div className="team-side">
          <span className="flag">{match.home_flag || '🏳️'}</span>
          <strong>{match.home_team}</strong>
        </div>
        <div className="score-block match-score-stack">
          {match.is_finished ? (
            <>
              <div className="actual-score-row">
                <small>матч</small>
                <strong>{formatActualScore(match)}</strong>
              </div>
              <div className={`prediction-score-row ${predictionScoreClass}`}>
                <small>прогноз</small>
                <strong>{formatPredictionScore(match.prediction)}</strong>
              </div>
            </>
          ) : (
            <>
              <strong>{formatPredictionScore(match.prediction)}</strong>
              {match.prediction && <small>мой прогноз</small>}
              {!match.prediction && !locked && <small>прогноза нет</small>}
              {locked && !match.prediction && <small>закрыт</small>}
            </>
          )}
        </div>
        <div className="team-side">
          <span className="flag">{match.away_flag || '🏳️'}</span>
          <strong>{match.away_team}</strong>
        </div>
      </div>

      <div className="match-actions">
        {!locked && <button onClick={() => onPredict(match)}>{match.prediction ? 'Изменить прогноз' : 'Сделать прогноз'}</button>}
        <button onClick={() => onParticipants(match)}>Участники</button>
        <button onClick={() => onForecast(match)}><Icon name="robot" /> Прогноз Отца</button>
      </div>

      {showDistribution && locked && <PredictionBars distribution={match.prediction_distribution} />}
    </article>
  );
}

function groupMatchesByDay(matches) {
  const map = new Map();

  for (const match of matches || []) {
    const date = new Date(match.starts_at);
    const key = Number.isNaN(date.getTime())
      ? (match.starts_at || '').slice(0, 10)
      : [
          date.getFullYear(),
          String(date.getMonth() + 1).padStart(2, '0'),
          String(date.getDate()).padStart(2, '0'),
        ].join('-');

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

function MatchCenter({ onPredict, onForecast, onParticipants }) {
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
                {matches.map((match) => <MatchCard key={match.id} match={match} onPredict={onPredict} onForecast={onForecast} onParticipants={onParticipants} />)}
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


function MatchParticipantsModal({ match, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);

    api(`/api/webapp/matches/${match.id}/predictions`)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err) => {
        if (active) setError(err);
      });

    return () => { active = false; };
  }, [match.id]);

  const participants = data?.participants || [];

  return (
    <div className="modal-backdrop">
      <section className="modal-card participants-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>Участники матча</h2>
        <p className="muted">{match.home_team} — {match.away_team}</p>

        {error && <p className="error-text">{error.message}</p>}
        {!error && !data && <LoadingCard text="Загружаю участников..." />}

        {data && (
          <>
            <div className="participants-summary">
              <strong>{data.participants_count}</strong>
              <span>{pluralRu(data.participants_count, 'прогноз сделан', 'прогноза сделано', 'прогнозов сделано')}</span>
            </div>

            {!data.has_started && (
              <p className="participants-note">
                До начала матча показываем только, кто уже сделал ставку. Счета откроются после стартового свистка.
              </p>
            )}

            {participants.length === 0 ? (
              <div className="empty-state compact-empty">
                <div className="empty-icon"><Icon name="target" /></div>
                <h2>Пока никто не поставил</h2>
                <p>Будь первым, кто рискнет репутацией.</p>
              </div>
            ) : (
              <div className="participants-list">
                {participants.map((participant) => (
                  <div className="participant-row" key={participant.user_id}>
                    <span>{participant.display_name}</span>
                    {data.has_started ? (
                      <b>{participant.pred_home}:{participant.pred_away}</b>
                    ) : (
                      <em>ставка сделана</em>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
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

function Fantasy() {
  const [players, setPlayers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [rules, setRules] = useState(null);
  const [team, setTeam] = useState(null);
  const [formation, setFormation] = useState('4-3-3');
  const [selectedBySlot, setSelectedBySlot] = useState({});
  const [captainId, setCaptainId] = useState(null);
  const [pickerSlot, setPickerSlot] = useState(null);
  const [replacingStarterSlot, setReplacingStarterSlot] = useState(null);
  const [q, setQ] = useState('');
  const [filterTeam, setFilterTeam] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [showDetailedRules, setShowDetailedRules] = useState(false);
  const now = useNowTick();

  async function load() {
    setError(null);
    try {
      const [playersResult, teamResult] = await Promise.all([
        api('/api/webapp/fantasy/players?limit=1000'),
        api('/api/webapp/fantasy/team/me'),
      ]);
      setPlayers(playersResult.players || []);
      setTeams(playersResult.teams || []);
      setRules(playersResult.rules || teamResult.rules || null);
      setTeam(teamResult.team || null);

      const loadedFormation = teamResult.team?.formation || '4-3-3';
      const loadedStarterSlots = buildFormationSlots(loadedFormation);
      setFormation(loadedFormation);

      const nextSelected = {};
      const startersByPosition = { Goalkeeper: [], Defender: [], Midfielder: [], Attacker: [] };
      const benchItems = [];

      for (const item of teamResult.team?.players || []) {
        if (item.is_starter) {
          startersByPosition[item.position]?.push(item);
        } else {
          benchItems.push(item);
        }
      }

      for (const slot of loadedStarterSlots) {
        const item = startersByPosition[slot.position]?.shift();
        if (item) nextSelected[slot.slot] = item.player;
      }

      for (const item of benchItems.sort((a, b) => (a.bench_order || 0) - (b.bench_order || 0))) {
        const slot = FANTASY_BENCH_SLOTS.find((candidate) => !nextSelected[candidate.slot] && candidate.position === item.position)
          || FANTASY_BENCH_SLOTS.find((candidate) => !nextSelected[candidate.slot]);

        if (slot) nextSelected[slot.slot] = item.player;
      }

      setSelectedBySlot(nextSelected);
      setCaptainId(teamResult.team?.captain_player_id || null);
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, []);

  const starterSlots = buildFormationSlots(formation);
  const allSlots = [...starterSlots, ...FANTASY_BENCH_SLOTS];
  const formationConfig = getFormationConfig(formation);

  const selectedPlayers = Object.values(selectedBySlot).filter(Boolean);
  const selectedIds = new Set(selectedPlayers.map((player) => player.id));
  const selectedCount = selectedPlayers.length;
  const points = team?.points || 0;
  const roundState = rules?.round_state || {};
  const categoryCounts = selectedPlayers.reduce((acc, player) => {
    acc[player.fifa_category] = (acc[player.fifa_category] || 0) + 1;
    return acc;
  }, {});
  const starterCategoryCounts = starterSlots
    .map((slot) => selectedBySlot[slot.slot])
    .filter(Boolean)
    .reduce((acc, player) => {
      acc[player.fifa_category] = (acc[player.fifa_category] || 0) + 1;
      return acc;
    }, {});
  const teamCounts = selectedPlayers.reduce((acc, player) => {
    acc[player.team_display_name] = (acc[player.team_display_name] || 0) + 1;
    return acc;
  }, {});
  const categoryLimits = rules?.category_limits || {};
  const maxFromOneTeam = rules?.max_from_one_team || 3;
  const deadlineText = formatDeadlineCountdown(roundState.deadline_at, now);

  function changeFormation(nextFormation) {
    const nextStarterSlots = buildFormationSlots(nextFormation);
    const currentStarters = starterSlots
      .map((slot) => selectedBySlot[slot.slot])
      .filter(Boolean);

    const currentBench = FANTASY_BENCH_SLOTS
      .map((slot) => selectedBySlot[slot.slot])
      .filter(Boolean);

    const poolByPosition = { Goalkeeper: [], Defender: [], Midfielder: [], Attacker: [] };

    for (const player of currentStarters) {
      poolByPosition[player.position]?.push(player);
    }

    const nextSelected = {};

    for (const slot of nextStarterSlots) {
      const player = poolByPosition[slot.position]?.shift();
      if (player) nextSelected[slot.slot] = player;
    }

    const leftoverStarters = Object.values(poolByPosition).flat();
    const benchPool = [...currentBench, ...leftoverStarters];
    const usedIds = new Set(Object.values(nextSelected).map((player) => player.id));

    for (const slot of FANTASY_BENCH_SLOTS) {
      const exactIndex = benchPool.findIndex((player) => !usedIds.has(player.id) && player.position === slot.position);
      const fallbackIndex = exactIndex >= 0 ? exactIndex : benchPool.findIndex((player) => !usedIds.has(player.id));

      if (fallbackIndex >= 0) {
        const player = benchPool.splice(fallbackIndex, 1)[0];
        nextSelected[slot.slot] = player;
        usedIds.add(player.id);
      }
    }

    setFormation(nextFormation);
    setSelectedBySlot(nextSelected);
    setReplacingStarterSlot(null);

    if (captainId && !nextStarterSlots.some((slot) => nextSelected[slot.slot]?.id === captainId)) {
      setCaptainId(null);
    }
  }

  function selectPlayer(slot, player) {
    const previous = selectedBySlot[slot.slot];
    const nextSelected = { ...selectedBySlot };
    nextSelected[slot.slot] = player;

    if (previous?.id === captainId) {
      setCaptainId(null);
    }

    setSelectedBySlot(nextSelected);
    setPickerSlot(null);
    setReplacingStarterSlot(null);
    setQ('');
  }

  function removePlayer(slotName) {
    const player = selectedBySlot[slotName];
    const nextSelected = { ...selectedBySlot };
    delete nextSelected[slotName];
    setSelectedBySlot(nextSelected);
    setReplacingStarterSlot(null);

    if (player?.id === captainId) {
      setCaptainId(null);
    }
  }

  function swapWithBench(benchSlotName) {
    if (!replacingStarterSlot) return;

    const starterPlayer = selectedBySlot[replacingStarterSlot.slot];
    const benchPlayer = selectedBySlot[benchSlotName];

    if (!starterPlayer || !benchPlayer) return;
    if (starterPlayer.position !== benchPlayer.position) return;

    const nextSelected = { ...selectedBySlot };
    nextSelected[replacingStarterSlot.slot] = benchPlayer;
    nextSelected[benchSlotName] = starterPlayer;

    setSelectedBySlot(nextSelected);

    if (captainId === starterPlayer.id) {
      setCaptainId(benchPlayer.id);
    }

    setReplacingStarterSlot(null);
  }


  function setRandomTeam() {
    const nextSelected = {};
    const nextTeamCounts = {};
    const nextStarterCategoryCounts = {};
    const shuffled = [...players].sort(() => Math.random() - 0.5);

    function isStarterSlot(slot) {
      return starterSlots.some((starterSlot) => starterSlot.slot === slot.slot);
    }

    function canPickPlayer(player, slot) {
      if (player.position !== slot.position) return false;
      if (Object.values(nextSelected).some((selected) => selected.id === player.id)) return false;
      if ((nextTeamCounts[player.team_display_name] || 0) >= maxFromOneTeam) return false;

      if (isStarterSlot(slot)) {
        const categoryLimit = categoryLimits[player.fifa_category];
        if (categoryLimit && (nextStarterCategoryCounts[player.fifa_category] || 0) >= categoryLimit) return false;
      }

      return true;
    }

    const orderedSlots = [...starterSlots, ...FANTASY_BENCH_SLOTS];

    for (const slot of orderedSlots) {
      let candidate = shuffled.find((player) => canPickPlayer(player, slot));

      // Fallback for bench: keep the team limit and uniqueness, but do not let category limits block filling the bench.
      if (!candidate && !isStarterSlot(slot)) {
        candidate = shuffled.find((player) => {
          if (player.position !== slot.position) return false;
          if (Object.values(nextSelected).some((selected) => selected.id === player.id)) return false;
          if ((nextTeamCounts[player.team_display_name] || 0) >= maxFromOneTeam) return false;
          return true;
        });
      }

      if (candidate) {
        nextSelected[slot.slot] = candidate;
        nextTeamCounts[candidate.team_display_name] = (nextTeamCounts[candidate.team_display_name] || 0) + 1;

        if (isStarterSlot(slot)) {
          nextStarterCategoryCounts[candidate.fifa_category] = (nextStarterCategoryCounts[candidate.fifa_category] || 0) + 1;
        }
      }
    }

    setSelectedBySlot(nextSelected);
    setReplacingStarterSlot(null);
    const firstStarter = starterSlots.map((slot) => nextSelected[slot.slot]).find(Boolean);
    setCaptainId(firstStarter?.id || null);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const playerIds = allSlots.map((slot) => selectedBySlot[slot.slot]?.id).filter(Boolean);
      const startingPlayerIds = starterSlots.map((slot) => selectedBySlot[slot.slot]?.id).filter(Boolean);
      if (playerIds.length !== 15) throw new Error('Выберите всех 15 игроков: 11 в основе и 4 запасных.');
      if (startingPlayerIds.length !== 11) throw new Error('Выберите всех 11 игроков стартового состава.');
      if (!captainId) throw new Error('Выберите капитана — его очки будут удваиваться.');
      const result = await api('/api/webapp/fantasy/team', {
        method: 'POST',
        body: JSON.stringify({ formation, player_ids: playerIds, starting_player_ids: startingPlayerIds, captain_player_id: captainId }),
      });
      setTeam(result.team);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  if (error && !players.length) return <ErrorCard error={error} onRetry={load} />;
  if (!rules) return <LoadingCard />;

  return (
    <main className="screen-content fantasy-screen">
      <div className="section-label">Собрать команду</div>

      <section className="fantasy-hero">
        <div>
          <h2>Fantasy ЧМ-2026</h2>
          <p>{selectedCount}/15 · до {maxFromOneTeam} из сборной · капитан x2</p>
        </div>
        <div className="fantasy-points"><b>{points}</b><span>очков</span></div>
      </section>

      <section className="fantasy-deadline-card compact-deadline-card">
        <span>Дедлайн: {roundState.title || 'следующий тур'}</span>
        <strong>{deadlineText}</strong>
        <small>{roundState.free_transfers === null ? 'трансферы без ограничений' : `бесплатных трансферов: ${roundState.free_transfers}, лишний: -${roundState.extra_transfer_penalty}`}</small>
      </section>

      <div className="fantasy-toolbar fantasy-formation-toolbar">
        <label>
          <span>Схема</span>
          <select value={formation} onChange={(event) => changeFormation(event.target.value)}>
            {FANTASY_FORMATIONS.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <strong>{formationConfig.label}</strong>
        <span>Основа: {formationConfig.defenders}-{formationConfig.midfielders}-{formationConfig.attackers}</span>
      </div>

      <section className="football-pitch">
        <div className="pitch-line box-top" />
        <div className="pitch-line center-line" />
        <div className="pitch-circle" />
        <div className="pitch-line box-bottom" />
        {starterSlots.map((slot) => {
          const player = selectedBySlot[slot.slot];
          const isCaptain = player?.id === captainId;
          const isReplacing = replacingStarterSlot?.slot === slot.slot;
          return (
            <div
              key={slot.slot}
              role="button"
              tabIndex={0}
              className={`pitch-slot ${player ? 'filled' : ''} ${isCaptain ? 'captain' : ''} ${isReplacing ? 'replace-active' : ''}`}
              style={{ top: `${slot.top}%`, left: `${slot.left}%` }}
              onClick={() => setPickerSlot(slot)}
              title={player?.name || slot.label}
            >
              {player ? (
                <>
                  <span>{player.team_flag}</span>
                  <strong>{player.name}</strong>
                  {isCaptain && <em>C</em>}
                  <button
                    type="button"
                    className="player-swap-button swap-down"
                    onClick={(event) => {
                      event.stopPropagation();
                      setReplacingStarterSlot(isReplacing ? null : slot);
                    }}
                    title="Заменить игрока игроком со скамейки"
                  >
                    <Icon name="arrowDown" />
                  </button>
                </>
              ) : (
                <>
                  <b>+</b>
                  <small>{slot.label}</small>
                </>
              )}
            </div>
          );
        })}
        <button className="random-team-button" onClick={setRandomTeam}>случайный состав</button>
      </section>

      <section className="card fantasy-bench-card">
        <div className="bench-title-row">
          <h2>Скамейка</h2>
          {replacingStarterSlot && <span>Выберите игрока той же позиции, чтобы выпустить его на поле</span>}
        </div>
        <div className="fantasy-bench-grid">
          {FANTASY_BENCH_SLOTS.map((slot) => {
            const player = selectedBySlot[slot.slot];
            const canSwap = Boolean(replacingStarterSlot && player && player.position === replacingStarterSlot.position);
            return (
              <div key={slot.slot} role="button" tabIndex={0} className={`${player ? 'filled' : ''} ${canSwap ? 'release-active' : ''}`} onClick={() => setPickerSlot(slot)}>
                <span>{player?.team_flag || '+'}</span>
                <strong>{player?.name || slot.label}</strong>
                <small>{player ? `${player.team_display_name} · ${player.position_label}` : 'выбрать'}</small>
                {replacingStarterSlot && player && (
                  <button
                    type="button"
                    className={`player-swap-button swap-up ${canSwap ? '' : 'disabled'}`}
                    disabled={!canSwap}
                    onClick={(event) => {
                      event.stopPropagation();
                      swapWithBench(slot.slot);
                    }}
                    title={canSwap ? 'Выпустить игрока на поле' : 'Нужен игрок той же позиции'}
                  >
                    <Icon name="arrowUp" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section className="card fantasy-save-card">
        <div>
          <strong>{selectedCount}/15 игроков</strong>
          <span>Капитан: {selectedPlayers.find((player) => player.id === captainId)?.name || 'не выбран'}</span>
          {team?.transfer_penalty_points > 0 && <span className="error-text">Штраф за лишние трансферы: -{team.transfer_penalty_points}</span>}
        </div>
        {error && <p className="error-text">{error.message}</p>}
        <button className="primary full" disabled={saving || rules.is_locked} onClick={save}>
          {rules.is_locked ? 'Команда закрыта' : saving ? 'Сохраняю...' : 'Сохранить команду'}
        </button>
      </section>

      <section className="card fantasy-rules-card">
        <h2>Правила набора</h2>
        <ul className="nice-list">
          <li><b>Заявка:</b> 15 игроков — 2 ВР, 5 ЗЩ, 5 ПЗ, 3 НП.</li>
          <li><b>Основа:</b> 11 игроков по схеме 4-3-3.</li>
          <li>Капитан должен быть в основе, его очки удваиваются.</li>
          <li>Лимит сборной на текущей стадии: до {maxFromOneTeam} игроков.</li>
        </ul>
        <div className="fantasy-categories">
          {rules.categories.map((category) => (
            <div key={category.id} className={`category-line category-${category.id} ${category.enabled ? '' : 'disabled'}`}>
              <i>Г{category.id}</i>
              <span><strong>{category.title}</strong><small>{category.enabled ? `${category.range} · основа` : 'лимит снят с 1/4'}</small></span>
              <b>{categoryCounts[category.id] || 0}/{category.enabled ? category.limit : '∞'}</b>
            </div>
          ))}
        </div>
      </section>

      <section className="card fantasy-scoring-card">
        <div className="rules-title-row fantasy-rules-title">
          <h2>Как начисляются очки</h2>
          <button onClick={() => setShowDetailedRules(!showDetailedRules)}>{showDetailedRules ? 'Скрыть детали' : 'Детально'}</button>
        </div>
        <p className="gold-text">Очки капитана удваиваются. Бюджета игроков нет.</p>
        <div className="fantasy-scoring-grid">
          {rules.scoring.map((item) => (
            <div key={item.title} className={item.type === 'minus' ? 'minus' : ''}>
              <strong>{item.title}</strong>
              <span>{item.description}</span>
              <b>{item.points > 0 ? '+' : ''}{item.points}</b>
            </div>
          ))}
        </div>
        {showDetailedRules && (
          <div className="fantasy-detailed-rules">
            {(rules.detailed_rules || []).map((item) => <p key={item}>{item}</p>)}
          </div>
        )}
      </section>

      {pickerSlot && (
        <FantasyPlayerPicker
          slot={pickerSlot}
          players={players}
          teams={teams}
          selectedIds={selectedIds}
          selectedBySlot={selectedBySlot}
          teamCounts={teamCounts}
          categoryCounts={categoryCounts}
          starterCategoryCounts={starterCategoryCounts}
          rules={rules}
          q={q}
          setQ={setQ}
          filterTeam={filterTeam}
          setFilterTeam={setFilterTeam}
          captainId={captainId}
          setCaptainId={setCaptainId}
          onSelect={selectPlayer}
          onRemove={removePlayer}
          onClose={() => setPickerSlot(null)}
        />
      )}
    </main>
  );
}

function FantasyPlayerPicker({
  slot,
  players,
  teams,
  selectedIds,
  selectedBySlot,
  teamCounts,
  categoryCounts,
  starterCategoryCounts,
  rules,
  q,
  setQ,
  filterTeam,
  setFilterTeam,
  captainId,
  setCaptainId,
  onSelect,
  onRemove,
  onClose,
}) {
  const current = selectedBySlot[slot.slot];
  const isStarterSlot = Boolean(slot.isStarter);
  const [selectedPlayerId, setSelectedPlayerId] = useState('');

  const positionPlayers = players
    .filter((player) => player.position === slot.position)
    .sort((a, b) => (a.fifa_category - b.fifa_category) || a.team_display_name.localeCompare(b.team_display_name) || a.name.localeCompare(b.name));

  const availableTeams = teams
    .filter((team) => positionPlayers.some((player) => player.team_display_name === team.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  const teamPlayers = positionPlayers
    .filter((player) => !filterTeam || player.team_display_name === filterTeam);

  useEffect(() => {
    setSelectedPlayerId('');
  }, [slot.slot, filterTeam]);

  function disabledReason(player) {
    if (current?.id === player.id) return '';
    if (selectedIds.has(player.id)) return 'уже выбран';

    const effectiveTeamCount = (teamCounts[player.team_display_name] || 0) - (current?.team_display_name === player.team_display_name ? 1 : 0);
    if (effectiveTeamCount >= (rules?.max_from_one_team || 3)) return 'лимит сборной';

    if (isStarterSlot) {
      const categoryLimit = rules?.category_limits?.[player.fifa_category];
      const effectiveCategoryCount = (starterCategoryCounts?.[player.fifa_category] || 0) - (current?.fifa_category === player.fifa_category ? 1 : 0);
      if (categoryLimit && effectiveCategoryCount >= categoryLimit) return 'лимит категории';
    }

    return '';
  }

  function selectFromDropdown(value) {
    setSelectedPlayerId(value);

    const player = teamPlayers.find((item) => String(item.id) === String(value));
    if (!player) return;

    const reason = disabledReason(player);
    if (reason) return;

    onSelect(slot, player);
  }

  return (
    <div className="modal-backdrop">
      <section className="modal-card fantasy-picker-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>Выбор игрока · {slot.label}</h2>
        <p className="muted">Сначала выберите сборную, затем игрока из выпадающего списка.</p>

        <div className="fantasy-picker-selects">
          <label>
            <span>Сборная</span>
            <select
              value={filterTeam}
              onChange={(event) => {
                setFilterTeam(event.target.value);
                setQ('');
              }}
            >
              <option value="">Выберите сборную</option>
              {availableTeams.map((team) => <option key={team.name} value={team.name}>{team.flag} {team.name}</option>)}
            </select>
          </label>

          <label>
            <span>Игрок</span>
            <select
              value={selectedPlayerId}
              disabled={!filterTeam}
              onChange={(event) => selectFromDropdown(event.target.value)}
            >
              <option value="">{filterTeam ? 'Выберите игрока' : 'Сначала выберите сборную'}</option>
              {teamPlayers.map((player) => {
                const reason = disabledReason(player);
                return (
                  <option key={player.id} value={player.id} disabled={Boolean(reason)}>
                    {player.name} · {player.position_label} · Г{player.fifa_category}{reason ? ` · ${reason}` : ''}
                  </option>
                );
              })}
            </select>
          </label>
        </div>

        {current && (
          <div className="current-player-card fantasy-current-player">
            <span>{current.team_flag}</span>
            <strong>{current.name}</strong>
            <small>{current.team_display_name} · {current.position_label} · Г{current.fifa_category}</small>
            {isStarterSlot && <button onClick={() => setCaptainId(current.id)}>{captainId === current.id ? 'Капитан выбран' : 'Сделать капитаном'}</button>}
            <button className="danger" onClick={() => onRemove(slot.slot)}>Убрать</button>
          </div>
        )}

        {filterTeam && teamPlayers.length === 0 && (
          <div className="empty-state compact-empty">
            <div className="empty-icon"><Icon name="team" /></div>
            <h2>Нет игроков</h2>
            <p>В этой сборной нет игроков нужной позиции.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function Predictions({ onPredict, onForecast, onParticipants }) {
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
                {dayMatches.map((match) => <MatchCard key={match.id} match={match} onPredict={onPredict} onForecast={onForecast} onParticipants={onParticipants} showDistribution={false} />)}
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
  const [includeFantasy, setIncludeFantasy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api('/api/webapp/table').then(setData).catch(setError);
  }, []);

  if (error) return <ErrorCard error={error} />;
  if (!data) return <LoadingCard />;

  const rows = [...(data.rows || [])]
    .map((row) => ({
      ...row,
      display_points: includeFantasy ? (row.points || 0) + (row.fantasy_points || 0) : (row.points || 0),
    }))
    .sort((a, b) => (b.display_points - a.display_points) || ((b.exact_scores || 0) - (a.exact_scores || 0)));

  return (
    <main className="screen-content rating-screen">
      <div className="section-label">Рейтинг участников</div>

      <label className="rating-toggle-card">
        <input type="checkbox" checked={includeFantasy} onChange={(event) => setIncludeFantasy(event.target.checked)} />
        <span />
        <strong>Учитывать Fantasy</strong>
        <small>{includeFantasy ? 'очки прогноза + fantasy' : 'только прогнозы'}</small>
      </label>

      <div className="ranking-list compact-ranking-list">
        {rows.map((row, index) => (
          <div key={row.name} className={`ranking-row rating-rich-row ${row.is_current_user ? 'me' : ''}`}>
            <div className="rating-main-line">
              <span className="rank">#{index + 1}</span>
              <div className="rating-player">
                <strong>{row.name}</strong>
                <small>
                  {row.display_points} очков · прогнозы {row.points} · fantasy {row.fantasy_points || 0}
                </small>
              </div>
              <div className={`tournament-progress-pill ${row.has_tournament_prediction ? 'done' : 'empty'}`}>
                {row.tournament_prediction_progress || '0/4'}
              </div>
            </div>

            <div className="rating-metrics-grid">
              <div>
                <b>{row.match_predictions_count ?? row.total_predictions ?? 0}</b>
                <span>прогнозов</span>
              </div>
              <div>
                <b>{row.outcomes ?? 0}</b>
                <span>исходов</span>
              </div>
              <div>
                <b>{row.exact_scores ?? 0}</b>
                <span>точных</span>
              </div>
              <div>
                <b>{row.accuracy_percent ?? 0}%</b>
                <span>попаданий</span>
              </div>
            </div>

            <div className="rating-foot-line">
              <span>Матчи: {row.match_predictions_progress || row.match_predictions_count || 0}</span>
              <span>Fantasy: {row.fantasy_team_progress || '0/15'}</span>
              <span>Проход: +{row.advancement_plus || 0} / {row.advancement_minus || 0}</span>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}


function Profile({ tournamentPrediction, appTheme, setAppTheme }) {
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

      <section className="card profile-settings-card">
        <div className="profile-section-head">
          <h2>Настройки</h2>
          <span>{appTheme === 'light' ? 'светлая' : 'темная'}</span>
        </div>
        <label className="theme-segmented-row">
          <input
            type="checkbox"
            checked={appTheme === 'light'}
            onChange={(event) => setAppTheme(event.target.checked ? 'light' : 'dark')}
          />
          <span className="theme-option dark-option">Темная тема</span>
          <span className="theme-switch" />
          <span className="theme-option light-option">Светлая тема</span>
        </label>
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


function Resources() {
  const [fact, setFact] = useState('');
  const [archive, setArchive] = useState('');
  const [forecast, setForecast] = useState(null);
  const [scorers, setScorers] = useState(null);
  const [openFather, setOpenFather] = useState(false);
  const [openHelp, setOpenHelp] = useState(false);

  useEffect(() => {
    api('/api/webapp/tournament-forecast').then(setForecast).catch(() => {});
    api('/api/webapp/top-scorer-candidates').then(setScorers).catch(() => {});
  }, []);

  async function loadFact() {
    const result = await api('/api/webapp/facts/random');
    setFact(result.fact?.text || '');
  }

  async function loadArchive() {
    const result = await api('/api/webapp/archive/random');
    setArchive(`${result.card?.title || ''}\n${result.card?.text || ''}`);
  }

  const father = forecast?.forecast;
  const fatherPicks = father?.forecast || {};
  const links = [
    {
      title: 'Sofascore',
      icon: '📊',
      description: 'лайв-центр, составы, форма и статистика матчей',
      url: 'https://www.sofascore.com/football/tournament/world/world-championship/16#id:58210',
    },
    {
      title: 'Flashscore',
      icon: '⚡',
      description: 'быстрые результаты, календарь и таблицы',
      url: 'https://www.flashscore.com/football/world/world-championship/',
    },
    {
      title: 'FIFA',
      icon: '🏆',
      description: 'официальное расписание, стадионы и матч-центр',
      url: 'https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures',
    },
    {
      title: 'Матч ТВ',
      icon: '📺',
      description: 'русскоязычные новости, трансляции и контекст',
      url: 'https://matchtv.ru/football/worldcup/2026',
    },
    {
      title: 'Чемпионат',
      icon: '📰',
      description: 'новости сборных, травмы и турнирные сюжеты',
      url: 'https://www.championat.com/news/football/_worldcup/1.html',
    },
  ];

  return (
    <main className="screen-content resources-screen">
      <div className="section-label">Полезные ресурсы</div>

      <section className="resource-quick-grid">
        <button className="resource-quick-card father" onClick={() => setOpenFather(!openFather)}>
          <span>🤖</span>
          <strong>Прогноз Отца</strong>
          <small>итоги турнира</small>
        </button>
        <button className="resource-quick-card scorers" onClick={() => setOpenHelp(!openHelp)}>
          <span>⚽</span>
          <strong>Бомбардиры</strong>
          <small>кого выбрать</small>
        </button>
      </section>

      {openFather && (
        <section className="card resource-panel">
          {father ? (
            <>
              <div className="tournament-grid">
                <div><Icon name="cup" /> <b>{fatherPicks.champion}</b><small>Победитель</small></div>
                <div><Icon name="rank" /> <b>{fatherPicks.runner_up}</b><small>Финалист</small></div>
                <div><Icon name="rank" /> <b>{fatherPicks.third_place}</b><small>3 место</small></div>
                <div><Icon name="ball" /> <b>{fatherPicks.top_scorer}</b><small>Бомбардир</small></div>
              </div>
              <h3>Почему так</h3>
              <ul className="nice-list">
                {(father.reasoning || []).map((item) => <li key={item}>{item}</li>)}
              </ul>
              <p className="father-comment">{father.spicy_comment}</p>
            </>
          ) : <LoadingCard />}
        </section>
      )}

      {openHelp && (
        <section className="card resource-panel">
          <h2>⚽ Помощь по бомбардирам</h2>
          <p className="muted">{scorers?.hint || 'Загружаю подсказку...'}</p>
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
        </section>
      )}

      <section className="resource-actions">
        <button className="resource-action-card" onClick={loadFact}>
          <span>📚</span>
          <strong>Факт о ЧМ</strong>
          <small>короткая футбольная история</small>
        </button>
        <button className="resource-action-card" onClick={loadArchive}>
          <span>🗂</span>
          <strong>Архив Отца</strong>
          <small>случайная карточка прошлого</small>
        </button>
      </section>

      {fact && <section className="card resource-text-card"><p>{fact}</p></section>}
      {archive && <section className="card resource-text-card"><pre>{archive}</pre></section>}

      <section className="card resources-links-card">
        <h2>Матч-центры и статистика</h2>
        <div className="resource-links-list">
          {links.map((item) => (
            <button key={item.title} onClick={() => tg?.openLink ? tg.openLink(item.url) : window.open(item.url, '_blank')}>
              <span className="resource-link-icon">{item.icon}</span>
              <span className="resource-link-text">
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </span>
              <b>→</b>
            </button>
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
  const [appTheme, setAppTheme] = useState(() => localStorage.getItem('ff-app-theme') || 'light');
  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState(null);
  const [predictionMatch, setPredictionMatch] = useState(null);
  const [forecastMatch, setForecastMatch] = useState(null);
  const [participantsMatch, setParticipantsMatch] = useState(null);
  const [tournamentPickField, setTournamentPickField] = useState(null);
  const [tournamentPrediction, setTournamentPrediction] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [rulesOpen, setRulesOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem('ff-app-theme', appTheme);
  }, [appTheme]);

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
    <div className={`app theme-${appTheme}`}>
      <Header dashboard={dashboard} onRules={() => setRulesOpen(true)} />

      {tab === 'matches' && (
        <>
          <HomeHero dashboard={dashboard} tournamentPrediction={tournamentPrediction} onTournamentPick={setTournamentPickField} setTab={setTab} />
          <MatchCenter key={`matches-${refreshKey}`} onPredict={setPredictionMatch} onForecast={setForecastMatch} onParticipants={setParticipantsMatch} />
        </>
      )}
      {tab === 'fantasy' && <Fantasy />}
      {tab === 'predictions' && <Predictions key={`predictions-${refreshKey}`} onPredict={setPredictionMatch} onForecast={setForecastMatch} onParticipants={setParticipantsMatch} />}
      {tab === 'resources' && <Resources />}
      {tab === 'rating' && <Rating />}
      {tab === 'profile' && <Profile tournamentPrediction={tournamentPrediction} appTheme={appTheme} setAppTheme={setAppTheme} />}

      <nav className="bottom-nav">
        {TABS.map((item) => (
          <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}>
            <Icon name={item.icon} />
            <small>{item.label}</small>
          </button>
        ))}
      </nav>

      {predictionMatch && <ScorePicker match={predictionMatch} onClose={() => setPredictionMatch(null)} onSaved={handleSaved} />}
      {participantsMatch && <MatchParticipantsModal match={participantsMatch} onClose={() => setParticipantsMatch(null)} />}
      {forecastMatch && <ForecastModal match={forecastMatch} onClose={() => setForecastMatch(null)} />}
      {tournamentPickField && <TournamentPredictionModal currentPrediction={tournamentPrediction} initialField={tournamentPickField} onClose={() => setTournamentPickField(null)} onSaved={handleTournamentSaved} />}
      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
