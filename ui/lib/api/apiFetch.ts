import { API_BASE } from "@/lib/config";
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "@/lib/sessionAuth";

type RefreshResult = {
  accessToken: string | null;
  shouldLogout: boolean;
};

let refreshPromise: Promise<RefreshResult> | null = null;
const SOFT_RETRY_DELAY_MS = 400;
const REFRESH_LOCK_NAME = "snacknsip-jwt-refresh";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isIdempotentMethod(method: string | undefined) {
  const normalized = (method ?? "GET").toUpperCase();
  return normalized === "GET" || normalized === "HEAD";
}

async function fetchWithSoftRetry(
  url: string,
  init: RequestInit,
  canRetry: boolean,
): Promise<Response> {
  try {
    const response = await fetch(url, init);

    if (canRetry && response.status >= 500) {
      await sleep(SOFT_RETRY_DELAY_MS);
      return fetch(url, init);
    }

    return response;
  } catch (error) {
    if (!canRetry) {
      throw error;
    }
    await sleep(SOFT_RETRY_DELAY_MS);
    return fetch(url, init);
  }
}

async function refreshAccessToken(refreshToken: string): Promise<RefreshResult> {
  const refreshResponse = await fetch(`${API_BASE}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
  });

  if (!refreshResponse.ok) {
    if (refreshResponse.status === 401 || refreshResponse.status === 400) {
      return { accessToken: null, shouldLogout: true };
    }
    throw new Error("Failed to refresh access token");
  }

  const data = (await refreshResponse.json()) as { access?: string; refresh?: string };
  if (!data.access) {
    throw new Error("Refresh endpoint returned empty access token");
  }

  setTokens(data.access, data.refresh);
  return { accessToken: data.access, shouldLogout: false };
}

/**
 * Сериализует параллельные refresh внутри вкладки (и при общем lock между вкладками — безопасно).
 */
async function coordinatedRefresh(): Promise<RefreshResult> {
  const run = async (): Promise<RefreshResult> => {
    const rt = getRefreshToken();
    if (!rt) {
      return { accessToken: null, shouldLogout: true };
    }
    return refreshAccessToken(rt);
  };

  if (typeof navigator !== "undefined" && navigator.locks?.request) {
    return navigator.locks.request(REFRESH_LOCK_NAME, run);
  }
  return run();
}

function forceLogoutToEvent() {
  clearSession();
  window.location.href = "/event";
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const accessToken = getAccessToken();
  const refreshToken = getRefreshToken();
  const canSoftRetry = isIdempotentMethod(options.method);

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };

  let response = await fetchWithSoftRetry(
    `${API_BASE}${endpoint}`,
    {
      ...options,
      headers,
    },
    canSoftRetry,
  );

  if (response.status === 401 && refreshToken) {
    try {
      if (!refreshPromise) {
        refreshPromise = coordinatedRefresh().finally(() => {
          refreshPromise = null;
        });
      }

      const { accessToken: newAccessToken, shouldLogout } = await refreshPromise;
      if (shouldLogout || !newAccessToken) {
        forceLogoutToEvent();
        throw new Error("Refresh token expired");
      }

      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${newAccessToken}`,
      };

      response = await fetchWithSoftRetry(
        `${API_BASE}${endpoint}`,
        {
          ...options,
          headers: retryHeaders,
        },
        canSoftRetry,
      );

      if (response.status === 401) {
        forceLogoutToEvent();
        throw new Error("Unauthorized after refresh");
      }
    } catch (error) {
      throw error;
    }
  }

  return response;
}
