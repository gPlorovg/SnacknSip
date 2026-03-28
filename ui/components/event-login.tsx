"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/config";

interface LoginResponse {
  access: string;
  refresh: string;
  user: {
    id: number;
    name: string;
    login: string;
    role: string;
  };
  event: {
    id: number;
    code: string;
    name: string;
  };
}

export default function EventLogin({ initialEventCode = "" }: { initialEventCode?: string }) {
  const router = useRouter();

  const [eventCode, setEventCode] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialEventCode) {
      setEventCode(initialEventCode);
    }
  }, [initialEventCode]);

  const handleLogin = async () => {
    setErrorMessage("");

    if (!eventCode) {
      setErrorMessage("Введите код мероприятия");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/auth/login/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          login,
          password,
          event_code: eventCode,
        }),
      });

      if (!res.ok) {
        throw new Error("Неверный логин или пароль");
      }

      const data: LoginResponse = await res.json();

      localStorage.setItem("accessToken", data.access);
      localStorage.setItem("refreshToken", data.refresh);
      localStorage.setItem("user", JSON.stringify(data.user));
      localStorage.setItem("event", JSON.stringify(data.event));

      if (data.user.role === "staff") {
        router.push(`/event/${data.event.code}/staff`);
      } else if (data.user.role === "guest") {
        router.push(`/event/${data.event.code}/guest`);
      } else {
        // fallback (на всякий случай)
        router.push(`/event/${data.event.code}`);
      }

    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Ошибка при входе");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <div className="w-full max-w-sm bg-white p-6 rounded-2xl shadow-md flex flex-col gap-4">
        <h1 className="text-2xl font-bold text-center">Вход на мероприятие</h1>

        {/* Код мероприятия */}
        <div className="flex flex-col gap-1">
          <label className="text-sm text-gray-600">Код мероприятия</label>
          <Input
            value={eventCode}
            onChange={(e) => setEventCode(e.target.value)}
          />
        </div>

        {/* Логин */}
        <div className="flex flex-col gap-1">
          <label className="text-sm text-gray-600">Логин</label>
          <Input
            value={login}
            onChange={(e) => setLogin(e.target.value)}
          />
        </div>

        {/* Пароль */}
        <div className="flex flex-col gap-1">
          <label className="text-sm text-gray-600">Пароль</label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {errorMessage && (
          <div className="text-red-600 text-sm">{errorMessage}</div>
        )}

        <Button onClick={handleLogin} disabled={loading}>
          {loading ? "Вход..." : "Войти"}
        </Button>
      </div>
    </div>
  );
}
