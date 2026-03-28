import { API_BASE } from "@/lib/config";

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const accessToken = localStorage.getItem("accessToken");
  const refreshToken = localStorage.getItem("refreshToken");

  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
    Authorization: accessToken ? `Bearer ${accessToken}` : "",
  };

  let response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Если access токен протух
  if (response.status === 401 && refreshToken) {
    try {
      // Обновление токена через API
      const refreshResponse = await fetch(`${API_BASE}/api/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: refreshToken }),
      });

      if (!refreshResponse.ok) {
        throw new Error("Refresh token expired");
      }

      const data = await refreshResponse.json();
      localStorage.setItem("accessToken", data.access);

      // Повторяем исходный запрос с новым токеном
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${data.access}`,
      };

      response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: retryHeaders,
      });
    } catch (error) {
      // refresh тоже протух → разлогиниваем
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
      window.location.href = "/login";
      throw error;
    }
  }

  return response;
}