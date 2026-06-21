
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createPortal } from 'react-dom';
import './styles.css';

const tg = window.Telegram?.WebApp;
const APP_VERSION = '2.8.49';
const FANTASY_UI_ENABLED = false;


if (tg) {
  tg.ready();
  tg.expand();
}

const TABS = [
  { id: 'matches', label: 'Матч-центр', icon: 'ball' },
  { id: 'predictions', label: 'Прогнозы', icon: 'target' },
  { id: 'rating', label: 'Рейтинг', icon: 'rank' },
  { id: 'leagues', label: 'Лиги', icon: 'team' },
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

const VIDEO_TYPES = [
  { id: 'live', label: 'Трансляция', short: 'Live' },
  { id: 'highlights', label: 'Голы и лучшие моменты', short: 'Хайлайты' },
  { id: 'review', label: 'Обзор матча', short: 'Обзор' },
  { id: 'full_replay', label: 'Полная запись', short: 'Запись' },
  { id: 'goal', label: 'Гол', short: 'Гол' },
  { id: 'moment', label: 'Момент', short: 'Момент' },
  { id: 'other', label: 'Другое видео', short: 'Видео' },
];

function videoTypeLabel(type, short = false) {
  const item = VIDEO_TYPES.find((entry) => entry.id === type);
  return item ? (short ? item.short : item.label) : 'Видео';
}

function openExternalUrl(url) {
  if (!url) return;
  if (tg?.openLink) {
    tg.openLink(url, { try_instant_view: false });
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}



function BottomNavigation({ tab, onChange }) {
  const navigation = (
    <nav className="bottom-nav" aria-label="Основное меню">
      {TABS.map((item) => (
        <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => onChange(item.id)}>
          <Icon name={item.icon} />
          <small>{item.label}</small>
        </button>
      ))}
    </nav>
  );

  // Telegram Desktop/WebView can place fixed children of a scrolling app shell
  // into that shell's coordinate system. Rendering in document.body keeps the
  // menu attached to the viewport on desktop, iOS and Android alike.
  return typeof document === 'undefined' ? navigation : createPortal(navigation, document.body);
}


function TeamFlag({ code, emoji, name = '', size = 'normal' }) {
  const normalizedCode = String(code || '').trim().toLowerCase();
  const hasCode = /^[a-z0-9-]{2,10}$/.test(normalizedCode);
  const className = `flag flag-img ${size === 'mini' ? 'mini' : ''}`.trim();

  if (hasCode) {
    return (
      <span className={className} title={name} aria-label={name ? `Флаг: ${name}` : 'Флаг'}>
        <img
          src={`https://flagcdn.com/${normalizedCode}.svg`}
          alt=""
          loading="lazy"
          onError={(event) => {
            const img = event.currentTarget;
            img.style.display = 'none';
            const parent = img.parentElement;
            if (parent) parent.classList.add('flag-fallback-visible');
          }}
        />
        <span className="flag-fallback">{emoji || normalizedCode.toUpperCase()}</span>
      </span>
    );
  }

  return <span className={`flag ${size === 'mini' ? 'mini' : ''}`.trim()} title={name}>{emoji || '🏳️'}</span>;
}

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

  if (name === 'share') {
    return (
      <svg {...common}>
        <circle cx="18" cy="5" r="2.5" />
        <circle cx="6" cy="12" r="2.5" />
        <circle cx="18" cy="19" r="2.5" />
        <path d="m8.2 10.8 7.5-4.4M8.2 13.2l7.5 4.4" />
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

  if (name === 'edit') {
    return (
      <svg {...common}>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4L16.5 3.5Z" />
      </svg>
    );
  }

  if (name === 'video') {
    return (
      <svg {...common}>
        <rect x="3" y="6" width="13" height="12" rx="3" />
        <path d="m16 10 5-3v10l-5-3v-4Z" />
      </svg>
    );
  }

  return null;
}

const WEB_SESSION_KEY = 'ff-web-session-token';

function initData() {
  return tg?.initData || '';
}

function isTelegramMode() {
  return Boolean(initData());
}

function getCookieValue(name) {
  return document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
    ?.split('=')
    .slice(1)
    .join('=') || '';
}

function getWebSessionToken() {
  return localStorage.getItem(WEB_SESSION_KEY) || decodeURIComponent(getCookieValue('ff_web_session') || '');
}

function installWebTokenFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('web_token');

  if (!token) return false;

  localStorage.setItem(WEB_SESSION_KEY, token);
  params.delete('web_token');

  const nextSearch = params.toString();
  const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ''}${window.location.hash || ''}`;
  window.history.replaceState({}, document.title, nextUrl);

  return true;
}

installWebTokenFromUrl();

async function api(path, options = {}) {
  const webToken = getWebSessionToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (initData()) {
    headers['X-Telegram-Init-Data'] = initData();
  }

  if (!initData() && webToken) {
    headers['X-Web-Session-Token'] = webToken;
  }

  const response = await fetch(path, {
    cache: options.cache || 'no-store',
    ...options,
    headers,
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || 'Ошибка запроса');
  }

  return payload;
}

const ANALYTICS_SESSION_KEY = 'ff-analytics-session';
const ANALYTICS_SESSION_TTL_MS = 30 * 60 * 1000;

function getAnalyticsSource() {
  if (isTelegramMode()) return 'telegram';
  const isStandalone = window.matchMedia?.('(display-mode: standalone)')?.matches || window.navigator?.standalone;
  return isStandalone ? 'pwa' : 'browser';
}

function getAnalyticsSessionId() {
  const now = Date.now();
  try {
    const stored = JSON.parse(localStorage.getItem(ANALYTICS_SESSION_KEY) || '{}');
    if (stored?.id && stored?.lastSeen && now - stored.lastSeen < ANALYTICS_SESSION_TTL_MS) {
      localStorage.setItem(ANALYTICS_SESSION_KEY, JSON.stringify({ id: stored.id, lastSeen: now }));
      return stored.id;
    }
  } catch {
    // A broken local value should not prevent the Mini App from working.
  }

  const id = window.crypto?.randomUUID?.() || `s-${now}-${Math.random().toString(16).slice(2)}`;
  try {
    localStorage.setItem(ANALYTICS_SESSION_KEY, JSON.stringify({ id, lastSeen: now }));
  } catch {
    // Private browser modes may disallow local storage; keep an in-memory event id instead.
  }
  return id;
}

function trackAnalytics(eventName, { screen = null, properties = {} } = {}) {
  if (!isTelegramMode() && !getWebSessionToken()) return Promise.resolve();

  return api('/api/webapp/analytics/events', {
    method: 'POST',
    body: JSON.stringify({
      event_name: eventName,
      screen,
      session_id: getAnalyticsSessionId(),
      source: getAnalyticsSource(),
      app_version: APP_VERSION,
      properties,
    }),
  }).catch(() => null);
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

function formatMatchCountdown(value, now = Date.now()) {
  if (!value) return '';
  const diff = new Date(value).getTime() - now;
  if (!Number.isFinite(diff) || diff <= 0) return 'матч начинается';

  const totalMinutes = Math.max(1, Math.floor(diff / 60000));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return `через ${days} ${pluralRu(days, 'день', 'дня', 'дней')}${hours ? ` ${hours} ч` : ''}`;
  if (hours > 0) return `через ${hours} ч ${minutes ? `${minutes} мин` : ''}`.trim();
  return `через ${minutes} мин`;
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

function pointsLabel(value) {
  const points = Number(value) || 0;
  return `${points} ${pluralRu(points, 'очко', 'очка', 'очков')}`;
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
  { slot: 'ЗАП1', position: null, label: 'Запас 1', isStarter: false },
  { slot: 'ЗАП2', position: null, label: 'Запас 2', isStarter: false },
  { slot: 'ЗАП3', position: null, label: 'Запас 3', isStarter: false },
  { slot: 'ЗАП4', position: null, label: 'Запас 4', isStarter: false },
];

const FANTASY_SQUAD_POSITION_LIMITS = {
  Goalkeeper: 2,
  Defender: 5,
  Midfielder: 5,
  Attacker: 3,
};

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


function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }

  return outputArray;
}

function assertPushSupported() {
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
    throw new Error('Этот браузер не поддерживает Web Push. На iPhone открой приложение через ярлык на экране «Домой».');
  }
}

async function getServiceWorkerRegistration() {
  assertPushSupported();
  return navigator.serviceWorker.register('/miniapp-static/sw.js', {
    updateViaCache: 'none',
  });
}

async function getCurrentPushSubscription() {
  const registration = await getServiceWorkerRegistration();
  return registration.pushManager.getSubscription();
}

async function ensurePushSubscription() {
  assertPushSupported();

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error('Уведомления не разрешены. Проверь разрешение в настройках iPhone для этого web-приложения.');
  }

  const keyResult = await api('/api/webapp/push/public-key');

  if (!keyResult.enabled || !keyResult.public_key) {
    throw new Error('Web Push не настроен на сервере: нужны VAPID_PUBLIC_KEY и VAPID_PRIVATE_KEY.');
  }

  const registration = await getServiceWorkerRegistration();
  let subscription = await registration.pushManager.getSubscription();

  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(keyResult.public_key),
    });
  }

  await api('/api/webapp/push/subscribe', {
    method: 'POST',
    body: JSON.stringify(subscription.toJSON()),
  });

  return subscription;
}

async function disablePushSubscription() {
  const subscription = await getCurrentPushSubscription();

  if (!subscription) {
    return false;
  }

  await api('/api/webapp/push/unsubscribe', {
    method: 'POST',
    body: JSON.stringify(subscription.toJSON()),
  });

  await subscription.unsubscribe();
  return true;
}


function parseVersion(value) {
  const parts = String(value || '')
    .trim()
    .replace(/^v/i, '')
    .split('.')
    .map((part) => Number.parseInt(part, 10));

  if (!parts.length || parts.some((part) => Number.isNaN(part) || part < 0)) return null;
  return parts;
}

function isNewerVersion(serverVersion, clientVersion) {
  const server = parseVersion(serverVersion);
  const client = parseVersion(clientVersion);
  if (!server || !client) return false;

  const length = Math.max(server.length, client.length);
  for (let index = 0; index < length; index += 1) {
    const left = server[index] || 0;
    const right = client[index] || 0;
    if (left !== right) return left > right;
  }

  return false;
}

function usePwaUpdateCheck() {
  const [updateInfo, setUpdateInfo] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function checkVersion() {
      try {
        const result = await api(`/api/webapp/app-version?client_version=${encodeURIComponent(APP_VERSION)}&t=${Date.now()}`, { cache: 'no-store' });
        if (cancelled) return;

        if (result.version && result.version !== 'unknown' && isNewerVersion(result.version, APP_VERSION)) {
          setUpdateInfo(result);
        } else {
          // A stale backend value (for example, after a partial deploy) must never
          // leave users with a permanent update banner.
          setUpdateInfo(null);
        }
      } catch {
        // Version check must never break the app.
      }
    }

    checkVersion();
    const timer = window.setInterval(checkVersion, 5 * 60 * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return updateInfo;
}

async function forcePwaUpdate() {
  const stamp = String(Date.now());

  try {
    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.register('/miniapp-static/sw.js', {
        updateViaCache: 'none',
      });

      await registration.update();
      registration.waiting?.postMessage({ type: 'SKIP_WAITING' });
      registration.installing?.postMessage({ type: 'SKIP_WAITING' });

      // Keep the registration intact: unregistering can disrupt Web Push in an
      // installed iOS PWA. The new worker activates through skipWaiting/claim.
      await navigator.serviceWorker.ready;
    }

    // Ensure the latest non-cached HTML is available before navigation.
    await fetch(`/app?app_v=${stamp}`, {
      cache: 'reload',
      credentials: 'include',
      headers: { 'Cache-Control': 'no-cache' },
    }).catch(() => null);
  } catch {
    // Best effort. The cache-busted navigation below is still enough for apps
    // without Service Worker support (for example, Telegram Desktop).
  }

  sessionStorage.setItem('ff-force-app-reload', stamp);
  window.location.assign(`/app?app_v=${stamp}&updated=1`);
}

function PwaUpdateBanner({ updateInfo }) {
  const [updating, setUpdating] = useState(false);
  if (!updateInfo) return null;

  async function handleUpdate() {
    if (updating) return;
    setUpdating(true);
    await forcePwaUpdate();
  }

  return (
    <div className={`pwa-update-banner ${updating ? 'is-updating' : ''}`}>
      <div>
        <b>{updating ? 'Обновляю приложение…' : 'Доступна новая версия'}</b>
        <span>v{updateInfo.version}</span>
      </div>
      <button type="button" disabled={updating} onClick={handleUpdate}>{updating ? 'Обновляю…' : 'Обновить'}</button>
    </div>
  );
}

function BrowserAuthGate() {
  return (
    <main className="screen-content browser-auth-screen">
      <section className="card browser-auth-card">
        <div className="empty-icon"><Icon name="cup" /></div>
        <h1>Отец прогнозов</h1>
        <p>
          Эта web-версия привязывается к Telegram-аккаунту. Сначала открой приложение из Telegram,
          затем в профиле нажми «Открыть web/PWA-версию».
        </p>
        <div className="browser-auth-steps">
          <span>1. Открой бота в Telegram</span>
          <span>2. Зайди в Mini App</span>
          <span>3. Профиль → Web/PWA → получить ссылку</span>
          <span>4. Открой ссылку в Safari и добавь на экран «Домой»</span>
        </div>
      </section>
    </main>
  );
}

function PwaAccessCard() {
  const [webUrl, setWebUrl] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushChecking, setPushChecking] = useState(false);
  const webMode = !isTelegramMode();

  async function refreshPushState() {
    if (!webMode) return;

    setPushChecking(true);
    try {
      const subscription = await getCurrentPushSubscription();
      const permissionGranted = Notification.permission === 'granted';
      setPushEnabled(Boolean(subscription && permissionGranted));

      const serverStatus = await api('/api/webapp/push/status').catch(() => null);
      if (serverStatus?.last_error) {
        setStatus(`Последняя ошибка push: ${serverStatus.last_error}`);
      }
    } catch {
      setPushEnabled(false);
    } finally {
      setPushChecking(false);
    }
  }

  useEffect(() => { refreshPushState(); }, [webMode]);

  async function createLink() {
    setBusy(true);
    setStatus('');

    try {
      const result = await api('/api/webapp/web-session/create', { method: 'POST' });
      setWebUrl(result.url);
      setStatus('Ссылка создана. Открой ее в Safari, затем добавь страницу на экран «Домой».');
    } catch (err) {
      setStatus(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyLink() {
    if (!webUrl) return;

    try {
      await navigator.clipboard.writeText(webUrl);
      setStatus('Ссылка скопирована.');
    } catch {
      setStatus('Не удалось скопировать автоматически. Открой ссылку кнопкой ниже.');
    }
  }

  async function enablePush() {
    setBusy(true);
    setStatus('');

    try {
      await ensurePushSubscription();
      setPushEnabled(true);
      setStatus('Уведомления включены для этой web/PWA-версии.');
    } catch (err) {
      setStatus(err.message);
      await refreshPushState();
    } finally {
      setBusy(false);
    }
  }

  async function disablePush() {
    setBusy(true);
    setStatus('');

    try {
      const unsubscribed = await disablePushSubscription();
      setPushEnabled(false);
      setStatus(unsubscribed ? 'Уведомления выключены для этой web/PWA-версии.' : 'Активной push-подписки на этом устройстве не найдено.');
    } catch (err) {
      setStatus(err.message);
      await refreshPushState();
    } finally {
      setBusy(false);
    }
  }

  async function togglePush() {
    if (pushEnabled) {
      await disablePush();
    } else {
      await enablePush();
    }
  }

  async function logoutWeb() {
    setBusy(true);

    try {
      await api('/api/webapp/web-session/logout', { method: 'POST' });
    } catch {
      // logout is best-effort
    }

    localStorage.removeItem(WEB_SESSION_KEY);
    window.location.reload();
  }

  const pushButtonText = busy
    ? (pushEnabled ? 'Выключаю...' : 'Подключаю...')
    : (pushEnabled ? 'Выключить уведомления' : 'Включить уведомления');

  return (
    <div className="pwa-access-card">
      <div>
        <strong>{webMode ? 'Web/PWA-версия активна' : 'Web/PWA на iPhone'}</strong>
        <span>
          {webMode
            ? `Push-уведомления: ${pushChecking ? 'проверяю...' : (pushEnabled ? 'включены' : 'выключены')}`
            : 'Создай личную ссылку, открой ее в Safari и сохрани как ярлык.'}
        </span>
      </div>

      {!webMode && (
        <button type="button" disabled={busy} onClick={createLink}>
          {busy ? 'Создаю...' : 'Создать ссылку'}
        </button>
      )}

      {webUrl && (
        <>
          <a className="pwa-open-link" href={webUrl} target="_blank" rel="noreferrer">Открыть web-версию</a>
          <button type="button" onClick={copyLink}>Скопировать ссылку</button>
        </>
      )}

      {webMode && (
        <>
          <button type="button" disabled={busy || pushChecking} onClick={togglePush}>
            {pushButtonText}
          </button>
          <button type="button" className="danger" disabled={busy} onClick={logoutWeb}>Выйти из web-версии</button>
        </>
      )}

      {status && <small>{status}</small>}
    </div>
  );
}

function HeaderLeagueSelector({ leagues = [], activeLeagueId, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const selectorRef = useRef(null);
  const menuRef = useRef(null);
  const selectedLeague = leagues.find((league) => Number(league.id) === Number(activeLeagueId)) || leagues[0];

  const updateMenuPosition = () => {
    const rect = selectorRef.current?.getBoundingClientRect();
    if (!rect) return;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const menuWidth = Math.min(320, Math.max(230, rect.width + 52));
    setMenuPosition({
      top: Math.max(12, rect.bottom + 8),
      left: Math.max(12, Math.min(rect.left, viewportWidth - menuWidth - 12)),
    });
  };

  useEffect(() => {
    if (!isOpen) return undefined;

    updateMenuPosition();
    const closeOnOutsideClick = (event) => {
      const insideTrigger = selectorRef.current?.contains(event.target);
      const insideMenu = menuRef.current?.contains(event.target);
      if (!insideTrigger && !insideMenu) setIsOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setIsOpen(false);
    };

    window.addEventListener('resize', updateMenuPosition);
    window.addEventListener('scroll', updateMenuPosition, true);
    document.addEventListener('pointerdown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      window.removeEventListener('resize', updateMenuPosition);
      window.removeEventListener('scroll', updateMenuPosition, true);
      document.removeEventListener('pointerdown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [isOpen]);

  if (!leagues.length || !selectedLeague) return null;

  const selectLeague = (leagueId) => {
    onChange?.(Number(leagueId));
    setIsOpen(false);
  };

  const menu = isOpen ? (
    <div
      className="header-league-menu floating"
      ref={menuRef}
      role="listbox"
      aria-label="Выбор лиги"
      style={{ top: `${menuPosition.top}px`, left: `${menuPosition.left}px` }}
    >
      {leagues.map((league) => {
        const selected = Number(league.id) === Number(selectedLeague.id);
        return (
          <button
            key={league.id}
            type="button"
            className={selected ? 'selected' : ''}
            role="option"
            aria-selected={selected}
            onClick={() => selectLeague(league.id)}
          >
            <span>{league.name}</span>
            {selected && <b aria-hidden="true">✓</b>}
          </button>
        );
      })}
    </div>
  ) : null;

  return (
    <div className={`header-league-selector${isOpen ? ' open' : ''}`} ref={selectorRef}>
      <Icon name="team" />
      <button
        type="button"
        className="header-league-trigger"
        onClick={() => setIsOpen((value) => !value)}
        aria-label={`Выбранная лига: ${selectedLeague.name}`}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="header-league-name">{selectedLeague.name}</span>
        <i className="header-league-chevron" aria-hidden="true">⌄</i>
      </button>
      {typeof document === 'undefined' ? menu : createPortal(menu, document.body)}
    </div>
  );
}

function Header({ dashboard, onRules, onAdmin, leagues = [], activeLeagueId, onLeagueChange }) {
  const stageText = dashboard?.tournament?.current_stage_label || (dashboard?.tournament?.is_started ? 'Турнир идет' : 'До старта');

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

      <div className="league-status-row">
        {dashboard?.user?.is_admin && <button className="header-admin-button" onClick={onAdmin}><Icon name="shield" /> Админ</button>}
        <div className="league-status">
          <HeaderLeagueSelector leagues={leagues} activeLeagueId={activeLeagueId} onChange={onLeagueChange} />
          {leagues.length > 0 && <span className="divider header-league-divider" />}
          <span className="status-section live-countdown">{stageText}</span>
          <span className="divider" />
          <span className="points">{pointsLabel(dashboard?.points ?? 0)}</span>
          <span className="muted">#{dashboard?.rank || '—'}</span>
        </div>
      </div>
    </header>
  );
}

function TournamentScorerAvatar({ prediction, className = '' }) {
  if (!prediction?.top_scorer) return null;
  const scorerInitials = String(prediction.top_scorer || '⚽')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();

  return (
    <div className={`tournament-scorer-avatar ${className}`.trim()} title={prediction.top_scorer || 'Бомбардир'}>
      {prediction.top_scorer_photo ? <img src={prediction.top_scorer_photo} alt="" /> : <span>{scorerInitials || '⚽'}</span>}
    </div>
  );
}

function TournamentCardPreview({ item, prediction }) {
  if (!item?.value || !prediction) return null;
  if (item.key === 'top_scorer') {
    return <TournamentScorerAvatar prediction={prediction} className="card-preview-avatar" />;
  }

  const team = {
    champion: { code: prediction.champion_flag_code, emoji: prediction.champion_flag, name: prediction.champion },
    runner_up: { code: prediction.runner_up_flag_code, emoji: prediction.runner_up_flag, name: prediction.runner_up },
    third_place: { code: prediction.third_place_flag_code, emoji: prediction.third_place_flag, name: prediction.third_place },
  }[item.key];

  if (!team?.name) return null;
  return (
    <div className="tournament-card-flag" title={team.name}>
      <TeamFlag code={team.code} emoji={team.emoji} name={team.name} />
    </div>
  );
}

function tournamentPredictionItemStatus(item, prediction) {
  if (!prediction) return null;
  return item.key === 'top_scorer'
    ? prediction.top_scorer_status
    : prediction[`${item.key}_status`];
}

function tournamentPredictionItemTarget(item, prediction) {
  if (!prediction || !item?.value) return null;
  if (item.key === 'top_scorer') {
    return prediction.top_scorer_player_id ? { type: 'player', id: prediction.top_scorer_player_id } : null;
  }
  const id = prediction[`${item.key}_team_id`];
  return id ? { type: 'team', id } : null;
}

function NextMatchHero({ match, onPredict, onShowPredictions }) {
  const [nowTick, setNowTick] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNowTick(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  if (!match) return null;

  const hasPrediction = Boolean(match.prediction);
  const statusText = hasPrediction
    ? `Твой прогноз: ${formatPredictionScore(match.prediction)}`
    : 'Прогноз пока не сделан';
  const statusClass = hasPrediction ? 'ready' : 'missing';
  const ctaText = hasPrediction ? 'Изменить прогноз' : 'Сделать прогноз';

  return (
    <section className={`next-match-hero ${hasPrediction ? 'has-prediction' : 'needs-prediction'}`}>
      <div className="next-match-hero-top">
        <span className="next-match-kicker"><Icon name="ball" /> Следующий матч</span>
        <span className="next-match-countdown">{formatMatchCountdown(match.starts_at, nowTick)}</span>
      </div>

      <div className="next-match-teams" aria-label={`${match.home_team} против ${match.away_team}`}>
        <div className="next-match-team home">
          <TeamFlag code={match.home_flag_code} emoji={match.home_flag} name={match.home_team} />
          <strong>{match.home_team}</strong>
        </div>
        <div className="next-match-versus">
          <b>—</b>
          <small>{formatDateTime(match.starts_at)}</small>
        </div>
        <div className="next-match-team away">
          <TeamFlag code={match.away_flag_code} emoji={match.away_flag} name={match.away_team} />
          <strong>{match.away_team}</strong>
        </div>
      </div>

      <div className={`next-match-status ${statusClass}`}>
        <span>{hasPrediction ? '✓' : '!'}</span>
        <strong>{statusText}</strong>
        {hasPrediction && <small>До стартового свистка можно изменить</small>}
      </div>

      <button type="button" className="next-match-cta" onClick={() => onPredict?.(match)}>
        <Icon name={hasPrediction ? 'edit' : 'target'} />
        {ctaText}
      </button>

      {hasPrediction && (
        <button type="button" className="next-match-secondary" onClick={() => onShowPredictions?.()}>
          Посмотреть матч-центр
        </button>
      )}
    </section>
  );
}

function TournamentPredictionSummary({
  tournamentPrediction,
  onTournamentPick,
  onTournamentParticipants,
  onOpenTournamentTeam,
  onOpenTournamentPlayer,
}) {
  // The tournament has started, so this summary should not compete with daily
  // fixtures. It stays collapsed until the user explicitly opens it.
  const [tournamentOpen, setTournamentOpen] = useState(false);
  const p = tournamentPrediction?.prediction;
  const canEditTournamentPrediction = Boolean(tournamentPrediction && (tournamentPrediction.can_submit || !tournamentPrediction.is_closed));
  const tournamentClosed = !canEditTournamentPrediction;
  const items = [
    { key: 'champion', label: 'Победитель', value: p?.champion, points: '+15', icon: 'cup' },
    { key: 'runner_up', label: '2-е место', value: p?.runner_up, points: '+10', icon: 'rank' },
    { key: 'third_place', label: '3-е место', value: p?.third_place, points: '+5', icon: 'rank' },
    { key: 'top_scorer', label: 'Бомбардир', value: p?.top_scorer, points: '+15', icon: 'ball' },
  ];
  const completedTournamentPicks = items.filter((item) => Boolean(item.value)).length;
  const tournamentPredictionMissing = completedTournamentPicks < items.length;
  const tournamentSummaryText = tournamentPredictionMissing
    ? `${completedTournamentPicks}/${items.length}`
    : (tournamentClosed ? 'закрыто' : `${completedTournamentPicks}/${items.length}`);

  function openTournamentTarget(target) {
    if (!target) return;
    if (target.type === 'team') onOpenTournamentTeam?.(target.id);
    if (target.type === 'player') onOpenTournamentPlayer?.(target.id);
  }

  return (
    <section className={`tournament-mini ${tournamentOpen ? 'open' : 'closed'} ${tournamentPredictionMissing ? 'needs-attention' : ''}`}>
      <div className="tournament-mini-head">
        <div className="tournament-mini-title">
          <span>Прогнозы на турнир</span>
          {tournamentPredictionMissing && <small className="tournament-mini-alert">не заполнено</small>}
        </div>
        <div className="tournament-mini-head-right">
          <div className="tournament-mini-actions">
            <button type="button" onClick={onTournamentParticipants}>Участники</button>
            <span className={tournamentPredictionMissing ? 'missing' : ''}>{tournamentSummaryText}</span>
          </div>
        </div>
        <button type="button" className="tournament-mini-toggle" onClick={() => setTournamentOpen((value) => !value)} aria-label={tournamentOpen ? 'Свернуть прогнозы на турнир' : 'Развернуть прогнозы на турнир'}>
          {tournamentOpen ? '−' : '+'}
        </button>
      </div>
      {tournamentOpen && (
        <div className="tournament-mini-grid">
          {items.map((item) => {
            const target = tournamentPredictionItemTarget(item, p);
            const status = tournamentPredictionItemStatus(item, p);
            const hasSelectedValue = Boolean(item.value);
            const canEdit = !tournamentClosed;
            const canOpen = Boolean(target);
            const disabled = !canOpen && (!canEdit || hasSelectedValue);
            const helper = hasSelectedValue
              ? (status?.label || 'Статус уточняется')
              : (tournamentClosed ? 'Нет прогноза' : item.points);
            return (
              <article key={item.key} className={`tournament-mini-card ${canOpen ? 'inspectable' : ''} ${status?.tone ? `status-${status.tone}` : ''}`}>
                <button
                  type="button"
                  className="tournament-mini-card-main"
                  disabled={disabled}
                  onClick={() => {
                    if (canOpen) openTournamentTarget(target);
                    else if (canEdit) onTournamentPick?.(item.key);
                  }}
                  aria-label={canOpen ? `Открыть информацию: ${item.value}` : `${item.label}: ${item.value || 'выбрать'}`}
                >
                  <TournamentCardPreview item={item} prediction={p} />
                  <i><Icon name={item.icon} /></i>
                  <span>{item.label}</span>
                  <strong>{item.value || (tournamentClosed ? 'Нет прогноза' : 'Выбрать')}</strong>
                  <small className={`tournament-prediction-status ${status?.tone || ''}`}>{helper}</small>
                </button>
                {hasSelectedValue && canEdit && <button type="button" className="tournament-mini-card-edit" onClick={() => onTournamentPick?.(item.key)}>Изменить</button>}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function LiveMatchHero({ match, onOpenDetails }) {
  if (!match) return null;
  const elapsed = match.elapsed ? `${match.elapsed}'` : (match.status_short === 'HT' ? 'Перерыв' : 'В игре');
  const score = `${match.score_home ?? '—'}:${match.score_away ?? '—'}`;
  const goals = match.goal_events || [];
  return (
    <section className="live-match-hero">
      <div className="live-match-hero-top">
        <span className="live-match-kicker"><i /> Сейчас идет</span>
        <span className="live-match-minute">{elapsed}</span>
      </div>
      <div className="live-match-teams">
        <div className="live-match-team">
          <TeamFlag code={match.home_flag_code} emoji={match.home_flag} name={match.home_team} />
          <strong>{match.home_team}</strong>
        </div>
        <div className="live-match-score"><b>{score}</b><small>{match.status_long || 'Матч идет'}</small></div>
        <div className="live-match-team">
          <TeamFlag code={match.away_flag_code} emoji={match.away_flag} name={match.away_team} />
          <strong>{match.away_team}</strong>
        </div>
      </div>
      {goals.length > 0 ? (
        <div className="live-match-goals">
          {goals.map((goal, index) => <span className={goal.side === 'away' ? 'away' : 'home'} key={`${goal.minute}-${goal.player}-${index}`}>
            <b>{goal.minute}</b> {goal.player}{goal.assist ? ` (${goal.assist})` : ''}
          </span>)}
        </div>
      ) : <p className="live-match-no-goals">Голов пока нет</p>}
      <button type="button" className="live-match-details" onClick={() => onOpenDetails?.(match)}><Icon name="more" /> Детали матча</button>
    </section>
  );
}

function HomeHero({ dashboard, setTab, onNextMatchPredict, onOpenLiveMatch }) {
  const missing = dashboard?.missing_predictions_count ?? 0;
  return (
    <section className="matchcenter-top">
      {dashboard?.nearest_matches?.[0] ? (
        <NextMatchHero
          match={dashboard.nearest_matches[0]}
          onPredict={onNextMatchPredict}
          onShowPredictions={() => setTab('predictions')}
        />
      ) : (
        <button className="compact-action" onClick={() => setTab('predictions')}>
          <span className="compact-action-icon"><Icon name="target" /></span>
          <span>
            <strong>{missing ? `Нужен прогноз для ${missing} матчей` : 'Все ближайшие прогнозы сделаны'}</strong>
            <small>{missing ? 'Перейти к матчам без вашего счета' : 'Можно посмотреть рейтинг и результаты'}</small>
          </span>
          <b>{missing || '✓'}</b>
        </button>
      )}
      <LiveMatchHero match={dashboard?.live_match} onOpenDetails={onOpenLiveMatch} />
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


function stripTextMarkup(value) {
  if (!value) return '';
  const doc = document.createElement('textarea');
  doc.innerHTML = String(value).replace(/<[^>]*>/g, ' ');
  return doc.value.replace(/\s+/g, ' ').trim();
}

function videoDisplayTitle(video) {
  const type = video?.video_type || 'other';
  if (type && type !== 'other') return videoTypeLabel(type);
  const clean = stripTextMarkup(video?.title || '');
  return clean || 'Видео Match TV';
}

function videoSourceLabel(source) {
  const value = String(source || '').toLowerCase();
  if (value.includes('match')) return 'Match TV';
  return source || 'Видео';
}

function MatchInlineSection({ title, meta, iconName, children, defaultOpen = false, className = '', onOpen }) {
  const [open, setOpen] = useState(defaultOpen);

  useEffect(() => {
    if (open && onOpen) onOpen();
  }, [open]);

  return (
    <section className={`match-inline-section ${className} ${open ? 'open' : 'closed'}`}>
      <button type="button" className="match-inline-head" onClick={() => setOpen((value) => !value)}>
        <span>{iconName && <Icon name={iconName} />} {title}</span>
        <small>{meta}</small>
        <b>{open ? '−' : '+'}</b>
      </button>
      {open && <div className="match-inline-body">{children}</div>}
    </section>
  );
}

function visibleVideosForMatch(match) {
  const videos = (match?.videos || []).filter((video) => video?.is_active !== false && video?.url);

  if (match?.is_finished) {
    return videos.filter((video) => video.video_type === 'highlights');
  }

  return videos.filter((video) => video.video_type === 'live');
}

function MatchVideoBlock({ match }) {
  const activeVideos = visibleVideosForMatch(match);
  if (!activeVideos.length) return null;

  const live = activeVideos.some((video) => video.video_type === 'live');
  const meta = live ? 'live' : `${activeVideos.length} ${pluralRu(activeVideos.length, 'ссылка', 'ссылки', 'ссылок')}`;

  return (
    <MatchInlineSection title="Видео" meta={meta} iconName="video" className={`match-video-block ${live ? 'has-live' : ''}`}>
      <div className="match-video-list">
        {activeVideos.map((video) => (
          <button key={video.id || video.url} type="button" onClick={() => {
            trackAnalytics('video_open', { screen: 'matches', properties: { match_id: match.id, video_id: video.id || 0 } });
            openExternalUrl(video.url);
          }}>
            <span>{video.video_type === 'live' ? '🔴' : '▶️'}</span>
            <strong>{videoDisplayTitle(video)}</strong>
            <small>{videoSourceLabel(video.source)}</small>
          </button>
        ))}
      </div>
    </MatchInlineSection>
  );
}

function MatchParticipantsInline({ match, leagueId = null }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    setError(null);
    try {
      const params = new URLSearchParams();
      if (leagueId) params.set('league_id', String(leagueId));
      const suffix = params.toString() ? `?${params.toString()}` : '';
      const result = await api(`/api/webapp/matches/${match.id}/predictions${suffix}`);
      setData(result);
      setLoaded(true);
    } catch (err) {
      setError(err);
    }
  }

  const count = data?.participants_count ?? match.prediction_distribution?.total ?? 0;
  const participants = data?.participants || [];

  return (
    <MatchInlineSection
      title="Прогнозы участников"
      meta={`${count} ${pluralRu(count, 'прогноз', 'прогноза', 'прогнозов')}`}
      iconName="target"
      className="match-participants-block"
      onOpen={() => { if (!loaded && !error) load(); }}
    >
      {!loaded && !error && <LoadingCard text="Загружаю прогнозы..." />}

      {error && (
        <div className="inline-error">
          <span>{error.message}</span>
          <button type="button" onClick={load}>Повторить</button>
        </div>
      )}

      {loaded && data && (
        <>
          <div className="participants-summary inline-summary">
            <strong>{data.participants_count}</strong>
            <span>{pluralRu(data.participants_count, 'прогноз сделан', 'прогноза сделано', 'прогнозов сделано')}</span>
          </div>

          {!data.has_started && (
            <p className="participants-note">
              До начала матча показываем только, кто уже сделал прогноз. Счета откроются после стартового свистка.
            </p>
          )}

          {participants.length === 0 ? (
            <div className="empty-state compact-empty inline-empty">
              <div className="empty-icon"><Icon name="target" /></div>
              <h2>Пока никто не поставил</h2>
              <p>Будь первым, кто рискнет репутацией.</p>
            </div>
          ) : (
            <div className="participants-list inline-participants-list">
              {data.father_prediction && (
                <div className={`participant-row father-row ${data.father_prediction.result_class ? `result-${data.father_prediction.result_class}` : ''}`}>
                  <span>🤖 Отец прогнозов</span>
                  <b>{data.father_prediction.pred_home}:{data.father_prediction.pred_away}</b>
                </div>
              )}
              {participants.map((participant) => (
                <div className={`participant-row ${participant.result_class ? `result-${participant.result_class}` : ''}`} key={participant.user_id}>
                  <span>{participant.display_name}</span>
                  {data.has_started ? (
                    <b>{participant.pred_home}:{participant.pred_away}</b>
                  ) : (
                    <em>прогноз сделан</em>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </MatchInlineSection>
  );
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function wrapCanvasText(ctx, text, maxWidth) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let line = '';
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
}

async function shareMatchEmotionCard({ match, emotion, leagueName }) {
  const canvas = document.createElement('canvas');
  canvas.width = 1080;
  canvas.height = 1350;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Не удалось подготовить карточку');

  const background = ctx.createLinearGradient(0, 0, 1080, 1350);
  background.addColorStop(0, '#12244c');
  background.addColorStop(0.48, '#0d1830');
  background.addColorStop(1, '#080d19');
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const glow = ctx.createRadialGradient(120, 70, 20, 120, 70, 650);
  glow.addColorStop(0, 'rgba(90,141,255,.38)');
  glow.addColorStop(1, 'rgba(90,141,255,0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = 'rgba(255,255,255,.08)';
  drawRoundedRect(ctx, 56, 56, 968, 1238, 44);
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,.16)';
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = '#a9c4ff';
  ctx.font = '700 28px system-ui, sans-serif';
  ctx.fillText('ОТЕЦ ПРОГНОЗОВ', 104, 126);
  ctx.fillStyle = '#f6f8ff';
  ctx.font = '800 42px system-ui, sans-serif';
  ctx.fillText('Твой итог матча', 104, 184);

  ctx.fillStyle = '#95a4bf';
  ctx.font = '600 26px system-ui, sans-serif';
  ctx.fillText(`Лига «${leagueName || 'Моя лига'}»`, 104, 228);

  ctx.fillStyle = 'rgba(255,255,255,.07)';
  drawRoundedRect(ctx, 104, 284, 872, 256, 30);
  ctx.fill();
  ctx.fillStyle = '#f6f8ff';
  ctx.font = '800 37px system-ui, sans-serif';
  const teams = `${match.home_team} — ${match.away_team}`;
  const teamLines = wrapCanvasText(ctx, teams, 800).slice(0, 2);
  teamLines.forEach((line, index) => ctx.fillText(line, 140, 350 + index * 48));
  ctx.fillStyle = '#a9c4ff';
  ctx.font = '900 76px system-ui, sans-serif';
  ctx.fillText(emotion.actual_score || '—', 140, 490);
  ctx.fillStyle = '#aebbd1';
  ctx.font = '600 24px system-ui, sans-serif';
  ctx.fillText('Итоговый счет', 315, 480);

  const accent = emotion.result_type === 'exact' ? '#f4bf36'
    : emotion.result_type === 'outcome' ? '#16c784'
      : emotion.result_type === 'miss' ? '#ff6872' : '#5a8dff';
  ctx.fillStyle = accent;
  drawRoundedRect(ctx, 104, 580, 872, 164, 28);
  ctx.fill();
  ctx.fillStyle = '#08101e';
  ctx.font = '800 31px system-ui, sans-serif';
  ctx.fillText(emotion.title || 'Твой итог', 140, 644);
  ctx.font = '700 25px system-ui, sans-serif';
  const recapLines = wrapCanvasText(ctx, emotion.text || '', 784).slice(0, 2);
  recapLines.forEach((line, index) => ctx.fillText(line, 140, 690 + index * 32));

  const tiles = [
    ['Очки', `+${pointsLabel(emotion.points || 0)}`],
    ['Место', emotion.rank_after ? `#${emotion.rank_after}` : '—'],
    ['Серия', emotion.streak ? `${emotion.streak} 🔥` : '—'],
  ];
  tiles.forEach(([label, value], index) => {
    const x = 104 + index * 292;
    ctx.fillStyle = 'rgba(255,255,255,.07)';
    drawRoundedRect(ctx, x, 794, 264, 164, 26);
    ctx.fill();
    ctx.fillStyle = '#96a2bc';
    ctx.font = '700 22px system-ui, sans-serif';
    ctx.fillText(label, x + 28, 844);
    ctx.fillStyle = '#f6f8ff';
    ctx.font = '800 34px system-ui, sans-serif';
    ctx.fillText(value, x + 28, 904);
  });

  const achievements = emotion.achievements || [];
  if (achievements.length) {
    ctx.fillStyle = '#f6f8ff';
    ctx.font = '800 30px system-ui, sans-serif';
    ctx.fillText('Достижения матча', 104, 1030);
    ctx.font = '700 25px system-ui, sans-serif';
    achievements.slice(0, 3).forEach((achievement, index) => {
      ctx.fillStyle = '#d7e3fb';
      ctx.fillText(`${achievement.icon} ${achievement.title}`, 104, 1082 + index * 46);
    });
  }

  ctx.fillStyle = '#7f90ad';
  ctx.font = '600 22px system-ui, sans-serif';
  ctx.fillText('Прогнозы. Эмоции. Репутация.', 104, 1242);

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('Не удалось сформировать изображение');
  const filename = `otets-prognozov-${match.id}.png`;
  const file = new File([blob], filename, { type: 'image/png' });

  let canShareFile = false;
  try {
    canShareFile = Boolean(
      navigator.share
      && (!navigator.canShare || navigator.canShare({ files: [file] }))
    );
  } catch (_) {
    canShareFile = false;
  }

  if (canShareFile) {
    await navigator.share({
      title: 'Мой итог матча · Отец прогнозов',
      text: `${match.home_team} — ${match.away_team}: ${emotion.actual_score}. ${emotion.title}`,
      files: [file],
    });
    return 'shared';
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return 'downloaded';
}

function MatchEmotionInline({ match, leagueId = null, leagueName = '' }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [shareMessage, setShareMessage] = useState('');

  async function load() {
    setError(null);
    try {
      const params = new URLSearchParams();
      if (leagueId) params.set('league_id', String(leagueId));
      const suffix = params.toString() ? `?${params.toString()}` : '';
      setData(await api(`/api/webapp/matches/${match.id}/emotion${suffix}`));
      setLoaded(true);
    } catch (err) {
      setError(err);
    }
  }

  async function share() {
    if (!data?.emotion) return;
    setSharing(true);
    setShareMessage('');
    try {
      const action = await shareMatchEmotionCard({
        match,
        emotion: data.emotion,
        leagueName: data.league?.name || leagueName,
      });
      setShareMessage(action === 'downloaded' ? 'Карточка сохранена' : 'Карточка отправлена');
    } catch (err) {
      if (err?.name !== 'AbortError') setShareMessage(err?.message || 'Не удалось поделиться карточкой');
    } finally {
      setSharing(false);
    }
  }

  const emotion = data?.emotion;
  const meta = !loaded ? 'открыть' : data?.eligible === false ? 'вне зачета' : emotion?.points ? `+${pointsLabel(emotion.points)}` : emotion?.title || 'итог';

  return (
    <MatchInlineSection
      title="Твой итог"
      meta={meta}
      iconName="fire"
      className="match-emotion-block"
      onOpen={() => { if (!loaded && !error) load(); }}
    >
      {!loaded && !error && <LoadingCard text="Собираю твой итог..." />}
      {error && <div className="inline-error"><span>{error.message}</span><button type="button" onClick={load}>Повторить</button></div>}
      {loaded && data?.eligible === false && <p className="participants-note">{data.message}</p>}
      {loaded && emotion && (
        <div className={`match-emotion-content ${emotion.result_type}`}>
          <div className="emotion-result-head">
            <span className="emotion-result-icon">
              {emotion.result_type === 'exact' ? '🎯' : emotion.result_type === 'outcome' ? '🔵' : emotion.result_type === 'miss' ? '😬' : '⏱️'}
            </span>
            <div>
              <strong>{emotion.title}</strong>
              <p>{emotion.text}</p>
            </div>
          </div>

          <div className="emotion-metrics">
            <div><span>Очки</span><b>+{pointsLabel(emotion.points)}</b></div>
            <div><span>Место</span><b>{emotion.rank_after ? `#${emotion.rank_after}` : '—'}</b></div>
            <div><span>Серия</span><b>{emotion.streak ? `${emotion.streak} 🔥` : '—'}</b></div>
          </div>

          {emotion.rank_after && (
            <p className={`emotion-rank-note ${emotion.rank_delta > 0 ? 'up' : emotion.rank_delta < 0 ? 'down' : ''}`}>
              {emotion.rank_delta > 0
                ? `📈 Подъем на ${emotion.rank_delta} ${pluralRu(emotion.rank_delta, 'позицию', 'позиции', 'позиций')} · теперь #${emotion.rank_after} из ${emotion.participants_count}`
                : emotion.rank_delta < 0
                  ? `↘️ Сейчас #${emotion.rank_after} из ${emotion.participants_count}. Следующий матч — шанс на камбэк.`
                  : `🏆 #${emotion.rank_after} из ${emotion.participants_count} · всего ${pointsLabel(emotion.league_points)}`}
            </p>
          )}

          {emotion.achievements?.length > 0 && (
            <div className="emotion-achievements">
              {emotion.achievements.map((achievement) => (
                <div key={achievement.code}>
                  <span>{achievement.icon}</span>
                  <strong>{achievement.title}</strong>
                  <small>{achievement.description}</small>
                </div>
              ))}
            </div>
          )}

          <section className="emotion-share-card" aria-label="Карточка результата для шаринга">
            <span>ОТЕЦ ПРОГНОЗОВ · {data.league?.name || leagueName || 'ЛИГА'}</span>
            <strong>{match.home_team} — {match.away_team}</strong>
            <div><b>{emotion.actual_score}</b><i>Твой прогноз: {emotion.prediction_score || '—'}</i></div>
            <p>{emotion.title} · +{pointsLabel(emotion.points)}</p>
          </section>

          <button type="button" className="emotion-share-button" onClick={share} disabled={sharing}>
            <Icon name="share" />
            {sharing ? 'Готовлю карточку…' : (typeof navigator !== 'undefined' && navigator.share ? 'Поделиться карточкой' : 'Скачать карточку')}
          </button>
          {shareMessage && <p className="emotion-share-message">{shareMessage}</p>}
        </div>
      )}
    </MatchInlineSection>
  );
}



function detailStatusLabel(details, match) {
  const status = String(details?.overview?.status_long || details?.overview?.status_short || '').trim();
  if (match?.is_finished) return 'Матч завершен';
  if (status) return status;
  return formatDateTime(match?.starts_at);
}

function DetailEmpty({ title, text }) {
  return (
    <div className="match-details-empty">
      <span>⌁</span>
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function MatchDetailsModal({ match, onClose, onPredict, onOpenTeam, onOpenPlayer }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [refreshing, setRefreshing] = useState(false);

  async function load({ silent = false } = {}) {
    if (!silent) setData(null);
    setError(null);
    setRefreshing(true);
    try {
      setData(await api(`/api/webapp/matches/${match.id}/details`));
    } catch (err) {
      setError(err);
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    api(`/api/webapp/matches/${match.id}/details`)
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, [match.id]);

  const currentMatch = data?.match || match;
  const details = data?.details || {};
  const locked = currentMatch.is_finished || new Date(currentMatch.starts_at).getTime() <= Date.now();
  const tabs = [
    ['overview', 'Обзор'],
    ['events', 'События'],
    ['scorers', 'Бомбардиры'],
    ['stats', 'Статистика'],
    ['lineups', 'Составы'],
  ];
  const homeScorers = (details.scorers || []).filter((item) => item.side === 'home');
  const awayScorers = (details.scorers || []).filter((item) => item.side === 'away');
  const detailScore = (details.overview?.score_home !== null && details.overview?.score_home !== undefined
    && details.overview?.score_away !== null && details.overview?.score_away !== undefined)
    ? `${details.overview.score_home} : ${details.overview.score_away}`
    : (currentMatch.is_finished ? formatActualScore(currentMatch) : '— : —');

  function renderOverview() {
    return (
      <div className="match-details-content overview">
        {!details.available && (
          <div className="match-details-pending">
            <span>⌁</span>
            <div>
              <strong>Детали пока собираются</strong>
              <p>{details.unavailable_reason || 'Обновляем данные матча из официального провайдера.'}</p>
            </div>
            <button type="button" onClick={() => load({ silent: true })} disabled={refreshing}>{refreshing ? 'Обновляю…' : 'Обновить'}</button>
          </div>
        )}

        <div className="match-details-facts">
          {details.overview?.round && <div><span>Турнир</span><b>{details.overview.round}</b></div>}
          {details.overview?.venue && <div><span>Стадион</span><b>{details.overview.venue}{details.overview?.city ? ` · ${details.overview.city}` : ''}</b></div>}
          {details.overview?.referee && <div><span>Арбитр</span><b>{details.overview.referee}</b></div>}
        </div>

        {(homeScorers.length || awayScorers.length) ? (
          <section className="details-goals-card">
            <div className="details-section-title"><span>⚽</span><strong>Голы</strong></div>
            <div className="details-goals-grid">
              <div className="details-goal-column home">
                {homeScorers.map((item) => <button className="details-goal-player" key={`${item.team}-${item.player}`} onClick={() => item.player_id && onOpenPlayer?.(item.player_id)} disabled={!item.player_id}><b>{item.player}</b><span>{item.minutes.join(', ')}</span></button>)}
              </div>
              <div className="details-goal-column away">
                {awayScorers.map((item) => <button className="details-goal-player" key={`${item.team}-${item.player}`} onClick={() => item.player_id && onOpenPlayer?.(item.player_id)} disabled={!item.player_id}><b>{item.player}</b><span>{item.minutes.join(', ')}</span></button>)}
              </div>
            </div>
          </section>
        ) : (
          <DetailEmpty title="Голов пока нет" text={currentMatch.is_finished ? 'Провайдер не передал события матча.' : 'Бомбардиры появятся после первого гола.'} />
        )}

        {!locked && (
          <button type="button" className="primary full details-predict-cta" onClick={() => { onPredict?.(currentMatch); onClose?.(); }}>
            {currentMatch.prediction ? 'Изменить прогноз' : 'Сделать прогноз'}
          </button>
        )}
      </div>
    );
  }

  function renderEvents() {
    const events = details.events || [];
    if (!events.length) return <DetailEmpty title="Событий пока нет" text={currentMatch.is_finished ? 'Провайдер пока не прислал ленту событий.' : 'Голы, карточки и замены появятся здесь во время матча.'} />;
    return (
      <div className="match-event-timeline">
        {events.map((event, index) => (
          <div className={`match-event-row ${event.side || ''}`} key={`${event.minute}-${event.player}-${index}`}>
            <time>{event.minute}</time>
            <span className="event-dot">{event.icon}</span>
            <div>
              <strong>{event.player || event.label}</strong>
              <small>{event.label}{event.assist ? ` · ассист ${event.assist}` : ''}</small>
            </div>
          </div>
        ))}
      </div>
    );
  }

  function renderScorers() {
    const scorers = details.scorers || [];
    if (!scorers.length) return <DetailEmpty title="Бомбардиров пока нет" text="Голы и авторы появятся здесь по мере игры." />;
    return (
      <div className="match-scorers-list">
        {scorers.map((scorer) => (
          <article className={`match-scorer-row ${scorer.side || ''}`} key={`${scorer.team}-${scorer.player}`}>
            <button className="match-scorer-click" onClick={() => scorer.player_id && onOpenPlayer?.(scorer.player_id)} disabled={!scorer.player_id}>{scorer.photo ? <img src={scorer.photo} alt="" /> : <span className="scorer-avatar">{(scorer.player || '?').slice(0, 1)}</span>}<div><strong>{scorer.player}</strong><small>{scorer.minutes.join(', ')}</small></div></button>
            <button className="match-scorer-team-link" onClick={() => scorer.team_id && onOpenTeam?.(scorer.team_id)} disabled={!scorer.team_id}>{scorer.team}</button><b>{scorer.goals}</b>
          </article>
        ))}
      </div>
    );
  }

  function renderStats() {
    const rows = details.statistics || [];
    if (!rows.length) return <DetailEmpty title="Статистика пока недоступна" text="Появится во время матча или после финального свистка." />;
    return (
      <div className="match-stats-list">
        {rows.map((row) => (
          <div className="match-stat-row" key={row.key}>
            <b>{row.home}</b><span>{row.label}</span><b>{row.away}</b>
          </div>
        ))}
      </div>
    );
  }

  function renderLineups() {
    const lineups = details.lineups || [];
    if (!lineups.length) return <DetailEmpty title="Составы еще не объявлены" text="Обычно стартовые составы появляются примерно за час до начала матча." />;
    return (
      <div className="match-lineups-grid">
        {lineups.map((lineup) => (
          <section className="lineup-team-card" key={lineup.team}>
            <header><strong>{lineup.team}</strong><span>{lineup.formation || '—'}</span></header>
            {lineup.coach && <p className="lineup-coach">Тренер: {lineup.coach}</p>}
            <div className="lineup-list">
              {(lineup.start || []).map((player) => <p key={`${player.number}-${player.name}`}><i>{player.number ?? '—'}</i><span>{player.name}</span><small>{player.position}</small></p>)}
            </div>
            {(lineup.bench || []).length > 0 && (
              <details className="lineup-bench"><summary>Запасные · {lineup.bench.length}</summary><div>{lineup.bench.map((player) => <p key={`${player.number}-${player.name}`}><i>{player.number ?? '—'}</i><span>{player.name}</span></p>)}</div></details>
            )}
          </section>
        ))}
      </div>
    );
  }

  const body = error
    ? <div className="inline-error match-details-error"><span>{error.message}</span><button type="button" onClick={() => load()}>Повторить</button></div>
    : !data
      ? <LoadingCard text="Загружаю детали матча..." />
      : activeTab === 'overview' ? renderOverview()
        : activeTab === 'events' ? renderEvents()
          : activeTab === 'scorers' ? renderScorers()
            : activeTab === 'stats' ? renderStats()
              : renderLineups();

  return (
    <div
      className="modal-backdrop match-details-backdrop"
      role="presentation"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose?.(); }}
    >
      <section className="modal-card match-details-modal" role="dialog" aria-modal="true" aria-label="Детали матча">
        <div className="match-details-drag-handle" aria-hidden="true"><span /></div>
        <button type="button" className="modal-close" aria-label="Закрыть детали матча" onClick={onClose}>×</button>
        <header className="match-details-hero">
          <button className="detail-team detail-team-button" onClick={() => currentMatch.home_team_id && onOpenTeam?.(currentMatch.home_team_id)} disabled={!currentMatch.home_team_id}><TeamFlag code={currentMatch.home_flag_code} emoji={currentMatch.home_flag} name={currentMatch.home_team} /><strong>{currentMatch.home_team}</strong></button>
          <div className="detail-score">
            <b>{detailScore}</b>
            <span>{detailStatusLabel(details, currentMatch)}</span>
          </div>
          <button className="detail-team detail-team-button" onClick={() => currentMatch.away_team_id && onOpenTeam?.(currentMatch.away_team_id)} disabled={!currentMatch.away_team_id}><TeamFlag code={currentMatch.away_flag_code} emoji={currentMatch.away_flag} name={currentMatch.away_team} /><strong>{currentMatch.away_team}</strong></button>
        </header>
        <p className="match-details-date">{formatDateTime(currentMatch.starts_at)}{details.last_synced_at ? ' · данные обновлены' : ''}</p>

        <nav className="match-details-tabs" aria-label="Разделы матча">
          {tabs.map(([id, label]) => <button type="button" key={id} className={activeTab === id ? 'active' : ''} onClick={() => setActiveTab(id)}>{label}</button>)}
        </nav>
        <div className="match-details-body">{body}</div>
      </section>
    </div>
  );
}

function MatchCard({ match, onPredict, onForecast, onDetails, showDistribution = true, leagueId = null, leagueName = '' }) {
  const locked = match.is_finished || new Date(match.starts_at).getTime() <= Date.now();
  const predictionScoreClass = predictionResultClass(match);
  const activeVideos = visibleVideosForMatch(match);
  const hasVideos = activeVideos.length > 0;
  const detailTriggerProps = onDetails ? {
    role: 'button',
    tabIndex: 0,
    'aria-label': `Открыть детали матча ${match.home_team} — ${match.away_team}`,
    onClick: () => onDetails(match),
    onKeyDown: (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onDetails(match);
      }
    },
  } : {};

  return (
    <article className={`match-card ${hasVideos ? 'has-video' : ''}`}>
      <div className="match-card-top">
        <span className="group-pill">{match.group_code ? `Группа ${match.group_code}` : match.stage}</span>
        <span className="round-pill">{formatRoundLabel(match)}</span>
        {hasVideos && <span className="video-mini-icon" aria-label="Видео" title="Видео">🎥</span>}
        <span className={match.is_finished ? 'dot dot-finished' : 'dot'} />
        <span className="muted small match-date">{formatDateTime(match.starts_at)}</span>
      </div>

      <div className={`match-teams ${onDetails ? 'match-teams-clickable' : ''}`} {...detailTriggerProps}>
        <div className="team-side">
          <TeamFlag code={match.home_flag_code} emoji={match.home_flag} name={match.home_team} />
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
          <TeamFlag code={match.away_flag_code} emoji={match.away_flag} name={match.away_team} />
          <strong>{match.away_team}</strong>
        </div>
      </div>

      {onDetails && (
        <button type="button" className="match-details-link" onClick={() => onDetails(match)}>
          <Icon name="more" />
          Детали матча
        </button>
      )}

      <div className="match-actions">
        {!locked && <button onClick={() => onPredict(match)}>{match.prediction ? 'Изменить прогноз' : 'Сделать прогноз'}</button>}
        {!locked && <button onClick={() => onForecast(match)}><Icon name="robot" /> Прогноз Отца</button>}
      </div>

      <MatchVideoBlock match={match} />
      <MatchParticipantsInline match={match} leagueId={leagueId} />
      {match.is_finished && <MatchEmotionInline match={match} leagueId={leagueId} leagueName={leagueName} />}

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

function TeamProfileModal({ teamId, onClose, onOpenMatch, onOpenPlayer }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('matches');

  useEffect(() => {
    if (teamId) trackAnalytics('team_open', { screen: 'matches', properties: { team_id: teamId } });
    let active = true;
    setData(null); setError(null);
    api(`/api/webapp/tournament/teams/${teamId}`)
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, [teamId]);

  if (error) return <div className="modal-backdrop"><section className="modal-card hub-modal"><button className="modal-close" onClick={onClose}>×</button><ErrorCard error={error} onRetry={() => window.location.reload()} /></section></div>;
  if (!data) return <div className="modal-backdrop"><section className="modal-card hub-modal"><button className="modal-close" onClick={onClose}>×</button><LoadingCard text="Открываю профиль сборной..." /></section></div>;

  const team = data.team || {};
  const stats = team.stats || {};
  const standing = team.standing;
  const tabs = [['matches', 'Матчи'], ['scorers', 'Бомбардиры'], ['stats', 'Статистика']];

  const body = activeTab === 'matches' ? (
    <div className="hub-match-list">
      {(data.matches || []).map((match) => (
        <button className="hub-team-match" key={match.id} onClick={() => onOpenMatch?.(match)}>
          <span className="hub-match-date">{formatDayTitle(match.starts_at)}</span>
          <span className="hub-match-line">
            <span><TeamFlag code={match.home_flag_code} emoji={match.home_flag} name={match.home_team} size="mini" /> {match.home_team}</span>
            <b>{match.is_finished ? formatActualScore(match) : formatDateTime(match.starts_at).split(', ')[1] || '—'}</b>
            <span>{match.away_team} <TeamFlag code={match.away_flag_code} emoji={match.away_flag} name={match.away_team} size="mini" /></span>
          </span>
          <small>{match.is_finished ? 'Открыть детали матча' : 'Скоро матч'}</small>
        </button>
      ))}
    </div>
  ) : activeTab === 'scorers' ? (
    (data.scorers || []).length ? <div className="hub-scorers-list">{data.scorers.map((player, index) => <TournamentScorerRow key={player.player_id || player.name} item={player} rank={index + 1} onOpenPlayer={onOpenPlayer} />)}</div> : <DetailEmpty title="Голов пока нет" text="Бомбардиры сборной появятся после первых матчей." />
  ) : (
    <div className="team-stats-grid">
      <div><b>{stats.played || 0}</b><span>матчей</span></div>
      <div><b>{stats.wins || 0}</b><span>побед</span></div>
      <div><b>{stats.draws || 0}</b><span>ничьих</span></div>
      <div><b>{stats.losses || 0}</b><span>поражений</span></div>
      <div><b>{stats.goals_for || 0}:{stats.goals_against || 0}</b><span>мячи</span></div>
      <div><b>{standing?.points ?? 0}</b><span>очков в группе</span></div>
    </div>
  );

  return (
    <div className="modal-backdrop hub-backdrop">
      <section className="modal-card hub-modal team-profile-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <header className="hub-team-hero">
          <TeamFlag code={team.flag_code} emoji={team.flag} name={team.name} />
          <div><p className="muted small">{team.group_code ? `Группа ${team.group_code}` : 'Сборная'}</p><h2>{team.name}</h2><span>{standing ? `${standing.rank}-е место · ${pointsLabel(standing.points)}` : 'Турнирная статистика'}</span></div>
        </header>
        <nav className="match-details-tabs hub-tabs">{tabs.map(([id, label]) => <button key={id} className={activeTab === id ? 'active' : ''} onClick={() => setActiveTab(id)}>{label}</button>)}</nav>
        <div className="hub-modal-body">{body}</div>
      </section>
    </div>
  );
}

function PlayerProfileModal({ playerId, onClose, onOpenTeam, onOpenMatch }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (playerId) trackAnalytics('player_open', { screen: 'matches', properties: { player_id: playerId } });
    let active = true;
    setData(null); setError(null);
    api(`/api/webapp/tournament/players/${playerId}`)
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, [playerId]);
  if (error) return <div className="modal-backdrop"><section className="modal-card hub-modal"><button className="modal-close" onClick={onClose}>×</button><ErrorCard error={error} onRetry={() => window.location.reload()} /></section></div>;
  if (!data) return <div className="modal-backdrop"><section className="modal-card hub-modal"><button className="modal-close" onClick={onClose}>×</button><LoadingCard text="Открываю профиль игрока..." /></section></div>;
  const player = data.player || {};
  return (
    <div className="modal-backdrop hub-backdrop">
      <section className="modal-card hub-modal player-profile-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <header className="player-profile-hero">
          {player.photo ? <img src={player.photo} alt="" /> : <span>{(player.name || '?').slice(0, 1)}</span>}
          <div><p className="muted small">{player.nationality || 'Игрок сборной'}</p><h2>{player.name}</h2>{player.team_id ? <button className="profile-team-link" onClick={() => onOpenTeam?.(player.team_id)}><TeamFlag code={player.team_flag_code} emoji={player.team_flag} name={player.team} size="mini" /> {player.team}</button> : <span>{player.team}</span>}</div>
        </header>
        <div className="player-stat-strip">
          <div><b>{player.goals || 0}</b><span>голы</span></div><div><b>{player.assists || 0}</b><span>ассисты</span></div><div><b>{player.appearances || 0}</b><span>матчи</span></div><div><b>{player.minutes || 0}</b><span>минуты</span></div>
        </div>
        <h3 className="hub-subtitle">Матчи турнира</h3>
        {(data.matches || []).length ? (
          <div className="hub-match-list">
            {data.matches.map((match) => (
              <button className="hub-team-match" key={match.match_id} onClick={() => onOpenMatch?.({ id: match.match_id, ...match })}>
                <span className="hub-match-line">
                  <span><TeamFlag code={match.home_flag_code} name={match.home_team} size="mini" /> {match.home_team}</span>
                  <b>{match.is_finished ? `${match.score_home}:${match.score_away}` : '—'}</b>
                  <span>{match.away_team} <TeamFlag code={match.away_flag_code} name={match.away_team} size="mini" /></span>
                </span>
                <small>{match.goals ? `⚽ ${match.goals}` : ''}{match.assists ? ` · 🅰 ${match.assists}` : ''}{match.minutes ? ` · ${match.minutes} мин` : ''}</small>
              </button>
            ))}
          </div>
        ) : <DetailEmpty title="Матчевая статистика еще не синхронизирована" text="Она появится после обновления деталей матчей." />}
      </section>
    </div>
  );
}

function TournamentScorerHeader({ compact = false }) {
  return <div className={`hub-scorer-list-head ${compact ? 'compact' : ''}`} aria-hidden="true">
    <span>№</span>
    <span className="hub-scorer-list-head-player">Игрок</span>
    <span>Г</span>
    <span>П</span>
  </div>;
}

function TournamentScorerRow({ item, rank, onOpenPlayer, onOpenTeam }) {
  const canOpenPlayer = Boolean(item.player_id);
  const canOpenTeam = Boolean(item.team_id && onOpenTeam);
  const appearances = Number(item.appearances || 0);
  return <article className="hub-scorer-row">
    <span className="hub-rank">{rank}</span>
    <button className="hub-scorer-photo" onClick={() => canOpenPlayer && onOpenPlayer?.(item.player_id)} disabled={!canOpenPlayer} aria-label={`Открыть профиль ${item.name || 'игрока'}`}>
      {item.photo ? <img src={item.photo} alt="" /> : <span className="hub-player-avatar">{(item.name || '?').slice(0, 1)}</span>}
    </button>
    <div className="hub-scorer-info">
      <div className="hub-scorer-name-row">
        <button className="hub-scorer-name" onClick={() => canOpenPlayer && onOpenPlayer?.(item.player_id)} disabled={!canOpenPlayer}>{item.name}</button>
        <button className="hub-scorer-team-inline" onClick={() => canOpenTeam && onOpenTeam?.(item.team_id)} disabled={!canOpenTeam} aria-label={item.team ? `Открыть сборную ${item.team}` : 'Открыть сборную'} title={item.team || 'Сборная'}>
          <TeamFlag code={item.team_flag_code} emoji={item.team_flag} name={item.team} size="mini" />
        </button>
      </div>
      <small>{appearances ? `${appearances} ${pluralRu(appearances, 'матч', 'матча', 'матчей')}` : 'Матчи уточняются'}</small>
    </div>
    <div className="hub-scorer-stat goals" title="Голы"><b>{item.goals || 0}</b></div>
    <div className="hub-scorer-stat assists" title="Ассисты"><b>{item.assists || 0}</b></div>
  </article>;
}

function TournamentHub({ mode = 'tournament', onModeChange, onOpenMatch, onOpenTeam, onOpenPlayer }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedGroups, setSelectedGroups] = useState([]);

  useEffect(() => {
    let active = true;
    api('/api/webapp/tournament/overview').then((result) => {
      if (!active) return;
      setData(result);
      const available = (result.groups || []).map((group) => group.group_code);
      const defaults = (result.default_group_codes || []).filter((code) => available.includes(code));
      setSelectedGroups((current) => {
        const validCurrent = current.filter((code) => available.includes(code));
        if (validCurrent.length) return validCurrent;
        return defaults.length ? defaults : available.slice(0, 1);
      });
    }).catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, []);

  function toggleGroup(code) {
    setSelectedGroups((current) => {
      if (current.includes(code)) {
        // Keep at least one table visible: this prevents an accidental empty tournament screen.
        return current.length === 1 ? current : current.filter((item) => item !== code);
      }
      return [...current, code].sort();
    });
  }

  if (error) return <ErrorCard error={error} onRetry={() => window.location.reload()} />;
  if (!data) return <LoadingCard text="Загружаю турнирный центр..." />;

  const groups = data.groups || [];
  const visibleGroups = groups.filter((item) => selectedGroups.includes(item.group_code));
  const scorers = data.top_scorers?.items || [];
  const selectedLabel = visibleGroups.length ? visibleGroups.map((item) => item.group_code).join(', ') : 'не выбраны';

  return <div className="tournament-hub">
    {mode === 'tournament' ? <>
      <details className="group-multi-select">
        <summary>
          <span>Группы</span>
          <b>{selectedLabel}</b>
          <i aria-hidden="true">⌄</i>
        </summary>
        <div className="group-multi-options">
          {groups.map((item) => (
            <label key={item.group_code}>
              <input type="checkbox" checked={selectedGroups.includes(item.group_code)} onChange={() => toggleGroup(item.group_code)} />
              <span className={`group-picker-dot group-${item.group_code}`}>{item.group_code}</span>
              <b>Группа {item.group_code}</b>
            </label>
          ))}
        </div>
      </details>
      <p className="group-selection-hint">По умолчанию выбраны группы с матчами текущего игрового дня по времени США.</p>
      <div className="tournament-group-tables">
        {visibleGroups.map((group) => <GroupTable key={group.group_code} group={group} onTeam={onOpenTeam} />)}
      </div>
      <section className="hub-preview-card"><header><div><span className="section-label">Лидеры гонки</span><h2>Бомбардиры</h2></div><button type="button" onClick={() => onModeChange?.('scorers')}>Все →</button></header><div className="hub-scorers-list compact"><TournamentScorerHeader compact />{scorers.slice(0, 5).map((item, index) => <TournamentScorerRow key={item.player_id || item.name} item={item} rank={index + 1} onOpenPlayer={onOpenPlayer} onOpenTeam={onOpenTeam} />)}</div></section>
    </> : <section className="hub-scorers-card"><header><div><h2>Топ бомбардиров</h2></div><small>{data.top_scorers?.source === 'match-events' ? 'по событиям матчей' : 'обновляется из статистики'}</small></header><div className="hub-scorers-list">{scorers.length ? <><TournamentScorerHeader />{scorers.map((item, index) => <TournamentScorerRow key={item.player_id || item.name} item={item} rank={index + 1} onOpenPlayer={onOpenPlayer} onOpenTeam={onOpenTeam} />)}</> : <DetailEmpty title="Бомбардиры появятся после первых голов" text="Данные автоматически обновляются из матчей турнира." />}</div></section>}
  </div>;
}

function GroupTable({ group, onTeam, compact = false }) {
  if (!group) return null;
  return (
    <section className={`group-table-card group-color group-${group.group_code} ${compact ? 'group-table-card-compact' : ''}`}>
      <div className="group-header">
        <div className="group-letter">{group.group_code}</div>
        <div>
          <h2>Группа {group.group_code}</h2>
          <p className="muted">1–2 место — 1/8 финала · 3-е — шанс на плей-офф</p>
        </div>
      </div>
      <div className="standings-table">
        <div className="standings-row headings"><span>#</span><span>Сборная</span><span>И</span><span>В</span><span>Н</span><span>П</span><span>М</span><span>±</span><span>О</span></div>
        {group.rows.map((row) => (
          <button key={row.team} className={`standings-row zone-${row.qualification_zone} ${row.team_id ? 'clickable' : ''}`} onClick={() => row.team_id && onTeam?.(row.team_id)} disabled={!row.team_id}>
            <span className="rank-cell">{row.rank}</span><span className="team-name"><TeamFlag code={row.flag_code} emoji={row.flag} name={row.team} size="mini" /> {row.team}</span><span>{row.played}</span><span>{row.wins}</span><span>{row.draws}</span><span>{row.losses}</span><span>{row.goals_for}:{row.goals_against}</span><span>{row.goal_difference}</span><strong>{row.points}</strong>
          </button>
        ))}
      </div>
      <div className="legend muted small"><span><i className="legend-direct" /> 1–2 · 1/8</span><span><i className="legend-playoff" /> 3 · плей-офф</span></div>
    </section>
  );
}

function activeLeagueLabel(leagues = [], activeLeagueId) {
  return leagues.find((league) => Number(league.id) === Number(activeLeagueId))?.name || 'Отец прогнозов';
}

function MatchCenter({ onPredict, onForecast, leagues = [], activeLeagueId }) {
  const [scope, setScope] = useState('all');
  const [group, setGroup] = useState(null);
  const [centerMode, setCenterMode] = useState('matches');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detailsMatch, setDetailsMatch] = useState(null);
  const [teamId, setTeamId] = useState(null);
  const [playerId, setPlayerId] = useState(null);
  async function load() {
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams({ scope });
      if (group) params.set('group_code', group);
      if (activeLeagueId) params.set('league_id', String(activeLeagueId));
      setData(await api(`/api/webapp/match-center?${params.toString()}`));
    } catch (err) { setError(err); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [scope, group, activeLeagueId]);
  const grouped = useMemo(() => groupMatchesByDay(data?.matches || []), [data]);
  const selectedStanding = group ? data?.standings?.[0] : null;
  const leagueName = activeLeagueLabel(leagues, activeLeagueId);
  const openMatch = (match) => {
    trackAnalytics('match_open', { screen: 'matches', properties: { match_id: match?.id || 0, league_id: activeLeagueId || 0, entry_point: 'match_center' } });
    setTeamId(null); setPlayerId(null); setDetailsMatch(match);
  };
  const openTeam = (id) => { if (!id) return; setDetailsMatch(null); setPlayerId(null); setTeamId(id); };
  const openPlayer = (id) => { if (!id) return; setDetailsMatch(null); setTeamId(null); setPlayerId(id); };
  const changeCenterMode = (mode) => {
    setCenterMode(mode);
    trackAnalytics('tournament_mode_open', { screen: 'matches', properties: { mode } });
  };
  if (error) return <ErrorCard error={error} onRetry={load} />;
  return <main className="screen-content">
    <div className="section-label">Матч-центр</div>
    <div className="center-mode-tabs"><button className={centerMode === 'matches' ? 'active' : ''} onClick={() => changeCenterMode('matches')}>Матчи</button><button className={centerMode === 'tournament' ? 'active' : ''} onClick={() => changeCenterMode('tournament')}>Турнир</button><button className={centerMode === 'scorers' ? 'active' : ''} onClick={() => changeCenterMode('scorers')}>Бомбардиры</button></div>
    <section className="match-center-mode-content" aria-live="polite">
    {centerMode !== 'matches' ? <TournamentHub mode={centerMode} onModeChange={changeCenterMode} onOpenMatch={openMatch} onOpenTeam={openTeam} onOpenPlayer={openPlayer} /> : <>
      <div className="filter-strip modern-filters">
        <button className={!group && scope === 'all' ? 'active' : ''} onClick={() => { setGroup(null); setScope('all'); }}><Icon name="star" /><span>Все</span></button>
        <button className={scope === 'upcoming' ? 'active future' : ''} onClick={() => { setGroup(null); setScope('upcoming'); }}><Icon name="ball" /><span>Будущие</span></button>
        <button className={scope === 'results' ? 'active result' : ''} onClick={() => { setGroup(null); setScope('results'); }}><Icon name="check" /><span>Результаты</span></button>
        {(data?.groups || []).map((item) => <button key={item.group_code} className={`group-color group-${item.group_code} ${group === item.group_code ? 'active group' : ''}`} onClick={() => { setGroup(item.group_code); setScope('all'); }}><b>{item.group_code}</b><span>группа</span></button>)}
      </div>
      <div className="match-center-results">{loading && !data ? <LoadingCard /> : <>{selectedStanding && <GroupTable group={selectedStanding} onTeam={openTeam} compact />}{loading && <LoadingCard text="Обновляю список..." />}{!loading && grouped.length === 0 && <EmptyState iconName="ball" title="Нет матчей" text={scope === 'results' ? 'Пока нет завершенных матчей' : scope === 'upcoming' ? 'Нет будущих матчей' : 'Матчи не найдены'} />}{!loading && grouped.map(([day, matches]) => <section key={day} className="match-day"><div className="day-heading"><span>{formatDayTitle(matches[0]?.starts_at)}</span><b>{matches.length} матч{matches.length === 1 ? '' : 'а'}</b></div>{matches.map((match) => <MatchCard key={match.id} match={match} onPredict={onPredict} onForecast={onForecast} onDetails={openMatch} leagueId={activeLeagueId} leagueName={leagueName} />)}</section>)}</>}</div>
    </>}
    </section>
    {detailsMatch && <MatchDetailsModal match={detailsMatch} onClose={() => setDetailsMatch(null)} onPredict={onPredict} onOpenTeam={openTeam} onOpenPlayer={openPlayer} />}
    {teamId && <TeamProfileModal teamId={teamId} onClose={() => setTeamId(null)} onOpenMatch={openMatch} onOpenPlayer={openPlayer} />}
    {playerId && <PlayerProfileModal playerId={playerId} onClose={() => setPlayerId(null)} onOpenTeam={openTeam} onOpenMatch={openMatch} />}
  </main>;
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

  useEffect(() => {
    if (match?.id) {
      trackAnalytics('prediction_open', {
        screen: 'matches',
        properties: { match_id: match.id, is_update: Boolean(match.prediction) },
      });
    }
  }, [match?.id]);

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
      trackAnalytics('prediction_save', {
        screen: 'matches',
        properties: { match_id: match.id, is_update: Boolean(match.prediction) },
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
            <span className="score-team"><TeamFlag code={match.home_flag_code} emoji={match.home_flag} name={match.home_team} size="mini" /><strong>{match.home_team}</strong></span>
            <div className="counter compact-counter">
              <button onClick={() => dec(setHome, home)}>−</button>
              <b>{home}</b>
              <button onClick={() => inc(setHome, home)}>+</button>
            </div>
          </div>
          <div className="score-row">
            <span className="score-team"><TeamFlag code={match.away_flag_code} emoji={match.away_flag} name={match.away_team} size="mini" /><strong>{match.away_team}</strong></span>
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
    trackAnalytics('tournament_prediction_open', {
      screen: 'matches',
      properties: { entry_point: initialField },
    });
  }, [initialField]);

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
      trackAnalytics('tournament_prediction_save', { screen: 'matches' });
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


function TournamentPredictionsModal({ onClose, leagueId = null, leagueName = '' }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    api(`/api/webapp/tournament-predictions${leagueId ? `?league_id=${leagueId}` : ''}`)
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, [leagueId]);

  return (
    <div className="modal-backdrop">
      <section className="modal-card tournament-predictions-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>Прогнозы участников на турнир</h2>
        {leagueName && <p className="muted small">Лига: {leagueName}</p>}
        <p className="muted">Турнир уже начался — прогнозы открыты для просмотра и закрыты для редактирования.</p>
        {error && <p className="error-text">{error.message}</p>}
        {!error && !data && <LoadingCard text="Загружаю турнирные прогнозы..." />}
        {data && (
          <div className="tournament-predictions-list">
            {(data.rows || []).map((row) => (
              <article key={row.user_name} className={`tournament-prediction-row ${row.has_prediction ? '' : 'empty'}`}>
                <strong>{row.user_name}</strong>
                {row.prediction ? (
                  <div>
                    <span>🏆 {row.prediction.champion}</span>
                    <span>🥈 {row.prediction.runner_up}</span>
                    <span>🥉 {row.prediction.third_place}</span>
                    <span>⚽ {row.prediction.top_scorer}</span>
                  </div>
                ) : (
                  <em>{data.revealed ? 'нет прогноза' : 'скрыто до старта'}</em>
                )}
              </article>
            ))}
          </div>
        )}
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
                {data.father_prediction && (
                  <div className={`participant-row father-row ${data.father_prediction.result_class ? `result-${data.father_prediction.result_class}` : ''}`}>
                    <span>🤖 Отец прогнозов</span>
                    <b>{data.father_prediction.pred_home}:{data.father_prediction.pred_away}</b>
                  </div>
                )}
                {participants.map((participant) => (
                  <div className={`participant-row ${participant.result_class ? `result-${participant.result_class}` : ''}`} key={participant.user_id}>
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
    if (match?.id) trackAnalytics('forecast_open', { screen: 'matches', properties: { match_id: match.id } });
  }, [match?.id]);

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


function PlayerInfoButton({ player, onInfo, className = '' }) {
  if (!player || !onInfo) return null;

  return (
    <button
      type="button"
      className={`player-info-button ${className}`}
      onClick={(event) => {
        event.stopPropagation();
        onInfo(player);
      }}
      title="Статистика игрока"
      aria-label={`Статистика игрока ${player.name}`}
    >
      i
    </button>
  );
}

function PlayerInfoModal({ playerId, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      setData(await api(`/api/webapp/fantasy/players/${playerId}/stats`));
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, [playerId]);

  const player = data?.player;
  const totals = data?.totals || {};

  return (
    <div className="modal-backdrop">
      <section className="modal-card player-info-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        {error && <ErrorCard error={error} onRetry={load} />}
        {!data && !error && <LoadingCard text="Загружаю статистику игрока..." />}
        {data && (
          <>
            <div className="player-info-head">
              <span>{player.team_flag}</span>
              <div>
                <h2>{player.name}</h2>
                <p className="muted">{player.team_display_name} · {player.position_label}</p>
              </div>
              <b>{data.total_points || 0}</b>
            </div>

            <div className="player-info-summary">
              <div><b>{totals.minutes || 0}</b><span>минут</span></div>
              <div><b>{totals.goals || 0}</b><span>голы</span></div>
              <div><b>{totals.assists || 0}</b><span>ассисты</span></div>
              <div><b>{totals.clean_sheets || 0}</b><span>сухие</span></div>
              <div><b>{totals.saves || 0}</b><span>сэйвы</span></div>
              <div><b>{totals.yellow_cards || 0}/{totals.red_cards || 0}</b><span>ЖК/КК</span></div>
            </div>

            {(data.matches || []).length === 0 ? (
              <div className="empty-state compact-empty">
                <div className="empty-icon"><Icon name="ball" /></div>
                <h2>Статистики пока нет</h2>
                <p>Баллы появятся после обновления статистики игроков в админке.</p>
              </div>
            ) : (
              <div className="player-stat-list">
                {(data.matches || []).map((row) => (
                  <article key={row.match_id} className="player-stat-row">
                    <div>
                      <strong>{row.match_label}</strong>
                      <small>{row.minutes} мин · {row.goals} гол · {row.assists} пас · {row.clean_sheet ? 'сухой матч' : `${row.goals_conceded} проп.`}</small>
                    </div>
                    <b>{row.points > 0 ? '+' : ''}{row.points}</b>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function OtherFantasyTeams({ onInfo }) {
  const [data, setData] = useState(null);
  const [openUserId, setOpenUserId] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      setData(await api('/api/webapp/fantasy/teams'));
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, []);

  if (error) return <ErrorCard error={error} onRetry={load} />;
  if (!data) return <LoadingCard text="Загружаю составы участников..." />;

  if (!data.visible) {
    return (
      <section className="card fantasy-other-teams-card">
        <div className="rules-title-row">
          <h2>Составы участников</h2>
          <span>закрыто</span>
        </div>
        <p className="muted">{data.visibility?.reason || 'Составы откроются после старта тура/стадии.'}</p>
      </section>
    );
  }

  return (
    <section className="card fantasy-other-teams-card">
      <div className="rules-title-row">
        <h2>Составы участников</h2>
        <span>{data.teams?.length || 0}</span>
      </div>
      <div className="other-team-list">
        {(data.teams || []).map((entry) => {
          const team = entry.team;
          const isOpen = openUserId === entry.user.id;
          const starters = (team?.players || []).filter((item) => item.is_starter);
          const bench = (team?.players || []).filter((item) => !item.is_starter);

          return (
            <article key={entry.user.id} className="other-team-card">
              <button type="button" onClick={() => setOpenUserId(isOpen ? null : entry.user.id)}>
                <strong>{entry.user.display_name}{entry.user.is_current_user ? ' · это вы' : ''}</strong>
                <span>{team?.formation || '—'} · {pointsLabel(team?.points || 0)}</span>
                <b>{isOpen ? '−' : '+'}</b>
              </button>
              {isOpen && (
                <div className="other-team-body">
                  <h3>Основа</h3>
                  <div className="other-player-list">
                    {starters.map((item) => (
                      <div key={item.position_slot}>
                        <span>{item.player.team_flag}</span>
                        <strong>{item.player.name}{item.is_captain ? ' ©' : ''}</strong>
                        <small>{item.position_label} · {item.points || 0} очк.</small>
                        <PlayerInfoButton player={item.player} onInfo={onInfo} />
                      </div>
                    ))}
                  </div>
                  <h3>Запас</h3>
                  <div className="other-player-list">
                    {bench.map((item) => (
                      <div key={item.position_slot}>
                        <span>{item.player.team_flag}</span>
                        <strong>{item.player.name}</strong>
                        <small>{item.position_label} · {item.points || 0} очк.</small>
                        <PlayerInfoButton player={item.player} onInfo={onInfo} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
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
  const [infoPlayerId, setInfoPlayerId] = useState(null);
  const now = useNowTick();

  async function load() {
    setError(null);
    try {
      const [playersResult, teamResult] = await Promise.all([
        api('/api/webapp/fantasy/players?limit=5000'),
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
  const squadPositionLimits = rules?.squad_positions || FANTASY_SQUAD_POSITION_LIMITS;
  const positionCounts = selectedPlayers.reduce((acc, player) => {
    acc[player.position] = (acc[player.position] || 0) + 1;
    return acc;
  }, {});
  const positionIssueLabels = Object.entries(squadPositionLimits)
    .filter(([position, limit]) => (positionCounts[position] || 0) !== limit)
    .map(([position, limit]) => `${rules?.position_labels?.[position] || position}: ${positionCounts[position] || 0}/${limit}`);
  const squadPositionWarning = selectedCount === 15 && positionIssueLabels.length
    ? `Состав не соответствует классическим ограничениям по позициям: ${positionIssueLabels.join(', ')}. Нужно: 2 ВР, 5 ЗЩ, 5 ПЗ, 3 НП.`
    : '';
  const categoryLimits = rules?.category_limits || {};
  const maxFromOneTeam = rules?.max_from_one_team || 2;
  const deadlineText = formatDeadlineCountdown(roundState.deadline_at, now);
  const missingPlayersCount = Math.max(0, 15 - selectedCount);
  const validationItems = [
    ['Goalkeeper', 'ВР'],
    ['Defender', 'ЗЩ'],
    ['Midfielder', 'ПЗ'],
    ['Attacker', 'НП'],
  ].map(([position, shortLabel]) => {
    const count = positionCounts[position] || 0;
    const limit = squadPositionLimits[position] || 0;
    return {
      position,
      shortLabel,
      count,
      limit,
      ok: count === limit,
      empty: count === 0,
    };
  });
  const positionsReady = validationItems.every((item) => item.ok);
  const captainReady = Boolean(captainId);
  const squadReady = selectedCount === 15 && positionsReady && captainReady;
  const readinessTitle = squadReady
    ? 'Состав готов'
    : missingPlayersCount > 0
      ? `Нужно добрать ${missingPlayersCount}`
      : !captainReady
        ? 'Нужен капитан'
        : 'Проверьте лимиты';
  const readinessHint = squadReady
    ? 'Можно спокойно менять до дедлайна'
    : missingPlayersCount > 0
      ? 'Заполните основу и скамейку'
      : !captainReady
        ? 'Назначьте капитана в стартовом составе'
        : 'В заявке должны соблюдаться ограничения 2/5/5/3';
  const transferInfoText = roundState.free_transfers === null
    ? 'трансферы без ограничений'
    : `бесплатных трансферов: ${roundState.free_transfers}, лишний: -${roundState.extra_transfer_penalty}`;

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
      if (slot.position && player.position !== slot.position) return false;
      if (Object.values(nextSelected).some((selected) => selected.id === player.id)) return false;
      if ((nextTeamCounts[player.team_display_name] || 0) >= maxFromOneTeam) return false;

      const currentPositionCount = Object.values(nextSelected).filter((selected) => selected.position === player.position).length;
      if (currentPositionCount >= (squadPositionLimits[player.position] || 0)) return false;

      return true;
    }

    const orderedSlots = [...starterSlots, ...FANTASY_BENCH_SLOTS];

    for (const slot of orderedSlots) {
      let candidate = shuffled.find((player) => canPickPlayer(player, slot));

      // Fallback for bench: keep the team limit and uniqueness, but do not let category limits block filling the bench.
      if (!candidate && !isStarterSlot(slot)) {
        candidate = shuffled.find((player) => {
          if (slot.position && player.position !== slot.position) return false;
          if (Object.values(nextSelected).some((selected) => selected.id === player.id)) return false;
          if ((nextTeamCounts[player.team_display_name] || 0) >= maxFromOneTeam) return false;
          const currentPositionCount = Object.values(nextSelected).filter((selected) => selected.position === player.position).length;
          if (currentPositionCount >= (squadPositionLimits[player.position] || 0)) return false;
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
      if (squadPositionWarning) throw new Error(squadPositionWarning);
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
          <p>{selectedCount}/15 · до {maxFromOneTeam || 2} из сборной · капитан x2</p>
        </div>
        <div className="fantasy-points"><b>{points}</b><span>очков</span></div>
      </section>

      <section className="fantasy-deadline-card compact-deadline-card elevated-deadline-card">
        <div className="deadline-copy">
          <span>Дедлайн · {roundState.title || 'следующий тур'}</span>
          <small>{transferInfoText}</small>
        </div>
        <strong>{deadlineText}</strong>
      </section>

      <section className="fantasy-quick-status-grid">
        <article className={`fantasy-status-card ${squadReady ? 'ok' : 'warn'}`}>
          <div>
            <span>Статус состава</span>
            <strong>{readinessTitle}</strong>
            <small>{readinessHint}</small>
          </div>
          <b>{selectedCount}/15</b>
        </article>

        <article className={`fantasy-limits-card ${positionsReady ? 'ok' : ''}`}>
          <div className="fantasy-limits-head">
            <span>Лимиты заявки</span>
            <small>до {maxFromOneTeam} из сборной</small>
          </div>
          <div className="fantasy-limit-pills">
            {validationItems.map((item) => (
              <div key={item.position} className={`fantasy-limit-pill ${item.ok ? 'ok' : item.empty ? 'empty' : 'partial'}`}>
                <b>{item.shortLabel}</b>
                <span>{item.count}/{item.limit}</span>
              </div>
            ))}
            <div className="fantasy-limit-pill team-cap ok team-cap-pill">
              <b>СБ</b>
              <span>макс {maxFromOneTeam}</span>
            </div>
          </div>
        </article>
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
                  <PlayerInfoButton player={player} onInfo={(item) => setInfoPlayerId(item.id)} className="pitch-info" />
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
        {selectedCount < 15 && <button className="random-team-button" onClick={setRandomTeam}>случайный состав</button>}
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
                {player && <PlayerInfoButton player={player} onInfo={(item) => setInfoPlayerId(item.id)} className="bench-info" />}
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
        {squadPositionWarning && <p className="error-text fantasy-squad-warning">{squadPositionWarning}</p>}
        {error && <p className="error-text">{error.message}</p>}
        <button className="primary full" disabled={saving || rules.is_locked || Boolean(squadPositionWarning)} onClick={save}>
          {rules.is_locked ? 'Команда закрыта' : saving ? 'Сохраняю...' : 'Сохранить команду'}
        </button>
      </section>

      <OtherFantasyTeams onInfo={(player) => setInfoPlayerId(player.id)} />

      <section className="card fantasy-rules-card">
        <h2>Правила набора</h2>
        <ul className="nice-list">
          <li><b>Заявка:</b> 15 игроков — 2 ВР, 5 ЗЩ, 5 ПЗ, 3 НП.</li>
          <li><b>Основа:</b> 11 игроков по выбранной схеме.</li>
          <li>Капитан должен быть в основе, его очки удваиваются.</li>
          <li>Лимит сборной на текущей стадии: до {maxFromOneTeam} игроков.</li>
          <li>Ограничения по рейтингу FIFA отключены.</li>
        </ul>
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
          onInfo={(player) => setInfoPlayerId(player.id)}
          onClose={() => setPickerSlot(null)}
        />
      )}
      {infoPlayerId && <PlayerInfoModal playerId={infoPlayerId} onClose={() => setInfoPlayerId(null)} />}
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
  onInfo,
  onClose,
}) {
  const current = selectedBySlot[slot.slot];
  const isStarterSlot = Boolean(slot.isStarter);
  const [selectedPlayerId, setSelectedPlayerId] = useState('');

  const positionPlayers = players
    .filter((player) => !slot.position || player.position === slot.position)
    .sort((a, b) => positionOrder(a.position) - positionOrder(b.position) || a.team_display_name.localeCompare(b.team_display_name) || a.name.localeCompare(b.name));

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

    const squadLimits = rules?.squad_positions || FANTASY_SQUAD_POSITION_LIMITS;
    const currentPositionCount = Object.values(selectedBySlot)
      .filter(Boolean)
      .filter((selected) => selected.position === player.position && selected.id !== current?.id)
      .length;
    if (currentPositionCount >= (squadLimits[player.position] || 0)) return 'лимит позиции';

    const effectiveTeamCount = (teamCounts[player.team_display_name] || 0) - (current?.team_display_name === player.team_display_name ? 1 : 0);
    if (effectiveTeamCount >= (rules?.max_from_one_team || 2)) return 'лимит сборной';

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
        <p className="muted">Сначала выберите сборную, затем игрока. Для запасных доступны любые позиции в рамках лимита заявки.</p>

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

        {filterTeam && teamPlayers.length > 0 && (
          <div className="picker-player-list">
            {teamPlayers.map((player) => {
              const reason = disabledReason(player);
              return (
                <div key={player.id} className={reason ? 'disabled' : ''}>
                  <span>{player.team_flag}</span>
                  <strong>{player.name}</strong>
                  <small>{player.position_label} · {player.team_display_name}{reason ? ` · ${reason}` : ''}</small>
                  <PlayerInfoButton player={player} onInfo={onInfo} />
                  <button type="button" disabled={Boolean(reason)} onClick={() => onSelect(slot, player)}>Выбрать</button>
                </div>
              );
            })}
          </div>
        )}

        {current && (
          <div className="current-player-card fantasy-current-player">
            <span>{current.team_flag}</span>
            <strong>{current.name}</strong>
            <small>{current.team_display_name} · {current.position_label} · Г{current.fifa_category}</small>
            <PlayerInfoButton player={current} onInfo={onInfo} className="current-info" />
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

function Predictions({ onPredict, onForecast, tournamentPrediction, onTournamentPick, onTournamentParticipants, onOpenTournamentTeam, onOpenTournamentPlayer }) {
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
    <main className="screen-content predictions-screen">
      <div className="section-label">Мои прогнозы</div>
      <TournamentPredictionSummary
        tournamentPrediction={tournamentPrediction}
        onTournamentPick={onTournamentPick}
        onTournamentParticipants={onTournamentParticipants}
        onOpenTournamentTeam={onOpenTournamentTeam}
        onOpenTournamentPlayer={onOpenTournamentPlayer}
      />
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

function RatingMatchAnalytics({ analytics, leagueName = '' }) {
  const exactScores = analytics?.exact_scores || [];
  const outcomes = analytics?.outcomes || [];

  function AnalyticsList({ title, subtitle, iconName, rows, accentClass }) {
    return (
      <section className={`rating-analytics-card ${accentClass}`}>
        <div className="rating-analytics-card-head">
          <div className="rating-analytics-icon"><Icon name={iconName} /></div>
          <div>
            <h3>{title}</h3>
            <p>{subtitle}</p>
          </div>
          <span className="rating-analytics-count">Топ {rows.length || 0}</span>
        </div>
        {rows.length === 0 ? (
          <p className="rating-analytics-empty">Пока ни один матч не попал в этот рейтинг.</p>
        ) : (
          <div className="rating-analytics-list">
            {rows.map((match, index) => (
              <div className="rating-analytics-row" key={`${title}-${match.match_id}`}>
                <span className="rating-analytics-place">{index + 1}</span>
                <div className="rating-analytics-teams">
                  <span className="rating-analytics-team">
                    <TeamFlag code={match.home_flag_code} emoji={match.home_flag} name={match.home_team} size="mini" />
                    <b>{match.home_team}</b>
                  </span>
                  <strong className="rating-analytics-score">{match.score_home}:{match.score_away}</strong>
                  <span className="rating-analytics-team away">
                    <TeamFlag code={match.away_flag_code} emoji={match.away_flag} name={match.away_team} size="mini" />
                    <b>{match.away_team}</b>
                  </span>
                </div>
                <span className="rating-analytics-result">{match.count}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="rating-analytics-section">
      <div className="rating-analytics-head">
        <div>
          <div className="section-label">Аналитика матчей</div>
          <h2>Где в лиге лучше всего читали игру</h2>
          <p>{leagueName ? `Лига «${leagueName}»` : 'Выбранная лига'} · только завершенные матчи</p>
        </div>
      </div>
      <div className="rating-analytics-grid">
        <AnalyticsList
          title="Точные счета"
          subtitle="Больше всего попаданий на 3 очка"
          iconName="target"
          rows={exactScores}
          accentClass="exact"
        />
        <AnalyticsList
          title="Угаданные исходы"
          subtitle="Больше всего попаданий на 1 очко"
          iconName="rank"
          rows={outcomes}
          accentClass="outcome"
        />
      </div>
    </section>
  );
}


function participantPredictionClass(resultType) {
  return ['exact', 'outcome', 'miss', 'missing'].includes(resultType) ? resultType : 'miss';
}

function participantPointsLabel(value) {
  const points = Number(value || 0);
  if (points > 0) return `+${points}`;
  return String(points);
}

function ParticipantPredictionsModal({ participant, leagueId = null, leagueName = '', onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [resultFilter, setResultFilter] = useState(null);

  useEffect(() => {
    if (participant?.user_id) {
      trackAnalytics('participant_history_open', {
        screen: 'rating',
        properties: { participant_id: participant.user_id, league_id: leagueId || 0 },
      });
    }
    let active = true;
    setData(null);
    setError(null);
    setResultFilter(null);
    const params = new URLSearchParams();
    if (leagueId) params.set('league_id', String(leagueId));
    const suffix = params.toString() ? `?${params.toString()}` : '';

    api(`/api/webapp/table/participant/${participant.user_id}/predictions${suffix}`)
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err); });

    return () => { active = false; };
  }, [participant.user_id, leagueId]);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const rows = data?.rows || [];
  const summary = data?.summary || {};
  const displayName = data?.participant?.name || participant.name;
  const visibleRows = resultFilter
    ? rows.filter((item) => participantPredictionClass(item.result_type) === resultFilter)
    : rows;
  const activeFilterLabel = resultFilter === 'exact' ? 'точным счётом' : 'угаданным исходом';

  const toggleResultFilter = (filter) => {
    setResultFilter((current) => {
      const next = current === filter ? null : filter;
      trackAnalytics('participant_history_filter', {
        screen: 'rating',
        properties: { participant_id: participant.user_id, league_id: leagueId || 0, filter: next || 'all' },
      });
      return next;
    });
  };

  return (
    <div
      className="modal-backdrop participant-predictions-backdrop"
      role="presentation"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose?.(); }}
    >
      <section className="modal-card participant-predictions-modal" role="dialog" aria-modal="true" aria-label={`Прогнозы участника ${displayName}`}>
        <button type="button" className="modal-close" aria-label="Закрыть прогнозы участника" onClick={onClose}>×</button>
        <header className="participant-predictions-head">
          <div className="participant-predictions-avatar">{(displayName || '?').slice(0, 1).toUpperCase()}</div>
          <div>
            <span>Прогнозы участника</span>
            <h2>{displayName}</h2>
            <p>{leagueName ? `Лига «${leagueName}»` : 'Выбранная лига'} · завершенные матчи</p>
          </div>
          {participant.rank && <b className="participant-rank-badge">#{participant.rank}</b>}
        </header>

        {error && <div className="inline-error participant-predictions-error"><span>{error.message}</span></div>}
        {!error && !data && <LoadingCard text="Загружаю прогнозы..." />}

        {data && (
          <>
            <div className="participant-predictions-summary">
              <div><b>{pointsLabel(summary.match_points || 0)}</b><span>за матчи</span></div>
              <button
                type="button"
                className={`participant-predictions-summary-filter exact ${resultFilter === 'exact' ? 'active' : ''}`}
                aria-pressed={resultFilter === 'exact'}
                title={resultFilter === 'exact' ? 'Показать все прогнозы' : 'Показать только точные счета'}
                onClick={() => toggleResultFilter('exact')}
              >
                <b>{summary.exact_scores || 0}</b><span>точных</span>
              </button>
              <button
                type="button"
                className={`participant-predictions-summary-filter outcome ${resultFilter === 'outcome' ? 'active' : ''}`}
                aria-pressed={resultFilter === 'outcome'}
                title={resultFilter === 'outcome' ? 'Показать все прогнозы' : 'Показать только угаданные исходы'}
                onClick={() => toggleResultFilter('outcome')}
              >
                <b>{summary.outcomes || 0}</b><span>исходов</span>
              </button>
              <div><b>{summary.matches_count || 0}</b><span>матчей</span></div>
            </div>

            {rows.length === 0 ? (
              <DetailEmpty title="Завершенных матчей пока нет" text="Когда в лиге появятся сыгранные матчи, здесь будет история прогнозов участника." />
            ) : visibleRows.length === 0 ? (
              <DetailEmpty
                title={`Нет прогнозов с ${activeFilterLabel}`}
                text="Нажмите на выделенную плашку еще раз, чтобы показать всю историю."
              />
            ) : (
              <div className="participant-predictions-list">
                {visibleRows.map((item) => {
                  const hasPrediction = item.prediction_home !== null && item.prediction_home !== undefined;
                  const resultClass = participantPredictionClass(item.result_type);
                  const predictionText = hasPrediction ? `${item.prediction_home}:${item.prediction_away}` : '—';
                  const points = Number(item.points || 0);
                  return (
                    <article className={`participant-prediction-row matchup ${resultClass}`} key={item.match_id}>
                      <small className="participant-prediction-date">{compactDate(item.starts_at)}</small>
                      <div className="participant-prediction-team-stack home" title={item.home_team}>
                        <TeamFlag code={item.home_flag_code} emoji={item.home_flag} name={item.home_team} size="mini" />
                        <b>{item.home_team}</b>
                      </div>
                      <div className="participant-prediction-score-stack">
                        <strong className="participant-prediction-actual">{item.actual_home}:{item.actual_away}</strong>
                        <span className={`participant-prediction-forecast ${resultClass}`} title={item.result_label}>
                          {predictionText}
                        </span>
                      </div>
                      <div className="participant-prediction-team-stack away" title={item.away_team}>
                        <TeamFlag code={item.away_flag_code} emoji={item.away_flag} name={item.away_team} size="mini" />
                        <b>{item.away_team}</b>
                      </div>
                      <div className="participant-prediction-points-panel">
                        <b className={`participant-prediction-points ${points > 0 ? 'positive' : points < 0 ? 'negative' : ''}`}>
                          <span>{participantPointsLabel(points)}</span>
                          <small>{pointsLabel(Math.abs(points)).replace(/^\d+\s*/, '')}</small>
                        </b>
                        {item.advancement_points ? <small className="participant-prediction-advancement">проход {item.advancement_points > 0 ? '+' : ''}{item.advancement_points}</small> : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}


function Rating({ activeLeagueId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedParticipant, setSelectedParticipant] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    const params = new URLSearchParams();
    if (activeLeagueId) params.set('league_id', String(activeLeagueId));
    const suffix = params.toString() ? `?${params.toString()}` : '';
    api(`/api/webapp/table${suffix}`).then(setData).catch(setError);
  }, [activeLeagueId]);

  if (error) return <ErrorCard error={error} />;
  if (!data) return <LoadingCard />;

  const fatherRow = data.father_row;
  const sourceRows = fatherRow ? [...(data.rows || []), fatherRow] : [...(data.rows || [])];
  const rows = sourceRows
    .map((row) => ({
      ...row,
      display_points: row.points || 0,
    }))
    .sort((a, b) => (b.display_points - a.display_points) || ((b.exact_scores || 0) - (a.exact_scores || 0)))
    .map((row, index) => ({ ...row, display_rank: index + 1 }));

  return (
    <main className="screen-content rating-screen">
      <div className="section-label">Рейтинг участников</div>

      <div className="ranking-list compact-ranking-list">
        {rows.map((row) => {
          const canOpenParticipant = Boolean(row.user_id) && !row.is_father;
          const openParticipant = () => {
            if (canOpenParticipant) setSelectedParticipant({ ...row, rank: row.display_rank });
          };
          return (
          <div
            key={row.user_id || row.name}
            className={`ranking-row rating-rich-row ${row.is_current_user ? 'me' : ''} ${row.is_father ? 'father-ranking-row' : ''} ${canOpenParticipant ? 'rating-row-clickable' : ''}`}
            role={canOpenParticipant ? 'button' : undefined}
            tabIndex={canOpenParticipant ? 0 : undefined}
            aria-label={canOpenParticipant ? `Открыть прогнозы участника ${row.name}` : undefined}
            onClick={openParticipant}
            onKeyDown={(event) => {
              if (canOpenParticipant && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault();
                openParticipant();
              }
            }}
          >
            <div className="rating-main-line">
              <span className="rank">#{row.display_rank}</span>
              <div className="rating-player">
                <strong>{row.name}</strong>
                <small>
                  {row.is_father ? 'ИИ-прогнозы вне конкурса, но в общей гонке видны' : `Очки: ${row.points || 0} · Турнир: ${row.tournament_prediction_progress || '0/4'}`}
                </small>
              </div>
              <div className="rating-points-pill">
                {pointsLabel(row.display_points)}
              </div>
            </div>

            <div className="rating-metrics-grid">
              <div>
                <b>{row.match_predictions_finished_count ?? 0}</b>
                <span>по завершенным</span>
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
                <span>попаданий из {row.match_predictions_finished_count ?? row.accuracy_base ?? 0}</span>
              </div>
            </div>

            <div className="rating-foot-line">
              <span>Матчи: {row.match_predictions_progress || row.match_predictions_count || 0}</span>
              <span>Завершено: {row.match_predictions_finished_count || 0}</span>
              <span>{row.is_father ? 'ИИ-вне конкурса' : `Проход: +${row.advancement_plus || 0} / ${row.advancement_minus || 0}`}</span>
            </div>
          </div>
          );
        })}
      </div>

      <RatingMatchAnalytics
        analytics={data.match_analytics}
        leagueName={data.league?.name || ''}
      />

      {selectedParticipant && (
        <ParticipantPredictionsModal
          participant={selectedParticipant}
          leagueId={activeLeagueId}
          leagueName={data.league?.name || ''}
          onClose={() => setSelectedParticipant(null)}
        />
      )}
    </main>
  );
}




function formatLeagueActivityTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const diffMinutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 1) return 'только что';
  if (diffMinutes < 60) return `${diffMinutes} мин назад`;
  if (diffMinutes < 24 * 60) return `${Math.floor(diffMinutes / 60)} ч назад`;
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
}

function LeaguesScreen({ leaguesData, activeLeagueId, onLeagueChange, onLeaguesChanged }) {
  const leagues = leaguesData?.leagues || [];
  const activeLeague = leagues.find((league) => Number(league.id) === Number(activeLeagueId));
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [managedLeagueId, setManagedLeagueId] = useState(null);
  const [membersData, setMembersData] = useState(null);
  const [membersLoading, setMembersLoading] = useState(false);
  const [memberActionBusy, setMemberActionBusy] = useState('');
  const [leagueChatIds, setLeagueChatIds] = useState({});
  const [createOpen, setCreateOpen] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);
  const [activityData, setActivityData] = useState([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState(null);

  async function loadLeagueActivity(leagueId = activeLeagueId) {
    if (leagueId) trackAnalytics('league_activity_open', { screen: 'leagues', properties: { league_id: leagueId } });
    if (!leagueId) {
      setActivityData([]);
      return;
    }
    setActivityLoading(true);
    setActivityError(null);
    try {
      const result = await api(`/api/webapp/leagues/${leagueId}/activity?limit=30`);
      setActivityData(result.events || []);
    } catch (err) {
      setActivityData([]);
      setActivityError(err);
    } finally {
      setActivityLoading(false);
    }
  }

  useEffect(() => {
    loadLeagueActivity(activeLeagueId);
  }, [activeLeagueId]);

  async function createLeague(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage('');
    try {
      const result = await api('/api/webapp/leagues', {
        method: 'POST',
        body: JSON.stringify({ name, description }),
      });
      setName('');
      setDescription('');
      setCreateOpen(false);
      await onLeaguesChanged?.();
      onLeagueChange?.(result.league.id);
      setManagedLeagueId(result.league.id);
      trackAnalytics('league_create', { screen: 'leagues', properties: { league_id: result.league.id } });
      setMessage(`Лига «${result.league.name}» создана`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function joinLeague(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage('');
    try {
      const result = await api('/api/webapp/leagues/join', {
        method: 'POST',
        body: JSON.stringify({ invite_code: inviteCode }),
      });
      setInviteCode('');
      setJoinOpen(false);
      await onLeaguesChanged?.();
      onLeagueChange?.(result.league.id);
      trackAnalytics('league_join', { screen: 'leagues', properties: { league_id: result.league.id } });
      setMessage(`Вы вступили в лигу «${result.league.name}»`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function copyInvite(value) {
    try {
      await navigator.clipboard?.writeText(value);
      setMessage('Приглашение скопировано');
    } catch {
      setMessage(`Код приглашения: ${value}`);
    }
  }

  async function loadMembers(leagueId = managedLeagueId) {
    if (!leagueId) return null;
    setMembersLoading(true);
    try {
      const result = await api(`/api/webapp/leagues/${leagueId}/members`);
      setMembersData(result);
      return result;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      setMembersLoading(false);
    }
  }

  async function toggleManageLeague(league) {
    if (!league?.id) return;
    if (Number(managedLeagueId) === Number(league.id)) {
      setManagedLeagueId(null);
      setMembersData(null);
      return;
    }
    setManagedLeagueId(league.id);
    setMembersData(null);
    setLeagueChatIds((prev) => ({ ...prev, [league.id]: league.chat_id || '' }));
    await loadMembers(league.id);
  }

  async function changeMemberRole(leagueId, member, role) {
    if (!leagueId || !member || member.role === role) return;
    const busyKey = `${leagueId}:${member.user_id}:${role}`;
    setMemberActionBusy(busyKey);
    setError(null);
    try {
      await api(`/api/webapp/leagues/${leagueId}/members/${member.user_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      });
      await loadMembers(leagueId);
      await onLeaguesChanged?.();
      await loadLeagueActivity(leagueId);
    } catch (err) {
      setError(err);
    } finally {
      setMemberActionBusy('');
    }
  }

  async function removeMember(leagueId, member) {
    if (!leagueId || !member) return;
    if (!window.confirm(`Исключить «${member.display_name || member.username || 'участника'}» из лиги?`)) return;
    const busyKey = `${leagueId}:${member.user_id}:remove`;
    setMemberActionBusy(busyKey);
    setError(null);
    try {
      await api(`/api/webapp/leagues/${leagueId}/members/${member.user_id}`, { method: 'DELETE' });
      await loadMembers(leagueId);
      await onLeaguesChanged?.();
    } catch (err) {
      setError(err);
    } finally {
      setMemberActionBusy('');
    }
  }

  async function deactivateLeagueAction(league) {
    if (!league?.id) return;
    if (!window.confirm(`Деактивировать лигу «${league.name}»? Участники больше не увидят ее в рейтинге и матч-центре.`)) return;
    const busyKey = `${league.id}:deactivate`;
    setMemberActionBusy(busyKey);
    setError(null);
    setMessage('');
    try {
      await api(`/api/webapp/leagues/${league.id}/deactivate`, { method: 'POST' });
      setManagedLeagueId(null);
      setMembersData(null);
      const result = await onLeaguesChanged?.();
      const nextLeague = result?.default_league_id || result?.leagues?.[0]?.id || null;
      if (Number(activeLeagueId) === Number(league.id)) {
        onLeagueChange?.(nextLeague);
      }
      setMessage(`Лига «${league.name}» деактивирована`);
    } catch (err) {
      setError(err);
    } finally {
      setMemberActionBusy('');
    }
  }

  async function saveLeagueChatId(league) {
    if (!league?.id) return;
    const busyKey = `${league.id}:chat`;
    setMemberActionBusy(busyKey);
    setError(null);
    setMessage('');
    try {
      const chatId = leagueChatIds[league.id] || '';
      await api(`/api/webapp/leagues/${league.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ chat_id: chatId.trim() || null }),
      });
      await onLeaguesChanged?.();
      setMessage(chatId.trim() ? 'Chat ID лиги сохранен' : 'Chat ID лиги очищен');
    } catch (err) {
      setError(err);
    } finally {
      setMemberActionBusy('');
    }
  }

  function memberRoleText(member) {
    if (member.is_owner || member.role === 'owner') return 'владелец';
    if (member.role === 'admin') return 'админ';
    return 'участник';
  }

  function renderMembersManager(league) {
    if (Number(managedLeagueId) !== Number(league.id)) return null;
    const members = membersData?.members || [];
    return (
      <div className="league-management-panel">
        <div className="league-chat-settings">
          <label>
            <span>Chat ID лиги для уведомлений</span>
            <input
              value={leagueChatIds[league.id] ?? league.chat_id ?? ''}
              onChange={(event) => setLeagueChatIds((prev) => ({ ...prev, [league.id]: event.target.value }))}
              placeholder="например -1001234567890"
            />
          </label>
          <button type="button" className="secondary small" onClick={() => saveLeagueChatId(league)} disabled={memberActionBusy === `${league.id}:chat`}>
            {memberActionBusy === `${league.id}:chat` ? 'Сохраняю…' : 'Сохранить chat_id'}
          </button>
          <p className="muted small">Если указать Telegram chat_id группы, уведомления по событиям этой лиги будут приходить туда.</p>
        </div>
        <div className="subsection-title compact">
          <h3>Участники</h3>
          <button type="button" className="secondary small" onClick={() => loadMembers(league.id)} disabled={membersLoading}>Обновить</button>
        </div>
        {membersLoading && <p className="muted small">Загружаю участников…</p>}
        {!membersLoading && members.length === 0 && <p className="muted small">Активных участников пока нет.</p>}
        <div className="league-members-list">
          {members.map((member) => {
            const isActive = member.status === 'active';
            const isProtected = member.is_owner || member.role === 'owner';
            return (
              <article key={`${league.id}-${member.user_id}`} className={`league-member-row ${!isActive ? 'inactive' : ''}`}>
                <div className="league-member-main">
                  <strong>{member.display_name || member.username || 'Участник'}</strong>
                  <small>
                    {member.username ? `@${member.username} · ` : ''}{memberRoleText(member)}{!isActive ? ` · ${member.status}` : ''}
                  </small>
                </div>
                {isActive && (
                  <div className="league-member-actions">
                    {!isProtected && member.role !== 'admin' && (
                      <button type="button" onClick={() => changeMemberRole(league.id, member, 'admin')} disabled={memberActionBusy === `${league.id}:${member.user_id}:admin`}>Сделать админом</button>
                    )}
                    {!isProtected && member.role === 'admin' && (
                      <button type="button" onClick={() => changeMemberRole(league.id, member, 'member')} disabled={memberActionBusy === `${league.id}:${member.user_id}:member`}>Снять админа</button>
                    )}
                    {!isProtected && (
                      <button type="button" className="danger" onClick={() => removeMember(league.id, member)} disabled={memberActionBusy === `${league.id}:${member.user_id}:remove`}>Исключить</button>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
        {league.can_deactivate && (
          <button type="button" className="danger wide" onClick={() => deactivateLeagueAction(league)} disabled={memberActionBusy === `${league.id}:deactivate`}>
            Деактивировать лигу
          </button>
        )}
      </div>
    );
  }

  return (
    <main className="screen-content leagues-screen">
      <div className="section-label">Лиги</div>

      <section className="league-active-compact" aria-label="Выбранная лига">
        <strong>{activeLeague?.name || 'Не выбрана'}</strong>
      </section>

      {message && <div className="success-card">{message}</div>}
      {error && <ErrorCard error={error} onRetry={() => setError(null)} />}

      <section className="leagues-list-card">
        <div className="subsection-title">
          <h2>Мои лиги</h2>
          <span>{leagues.length}</span>
        </div>
        {leagues.length === 0 ? (
          <EmptyState iconName="team" title="Лиг пока нет" text="После одобрения администратором здесь появится «Отец прогнозов» или приглашенные лиги." />
        ) : (
          <div className="leagues-list">
            {leagues.map((league) => (
              <article key={league.id} className={`league-row-card ${Number(league.id) === Number(activeLeagueId) ? 'active' : ''}`}>
                <button
                  type="button"
                  className="league-row-main"
                  onClick={() => {
                    if (Number(league.id) === Number(activeLeagueId)) return;
                    onLeagueChange?.(league.id);
                    trackAnalytics('league_selected', { screen: 'leagues', properties: { league_id: Number(league.id) || 0, entry_point: 'my_leagues' } });
                  }}
                  aria-pressed={Number(league.id) === Number(activeLeagueId)}
                >
                  <div>
                    <strong>{league.name}</strong>
                    <small>{league.members_count || 0} участник{(league.members_count || 0) === 1 ? '' : 'ов'} · {league.league_type === 'system' ? 'системная' : 'частная'}{league.role ? ` · ${league.role === 'owner' ? 'владелец' : league.role === 'admin' ? 'админ' : 'участник'}` : ''}{league.scoring_start_at ? ` · счет с ${formatDateTime(league.scoring_start_at)}` : ''}{league.chat_id ? ' · чат подключен' : ''}</small>
                  </div>
                  {Number(league.id) === Number(activeLeagueId) ? <span className="active-league-pill">активна</span> : <span className="league-row-select-hint">Выбрать</span>}
                </button>
                {league.can_manage && league.invite_code && (
                  <div className="invite-tools">
                    <code>{league.invite_code}</code>
                    <button type="button" onClick={() => copyInvite(league.invite_url || league.invite_code)}>Скопировать приглашение</button>
                  </div>
                )}
                {league.can_manage && (
                  <button type="button" className="league-manage-toggle" onClick={() => toggleManageLeague(league)}>
                    {Number(managedLeagueId) === Number(league.id) ? 'Свернуть управление' : 'Управлять лигой'}
                  </button>
                )}
                {renderMembersManager(league)}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className={`league-form-card collapsible ${createOpen ? 'open' : ''}`}>
        <button type="button" className="league-form-toggle" onClick={() => setCreateOpen((value) => !value)} aria-expanded={createOpen}>
          <span><b>Создать лигу</b><small>Новая таблица и приглашение для друзей</small></span>
          <span className="collapse-chevron">{createOpen ? '−' : '+'}</span>
        </button>
        {createOpen && (
          <form onSubmit={createLeague} className="league-form">
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Название лиги" maxLength={80} autoFocus />
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Описание, необязательно" maxLength={500} rows={3} />
            <button type="submit" disabled={busy || name.trim().length < 2}>{busy ? 'Сохраняю…' : 'Создать'}</button>
          </form>
        )}
      </section>

      <section className={`league-form-card collapsible ${joinOpen ? 'open' : ''}`}>
        <button type="button" className="league-form-toggle" onClick={() => setJoinOpen((value) => !value)} aria-expanded={joinOpen}>
          <span><b>Вступить по коду</b><small>Подключиться к лиге друзей</small></span>
          <span className="collapse-chevron">{joinOpen ? '−' : '+'}</span>
        </button>
        {joinOpen && (
          <form onSubmit={joinLeague} className="league-form league-join-form">
            <input value={inviteCode} onChange={(event) => setInviteCode(event.target.value)} placeholder="Код приглашения" autoFocus />
            <button type="submit" disabled={busy || inviteCode.trim().length < 3}>{busy ? 'Проверяю…' : 'Вступить'}</button>
          </form>
        )}
      </section>

      <section className="league-activity-card">
        <div className="subsection-title">
          <div>
            <h2>История действий</h2>
            <p className="muted small">{activeLeague?.name || 'Выбранная лига'}</p>
          </div>
          <button type="button" className="secondary small" onClick={() => loadLeagueActivity()} disabled={activityLoading}>Обновить</button>
        </div>
        {activityLoading && <p className="muted small">Загружаю действия участников…</p>}
        {!activityLoading && activityError && <ErrorCard error={activityError} onRetry={() => loadLeagueActivity()} />}
        {!activityLoading && !activityError && activityData.length === 0 && (
          <EmptyState iconName="clock" title="Пока тихо" text="Здесь будут появляться прогнозы, вступления в лигу и другие действия ее участников." />
        )}
        {!activityLoading && !activityError && activityData.length > 0 && (
          <div className="league-activity-list">
            {activityData.map((entry) => (
              <article key={entry.id} className="league-activity-row">
                <span className="league-activity-icon" aria-hidden="true">{entry.icon || '•'}</span>
                <div className="league-activity-body">
                  <strong>{entry.actor_name}</strong>
                  <span>{entry.title}</span>
                  {entry.detail && <small>{entry.detail}</small>}
                </div>
                <time>{formatLeagueActivityTime(entry.created_at)}</time>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function AdminAnalytics() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await api(`/api/webapp/admin/analytics?days=${days}`));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    trackAnalytics('analytics_open', { screen: 'admin', properties: { tab: 'analytics' } });
  }, []);

  useEffect(() => { load(); }, [days]);

  const summary = data?.summary || {};
  const screens = data?.screens || [];
  const events = data?.events || [];
  const features = data?.features || [];
  const funnel = data?.funnel || [];
  const activity = data?.activity || [];
  const recent = data?.recent || [];
  const maxScreenEvents = Math.max(1, ...screens.map((item) => item.events || 0));
  const maxFeatureUsers = Math.max(1, ...features.map((item) => item.users || 0));
  const maxActivityEvents = Math.max(1, ...activity.map((item) => item.events || 0));

  const formatDay = (value) => {
    if (!value) return '';
    const date = new Date(`${value}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
  };

  return (
    <section className="admin-analytics" aria-label="Продуктовая аналитика">
      <section className="card admin-analytics-intro">
        <div>
          <div className="section-label">Продуктовая аналитика</div>
          <h2>Что востребовано в приложении</h2>
          <p className="muted">Данные собираются только после установки этой версии. В статистику не попадают Telegram ID, username, фактические счета и тексты прогнозов.</p>
        </div>
        <div className="admin-analytics-period" role="group" aria-label="Период аналитики">
          {[7, 30].map((value) => (
            <button key={value} type="button" className={days === value ? 'active' : ''} onClick={() => setDays(value)}>{value} дней</button>
          ))}
        </div>
      </section>

      {loading && !data && <LoadingCard text="Собираю аналитику..." />}
      {error && <ErrorCard error={error} onRetry={load} />}

      {data && (
        <>
          <section className="admin-analytics-summary-grid">
            <div><b>{summary.active_users || 0}</b><span>активных пользователей</span></div>
            <div><b>{summary.app_opens || 0}</b><span>открытий приложения</span></div>
            <div><b>{summary.predictions_saved || 0}</b><span>сохраненных прогнозов</span></div>
            <div><b>{summary.prediction_conversion || 0}%</b><span>матч → прогноз</span></div>
          </section>

          <section className="card admin-analytics-card">
            <div className="admin-card-head">
              <div><h2>Воронка прогнозов</h2><p>Уникальные пользователи за выбранный период</p></div>
            </div>
            <div className="analytics-funnel">
              {funnel.map((step) => (
                <div key={step.label} className="analytics-funnel-row">
                  <div><strong>{step.label}</strong><small>{step.value || 0} пользователей</small></div>
                  <div className="analytics-funnel-track"><span style={{ width: `${Math.max(4, step.percent || 0)}%` }} /></div>
                  <b>{step.percent || 0}%</b>
                </div>
              ))}
            </div>
          </section>

          <section className="card admin-analytics-card">
            <div className="admin-card-head"><div><h2>Популярные разделы</h2><p>Просмотры экранов и уникальные пользователи</p></div></div>
            {screens.length ? <div className="analytics-bars">{screens.map((item) => <div key={item.key} className="analytics-bar-row"><div><strong>{item.label}</strong><small>{item.users || 0} польз.</small></div><div className="analytics-bar-track"><span style={{ width: `${Math.max(3, Math.round((item.events || 0) * 100 / maxScreenEvents))}%` }} /></div><b>{item.events || 0}</b></div>)}</div> : <p className="muted">Пока нет просмотров разделов за этот период.</p>}
          </section>

          <section className="card admin-analytics-card">
            <div className="admin-card-head"><div><h2>Функции</h2><p>Какими возможностями пользовались чаще</p></div></div>
            {features.length ? <div className="analytics-bars">{features.map((item) => <div key={item.label} className="analytics-bar-row"><div><strong>{item.label}</strong><small>{item.users || 0} польз.</small></div><div className="analytics-bar-track"><span style={{ width: `${Math.max(3, Math.round((item.users || 0) * 100 / maxFeatureUsers))}%` }} /></div><b>{item.events || 0}</b></div>)}</div> : <p className="muted">Пока нет данных по функциям.</p>}
          </section>

          <section className="card admin-analytics-card">
            <div className="admin-card-head"><div><h2>Активность по дням</h2><p>События и активные пользователи</p></div></div>
            {activity.length ? <div className="analytics-days">{activity.map((item) => <div key={item.date} className="analytics-day"><div className="analytics-day-bar"><span style={{ height: `${Math.max(6, Math.round((item.events || 0) * 100 / maxActivityEvents))}%` }} /></div><strong>{item.events || 0}</strong><small>{formatDay(item.date)}</small></div>)}</div> : <p className="muted">Пока нет активности за выбранный период.</p>}
          </section>

          <section className="card admin-analytics-card">
            <div className="admin-card-head"><div><h2>Последние действия</h2><p>Можно увидеть, кто и что открывал</p></div><button className="secondary small" type="button" onClick={load} disabled={loading}>{loading ? 'Обновляю…' : 'Обновить'}</button></div>
            {recent.length ? <div className="analytics-recent-list">{recent.map((item) => <article key={item.id} className="analytics-recent-row"><div><strong>{item.user_name}</strong><span>{item.label}</span>{item.screen && <small>{item.screen}</small>}</div><time>{formatDateTime(item.created_at)}</time></article>)}</div> : <p className="muted">Пока нет записанных действий.</p>}
          </section>

          <section className="card admin-analytics-card analytics-events-card">
            <div className="admin-card-head"><div><h2>Топ действий</h2><p>Сводка событий за период</p></div></div>
            <div className="analytics-event-chips">{events.map((item) => <div key={item.key}><b>{item.events || 0}</b><span>{item.label}</span><small>{item.users || 0} польз.</small></div>)}</div>
          </section>
        </>
      )}
    </section>
  );
}


function AdminPanel() {
  const [adminSection, setAdminSection] = useState('overview');
  const [data, setData] = useState(null);
  const [selectedMatchId, setSelectedMatchId] = useState('');
  const [scoreHome, setScoreHome] = useState('');
  const [scoreAway, setScoreAway] = useState('');
  const [winnerSide, setWinnerSide] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      const result = await api('/api/webapp/admin/overview');
      setData(result);
      if (!selectedMatchId && result.matches?.length) {
        setSelectedMatchId(String(result.matches[0].id));
      }
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, []);


  const matches = data?.matches || [];
  const selectedMatch = matches.find((match) => String(match.id) === String(selectedMatchId));

  async function runAction(action) {
    setBusy(true);
    setError(null);
    setMessage('');

    try {
      const result = await action();
      setMessage(result.message || JSON.stringify(result, null, 2));
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function saveManualResult() {
    if (!selectedMatchId) throw new Error('Выберите матч.');
    if (scoreHome === '' || scoreAway === '') throw new Error('Укажите счет.');

    return api(`/api/webapp/admin/matches/${selectedMatchId}/result`, {
      method: 'POST',
      body: JSON.stringify({
        score_home: Number(scoreHome),
        score_away: Number(scoreAway),
        winner_side: winnerSide || null,
      }),
    });
  }

  async function syncSelectedResult() {
    if (!selectedMatchId) throw new Error('Выберите матч.');
    return api(`/api/webapp/admin/matches/${selectedMatchId}/sync-result`, { method: 'POST' });
  }

  async function syncAllResults() {
    return api('/api/webapp/admin/sync-results', { method: 'POST' });
  }

  async function syncFantasyStats() {
    return api('/api/webapp/admin/fantasy/sync-player-stats', { method: 'POST' });
  }

  async function sendTestPush() {
    return api('/api/webapp/admin/push/test', { method: 'POST' });
  }


  async function toggleGlobalSetting(key, checked) {
    const result = await api(`/api/webapp/admin/settings/${key}`, {
      method: 'POST',
      body: JSON.stringify({ value: checked ? 'true' : 'false' }),
    });

    setData((current) => ({
      ...current,
      notification_settings: {
        ...(current?.notification_settings || {}),
        [key]: result.value,
      },
    }));
  }

  if (error && !data) return <ErrorCard error={error} onRetry={load} />;
  if (!data) return <LoadingCard text="Открываю админку..." />;

  return (
    <main className="screen-content admin-screen">
      <div className="section-label">Администрирование</div>
      <nav className="admin-section-tabs" aria-label="Разделы администрирования">
        <button type="button" className={adminSection === 'overview' ? 'active' : ''} onClick={() => setAdminSection('overview')}>Управление</button>
        <button type="button" className={adminSection === 'analytics' ? 'active' : ''} onClick={() => setAdminSection('analytics')}>Аналитика</button>
      </nav>

      {adminSection === 'analytics' ? <AdminAnalytics /> : <>
      <section className="admin-summary-grid">
        <div><b>{data.summary?.matches_total || 0}</b><span>матчей</span></div>
        <div><b>{data.summary?.finished || 0}</b><span>завершено</span></div>
        <div><b>{data.summary?.ready_for_api_sync || 0}</b><span>к синхронизации</span></div>
        {FANTASY_UI_ENABLED && <div><b>{data.summary?.fantasy_stat_rows || 0}</b><span>строк fantasy</span></div>}
        <div><b>{data.summary?.active_push_subscriptions || 0}</b><span>push-подписок</span></div>
        <div><b>{data.summary?.push_users_count || 0}</b><span>push-пользователей</span></div>
      </section>

      <section className="card admin-card">
        <h2>Матч</h2>
        <select value={selectedMatchId} onChange={(event) => setSelectedMatchId(event.target.value)}>
          {matches.map((match) => (
            <option key={match.id} value={match.id}>
              #{match.id} {match.home_team} — {match.away_team} {match.is_finished ? `(${match.score_home}:${match.score_away})` : ''}
            </option>
          ))}
        </select>
        {selectedMatch && <p className="muted small">{formatDateTime(selectedMatch.starts_at)} · {selectedMatch.status_short || 'статус не задан'} · fixture {selectedMatch.external_fixture_id || '—'}</p>}
      </section>

      <section className="card admin-card">
        <h2>1. Ручное выставление результата</h2>
        <div className="admin-score-row">
          <input type="number" min="0" value={scoreHome} onChange={(event) => setScoreHome(event.target.value)} placeholder="Хозяева" />
          <input type="number" min="0" value={scoreAway} onChange={(event) => setScoreAway(event.target.value)} placeholder="Гости" />
          <select value={winnerSide} onChange={(event) => setWinnerSide(event.target.value)}>
            <option value="">winner не нужен</option>
            <option value="home">прошли хозяева</option>
            <option value="away">прошли гости</option>
          </select>
        </div>
        <button className="primary full" disabled={busy} onClick={() => runAction(saveManualResult)}>Сохранить результат</button>
      </section>

      <section className="card admin-card">
        <h2>2. Обновление результата через API-Football</h2>
        <div className="admin-actions-row">
          <button disabled={busy} onClick={() => runAction(syncSelectedResult)}>Обновить выбранный матч</button>
          <button disabled={busy} onClick={() => runAction(syncAllResults)}>Обновить все сыгранные</button>
        </div>
      </section>

      {FANTASY_UI_ENABLED && (
        <section className="card admin-card">
          <h2>3. Статистика игроков Fantasy</h2>
          <p className="muted">Загружает статистику игроков по завершенным матчам и пересчитывает Fantasy-очки.</p>
          <button className="primary full" disabled={busy} onClick={() => runAction(syncFantasyStats)}>Обновить статистику игроков</button>
        </section>
      )}

      <section className="card admin-card">
        <h2>4. Push-уведомления</h2>
        <p className="muted">Отправляет тестовое push-уведомление на текущую web/PWA-подписку администратора.</p>
        <div className="admin-actions-row">
          <button className="primary" disabled={busy} onClick={() => runAction(sendTestPush)}>Отправить тестовое push-уведомление</button>
        </div>
        <p className="muted small">Активных подписок: {data.summary?.active_push_subscriptions || 0}; пользователей с push: {data.summary?.push_users_count || 0}.</p>
      </section>

      <section className="card admin-card">
        <h2>5. Напоминания и уведомления</h2>
        <div className="notification-list">
          {(data.notification_options || []).map((option) => {
            const settingKey = `${option.key}_enabled`;
            const value = data.notification_settings?.[settingKey];
            return (
              <label className="notification-row" key={settingKey}>
                <input
                  type="checkbox"
                  checked={String(value) === 'true'}
                  onChange={(event) => toggleGlobalSetting(settingKey, event.target.checked)}
                />
                <span />
                <b>{option.title}</b>
                <small>{String(value) === 'true' ? 'включено для всех' : 'выключено глобально'} · {option.description}</small>
              </label>
            );
          })}
        </div>
      </section>

      {error && <section className="card error-card"><p>{error.message}</p></section>}
      {message && <section className="card admin-result-card"><pre>{message}</pre></section>}
      </>}
    </main>
  );
}


function NotificationSettingsCard({ embedded = false }) {
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      setData(await api('/api/webapp/notifications/settings'));
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, []);

  async function toggle(key, value) {
    const nextSettings = { ...(data?.settings || {}), [key]: value };
    setData((current) => ({ ...current, settings: nextSettings }));
    setSaving(true);
    setError(null);

    try {
      const result = await api('/api/webapp/notifications/settings', {
        method: 'POST',
        body: JSON.stringify({ settings: nextSettings }),
      });
      setData(result);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  const content = (
    <>
      {error && <p className="error-text">{error.message}</p>}
      {!data && !error ? <LoadingCard text="Загружаю настройки уведомлений..." /> : (
        <div className="notification-list">
          {(data?.options || []).map((option) => (
            <label className="notification-row" key={option.key}>
              <input
                type="checkbox"
                checked={Boolean(data?.settings?.[option.key])}
                onChange={(event) => toggle(option.key, event.target.checked)}
              />
              <span />
              <b>{option.title}</b>
              <small>{option.description}</small>
            </label>
          ))}
        </div>
      )}
    </>
  );

  if (embedded) return content;

  return (
    <section className="card notification-settings-card">
      <div className="profile-section-head">
        <h2>Уведомления</h2>
        <span>{saving ? 'сохраняю' : 'настроено'}</span>
      </div>
      {content}
    </section>
  );
}


function CollapsibleProfileSection({ title, meta, defaultOpen = true, children, className = '' }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={`card profile-collapsible-card ${className} ${open ? 'open' : 'closed'}`}>
      <button className="profile-collapse-head profile-section-head" type="button" onClick={() => setOpen(!open)}>
        <h2>{title}</h2>
        <span>{meta}</span>
        <b>{open ? '−' : '+'}</b>
      </button>
      {open && <div className="profile-collapse-body">{children}</div>}
    </section>
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
  const pointsBreakdown = (profile.points_breakdown || []).filter((item) => item.key !== 'fantasy');
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

      <CollapsibleProfileSection title="Настройки" meta={appTheme === 'light' ? 'светлая' : 'темная'}>
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
        <PwaAccessCard />
      </CollapsibleProfileSection>

      <CollapsibleProfileSection title="Откуда очки" meta={pointsLabel(summary.points || 0)}>
        <div className="points-breakdown">
          {pointsBreakdown.map((item) => (
            <div key={item.key} className="points-row">
              <i><Icon name={item.icon} /></i>
              <span>{item.title}</span>
              <b>{pointsLabel(item.points)}</b>
              <em style={{ width: `${Math.min(100, Math.max(4, item.points || 0))}%` }} />
            </div>
          ))}
        </div>
      </CollapsibleProfileSection>

      <CollapsibleProfileSection
        title="Статистика"
        meta={`${summary.total_predictions || 0} ${pluralRu(summary.total_predictions || 0, 'прогноз', 'прогноза', 'прогнозов')}`}
      >
        <div className="stats-grid">
          <div><b>{summary.match_points || 0}</b><span>очки за матчи</span></div>
          <div><b>{summary.tournament_points || 0}</b><span>очки за турнир</span></div>
          <div><b>{summary.exact_scores || 0}</b><span>точные счета</span></div>
          <div><b>{summary.outcomes || 0}</b><span>исходы</span></div>
          <div><b>{summary.favorite_score || '—'}</b><span>любимый счет</span></div>
          <div><b>{summary.missing_predictions || 0}</b><span>ждут прогноза</span></div>
        </div>
      </CollapsibleProfileSection>

      <CollapsibleProfileSection title="Достижения" meta={`${earnedBadges.length}/${badges.length}`}>
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
      </CollapsibleProfileSection>

      <CollapsibleProfileSection title="Прогнозы на турнир" meta={tournament ? '4/4' : '0/4'}>
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
      </CollapsibleProfileSection>

      <CollapsibleProfileSection title="Уведомления" meta="подписки" className="notification-settings-card">
        <NotificationSettingsCard embedded />
      </CollapsibleProfileSection>

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
    trackAnalytics('resource_open', { screen: 'resources', properties: { resource: 'fact' } });
    const result = await api('/api/webapp/facts/random');
    setFact(result.fact?.text || '');
  }

  async function loadArchive() {
    trackAnalytics('resource_open', { screen: 'resources', properties: { resource: 'archive' } });
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
        <button className="resource-quick-card father" onClick={() => {
          const next = !openFather;
          setOpenFather(next);
          if (next) trackAnalytics('resource_open', { screen: 'resources', properties: { resource: 'father_forecast' } });
        }}>
          <span>🤖</span>
          <strong>Прогноз Отца</strong>
          <small>итоги турнира</small>
        </button>
        <button className="resource-quick-card scorers" onClick={() => {
          const next = !openHelp;
          setOpenHelp(next);
          if (next) trackAnalytics('resource_open', { screen: 'resources', properties: { resource: 'scorer_help' } });
        }}>
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
            <button key={item.title} onClick={() => {
              trackAnalytics('resource_open', { screen: 'resources', properties: { resource: 'external_link' } });
              tg?.openLink ? tg.openLink(item.url) : window.open(item.url, '_blank');
            }}>
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
  const updateInfo = usePwaUpdateCheck();
  const [tab, setTab] = useState('matches');
  const [appTheme, setAppTheme] = useState(() => localStorage.getItem('ff-app-theme') || 'light');
  const [leaguesData, setLeaguesData] = useState({ leagues: [], default_league_id: null });
  const [activeLeagueId, setActiveLeagueIdState] = useState(() => Number(localStorage.getItem('ff_active_league_id') || 0) || null);
  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState(null);
  const [predictionMatch, setPredictionMatch] = useState(null);
  const [forecastMatch, setForecastMatch] = useState(null);
  const [tournamentPickField, setTournamentPickField] = useState(null);
  const [tournamentPredictionsOpen, setTournamentPredictionsOpen] = useState(false);
  const [tournamentPrediction, setTournamentPrediction] = useState(null);
  const [homeTournamentTeamId, setHomeTournamentTeamId] = useState(null);
  const [homeTournamentPlayerId, setHomeTournamentPlayerId] = useState(null);
  const [homeTournamentMatch, setHomeTournamentMatch] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [rulesOpen, setRulesOpen] = useState(false);
  const hasBrowserSession = Boolean(getWebSessionToken());

  useEffect(() => {
    if (isTelegramMode() || hasBrowserSession) {
      trackAnalytics('app_open', { screen: 'matches', properties: { entry_point: 'launch' } });
    }
  }, [hasBrowserSession]);

  useEffect(() => {
    if (isTelegramMode() || hasBrowserSession) {
      trackAnalytics('screen_view', { screen: tab, properties: { league_id: activeLeagueId || 0 } });
    }
  }, [tab, activeLeagueId, hasBrowserSession]);

  useEffect(() => {
    localStorage.setItem('ff-app-theme', appTheme);
  }, [appTheme]);

  async function loadDashboard() {
    try {
      const dashboardQuery = activeLeagueId ? `?league_id=${encodeURIComponent(activeLeagueId)}` : '';
      const [dashboardResult, tournamentPredictionResult] = await Promise.all([
        api(`/api/webapp/dashboard${dashboardQuery}`),
        api('/api/webapp/tournament-prediction/me').catch(() => null),
      ]);
      setDashboard(dashboardResult);
      setTournamentPrediction(tournamentPredictionResult);
    } catch (err) {
      setDashboardError(err);
    }
  }

  useEffect(() => {
    if (!isTelegramMode() && !hasBrowserSession) return;
    loadDashboard();
  }, [refreshKey, hasBrowserSession, activeLeagueId]);

  useEffect(() => {
    if (!dashboard?.live_match) return undefined;
    const timer = window.setInterval(() => loadDashboard(), 60000);
    return () => window.clearInterval(timer);
  }, [Boolean(dashboard?.live_match), refreshKey, hasBrowserSession]);

  function handleSaved() {
    setRefreshKey((value) => value + 1);
  }

  function handleTournamentSaved() {
    setRefreshKey((value) => value + 1);
  }

  function setActiveLeagueId(nextLeagueId) {
    const normalized = Number(nextLeagueId) || null;
    setActiveLeagueIdState(normalized);
    if (normalized) {
      localStorage.setItem('ff_active_league_id', String(normalized));
    } else {
      localStorage.removeItem('ff_active_league_id');
    }
  }

  async function loadLeagues() {
    try {
      const result = await api('/api/webapp/leagues');
      const leagues = result.leagues || [];
      setLeaguesData(result);
      const stored = Number(localStorage.getItem('ff_active_league_id') || 0) || null;
      const storedAvailable = leagues.some((league) => Number(league.id) === Number(stored));
      if (stored && storedAvailable) {
        setActiveLeagueIdState(stored);
      } else if (result.active_league_id || result.default_league_id || leagues[0]?.id) {
        const fallback = result.active_league_id || result.default_league_id || leagues[0]?.id;
        setActiveLeagueId(fallback);
      }
      return result;
    } catch (err) {
      console.warn('Failed to load leagues', err);
      return null;
    }
  }

  useEffect(() => {
    if (!isTelegramMode() && !hasBrowserSession) return;
    loadLeagues();
  }, [hasBrowserSession, refreshKey]);

  const activeLeagueName = activeLeagueLabel(leaguesData.leagues || [], activeLeagueId);

  if (!isTelegramMode() && !hasBrowserSession) {
    return <div className={`app theme-${appTheme}`}><BrowserAuthGate /></div>;
  }

  if (dashboardError) {
    return <div className="app"><ErrorCard error={dashboardError} onRetry={loadDashboard} /></div>;
  }

  return (
    <div className={`app theme-${appTheme}`}>
      <PwaUpdateBanner updateInfo={updateInfo} />
      <Header
        dashboard={dashboard}
        leagues={leaguesData.leagues || []}
        activeLeagueId={activeLeagueId}
        onLeagueChange={(nextLeagueId) => {
          setActiveLeagueId(nextLeagueId);
          trackAnalytics('league_selected', { screen: tab, properties: { league_id: Number(nextLeagueId) || 0 } });
        }}
        onRules={() => setRulesOpen(true)}
        onAdmin={() => {
          trackAnalytics('admin_open', { screen: 'admin' });
          setTab('admin');
        }}
      />

      {tab === 'matches' && (
        <>
          <HomeHero
            dashboard={dashboard}
            setTab={setTab}
            onNextMatchPredict={setPredictionMatch}
            onOpenLiveMatch={(match) => setHomeTournamentMatch(match)}
          />
          <MatchCenter key={`matches-${refreshKey}-${activeLeagueId || 'default'}`} onPredict={setPredictionMatch} onForecast={setForecastMatch} leagues={leaguesData.leagues || []} activeLeagueId={activeLeagueId} />
        </>
      )}
      {FANTASY_UI_ENABLED && tab === 'fantasy' && <Fantasy />}
      {tab === 'predictions' && <Predictions
        key={`predictions-${refreshKey}`}
        onPredict={setPredictionMatch}
        onForecast={setForecastMatch}
        tournamentPrediction={tournamentPrediction}
        onTournamentPick={setTournamentPickField}
        onTournamentParticipants={() => setTournamentPredictionsOpen(true)}
        onOpenTournamentTeam={(id) => { setHomeTournamentPlayerId(null); setHomeTournamentMatch(null); setHomeTournamentTeamId(id); }}
        onOpenTournamentPlayer={(id) => { setHomeTournamentTeamId(null); setHomeTournamentMatch(null); setHomeTournamentPlayerId(id); }}
      />}
      {tab === 'resources' && <Resources />}
      {tab === 'leagues' && <LeaguesScreen leaguesData={leaguesData} activeLeagueId={activeLeagueId} onLeagueChange={setActiveLeagueId} onLeaguesChanged={loadLeagues} />}
      {tab === 'rating' && <Rating activeLeagueId={activeLeagueId} />}
      {tab === 'profile' && <Profile tournamentPrediction={tournamentPrediction} appTheme={appTheme} setAppTheme={setAppTheme} />}
      {tab === 'admin' && dashboard?.user?.is_admin && <AdminPanel />}

      <BottomNavigation tab={tab} onChange={setTab} />

      {predictionMatch && <ScorePicker match={predictionMatch} onClose={() => setPredictionMatch(null)} onSaved={handleSaved} />}
      {forecastMatch && <ForecastModal match={forecastMatch} onClose={() => setForecastMatch(null)} />}
      {tournamentPredictionsOpen && <TournamentPredictionsModal onClose={() => setTournamentPredictionsOpen(false)} leagueId={activeLeagueId} leagueName={activeLeagueName} />}
      {homeTournamentMatch && <MatchDetailsModal match={homeTournamentMatch} onClose={() => setHomeTournamentMatch(null)} onPredict={setPredictionMatch} onOpenTeam={(id) => { setHomeTournamentMatch(null); setHomeTournamentTeamId(id); }} onOpenPlayer={(id) => { setHomeTournamentMatch(null); setHomeTournamentPlayerId(id); }} />}
      {homeTournamentTeamId && <TeamProfileModal teamId={homeTournamentTeamId} onClose={() => setHomeTournamentTeamId(null)} onOpenMatch={(match) => { setHomeTournamentTeamId(null); setHomeTournamentMatch(match); }} onOpenPlayer={(id) => { setHomeTournamentTeamId(null); setHomeTournamentPlayerId(id); }} />}
      {homeTournamentPlayerId && <PlayerProfileModal playerId={homeTournamentPlayerId} onClose={() => setHomeTournamentPlayerId(null)} onOpenTeam={(id) => { setHomeTournamentPlayerId(null); setHomeTournamentTeamId(id); }} onOpenMatch={(match) => { setHomeTournamentPlayerId(null); setHomeTournamentMatch(match); }} />}
      {tournamentPickField && (tournamentPrediction?.can_submit || !tournamentPrediction?.is_closed) && <TournamentPredictionModal currentPrediction={tournamentPrediction} initialField={tournamentPickField} onClose={() => setTournamentPickField(null)} onSaved={handleTournamentSaved} />}
      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
