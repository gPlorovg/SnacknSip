/**
 * Сессия приложения в sessionStorage: отдельная для каждой вкладки браузера.
 * Так гость и персонал могут быть открыты в двух вкладках одного Chrome без перезаписи токенов.
 *
 * (HttpOnly cookies + Django session — другой объём работы на бэкенде; здесь — изоляция по вкладке.)
 */

const KEYS = [
  "accessToken",
  "refreshToken",
  "user",
  "event",
  "event_name",
] as const;

let legacyMigrated = false;

function migrateFromLocalStorageOnce(): void {
  if (legacyMigrated || typeof window === "undefined") return;
  legacyMigrated = true;
  if (sessionStorage.getItem("accessToken")) return;
  for (const k of KEYS) {
    const v = localStorage.getItem(k);
    if (v) {
      sessionStorage.setItem(k, v);
      localStorage.removeItem(k);
    }
  }
}

function ss(): Storage | null {
  if (typeof window === "undefined") return null;
  migrateFromLocalStorageOnce();
  return sessionStorage;
}

export function getAccessToken(): string | null {
  return ss()?.getItem("accessToken") ?? null;
}

export function getRefreshToken(): string | null {
  return ss()?.getItem("refreshToken") ?? null;
}

export function setTokens(access: string, refresh?: string): void {
  const s = ss();
  if (!s) return;
  s.setItem("accessToken", access);
  if (refresh) s.setItem("refreshToken", refresh);
}

/** После успешного POST /api/auth/login/ */
export function setSessionAfterLogin(payload: {
  access: string;
  refresh: string;
  user: object;
  event: object;
  eventName: string;
}): void {
  const s = ss();
  if (!s) return;
  s.setItem("accessToken", payload.access);
  s.setItem("refreshToken", payload.refresh);
  s.setItem("user", JSON.stringify(payload.user));
  s.setItem("event", JSON.stringify(payload.event));
  s.setItem("event_name", payload.eventName);
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  for (const k of KEYS) {
    sessionStorage.removeItem(k);
    localStorage.removeItem(k);
  }
}

export function getUserJson(): string | null {
  return ss()?.getItem("user") ?? null;
}

export function getEventJson(): string | null {
  return ss()?.getItem("event") ?? null;
}

export function getEventName(): string | null {
  return ss()?.getItem("event_name") ?? null;
}
