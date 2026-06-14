
import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const tg = window.Telegram?.WebApp;
const APP_VERSION = '2.8.12';


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

async function getCurrentPushSubscription() {
  assertPushSupported();
  const registration = await navigator.serviceWorker.register('/miniapp-static/sw.js');
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

  const registration = await navigator.serviceWorker.register('/miniapp-static/sw.js');
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


function usePwaUpdateCheck() {
  const [updateInfo, setUpdateInfo] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function checkVersion() {
      try {
        const result = await api(`/api/webapp/app-version?client_version=${encodeURIComponent(APP_VERSION)}&t=${Date.now()}`, { cache: 'no-store' });
        if (!cancelled && result.version && result.version !== 'unknown' && result.version !== APP_VERSION) {
          setUpdateInfo(result);
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
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map(async (registration) => {
        try {
          registration.waiting?.postMessage({ type: 'SKIP_WAITING' });
          registration.active?.postMessage({ type: 'SKIP_WAITING' });
          await registration.update();
          await registration.unregister();
        } catch {
          // Best effort for stubborn iOS PWA caches.
        }
      }));
    }

    if ('caches' in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
    }

    // Warm up the no-cache /app response and the version endpoint before reload.
    await Promise.all([
      fetch(`/api/webapp/app-version?client_version=${encodeURIComponent(APP_VERSION)}&force=${stamp}`, {
        cache: 'no-store',
        credentials: 'include',
      }).catch(() => null),
      fetch(`/app?app_v=${stamp}`, {
        cache: 'reload',
        credentials: 'include',
        headers: { 'Cache-Control': 'no-cache' },
      }).catch(() => null),
    ]);
  } catch {
    // Best effort. Reload below must still happen.
  }

  sessionStorage.setItem('ff-force-app-reload', stamp);
  window.location.replace(`/app?app_v=${stamp}`);
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

function Header({ dashboard, onRules, onAdmin }) {
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
          <span className="status-section live-countdown">{stageText}</span>
          <span className="divider" />
          <span className="points">{dashboard?.points ?? 0} очков</span>
          <span className="muted">#{dashboard?.rank || '—'}</span>
        </div>
      </div>
    </header>
  );
}

function HomeHero({ dashboard, tournamentPrediction, onTournamentPick, onTournamentParticipants, setTab }) {
  const missing = dashboard?.missing_predictions_count ?? 0;
  const p = tournamentPrediction?.prediction;
  const tournamentClosed = Boolean(tournamentPrediction?.is_closed || dashboard?.tournament?.is_started);
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
          <div className="tournament-mini-actions">
            <button type="button" onClick={onTournamentParticipants}>Участники</button>
            <span>{tournamentClosed ? 'закрыто' : (p ? '4/4' : '0/4')}</span>
          </div>
        </div>
        <div className="tournament-mini-grid">
          {items.map((item) => (
            <button key={item.key} disabled={tournamentClosed} onClick={() => !tournamentClosed && onTournamentPick(item.key)}>
              <i><Icon name={item.icon} /></i>
              <span>{item.label}</span>
              <strong>{item.value || (tournamentClosed ? 'Нет прогноза' : 'Выбрать')}</strong>
              <small>{tournamentClosed ? 'закрыто' : item.points}</small>
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
  const [selectedVideo, setSelectedVideo] = useState(null);

  useEffect(() => {
    if (!selectedVideo) return;
    const stillAvailable = activeVideos.some((video) => (video.id || video.url) === (selectedVideo.id || selectedVideo.url));
    if (!stillAvailable) setSelectedVideo(null);
  }, [activeVideos, selectedVideo]);

  if (!activeVideos.length) return null;

  const live = activeVideos.some((video) => video.video_type === 'live');
  const meta = live ? 'live' : `${activeVideos.length} ${pluralRu(activeVideos.length, 'ссылка', 'ссылки', 'ссылок')}`;

  return (
    <MatchInlineSection title="Видео" meta={meta} iconName="video" className={`match-video-block ${live ? 'has-live' : ''}`}>
      <div className="match-video-list">
        {activeVideos.map((video) => {
          const isSelected = selectedVideo && (selectedVideo.id || selectedVideo.url) === (video.id || video.url);
          return (
            <button
              key={video.id || video.url}
              type="button"
              className={isSelected ? 'selected' : ''}
              onClick={() => setSelectedVideo(video)}
            >
              <span>{video.video_type === 'live' ? '🔴' : '▶️'}</span>
              <strong>{videoDisplayTitle(video)}</strong>
              <small>{isSelected ? 'открыто' : 'смотреть'}</small>
            </button>
          );
        })}
      </div>

      {selectedVideo && (
        <div className="match-video-player match-video-external-card">
          <div className="match-video-preview" aria-hidden="true">
            <span>{selectedVideo.video_type === 'live' ? '🔴' : '🎥'}</span>
          </div>
          <div className="match-video-player-head">
            <strong>{videoDisplayTitle(selectedVideo)}</strong>
            <small>{selectedVideo.source_label || selectedVideo.source || 'официальный источник'}</small>
          </div>
          <p className="match-video-player-note">
            Match TV не разрешает встроенный плеер внутри других сайтов. Чтобы не показывать черный экран, открываем официальную страницу просмотра отдельной кнопкой.
          </p>
          <button type="button" className="match-video-watch-button" onClick={() => openExternalUrl(selectedVideo.url)}>
            Смотреть на Match TV
          </button>
        </div>
      )}
    </MatchInlineSection>
  );
}

function MatchParticipantsInline({ match }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    setError(null);
    try {
      const result = await api(`/api/webapp/matches/${match.id}/predictions`);
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

function MatchCard({ match, onPredict, onForecast, showDistribution = true }) {
  const locked = match.is_finished || new Date(match.starts_at).getTime() <= Date.now();
  const predictionScoreClass = predictionResultClass(match);
  const activeVideos = visibleVideosForMatch(match);
  const hasVideos = activeVideos.length > 0;

  return (
    <article className={`match-card ${hasVideos ? 'has-video' : ''}`}>
      <div className="match-card-top">
        <span className="group-pill">{match.group_code ? `Группа ${match.group_code}` : match.stage}</span>
        <span className="round-pill">{formatRoundLabel(match)}</span>
        {hasVideos && <span className="video-mini-icon" aria-label="Видео" title="Видео">🎥</span>}
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
        {!locked && <button onClick={() => onForecast(match)}><Icon name="robot" /> Прогноз Отца</button>}
      </div>

      <MatchVideoBlock match={match} />
      <MatchParticipantsInline match={match} />

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


function TournamentPredictionsModal({ onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    api('/api/webapp/tournament-predictions')
      .then((result) => { if (active) setData(result); })
      .catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, []);

  return (
    <div className="modal-backdrop">
      <section className="modal-card tournament-predictions-modal">
        <button className="modal-close" onClick={onClose}>×</button>
        <h2>Прогнозы участников на турнир</h2>
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
                <span>{team?.formation || '—'} · {team?.points || 0} очков</span>
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
  const [includeFantasy, setIncludeFantasy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api('/api/webapp/table').then(setData).catch(setError);
  }, []);

  if (error) return <ErrorCard error={error} />;
  if (!data) return <LoadingCard />;

  const fatherRow = data.father_row;
  const sourceRows = fatherRow ? [...(data.rows || []), fatherRow] : [...(data.rows || [])];
  const rows = sourceRows
    .map((row) => ({
      ...row,
      display_points: includeFantasy && !row.is_father ? (row.points || 0) + (row.fantasy_points || 0) : (row.points || 0),
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
          <div key={row.name} className={`ranking-row rating-rich-row ${row.is_current_user ? 'me' : ''} ${row.is_father ? 'father-ranking-row' : ''}`}>
            <div className="rating-main-line">
              <span className="rank">#{index + 1}</span>
              <div className="rating-player">
                <strong>{row.name}</strong>
                <small>
                  {row.is_father ? 'ИИ-прогнозы вне конкурса, но в общей гонке видны' : `Очки: ${row.points || 0} · Турнир: ${row.tournament_prediction_progress || '0/4'} · Fantasy: ${row.fantasy_points || 0}`}
                </small>
              </div>
              <div className="rating-points-pill">
                {row.display_points} очков
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
                <span>попаданий из {row.match_predictions_finished_count ?? row.accuracy_base ?? 0}</span>
              </div>
            </div>

            <div className="rating-foot-line">
              <span>Матчи: {row.match_predictions_progress || row.match_predictions_count || 0}</span>
              <span>{row.is_father ? `Завершено: ${row.match_predictions_finished_count || 0}` : `Fantasy: ${row.fantasy_team_progress || '0/15'}`}</span>
              <span>{row.is_father ? 'ИИ-вне конкурса' : `Проход: +${row.advancement_plus || 0} / ${row.advancement_minus || 0}`}</span>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}




function AdminPanel() {
  const [data, setData] = useState(null);
  const [selectedMatchId, setSelectedMatchId] = useState('');
  const [scoreHome, setScoreHome] = useState('');
  const [scoreAway, setScoreAway] = useState('');
  const [winnerSide, setWinnerSide] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [videos, setVideos] = useState([]);
  const [videoType, setVideoType] = useState('live');
  const [videoTitle, setVideoTitle] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [videoPriority, setVideoPriority] = useState('100');
  const [videoActive, setVideoActive] = useState(true);
  const [syncLookbackDays, setSyncLookbackDays] = useState('5');
  const [syncLookaheadDays, setSyncLookaheadDays] = useState('7');
  const [syncMinConfidence, setSyncMinConfidence] = useState('85');

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

  async function loadVideos(matchId = selectedMatchId) {
    if (!matchId) {
      setVideos([]);
      return;
    }

    try {
      const result = await api(`/api/webapp/admin/matches/${matchId}/videos`);
      setVideos(result.videos || []);
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    if (selectedMatchId) loadVideos(selectedMatchId);
  }, [selectedMatchId]);

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

  async function syncMatchTvVideos() {
    const result = await api('/api/webapp/admin/match-videos/sync-matchtv', {
      method: 'POST',
      body: JSON.stringify({
        lookback_days: Number(syncLookbackDays || 3),
        lookahead_days: Number(syncLookaheadDays || 2),
        activate_min_confidence: Number(syncMinConfidence || 85),
      }),
    });
    await loadVideos(selectedMatchId);
    return result;
  }

  function resetVideoForm() {
    setVideoTitle('');
    setVideoUrl('');
    setVideoType('live');
    setVideoPriority('100');
    setVideoActive(true);
  }

  async function addMatchVideo() {
    if (!selectedMatchId) throw new Error('Выберите матч.');
    if (!videoTitle.trim()) throw new Error('Укажите название видео.');
    if (!videoUrl.trim()) throw new Error('Укажите ссылку на видео.');

    const result = await api(`/api/webapp/admin/matches/${selectedMatchId}/videos`, {
      method: 'POST',
      body: JSON.stringify({
        video_type: videoType,
        title: videoTitle.trim(),
        url: videoUrl.trim(),
        source: 'matchtv',
        is_active: videoActive,
        priority: Number(videoPriority || 100),
        discovery_status: 'manual',
        confidence: 100,
      }),
    });

    resetVideoForm();
    await loadVideos(selectedMatchId);
    return result;
  }

  async function toggleMatchVideo(video) {
    const result = await api(`/api/webapp/admin/match-videos/${video.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        video_type: video.video_type || 'other',
        title: video.title || 'Видео',
        url: video.url,
        source: video.source || 'matchtv',
        is_active: !video.is_active,
        priority: Number(video.priority || 100),
        discovery_status: video.is_active ? 'hidden' : (video.discovery_status === 'hidden' ? 'verified' : (video.discovery_status || 'manual')),
        confidence: Number(video.confidence || 100),
      }),
    });

    await loadVideos(selectedMatchId);
    return result;
  }

  async function deleteMatchVideo(video) {
    const result = await api(`/api/webapp/admin/match-videos/${video.id}`, { method: 'DELETE' });
    await loadVideos(selectedMatchId);
    return result;
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

      <section className="admin-summary-grid">
        <div><b>{data.summary?.matches_total || 0}</b><span>матчей</span></div>
        <div><b>{data.summary?.finished || 0}</b><span>завершено</span></div>
        <div><b>{data.summary?.ready_for_api_sync || 0}</b><span>к синхронизации</span></div>
        <div><b>{data.summary?.fantasy_stat_rows || 0}</b><span>строк fantasy</span></div>
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

      <section className="card admin-card video-admin-card">
        <div className="admin-card-head">
          <h2>Видео матча</h2>
          <span>{videos.length || 0}</span>
        </div>
        <p className="muted small">Добавь официальную ссылку Match TV вручную или запусти автопоиск по ближайшим матчам. Автопоиск связывает только официальные страницы Match TV и оставляет спорные находки на проверку.</p>

        <div className="video-sync-panel">
          <div className="video-sync-fields">
            <label>Назад, дней<input type="number" min="0" max="30" value={syncLookbackDays} onChange={(event) => setSyncLookbackDays(event.target.value)} /></label>
            <label>Вперед, дней<input type="number" min="0" max="30" value={syncLookaheadDays} onChange={(event) => setSyncLookaheadDays(event.target.value)} /></label>
            <label>Автопоказ от %<input type="number" min="0" max="100" value={syncMinConfidence} onChange={(event) => setSyncMinConfidence(event.target.value)} /></label>
          </div>
          <button type="button" disabled={busy} onClick={() => runAction(syncMatchTvVideos)}>Найти видео Match TV</button>
        </div>

        <div className="video-admin-form">
          <select value={videoType} onChange={(event) => setVideoType(event.target.value)}>
            {VIDEO_TYPES.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
          </select>
          <input value={videoTitle} onChange={(event) => setVideoTitle(event.target.value)} placeholder="Название: Смотреть трансляцию" />
          <input value={videoUrl} onChange={(event) => setVideoUrl(event.target.value)} placeholder="https://matchtv.ru/..." />
          <div className="video-admin-inline">
            <input type="number" min="0" max="10000" value={videoPriority} onChange={(event) => setVideoPriority(event.target.value)} placeholder="Порядок" />
            <label className="video-active-toggle">
              <input type="checkbox" checked={videoActive} onChange={(event) => setVideoActive(event.target.checked)} />
              <span>Показывать</span>
            </label>
          </div>
          <button className="primary full" disabled={busy} onClick={() => runAction(addMatchVideo)}>Добавить видео</button>
        </div>

        <div className="video-admin-list">
          {videos.length === 0 && <p className="muted small">Для выбранного матча видео пока не добавлено.</p>}
          {videos.map((video) => (
            <div className={`video-admin-item ${video.is_active ? '' : 'is-disabled'}`} key={video.id}>
              <div>
                <strong>{video.title}</strong>
                <small>{videoTypeLabel(video.video_type)} · {video.source || 'matchtv'} · {video.discovery_status || 'manual'} · {video.confidence || 0}% · порядок {video.priority || 100}</small>
              </div>
              <div className="video-admin-actions">
                <button type="button" onClick={() => openExternalUrl(video.url)}>Открыть</button>
                <button type="button" disabled={busy} onClick={() => runAction(() => toggleMatchVideo(video))}>{video.is_active ? 'Скрыть' : 'Показать'}</button>
                <button type="button" disabled={busy} onClick={() => runAction(() => deleteMatchVideo(video))}>Удалить</button>
              </div>
            </div>
          ))}
        </div>
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

      <section className="card admin-card">
        <h2>3. Статистика игроков Fantasy</h2>
        <p className="muted">Загружает статистику игроков по завершенным матчам и пересчитывает Fantasy-очки.</p>
        <button className="primary full" disabled={busy} onClick={() => runAction(syncFantasyStats)}>Обновить статистику игроков</button>
      </section>

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

      <CollapsibleProfileSection title="Откуда очки" meta={`${summary.points || 0} очков`}>
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
  const updateInfo = usePwaUpdateCheck();
  const [tab, setTab] = useState('matches');
  const [appTheme, setAppTheme] = useState(() => localStorage.getItem('ff-app-theme') || 'light');
  const [dashboard, setDashboard] = useState(null);
  const [dashboardError, setDashboardError] = useState(null);
  const [predictionMatch, setPredictionMatch] = useState(null);
  const [forecastMatch, setForecastMatch] = useState(null);
  const [tournamentPickField, setTournamentPickField] = useState(null);
  const [tournamentPredictionsOpen, setTournamentPredictionsOpen] = useState(false);
  const [tournamentPrediction, setTournamentPrediction] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [rulesOpen, setRulesOpen] = useState(false);
  const hasBrowserSession = Boolean(getWebSessionToken());

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

  useEffect(() => {
    if (!isTelegramMode() && !hasBrowserSession) return;
    loadDashboard();
  }, [refreshKey, hasBrowserSession]);

  function handleSaved() {
    setRefreshKey((value) => value + 1);
  }

  function handleTournamentSaved() {
    setRefreshKey((value) => value + 1);
  }

  if (!isTelegramMode() && !hasBrowserSession) {
    return <div className={`app theme-${appTheme}`}><BrowserAuthGate /></div>;
  }

  if (dashboardError) {
    return <div className="app"><ErrorCard error={dashboardError} onRetry={loadDashboard} /></div>;
  }

  return (
    <div className={`app theme-${appTheme}`}>
      <PwaUpdateBanner updateInfo={updateInfo} />
      <Header dashboard={dashboard} onRules={() => setRulesOpen(true)} onAdmin={() => setTab('admin')} />

      {tab === 'matches' && (
        <>
          <HomeHero dashboard={dashboard} tournamentPrediction={tournamentPrediction} onTournamentPick={setTournamentPickField} onTournamentParticipants={() => setTournamentPredictionsOpen(true)} setTab={setTab} />
          <MatchCenter key={`matches-${refreshKey}`} onPredict={setPredictionMatch} onForecast={setForecastMatch} />
        </>
      )}
      {tab === 'fantasy' && <Fantasy />}
      {tab === 'predictions' && <Predictions key={`predictions-${refreshKey}`} onPredict={setPredictionMatch} onForecast={setForecastMatch} />}
      {tab === 'resources' && <Resources />}
      {tab === 'rating' && <Rating />}
      {tab === 'profile' && <Profile tournamentPrediction={tournamentPrediction} appTheme={appTheme} setAppTheme={setAppTheme} />}
      {tab === 'admin' && dashboard?.user?.is_admin && <AdminPanel />}

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
      {tournamentPredictionsOpen && <TournamentPredictionsModal onClose={() => setTournamentPredictionsOpen(false)} />}
      {tournamentPickField && !tournamentPrediction?.is_closed && <TournamentPredictionModal currentPrediction={tournamentPrediction} initialField={tournamentPickField} onClose={() => setTournamentPickField(null)} onSaved={handleTournamentSaved} />}
      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
