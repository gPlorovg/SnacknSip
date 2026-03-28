"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api/apiFetch";

// Типы
interface Stall {
  id: number;
  name: string;
  abbr: string;
  status: "open" | "closed";
}

interface MenuItem {
  id: number;
  menu_item_id: number;
  name: string;
  price: string;
  is_available: boolean;
}

interface OrderItem {
  id: number;
  menu_item_id: number;
  menu_item_name: string;
  menu_item_price: string;
  quantity: number;
  removed: boolean;
}

interface Order {
  id: number;
  order_number: string;
  status:
    | "created"
    | "preparing"
    | "ready"
    | "completed"
    | "cancelled"
    | "modified";
  guest_name: string;
  items: OrderItem[];
  cancel_note: string;
  created_at: string;
  updated_at: string;
}

export default function StaffStallPage() {
  const router = useRouter();
  const [stall, setStall] = useState<Stall | null>(null);
  const [menu, setMenu] = useState<MenuItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const pollingRef = useRef<NodeJS.Timer | null>(null);

  const statusMap: Record<string, string> = {
    open: "Открыта",
    closed: "Закрыта",
  };

  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      setLoading(true);
      try {
        const [stallRes, menuRes, ordersRes] = await Promise.all([
          apiFetch("/api/staff/stall/"),
          apiFetch("/api/staff/menu/"),
          apiFetch("/api/staff/orders/"),
        ]);

        if (!stallRes.ok || !menuRes.ok || !ordersRes.ok) throw new Error();

        const stallData = await stallRes.json();
        const menuData = await menuRes.json();
        const ordersData = await ordersRes.json();

        if (!isMounted) return;

        setStall(stallData);
        setMenu(menuData);

        // сортировка заказов по времени (старые сверху)
        const sorted = ordersData.sort(
          (a: Order, b: Order) =>
            new Date(a.created_at).getTime() -
            new Date(b.created_at).getTime()
        );

        setOrders(sorted);
      } catch (e) {
        console.error(e);
        alert("Ошибка загрузки");
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadData();

    pollingRef.current = setInterval(async () => {
      try {
        const res = await apiFetch("/api/staff/orders/");
        if (!res.ok) throw new Error();
        const data = await res.json();

        const sorted = data.sort(
          (a: Order, b: Order) =>
            new Date(a.created_at).getTime() -
            new Date(b.created_at).getTime()
        );

        if (isMounted) setOrders(sorted);
      } catch (e) {
        console.error(e);
      }
    }, 5000);

    return () => {
      isMounted = false;
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handleOpenStall = async () => {
    const res = await apiFetch("/api/staff/stall/open/", { method: "POST" });
    if (res.ok && stall) setStall({ ...stall, status: "open" });
  };

  const handleCloseStall = async () => {
    const res = await apiFetch("/api/staff/stall/close/", { method: "POST" });
    if (res.ok && stall) setStall({ ...stall, status: "closed" });
  };

  const handleCancelAllOrders = async () => {
    const res = await apiFetch("/api/staff/orders/cancel-all/", {
      method: "POST",
    });
    if (res.ok) setOrders([]);
  };

  const handleRedistributeOrders = async () => {
    await apiFetch("/api/staff/orders/redistribute/", { method: "POST" });
  };

  const handleMenuStatusChange = async (id: number, is_available: boolean) => {
    const res = await apiFetch(`/api/staff/menu/${id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_available }),
    });

    if (res.ok) {
      setMenu(menu.map(m => (m.id === id ? { ...m, is_available } : m)));
    }
  };

  const ORDER_STATUS_LABELS: Record<string, string> = {
  created: "Создан",
  preparing: "Готовится",
  ready: "Готов",
  completed: "Выдан",
  cancelled: "Отменён",
  modified: "Изменён",
};


const ORDER_TRANSITIONS: Record<string, string[]> = {
  created: ["preparing", "cancelled", "modified"],
  preparing: ["ready", "cancelled", "modified"],
  ready: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
  modified: ["preparing", "cancelled"],
};

    // Обработчик смены статуса заказа
    const handleOrderStatusChange = async (
    orderId: number,
    newStatus: Order["status"]
    ) => {
    let cancelNote = "";

    if (newStatus === "cancelled") {
        cancelNote = prompt("Введите причину отмены заказа") || "";
    }

    const res = await apiFetch(`/api/staff/orders/${orderId}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus, cancel_note: cancelNote }),
    });

    if (res.ok) {
        setOrders(prev =>
        prev
            .map(o =>
            o.id === orderId ? { ...o, status: newStatus, cancel_note: cancelNote } : o
            )
            // удаляем заказ, если он достиг конечного состояния
            .filter(o => !["completed", "cancelled"].includes(o.status))
        );
    }
    };

  if (loading) return <div className="p-6">Загрузка...</div>;
  if (!stall) return <div className="p-6">Нет данных</div>;

  return (
    <div className="min-h-screen p-6 bg-gray-50 flex flex-col gap-6">
      {/* Точка */}
      <Card className="p-4 max-w-xl">
        <h2 className="text-2xl font-bold">{stall.name}</h2>
        <p>Код: {stall.abbr}</p>
        <p>Статус: {statusMap[stall.status]}</p>

        <div className="flex flex-col sm:flex-row gap-2 mt-2">
        {stall.status === "open" && (
            <Button variant="destructive" className="w-full sm:w-auto" onClick={handleCloseStall}>
            Закрыть точку
            </Button>
        )}

        {stall.status === "closed" && (
            <>
            <Button
                className="bg-green-600 text-white hover:bg-green-700 w-full sm:w-auto"
                onClick={handleOpenStall}
            >
                Открыть точку
            </Button>

            <Button className="w-full sm:w-auto" onClick={handleCancelAllOrders}>
                Отменить все заказы
            </Button>

            <Button className="w-full sm:w-auto" onClick={handleRedistributeOrders}>
                Перераспределить заказы
            </Button>
            </>
        )}
        </div>
      </Card>

      {/* Меню */}
      <Accordion type="single" collapsible>
        <AccordionItem value="menu">
          <AccordionTrigger>
            <Card className="p-4 max-w-xl">Меню</Card>
          </AccordionTrigger>
          <AccordionContent className="p-4 flex flex-col gap-2 max-w-xl">
            {menu.map(m => (
                <Card
                key={m.id}
                className="p-3 flex items-center justify-between gap-4 max-w-md w-full"
                >
                <span className="font-medium whitespace-nowrap">
                    {m.name}
                </span>

                <select
                    value={m.is_available ? "available" : "stoplist"}
                    onChange={(e) =>
                    handleMenuStatusChange(m.id, e.target.value === "available")
                    }
                    className="border border-gray-300 rounded-md p-1 shrink-0"
                >
                    <option value="available">Доступно</option>
                    <option value="stoplist">Стоп лист</option>
                </select>
                </Card>
            ))}
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {/* Заказы */}
      <Accordion type="single" collapsible>
        <AccordionItem value="orders">
          <AccordionTrigger>
            <Card className="p-4 max-w-xl">Заказы</Card>
          </AccordionTrigger>
        <AccordionContent className="p-4 flex flex-col gap-2 max-w-xl">
        <div className="flex flex-col gap-2 w-full items-stretch">
            {orders.map(o => (
            <Card
                key={o.id}
                className="p-3 flex flex-col gap-2 w-full min-h-[160px]"
            >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="font-medium">
                    {o.order_number} ({o.guest_name})
                </span>

                    <select
                    value={o.status}
                    onChange={e =>
                        handleOrderStatusChange(o.id, e.target.value as Order["status"])
                    }
                    className="border border-gray-300 rounded-md p-1 shrink-0"
                    >
                    {/* Опции для текущего статуса + доступные переходы */}
                    <option value={o.status}>
                        {ORDER_STATUS_LABELS[o.status]}
                    </option>
                    {ORDER_TRANSITIONS[o.status].map(s => (
                        <option key={s} value={s}>
                        {ORDER_STATUS_LABELS[s]}
                        </option>
                    ))}
                    </select>
                </div>

                <div className="text-sm text-gray-600">
                Время создания:{" "}
                {new Date(o.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                })}
                </div>

                <div className="flex flex-col">
                {o.items.map(item => (
                    <span key={item.id}>
                    {item.menu_item_name} x{item.quantity}
                    </span>
                ))}
                </div>

                {o.cancel_note && (
                <div className="text-red-600">Причина: {o.cancel_note}</div>
                )}
            </Card>
            ))}
        </div>
        </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
