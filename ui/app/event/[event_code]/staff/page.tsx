"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiFetch } from "@/lib/api/apiFetch";
import { resolvedEventCode } from "@/lib/eventRoute";
import { getUserJson } from "@/lib/sessionAuth";

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

export type OrderStatus =
  | "created"
  | "preparing"
  | "ready"
  | "completed"
  | "cancelled"
  | "modified";

interface Order {
  id: number;
  order_number: string;
  status: OrderStatus;
  guest_name: string;
  items: OrderItem[];
  cancel_note: string;
  created_at: string;
  updated_at: string;
}

const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  created: "Создан",
  preparing: "Готовится",
  ready: "Готов",
  completed: "Выдан",
  cancelled: "Отменён",
  modified: "Изменён",
};

const ORDER_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  created: ["preparing", "cancelled", "modified"],
  preparing: ["ready", "cancelled", "modified"],
  ready: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
  modified: ["preparing", "cancelled"],
};

type OrderTab = "queue" | "cooking" | "ready";

const TAB_LABELS: Record<OrderTab, string> = {
  queue: "В очереди",
  cooking: "Готовятся",
  ready: "К выдаче",
};

function sortOrdersByCreated(a: Order, b: Order) {
  return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
}

function nextStatusTowardReady(status: OrderStatus): OrderStatus | null {
  if (status === "created" || status === "modified") return "preparing";
  if (status === "preparing") return "ready";
  return null;
}

function mergeOrderList(prev: Order[], updated: Order): Order[] {
  const next = prev.map((o) => (o.id === updated.id ? updated : o));
  return next.filter((o) => !["completed", "cancelled"].includes(o.status));
}

export default function StaffStallPage() {
  const router = useRouter();
  const params = useParams();
  const eventCode = resolvedEventCode(
    params?.event_code as string | string[] | undefined,
  );

  const [stall, setStall] = useState<Stall | null>(null);
  const [menu, setMenu] = useState<MenuItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [orderTab, setOrderTab] = useState<OrderTab>("queue");
  const [bulkWorking, setBulkWorking] = useState(false);
  const [cancelOrderId, setCancelOrderId] = useState<number | null>(null);
  const [cancelNote, setCancelNote] = useState("");
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ordersRef = useRef<Order[]>([]);

  ordersRef.current = orders;

  const statusMap: Record<string, string> = {
    open: "Открыта",
    closed: "Закрыта",
  };

  const patchOrderStatus = useCallback(
    async (
      orderId: number,
      newStatus: OrderStatus,
      cancelNoteArg = "",
    ): Promise<Order | null> => {
      const res = await apiFetch(`/api/staff/orders/${orderId}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: newStatus,
          cancel_note: cancelNoteArg,
        }),
      });
      if (!res.ok) {
        try {
          const err = (await res.json()) as { detail?: unknown; status?: unknown };
          let msg = "Не удалось обновить статус";
          if (typeof err.detail === "string") msg = err.detail;
          else if (Array.isArray(err.status) && err.status.length)
            msg = String(err.status[0]);
          else if (typeof err.status === "string") msg = err.status;
          alert(msg);
        } catch {
          alert("Не удалось обновить статус");
        }
        return null;
      }
      return (await res.json()) as Order;
    },
    [],
  );

  const applyOrderUpdate = useCallback((updated: Order) => {
    setOrders((prev) => mergeOrderList(prev, updated));
  }, []);

  const handleOrderStatusChange = useCallback(
    async (orderId: number, newStatus: OrderStatus) => {
      if (newStatus === "cancelled") {
        setCancelOrderId(orderId);
        setCancelNote("");
        return;
      }
      const updated = await patchOrderStatus(orderId, newStatus, "");
      if (updated) applyOrderUpdate(updated);
    },
    [applyOrderUpdate, patchOrderStatus],
  );

  const confirmCancelOrder = useCallback(async () => {
    if (cancelOrderId == null) return;
    const updated = await patchOrderStatus(
      cancelOrderId,
      "cancelled",
      cancelNote.trim(),
    );
    if (updated) applyOrderUpdate(updated);
    setCancelOrderId(null);
    setCancelNote("");
  }, [applyOrderUpdate, cancelNote, cancelOrderId, patchOrderStatus]);

  const advanceOrderToReady = useCallback(
    async (orderId: number): Promise<boolean> => {
      let status: OrderStatus | undefined = ordersRef.current.find(
        (o) => o.id === orderId,
      )?.status;
      while (status && status !== "ready") {
        const next = nextStatusTowardReady(status);
        if (!next) return true;
        const updated = await patchOrderStatus(orderId, next, "");
        if (!updated) return false;
        applyOrderUpdate(updated);
        status = updated.status;
      }
      return true;
    },
    [applyOrderUpdate, patchOrderStatus],
  );

  const handleBulkAllToReady = useCallback(async () => {
    const list = [...ordersRef.current].sort(sortOrdersByCreated);
    const targets = list.filter((o) =>
      ["created", "modified", "preparing"].includes(o.status),
    );
    if (targets.length === 0) return;
    setBulkWorking(true);
    try {
      for (const o of targets) {
        if (!ordersRef.current.some((x) => x.id === o.id)) continue;
        const ok = await advanceOrderToReady(o.id);
        if (!ok) break;
      }
    } finally {
      setBulkWorking(false);
    }
  }, [advanceOrderToReady]);

  const handleBulkReadyToCompleted = useCallback(async () => {
    const ready = ordersRef.current.filter((o) => o.status === "ready");
    if (ready.length === 0) return;
    setBulkWorking(true);
    try {
      for (const o of ready.sort(sortOrdersByCreated)) {
        if (!ordersRef.current.some((x) => x.id === o.id && x.status === "ready"))
          continue;
        const updated = await patchOrderStatus(o.id, "completed", "");
        if (updated) applyOrderUpdate(updated);
        else break;
      }
    } finally {
      setBulkWorking(false);
    }
  }, [applyOrderUpdate, patchOrderStatus]);

  useEffect(() => {
    let isMounted = true;

    if (!eventCode) {
      return () => {
        isMounted = false;
      };
    }

    const rawUser = getUserJson();
    if (rawUser) {
      try {
        const u = JSON.parse(rawUser) as { role?: string };
        if (u.role === "guest") {
          router.replace(`/event/${eventCode}/guest`);
          return () => {
            isMounted = false;
          };
        }
      } catch {
        /* ignore */
      }
    }

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

        const sorted = (ordersData as Order[]).sort(sortOrdersByCreated);
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
        const sorted = (data as Order[]).sort(sortOrdersByCreated);
        if (isMounted) setOrders(sorted);
      } catch (e) {
        console.error(e);
      }
    }, 5000);

    return () => {
      isMounted = false;
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [eventCode, router]);

  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      if (orderTab === "queue")
        return o.status === "created" || o.status === "modified";
      if (orderTab === "cooking") return o.status === "preparing";
      return o.status === "ready";
    });
  }, [orders, orderTab]);

  const tabCounts = useMemo(() => {
    return {
      queue: orders.filter(
        (o) => o.status === "created" || o.status === "modified",
      ).length,
      cooking: orders.filter((o) => o.status === "preparing").length,
      ready: orders.filter((o) => o.status === "ready").length,
    };
  }, [orders]);

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
      setMenu(menu.map((m) => (m.id === id ? { ...m, is_available } : m)));
    }
  };

  if (loading) return <div className="p-6">Загрузка...</div>;
  if (!stall) return <div className="p-6">Нет данных</div>;

  return (
    <div className="min-h-screen p-6 bg-gray-50 flex flex-col gap-6">
      <Dialog
        open={cancelOrderId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setCancelOrderId(null);
            setCancelNote("");
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Отмена заказа</DialogTitle>
            <DialogDescription>
              Укажите причину отмены — её увидит гость.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Причина отмены"
            value={cancelNote}
            onChange={(e) => setCancelNote(e.target.value)}
            className="w-full"
          />
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                setCancelOrderId(null);
                setCancelNote("");
              }}
            >
              Назад
            </Button>
            <Button variant="destructive" onClick={() => void confirmCancelOrder()}>
              Отменить заказ
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card className="p-4 max-w-xl">
        <h2 className="text-2xl font-bold">{stall.name}</h2>
        <p>Код: {stall.abbr}</p>
        <p>Статус: {statusMap[stall.status]}</p>

        <div className="flex flex-col sm:flex-row gap-2 mt-2">
          {stall.status === "open" && (
            <Button
              variant="destructive"
              className="w-full sm:w-auto"
              onClick={handleCloseStall}
            >
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

      <Accordion type="single" collapsible>
        <AccordionItem value="menu">
          <AccordionTrigger>
            <Card className="p-4 max-w-xl">Меню</Card>
          </AccordionTrigger>
          <AccordionContent className="p-4 flex flex-col gap-2 max-w-xl">
            {menu.map((m) => (
              <Card
                key={m.id}
                className="p-3 flex items-center justify-between gap-4 max-w-md w-full"
              >
                <span className="font-medium whitespace-nowrap">{m.name}</span>

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

      <Accordion type="single" collapsible defaultValue="orders">
        <AccordionItem value="orders">
          <AccordionTrigger>
            <Card className="p-4 max-w-3xl w-full">Заказы</Card>
          </AccordionTrigger>
          <AccordionContent className="p-4 flex flex-col gap-4 max-w-3xl w-full">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
              <Button
                variant="secondary"
                size="sm"
                disabled={bulkWorking || stall.status !== "open"}
                onClick={() => void handleBulkAllToReady()}
                title="Для каждого заказа: в работу → готов (по шагам API)"
              >
                Все в «Готов»
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={bulkWorking || stall.status !== "open"}
                onClick={() => void handleBulkReadyToCompleted()}
              >
                Все «Готов» → «Выдан»
              </Button>
              {bulkWorking && (
                <span className="text-sm text-muted-foreground">Обработка…</span>
              )}
            </div>

            <div className="flex gap-1 p-1 bg-muted/60 rounded-lg w-fit flex-wrap">
              {(["queue", "cooking", "ready"] as const).map((tab) => (
                <Button
                  key={tab}
                  type="button"
                  variant={orderTab === tab ? "default" : "ghost"}
                  size="sm"
                  className="rounded-md"
                  onClick={() => setOrderTab(tab)}
                >
                  {TAB_LABELS[tab]} ({tabCounts[tab]})
                </Button>
              ))}
            </div>

            <div className="flex flex-col gap-3 w-full">
              {filteredOrders.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  В этой вкладке нет заказов.
                </p>
              ) : (
                filteredOrders.map((o) => {
                  const transitions = ORDER_TRANSITIONS[o.status] ?? [];
                  const canPreparing = transitions.includes("preparing");
                  const canReady = transitions.includes("ready");
                  const canCompleted = transitions.includes("completed");
                  const canCancelled = transitions.includes("cancelled");

                  return (
                    <Card
                      key={o.id}
                      className="p-3 flex flex-col gap-3 w-full border border-border/80"
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <span className="font-medium">
                            {o.order_number}{" "}
                            <span className="text-muted-foreground">
                              ({o.guest_name})
                            </span>
                          </span>
                          <div className="text-sm text-muted-foreground mt-0.5">
                            {ORDER_STATUS_LABELS[o.status]} ·{" "}
                            {new Date(o.created_at).toLocaleTimeString([], {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </div>
                        </div>

                        <details className="group shrink-0 sm:ml-auto">
                          <summary className="cursor-pointer list-none rounded-md border px-2 py-1 text-sm font-medium hover:bg-muted/80 [&::-webkit-details-marker]:hidden flex items-center gap-1">
                            <span aria-hidden>⋯</span>
                            <span className="text-xs text-muted-foreground">
                              ещё
                            </span>
                          </summary>
                          <div className="mt-2 p-2 rounded-md border bg-background">
                            <label className="text-xs text-muted-foreground block mb-1">
                              Все переходы
                            </label>
                            <select
                              value={o.status}
                              onChange={(e) =>
                                void handleOrderStatusChange(
                                  o.id,
                                  e.target.value as OrderStatus,
                                )
                              }
                              className="border border-gray-300 rounded-md p-1 w-full min-w-[10rem]"
                            >
                              <option value={o.status}>
                                {ORDER_STATUS_LABELS[o.status]}
                              </option>
                              {transitions.map((s) => (
                                <option key={s} value={s}>
                                  {ORDER_STATUS_LABELS[s]}
                                </option>
                              ))}
                            </select>
                          </div>
                        </details>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {canPreparing && (
                          <Button
                            size="sm"
                            disabled={bulkWorking}
                            onClick={() =>
                              void handleOrderStatusChange(o.id, "preparing")
                            }
                          >
                            В работу
                          </Button>
                        )}
                        {canReady && (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={bulkWorking}
                            onClick={() => void handleOrderStatusChange(o.id, "ready")}
                          >
                            Готов
                          </Button>
                        )}
                        {canCompleted && (
                          <Button
                            size="sm"
                            className="bg-green-600 text-white hover:bg-green-700"
                            disabled={bulkWorking}
                            onClick={() =>
                              void handleOrderStatusChange(o.id, "completed")
                            }
                          >
                            Выдан
                          </Button>
                        )}
                        {canCancelled && (
                          <Button
                            size="sm"
                            variant="destructive"
                            disabled={bulkWorking}
                            onClick={() => void handleOrderStatusChange(o.id, "cancelled")}
                          >
                            Отмена
                          </Button>
                        )}
                      </div>

                      <div className="flex flex-col text-sm border-t pt-2">
                        {o.items.map((item) => (
                          <span key={item.id}>
                            {item.menu_item_name} ×{item.quantity}
                          </span>
                        ))}
                      </div>

                      {o.cancel_note ? (
                        <div className="text-sm text-red-600">
                          Причина: {o.cancel_note}
                        </div>
                      ) : null}
                    </Card>
                  );
                })
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
