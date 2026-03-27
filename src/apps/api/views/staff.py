"""Staff-facing API views."""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.auth.permissions import IsOrganizerOrStaff, IsStaff
from apps.api.models import MenuItem, Notification, Order, Stall
from apps.api.models.orders import OrderStatus
from apps.api.models.stalls import StallMenuItem, StallStatus
from drf_spectacular.utils import OpenApiExample
from apps.api.serializers.staff import (
    OrderStatusUpdateSerializer,
    RedistributeOrderSerializer,
    StaffOrderSerializer,
    StallMenuItemSerializer,
    StallStatusSerializer,
    ToggleMenuItemSerializer,
)
from apps.api.views.guest import _release_limit
from apps.api.tasks.notifications import send_push_notification


def _get_staff_stall(request) -> Stall | None:
    """Return the stall the staff member is assigned to."""
    try:
        return request.user.staff_profile.stall
    except Exception:
        return None


def _create_notification(event_user, order, message: str):
    notification = Notification.objects.create(
        event_user=event_user,
        order=order,
        message=message,
        order_status=order.status,
    )
    transaction.on_commit(lambda: send_push_notification.delay(notification.id))


# ─────────────────────────────────────────────────────
# Stall management
# ─────────────────────────────────────────────────────


@extend_schema(
    tags=["Staff — Stall"],
    summary="Моя точка (текущий статус)",
    examples=[
        OpenApiExample(
            name="Статус точки",
            value={"id": 1, "name": "Бар", "status": "open"},
            response_only=True,
        )
    ],
)
class MyStallView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        stall = _get_staff_stall(request)
        if not stall:
            return Response(
                {"detail": "Вы не привязаны ни к одной точке."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(StallStatusSerializer(stall).data)


@extend_schema(
    tags=["Staff — Stall"],
    summary="Открыть точку",
    examples=[
        OpenApiExample(
            name="Успешное открытие",
            value={"id": 1, "name": "Бар", "status": "open"},
            response_only=True,
        )
    ],
)
class OpenStallView(APIView):
    permission_classes = [IsStaff]

    def post(self, request):
        stall = _get_staff_stall(request)
        if not stall:
            return Response(
                {"detail": "Точка не найдена."}, status=status.HTTP_404_NOT_FOUND
            )
        stall.status = StallStatus.OPEN
        stall.save(update_fields=["status"])
        return Response(StallStatusSerializer(stall).data)


@extend_schema(
    tags=["Staff — Stall"],
    summary="Закрыть точку",
    examples=[
        OpenApiExample(
            name="Ответ при закрытии",
            value={
                "detail": "Точка закрыта.",
                "pending_orders": 3,
                "hint": "Используйте POST /staff/orders/redistribute/ для перераспределения или отмены заказов.",
            },
            response_only=True,
        )
    ],
)
class CloseStallView(APIView):
    permission_classes = [IsStaff]

    def post(self, request):
        stall = _get_staff_stall(request)
        if not stall:
            return Response(
                {"detail": "Точка не найдена."}, status=status.HTTP_404_NOT_FOUND
            )

        pending_count = Order.objects.filter(
            stall=stall,
            status__in=[
                OrderStatus.CREATED,
                OrderStatus.PREPARING,
                OrderStatus.MODIFIED,
            ],
        ).count()

        stall.status = StallStatus.CLOSED
        stall.save(update_fields=["status"])

        return Response(
            {
                "detail": "Точка закрыта.",
                "pending_orders": pending_count,
                "hint": (
                    "Используйте POST /staff/stall/orders/redistribute/ "
                    "для перераспределения или отмены заказов."
                )
                if pending_count
                else None,
            }
        )


# ─────────────────────────────────────────────────────
# Stop-list (menu availability)
# ─────────────────────────────────────────────────────


@extend_schema(
    tags=["Staff — Menu"],
    summary="Меню точки (управление стоп-листом)",
    examples=[
        OpenApiExample(
            name="Список позиций",
            value=[
                {
                    "id": 1,
                    "menu_item": {
                        "id": 5,
                        "name": "Эспрессо",
                        "description": "Двойной",
                        "image": "...",
                    },
                    "is_available": True,
                }
            ],
            response_only=True,
        )
    ],
)
class StallMenuView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        stall = _get_staff_stall(request)
        if not stall or not stall.menu:
            return Response([])
        items = StallMenuItem.objects.filter(stall=stall).select_related("menu_item")
        return Response(StallMenuItemSerializer(items, many=True).data)


@extend_schema(
    tags=["Staff — Menu"],
    summary="Изменить доступность позиции (стоп-лист)",
    request=ToggleMenuItemSerializer,
    responses={200: StallMenuItemSerializer},
    examples=[
        OpenApiExample(
            name="Убрать в стоп-лист",
            value={"is_available": False},
            request_only=True,
        ),
        OpenApiExample(
            name="Ответ",
            value={
                "id": 1,
                "menu_item": {
                    "id": 5,
                    "name": "Эспрессо",
                    "description": "Двойной",
                    "image": "...",
                },
                "is_available": False,
            },
            response_only=True,
        ),
    ],
)
class ToggleMenuItemView(APIView):
    permission_classes = [IsStaff]

    def patch(self, request, item_id):
        stall = _get_staff_stall(request)
        if not stall:
            return Response(
                {"detail": "Точка не найдена."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            stall_item = StallMenuItem.objects.select_related("menu_item").get(
                stall=stall, menu_item_id=item_id
            )
        except StallMenuItem.DoesNotExist:
            return Response(
                {"detail": "Позиция не найдена в меню точки."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ToggleMenuItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_available = serializer.validated_data["is_available"]

        # If disabling — add to stop-list and update active orders
        if not new_available and stall_item.is_available:
            _handle_stop_list(stall, stall_item.menu_item)

        stall_item.is_available = new_available
        stall_item.save(update_fields=["is_available"])
        return Response(StallMenuItemSerializer(stall_item).data)


def _handle_stop_list(stall: Stall, menu_item: MenuItem):
    """
    When an item is removed from menu:
    - Mark it as removed in all active orders at this stall
    - Return limits to guests
    - Notify guests
    - Set order status to MODIFIED if it had active items removed
    """
    active_statuses = [OrderStatus.CREATED, OrderStatus.PREPARING, OrderStatus.MODIFIED]
    orders = Order.objects.filter(
        stall=stall, status__in=active_statuses
    ).prefetch_related("items__menu_item", "guest")

    for order in orders:
        affected_items = order.items.filter(menu_item=menu_item, removed=False)
        if not affected_items.exists():
            continue

        with transaction.atomic():
            for oi in affected_items:
                oi.removed = True
                oi.save(update_fields=["removed"])
                # Return limits
                _release_limit(order.guest, menu_item, oi.quantity)

            # Check if order still has items
            remaining = order.items.filter(removed=False).count()
            if remaining == 0:
                order.status = OrderStatus.CANCELLED
                order.cancel_note = (
                    f"Все позиции убраны из стоп-листа ({menu_item.name})."
                )
            else:
                order.status = OrderStatus.MODIFIED
            order.save(update_fields=["status", "cancel_note"])

            _create_notification(
                order.guest,
                order,
                f"«{menu_item.name}» убрана из меню точки. Ваш заказ изменён.",
            )


# ─────────────────────────────────────────────────────
# Order management
# ─────────────────────────────────────────────────────


@extend_schema(
    tags=["Staff — Orders"],
    summary="Заказы на моей точке",
    examples=[
        OpenApiExample(
            name="Список заказов",
            value=[
                {
                    "id": 1,
                    "order_number": "TECH24-COF-001",
                    "status": "created",
                    "items": [
                        {"id": 1, "menu_item": {"name": "Эспрессо"}, "quantity": 1}
                    ],
                }
            ],
            response_only=True,
        )
    ],
)
class StallOrderListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        stall = _get_staff_stall(request)
        if not stall:
            return Response([])
        active_statuses = [
            OrderStatus.CREATED,
            OrderStatus.PREPARING,
            OrderStatus.MODIFIED,
            OrderStatus.READY,
        ]
        orders = (
            Order.objects.filter(stall=stall, status__in=active_statuses)
            .prefetch_related("items__menu_item")
            .select_related("guest")
        )
        return Response(StaffOrderSerializer(orders, many=True).data)


@extend_schema(
    tags=["Staff — Orders"],
    summary="Обновить статус заказа",
    request=OrderStatusUpdateSerializer,
    responses={200: StaffOrderSerializer},
    examples=[
        OpenApiExample(
            name="Взять в работу",
            value={"status": "preparing"},
            request_only=True,
        ),
        OpenApiExample(
            name="Отменить (нет молока)",
            value={"status": "cancelled", "cancel_note": "Закончилось молоко"},
            request_only=True,
        ),
        OpenApiExample(
            name="Ответ",
            value={
                "id": 1,
                "order_number": "TECH24-COF-001",
                "status": "preparing",
                "items": [{"id": 1, "menu_item": {"name": "Эспрессо"}, "quantity": 1}],
            },
            response_only=True,
        ),
    ],
)
class UpdateOrderStatusView(APIView):
    permission_classes = [IsStaff]

    def patch(self, request, pk):
        stall = _get_staff_stall(request)
        if not stall:
            return Response(
                {"detail": "Точка не найдена."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            order = (
                Order.objects.prefetch_related("items__menu_item")
                .select_related("guest")
                .get(pk=pk, stall=stall)
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = OrderStatusUpdateSerializer(
            data=request.data, context={"order": order}
        )
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        cancel_note = serializer.validated_data.get("cancel_note", "")

        with transaction.atomic():
            if new_status == OrderStatus.CANCELLED:
                # Return limits for all active items
                for oi in order.items.filter(removed=False):
                    _release_limit(order.guest, oi.menu_item, oi.quantity)
                order.cancel_note = cancel_note

            order.status = new_status
            order.save(update_fields=["status", "cancel_note"])

            _create_notification(
                order.guest,
                order,
                _status_message(new_status, order.order_number),
            )

        return Response(StaffOrderSerializer(order).data)


def _status_message(new_status: str, order_number: str) -> str:
    messages = {
        OrderStatus.PREPARING: f"Ваш заказ {order_number} принят в работу.",
        OrderStatus.READY: f"Ваш заказ {order_number} готов! Подойдите к точке.",
        OrderStatus.COMPLETED: f"Заказ {order_number} выдан. Приятного аппетита!",
        OrderStatus.CANCELLED: f"Заказ {order_number} отменён.",
    }
    return messages.get(new_status, f"Статус заказа {order_number} обновлён.")


# ─────────────────────────────────────────────────────
# Order redistribution on stall close
# ─────────────────────────────────────────────────────


@extend_schema(
    tags=["Staff — Orders"],
    summary="Автоматически перераспределить заказы закрытой точки",
    description=(
        "Заказ перераспределяется на другую точку если её меню содержит "
        "все позиции заказа. Иначе требует ручной обработки."
    ),
    examples=[
        OpenApiExample(
            name="Пример перераспределения",
            value={
                "redistributed": ["TECH24-COF-001", "TECH24-COF-002"],
                "failed": ["TECH24-COF-003"],
                "hint": "Заказы из 'failed' требуют ручной обработки или отмены.",
            },
            response_only=True,
        )
    ],
)
class AutoRedistributeView(APIView):
    permission_classes = [IsOrganizerOrStaff]

    def post(self, request):
        stall = _get_staff_stall(request)
        if not stall:
            # Organizer can pass stall_id
            stall_id = request.data.get("stall_id")
            if not stall_id:
                return Response(
                    {"detail": "stall_id required for organizers."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                stall = Stall.objects.get(
                    pk=stall_id, event=request.user.organized_events.first()
                )
            except Stall.DoesNotExist:
                return Response(
                    {"detail": "Точка не найдена."}, status=status.HTTP_404_NOT_FOUND
                )

        active_statuses = [
            OrderStatus.CREATED,
            OrderStatus.PREPARING,
            OrderStatus.MODIFIED,
        ]
        pending_orders = Order.objects.filter(
            stall=stall, status__in=active_statuses
        ).prefetch_related("items__menu_item")

        # Other open stalls in the same event
        other_stalls = (
            Stall.objects.filter(event=stall.event, status=StallStatus.OPEN)
            .exclude(pk=stall.pk)
            .prefetch_related("stall_items__menu_item")
        )

        redistributed = []
        failed = []

        for order in pending_orders:
            active_items = order.items.filter(removed=False)
            order_menu_ids = set(active_items.values_list("menu_item_id", flat=True))

            target = _find_stall_for_order(other_stalls, order_menu_ids)

            if target:
                with transaction.atomic():
                    order.stall = target
                    order.status = OrderStatus.CREATED
                    order.save(update_fields=["stall", "status"])
                    _create_notification(
                        order.guest,
                        order,
                        f"Ваш заказ {order.order_number} перенаправлен на точку «{target.name}».",
                    )
                redistributed.append(order.order_number)
            else:
                failed.append(order.order_number)

        return Response(
            {
                "redistributed": redistributed,
                "failed": failed,
                "hint": "Заказы из 'failed' требуют ручной обработки или отмены."
                if failed
                else None,
            }
        )


def _find_stall_for_order(stalls, order_menu_ids: set) -> Stall | None:
    """Find the first stall whose available menu covers all order items."""
    for stall in stalls:
        available_ids = set(
            stall.stall_items.filter(is_available=True).values_list(
                "menu_item_id", flat=True
            )
        )
        if order_menu_ids.issubset(available_ids):
            return stall
    return None


@extend_schema(
    tags=["Staff — Orders"],
    summary="Ручное перераспределение одного заказа на другую точку",
    request=RedistributeOrderSerializer,
    responses={200: StaffOrderSerializer},
    examples=[
        OpenApiExample(
            name="Перенести на точку ID=2",
            value={"target_stall_id": 2},
            request_only=True,
        ),
        OpenApiExample(
            name="Ответ",
            value={
                "id": 1,
                "order_number": "TECH24-COF-001",
                "status": "created",
                "items": [{"id": 1, "menu_item": {"name": "Эспрессо"}, "quantity": 1}],
            },
            response_only=True,
        ),
    ],
)
class ManualRedistributeView(APIView):
    permission_classes = [IsOrganizerOrStaff]

    def post(self, request, pk):
        try:
            order = (
                Order.objects.select_related("guest", "stall__event")
                .prefetch_related("items__menu_item")
                .get(pk=pk)
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = RedistributeOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            target = Stall.objects.get(
                pk=serializer.validated_data["target_stall_id"],
                event=order.event,
                status=StallStatus.OPEN,
            )
        except Stall.DoesNotExist:
            return Response(
                {"detail": "Целевая точка не найдена или закрыта."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            order.stall = target
            order.status = OrderStatus.CREATED
            order.save(update_fields=["stall", "status"])
            _create_notification(
                order.guest,
                order,
                f"Ваш заказ {order.order_number} перенаправлен на точку «{target.name}».",
            )

        return Response(StaffOrderSerializer(order).data)


@extend_schema(
    tags=["Staff — Orders"],
    summary="Массовая отмена заказов на закрытой точке",
    examples=[
        OpenApiExample(
            name="Отмена с комментарием",
            value={"cancel_note": "Точка закрыта, молоко скисло."},
            request_only=True,
        ),
        OpenApiExample(
            name="Результат отмены",
            value={"cancelled": ["TECH24-COF-003"], "count": 1},
            response_only=True,
        ),
    ],
)
class BulkCancelOrdersView(APIView):
    permission_classes = [IsOrganizerOrStaff]

    def post(self, request):
        stall = _get_staff_stall(request)
        if not stall:
            stall_id = request.data.get("stall_id")
            try:
                stall = Stall.objects.get(pk=stall_id)
            except (Stall.DoesNotExist, TypeError):
                return Response(
                    {"detail": "stall_id required."}, status=status.HTTP_400_BAD_REQUEST
                )

        cancel_note = request.data.get("cancel_note", "Точка закрыта. Заказ отменён.")
        active_statuses = [
            OrderStatus.CREATED,
            OrderStatus.PREPARING,
            OrderStatus.MODIFIED,
        ]

        orders = Order.objects.filter(
            stall=stall, status__in=active_statuses
        ).prefetch_related("items__menu_item", "guest")

        cancelled = []
        with transaction.atomic():
            for order in orders:
                for oi in order.items.filter(removed=False):
                    _release_limit(order.guest, oi.menu_item, oi.quantity)
                order.status = OrderStatus.CANCELLED
                order.cancel_note = cancel_note
                order.save(update_fields=["status", "cancel_note"])
                _create_notification(
                    order.guest,
                    order,
                    f"Заказ {order.order_number} отменён: {cancel_note}",
                )
                cancelled.append(order.order_number)

        return Response({"cancelled": cancelled, "count": len(cancelled)})
