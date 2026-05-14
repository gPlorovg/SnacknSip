"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { apiFetch } from "@/lib/api/apiFetch";
import { resolvedEventCode } from "@/lib/eventRoute";
import { getEventName, getUserJson } from "@/lib/sessionAuth";

interface OrderItem {
  id: number;
  name: string;
  quantity: number;
  price: number;
  removed: boolean;
}

interface Order {
  id: number;
  orderNumber: string;
  stallName: string;
  status: string;
  items: OrderItem[];
  createdAt: string;
  totalPrice: number;
  cancelReason?: string; // <-- добавлено поле для причины отмены
}

interface Stall {
  id: number;
  name: string;
  abbr: string;
  status: "open" | "closed";
}

// Локализация статусов заказов
const STATUS_LABELS: Record<string, string> = {
  created: "Создан",
  preparing: "Готовится",
  ready: "Готов",
  completed: "Выдан",
  cancelled: "Отменён",
  modified: "Изменён",
};

// Цвета по статусу
const STATUS_COLORS: Record<string, string> = {
  created: "text-blue-600",
  preparing: "text-yellow-600",
  ready: "text-yellow-600",
  completed: "text-green-600",
  cancelled: "text-red-600",
  modified: "text-gray-600",
};

// Локализация статусов точек выдачи
const STALL_STATUS_LABELS: Record<string, string> = {
  open: "Открыта",
  closed: "Закрыта",
};

// Получение заказов
const fetchOrders = async (): Promise<Order[]> => {
  const res = await apiFetch("/api/orders/");
  if (!res.ok) throw new Error("Ошибка загрузки заказов");
  const data = await res.json();
  return data.map((order: any) => {
    const totalPrice = order.items.reduce((sum: number, item: any) => {
      if (item.removed) return sum;
      return sum + Number(item.menu_item_price) * item.quantity;
    }, 0);

    return {
      id: order.id,
      orderNumber: order.order_number,
      stallName: order.stall_name,
      status: order.status,
      cancelReason: order.cancel_note || "", // <-- добавляем сюда
      items: order.items.map((item: any) => ({
        id: item.id,
        name: item.menu_item_name,
        quantity: item.quantity,
        price: Number(item.menu_item_price),
        removed: item.removed,
      })),
      createdAt: order.created_at,
      totalPrice,
    };
  });
};

// Получение статуса заказа для поллинга
const fetchOrderStatus = async (orderId: number) => {
  const res = await apiFetch(`/api/orders/${orderId}/status/`);
  if (!res.ok) throw new Error("Ошибка получения статуса заказа");
  return res.json();
};

// Получение точек выдачи
const fetchStalls = async (): Promise<Stall[]> => {
  const res = await apiFetch("/api/stalls/");
  if (!res.ok) throw new Error("Ошибка загрузки точек выдачи");
  return res.json();
};

export default function GuestEventPage() {
  const router = useRouter();
  const params = useParams();
  const eventCode = resolvedEventCode(
    params?.event_code as string | string[] | undefined,
  );

  const [eventName, setEventName] = useState("");
  const [orders, setOrders] = useState<Order[]>([]);
  const [stalls, setStalls] = useState<Stall[]>([]);
  const [loadingOrders, setLoadingOrders] = useState(true);
  const [loadingStalls, setLoadingStalls] = useState(true);
  const [showCompleted, setShowCompleted] = useState(false);

  const ordersRef = useRef<Order[]>([]);
  const prevOrderStatuses = useRef<Record<number, string>>({});

  useEffect(() => {
    if (!eventCode) {
      return;
    }

    const rawUser = getUserJson();
    if (rawUser) {
      try {
        const u = JSON.parse(rawUser) as { role?: string };
        if (u.role === "staff") {
          router.replace(`/event/${eventCode}/staff`);
          return;
        }
      } catch {
        /* ignore */
      }
    }

    const storedEventName = getEventName();
    if (storedEventName) setEventName(storedEventName);

    const loadOrders = async () => {
      setLoadingOrders(true);
      try {
        const data = await fetchOrders();
        setOrders(data);
        ordersRef.current = data;
        prevOrderStatuses.current = Object.fromEntries(data.map(o => [o.id, o.status]));
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingOrders(false);
      }
    };

    const loadStalls = async () => {
      setLoadingStalls(true);
      try {
        const data = await fetchStalls();
        setStalls(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoadingStalls(false);
      }
    };

    loadOrders();
    loadStalls();

    const interval = setInterval(async () => {
      const activeOrders = ordersRef.current.filter(
        o => o.status === "created" || o.status === "preparing" || o.status === "ready" || o.status === "modified"
      );

      if (activeOrders.length === 0) return;

      try {
        const updates = await Promise.all(activeOrders.map(async o => {
          const updated = await fetchOrderStatus(o.id);
          if (updated.status !== o.status) {
            return { id: o.id, status: updated.status, orderNumber: updated.order_number };
          }
          return null;
        }));

        let updatedOrders = [...ordersRef.current];
        let changed = false;

        updates.forEach(upd => {
          if (upd) {
            updatedOrders = updatedOrders.map(o =>
              o.id === upd.id ? { ...o, status: upd.status } : o
            );
            alert(`Заказ #${upd.orderNumber} теперь ${STATUS_LABELS[upd.status]}`);
            changed = true;
          }
        });

        if (changed) {
          setOrders(updatedOrders);
          ordersRef.current = updatedOrders;
        }
      } catch (e) {
        console.error(e);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [eventCode, router]);

  const activeOrders = orders.filter(
    o => o.status === "created" || o.status === "preparing" || o.status === "ready" || o.status === "modified"
  );
  const completedOrders = orders.filter(
    o => o.status === "completed" || o.status === "cancelled"
  );

  const displayedOrders = showCompleted ? [...activeOrders, ...completedOrders] : activeOrders;
  const showToggleButton = completedOrders.length > 0;

  return (
    <div className="min-h-screen p-6 bg-gray-50 flex flex-col gap-6">
      <h1 className="text-3xl font-bold">{eventName}</h1>

      <h2 className="text-2xl font-bold mt-4">Мои заказы</h2>
      {loadingOrders ? (
        <div>Загрузка заказов...</div>
      ) : (
        <>
          {displayedOrders.length === 0 && !showCompleted ? (
            <div>Активных заказов нет</div>
          ) : (
            <div className="flex flex-col gap-3">
              <Accordion type="single" collapsible>
                {displayedOrders.map(order => (
                  <AccordionItem key={order.id} value={`order-${order.id}`}>
                    <AccordionTrigger>
                      <Card className="p-4 cursor-pointer bg-white hover:bg-blue-50 max-w-xl">
                        <ul className="flex flex-col gap-1 text-sm">
                          <li>
                            <span className="font-semibold">Заказ:</span> {order.orderNumber}
                          </li>
                          <li>
                            <span className="font-semibold">Точка выдачи:</span> {order.stallName}
                          </li>
                          <li>
                            <span className="font-semibold">Статус:</span>{" "}
                            <span className={`font-medium ${STATUS_COLORS[order.status] || "text-gray-600"}`}>
                              {STATUS_LABELS[order.status]}
                            </span>
                          </li>
                          <li>
                            <span className="font-semibold">Итого:</span> {order.totalPrice} ₽
                          </li>
                          <li>
                            <span className="font-semibold">Время:</span>{" "}
                            {new Date(order.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </li>
                          {order.status === "cancelled" && order.cancelReason && (
                            <li className="text-red-600">
                              <span className="font-semibold">Причина отмены:</span> {order.cancelReason}
                            </li>
                          )}
                        </ul>
                      </Card>
                    </AccordionTrigger>

                    <AccordionContent className="p-0">
                      <div className="max-w-xl w-full border-t border-gray-200">
                        {order.items.map(item => (
                          <div
                            key={item.id}
                            className={`grid grid-cols-[2fr_1fr_1fr] gap-4 items-center p-2 border-b last:border-b-0 ${item.removed ? "opacity-50" : ""}`}
                          >
                            <span className="truncate font-medium">{item.name}</span>
                            <span className="text-gray-600">{item.quantity}</span>
                            <span className="font-semibold">
                              {item.removed ? "❌" : item.price * item.quantity + " ₽"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          )}

          {showToggleButton && (
            <Button
              variant="outline"
              size="lg"
              className="mt-4 w-fit self-start"
              onClick={() => setShowCompleted(prev => !prev)}
            >
              {showCompleted ? "Скрыть выполненные заказы" : "Показать выполненные заказы"}
            </Button>
          )}
        </>
      )}

      <h2 className="text-2xl font-bold mt-6">Точки выдачи</h2>
      {loadingStalls ? (
        <div>Загрузка точек выдачи...</div>
      ) : (
        <div className="flex flex-col gap-4 overflow-y-auto max-h-[60vh]">
          {stalls.map(stall => (
            <Card
              key={stall.id}
              className={`p-4 max-w-xl ${stall.status === "open" ? "cursor-pointer bg-white hover:bg-blue-50" : "bg-gray-100"}`}
              onClick={() => stall.status === "open" && router.push(`/event/${eventCode}/guest/stall/${stall.id}`)}
            >
              <h3 className="font-semibold">{stall.name}</h3>
              <p className="text-gray-600">Код: {stall.abbr}</p>
              <p className="text-gray-600">Статус: {STALL_STATUS_LABELS[stall.status]}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
