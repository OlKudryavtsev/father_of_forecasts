
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
}

const TABS = [
  { id: 'matches', label: 'Матчи', icon: '🏀' },
  { id: 'predictions', label: 'Прогнозы', icon: '🎯' },
  { id: 'tournament', label: 'Турнир', icon: '🏆' },
  { id: 'rating', label: 'Рейтинг', icon: '🏅' },
  { id: 'more', label: 'Еще', icon: '☰' },
];

const QUICK_SCORES = [
  [1, 0],
  [1, 1],
  [2, 1],
  [2, 0],
  [0, 0],
  [0, 1],
];

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
  return (
    <header className="league-header">
      <div className="telegram-title">ЛИГА ПРОГНОЗОВ — ЧМ 2026</div>

      <div className="league-main">
        <div className="league-logo">🏆</div>
        <div className="league-text">
          <h1>Лига Прогнозов</h1>
          <div className="muted">ЧМ-2026 · США · Мексика · Канада</div>
        </div>
        <button className="rules-button" onClick={onRules}>Правила</button>
      </div>

      <div className="league-status">
        <span className="status-section">{formatCountdown(dashboard?.tournament?.days_until_start)}</span>
        <span className="divider" />
        <span className="points">{dashboard?.points ?? 0} очков</span>
        <span className="muted">#{dashboard?.rank || '—'}</span>
      </div>
    </header>
  );
}

function HomeHero({ dashboard, setTab }) {
  const missing = dashboard?.missing_predictions_count ?? 0;
  const tournamentDone = dashboard?.tournament?.has_prediction;
  return (
    <section className="home-hero">
      <button className="hero-action hero-primary" onClick={() => setTab('predictions')}>
        <span className="hero-icon">🎯</span>
        <span>
          <strong>Выберите счет для {missing} матчей</strong>
          <small>Откроем матчи, на которые еще можно ставить</small>
        </span>
        <b>{missing}</b>
      </button>

      <button className="hero-action hero-green" onClick={() => setTab('tournament')}>
        <span className="hero-icon">🏆</span>
        <span>
          <strong>Прогнозы на турнир</strong>
          <small>Победитель · призеры · бомбардир</small>
        </span>
        <b>{tournamentDone ? '4/4' : '0/4'}</b>
      </button>
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
        <span>{data.total || 0} прогнозов</span>
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

function MatchCard({ match, onPredict, showDistribution = true }) {
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
          {!match.prediction && !locked && <button onClick={() => onPredict(match)}>Сделать прогноз</button>}
          {locked && !match.is_finished && <small>закрыт</small>}
        </div>
        <div className="team-side">
          <span className="flag">{match.away_flag || '🏳️'}</span>
          <strong>{match.away_team}</strong>
        </div>
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
    <section className="group-table-card">
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
            <span>{row.rank}</span>
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

function MatchCenter({ onPredict }) {
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
  const selectedStanding = data?.standings?.[0];

  if (error) return <ErrorCard error={error} onRetry={load} />;

  return (
    <main className="screen-content">
      <div className="section-label">Матч-центр</div>

      <div className="filter-strip">
        <button className={!group && scope === 'all' ? 'active' : ''} onClick={() => { setGroup(null); setScope('all'); }}>⭐ Все</button>
        <button className={scope === 'results' ? 'active result' : ''} onClick={() => { setGroup(null); setScope('results'); }}>✓ Результаты</button>
        {(data?.groups || []).map((item) => (
          <button key={item.group_code} className={group === item.group_code ? 'active group' : ''} onClick={() => { setGroup(item.group_code); setScope('all'); }}>
            {item.group_code} группа
          </button>
        ))}
      </div>

      {loading ? <LoadingCard /> : (
        <>
          {selectedStanding && <GroupTable group={selectedStanding} />}
          {grouped.length === 0 && <EmptyState icon="🏀" title="Нет матчей" text={scope === 'results' ? 'Пока нет завершенных матчей' : 'Матчи не найдены'} />}
          {grouped.map(([day, matches]) => (
            <section key={day} className="match-day">
              <div className="day-heading">
                <span>{formatDayTitle(matches[0]?.starts_at)}</span>
                <b>{matches.length} матч{matches.length === 1 ? '' : 'а'}</b>
              </div>
              {matches.map((match) => <MatchCard key={match.id} match={match} onPredict={onPredict} />)}
            </section>
          ))}
        </>
      )}
    </main>
  );
}

function EmptyState({ icon, title, text }) {
  return (
    <div className="empty-state">
      <div>{icon}</div>
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
      <section className="modal-card">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>{match.home_team} — {match.away_team}</h2>
        <p className="muted">{formatDateTime(match.starts_at)}</p>

        <div className="score-editor-2">
          <div>
            <span>{match.home_flag}</span>
            <strong>{match.home_team}</strong>
            <div className="counter">
              <button onClick={() => dec(setHome, home)}>−</button>
              <b>{home}</b>
              <button onClick={() => inc(setHome, home)}>+</button>
            </div>
          </div>
          <div>
            <span>{match.away_flag}</span>
            <strong>{match.away_team}</strong>
            <div className="counter">
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

function Predictions({ onPredict }) {
  const [data, setData] = useState(null);
  const [scope, setScope] = useState('missing');
  const [error, setError] = useState(null);

  async function load(nextScope = scope) {
    setError(null);
    try {
      const result = await api(`/api/webapp/matches?scope=${nextScope}`);
      setData(result);
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(scope); }, [scope]);

  if (error) return <ErrorCard error={error} onRetry={() => load(scope)} />;

  const matches = data?.matches || [];
  return (
    <main className="screen-content">
      <div className="section-label">Мои прогнозы</div>
      <div className="stat-grid">
        <div className="stat-card"><b>{scope === 'missing' ? matches.length : '—'}</b><span>Нужен прогноз</span></div>
        <div className="stat-card"><b>{scope === 'all' ? matches.length : '—'}</b><span>Можно изменить</span></div>
      </div>

      <div className="segmented">
        <button className={scope === 'missing' ? 'active' : ''} onClick={() => setScope('missing')}>Нужен прогноз</button>
        <button className={scope === 'all' ? 'active' : ''} onClick={() => setScope('all')}>Все будущие</button>
      </div>

      {!data ? <LoadingCard /> : matches.length === 0 ? <EmptyState icon="🎯" title="Все готово" text="Нет матчей в выбранном фильтре" /> : (
        groupMatchesByDay(matches).map(([day, dayMatches]) => (
          <section key={day} className="match-day">
            <div className="day-heading"><span>{formatDayTitle(dayMatches[0]?.starts_at)}</span><b>{dayMatches.length}</b></div>
            {dayMatches.map((match) => <MatchCard key={match.id} match={match} onPredict={onPredict} showDistribution={false} />)}
          </section>
        ))
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

function Tournament() {
  const [prediction, setPrediction] = useState(null);
  const [forecast, setForecast] = useState(null);
  useEffect(() => {
    api('/api/webapp/tournament-prediction/me').then(setPrediction).catch(() => {});
    api('/api/webapp/tournament-forecast').then(setForecast).catch(() => {});
  }, []);
  const p = prediction?.prediction;
  return (
    <main className="screen-content">
      <div className="section-label">Турнир</div>
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
          <p className="muted">Турнирный прогноз пока не заполнен.</p>
        )}
      </section>
      <section className="card">
        <h2>🤖 Прогноз Отца прогнозов</h2>
        {forecast ? (
          <div className="tournament-grid">
            <div>🏆 <b>{forecast.forecast.forecast.champion}</b><small>Победитель</small></div>
            <div>🥈 <b>{forecast.forecast.forecast.runner_up}</b><small>Финалист</small></div>
            <div>🥉 <b>{forecast.forecast.forecast.third_place}</b><small>3 место</small></div>
            <div>⚽ <b>{forecast.forecast.forecast.top_scorer}</b><small>Бомбардир</small></div>
          </div>
        ) : <p className="muted">Загружаю...</p>}
      </section>
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
      <section className="modal-card">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>Правила</h2>
        <ul className="rules-list">
          <li>Прогноз на матч принимается до стартового свистка.</li>
          <li>Точный счет — максимум очков.</li>
          <li>Исход без точного счета — частичные очки.</li>
          <li>Турнирный прогноз можно менять до старта ЧМ.</li>
        </ul>
      </section>
    </div>
  );
}

function App() {
  const [tab, setTab] = useState('matches');
  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState(null);
  const [predictionMatch, setPredictionMatch] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [rulesOpen, setRulesOpen] = useState(false);

  async function loadDashboard() {
    try {
      setDashboard(await api('/api/webapp/dashboard'));
    } catch (err) {
      setDashboardError(err);
    }
  }

  useEffect(() => { loadDashboard(); }, [refreshKey]);

  function handleSaved() {
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
          <HomeHero dashboard={dashboard} setTab={setTab} />
          <MatchCenter key={`matches-${refreshKey}`} onPredict={setPredictionMatch} />
        </>
      )}
      {tab === 'predictions' && <Predictions key={`predictions-${refreshKey}`} onPredict={setPredictionMatch} />}
      {tab === 'tournament' && <Tournament />}
      {tab === 'rating' && <Rating />}
      {tab === 'more' && <More />}

      <nav className="bottom-nav">
        {TABS.map((item) => (
          <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}>
            <span>{item.icon}</span>
            <small>{item.label}</small>
          </button>
        ))}
      </nav>

      {predictionMatch && <ScorePicker match={predictionMatch} onClose={() => setPredictionMatch(null)} onSaved={handleSaved} />}
      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
