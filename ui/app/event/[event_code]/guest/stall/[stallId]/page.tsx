"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiFetch } from "@/lib/api/apiFetch";

interface MenuItem {
  id: number;
  name: string;
  description: string;
  price: number;
  image: string;
  is_available: boolean;
}

interface Stall {
  id: number;
  name: string;
  abbr: string;
  status: "open" | "closed";
  menu_items: MenuItem[];
}

export default function StallPage() {
  const params = useParams();
  const router = useRouter();
  const eventId = Array.isArray(params.eventId) ? params.eventId[0] : params.eventId || "";
  const stallId = Array.isArray(params.stallId) ? params.stallId[0] : params.stallId || "";

  const [stall, setStall] = useState<Stall | null>(null);
  const [loading, setLoading] = useState(true);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const loadStall = async () => {
      setLoading(true);
      try {
        const res = await apiFetch(`/api/stalls/${stallId}/`);
        if (!res.ok) throw new Error("Ошибка загрузки точки выдачи");
        const data = await res.json();
        setStall(data);
      } catch (e) {
        console.error(e);
        alert("Не удалось загрузить точку выдачи");
      } finally {
        setLoading(false);
      }
    };
    loadStall();
  }, [stallId]);

  const increment = (itemId: number) => {
    setCart((prev) => ({ ...prev, [itemId]: (prev[itemId] || 0) + 1 }));
  };

  const decrement = (itemId: number) => {
    setCart((prev) => {
      const qty = (prev[itemId] || 0) - 1;
      if (qty <= 0) {
        const copy = { ...prev };
        delete copy[itemId];
        return copy;
      }
      return { ...prev, [itemId]: qty };
    });
  };

  const handleCreateOrder = async () => {
    if (!stall || Object.keys(cart).length === 0) return;
    setCreating(true);
    try {
      const items = Object.entries(cart).map(([menu_item_id, quantity]) => ({
        menu_item_id: Number(menu_item_id),
        quantity,
      }));
      const res = await apiFetch("/api/orders/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stall_id: stall.id, items }),
      });
      if (!res.ok) throw new Error("Не удалось создать заказ");
      router.back();
    } catch (e) {
      alert("Не удалось создать заказ");
    } finally {
      setCreating(false);
    }
  };

  const totalSum = Object.entries(cart).reduce((sum, [menu_item_id, qty]) => {
    const item = stall?.menu_items.find((i) => i.id === Number(menu_item_id));
    return sum + (item ? item.price * qty : 0);
  }, 0);

  if (loading) return <div className="p-6">Загрузка точки выдачи...</div>;
  if (!stall) return <div className="p-6 text-red-600">Точка выдачи не найдена</div>;

  return (
    <div className="min-h-screen p-6 bg-gray-50 flex flex-col gap-6">
      {/* Кнопка назад */}
      <Button
        variant="secondary"
        className="w-fit"
        onClick={() => router.back()}
      >
        ← Назад
      </Button>

      {/* Шапка точки выдачи */}
      <div className="max-w-xl p-4 bg-white rounded-md shadow-sm flex flex-col gap-1">
        <h1 className="text-2xl font-bold">{stall.name}</h1>
        <p className="text-gray-600">Код: {stall.abbr}</p>
        <p className="text-gray-600">Статус: {stall.status === "open" ? "Открыта" : "Закрыта"}</p>
      </div>

      {/* Меню */}
      <h2 className="text-2xl font-bold mt-4">Меню</h2>
      {stall.menu_items.filter(i => i.is_available).length === 0 ? (
        <div>Нет доступных товаров</div>
      ) : (
        <div className="flex flex-col gap-4">
          {stall.menu_items
            .filter(item => item.is_available)
            .map((item) => {
              const quantity = cart[item.id] || 0;
              return (
                <Card
                  key={item.id}
                  className="p-4 flex flex-col gap-4 min-h-[180px] max-w-xl w-full overflow-x-auto"
                >
                  <div className="flex gap-4 items-center">
                    {item.image && (
                      <img
                        src={item.image}
                        alt={item.name}
                        className="w-24 h-24 object-cover rounded-md"
                      />
                    )}
                    <div className="flex flex-col gap-1 min-w-[200px]">
                      <span className="font-medium text-lg">{item.name}</span>
                      <span className="text-gray-600 text-sm">{item.description}</span>
                      <span className="text-gray-800 font-semibold">{item.price} ₽</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mt-auto pt-2 border-t border-gray-200">
                    <div className="flex items-center gap-2">
                      <Button size="sm" onClick={() => decrement(item.id)}>-</Button>
                      <span className="w-6 text-center">{quantity}</span>
                      <Button size="sm" onClick={() => increment(item.id)}>+</Button>
                      <span className="font-semibold ml-2">{quantity * item.price} ₽</span>
                    </div>
                  </div>
                </Card>
              );
            })}

          {/* Сумма заказа */}
          <div className="flex items-center justify-start gap-2 mt-4">
            <span className="font-semibold text-lg">Сумма заказа:</span>
            <span className="font-bold text-lg">{totalSum} ₽</span>
          </div>

          {/* Создать заказ */}
          <Button
            className="mt-2 w-full max-w-xl"
            disabled={creating || Object.keys(cart).length === 0}
            onClick={handleCreateOrder}
          >
            {creating ? "Создание заказа..." : "Создать заказ"}
          </Button>
        </div>
      )}
    </div>
  );
}
