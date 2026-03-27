"""Guest-facing API views."""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.auth.permissions import IsGuest
from apps.api.models import (
    MenuItem,
    Notification,
    Order,
    OrderItem,
    Stall,
)
from apps.api.models.guest_roles import GuestLimitUsage, GuestRoleItem
from apps.api.serializers.guest import (
    CreateOrderSerializer,
    NotificationSerializer,
    OrderSerializer,
    OrderStatusSerializer,
    StallDetailSerializer,
    StallListSerializer,
)


def _get_guest_event(request):
    """Return the event attached to the authenticated EventUser."""
    return getattr(request.user, "_event", None) or request.user.event


# ─────────────────────────────────────────────────────
# Stalls
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Guest — Stalls"], summary="Список открытых точек мероприятия")
class StallListView(APIView):
    permission_classes = [IsGuest]

    def get(self, request):
        event = _get_guest_event(request)
        stalls = Stall.objects.filter(event=event, status="open").select_related("menu")
        return Response(StallListSerializer(stalls, many=True).data)


@extend_schema(tags=["Guest — Stalls"], summary="Меню точки (со стоп-листом)")
class StallDetailView(APIView):
    permission_classes = [IsGuest]

    def get(self, request, pk):
        event = _get_guest_event(request)
        try:
            stall = Stall.objects.select_related("menu").get(
                pk=pk, event=event, status="open"
            )
        except Stall.DoesNotExist:
            return Response(
                {"detail": "Точка не найдена или закрыта."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(StallDetailSerializer(stall, context={"request": request}).data)


# ─────────────────────────────────────────────────────
# Orders
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Guest — Orders"], summary="Список моих заказов")
class OrderListView(APIView):
    permission_classes = [IsGuest]

    def get(self, request):
        event = _get_guest_event(request)
        orders = (
            Order.objects.filter(guest=request.user, event=event)
            .prefetch_related("items__menu_item")
            .select_related("stall")
        )
        return Response(OrderSerializer(orders, many=True).data)

    @extend_schema(
        tags=["Guest — Orders"],
        summary="Создать заказ",
        request=CreateOrderSerializer,
        responses={201: OrderSerializer},
    )
    def post(self, request):
        event = _get_guest_event(request)
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate stall
        try:
            stall = Stall.objects.select_related("menu").get(
                pk=data["stall_id"], event=event, status="open"
            )
        except Stall.DoesNotExist:
            return Response(
                {"detail": "Точка не найдена или закрыта."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate items
        errors = []
        validated_items = []
        for item_data in data["items"]:
            menu_item_id = item_data["menu_item_id"]
            quantity = item_data["quantity"]

            # Check menu item exists in stall menu
            try:
                menu_item = MenuItem.objects.get(pk=menu_item_id, menu=stall.menu)
            except MenuItem.DoesNotExist:
                errors.append(f"Позиция {menu_item_id} не найдена в меню точки.")
                continue

            # Check stop-list
            from apps.api.models.stalls import StallMenuItem

            stall_item = StallMenuItem.objects.filter(
                stall=stall, menu_item=menu_item
            ).first()
            if stall_item and not stall_item.is_available:
                errors.append(f"«{menu_item.name}» сейчас недоступна (стоп-лист).")
                continue

            # Check guest limits
            limit_error = _check_and_hold_limit(request.user, menu_item, quantity)
            if limit_error:
                errors.append(limit_error)
                continue

            validated_items.append((menu_item, quantity))

        if errors:
            # Release any holds already made
            for menu_item, quantity in validated_items:
                _release_limit(request.user, menu_item, quantity)
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        # Create order
        with transaction.atomic():
            order = Order.objects.create(
                event=event,
                guest=request.user,
                stall=stall,
            )
            for menu_item, quantity in validated_items:
                OrderItem.objects.create(
                    order=order, menu_item=menu_item, quantity=quantity
                )

        order.refresh_from_db()
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Guest — Orders"], summary="Детали заказа")
class OrderDetailView(APIView):
    permission_classes = [IsGuest]

    def _get_order(self, request, pk):
        event = _get_guest_event(request)
        try:
            return (
                Order.objects.prefetch_related("items__menu_item")
                .select_related("stall")
                .get(pk=pk, guest=request.user, event=event)
            )
        except Order.DoesNotExist:
            return None

    def get(self, request, pk):
        order = self._get_order(request, pk)
        if not order:
            return Response(
                {"detail": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(OrderSerializer(order).data)


@extend_schema(
    tags=["Guest — Orders"],
    summary="Статус заказа (для polling)",
    responses={200: OrderStatusSerializer},
)
class OrderStatusView(APIView):
    permission_classes = [IsGuest]

    def get(self, request, pk):
        event = _get_guest_event(request)
        try:
            order = Order.objects.only(
                "id", "order_number", "status", "updated_at"
            ).get(pk=pk, guest=request.user, event=event)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(OrderStatusSerializer(order).data)


# ─────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────


@extend_schema(tags=["Guest — Notifications"], summary="Мои уведомления")
class NotificationListView(APIView):
    permission_classes = [IsGuest]

    def get(self, request):
        notifications = Notification.objects.filter(
            event_user=request.user
        ).select_related("order")
        return Response(NotificationSerializer(notifications, many=True).data)


@extend_schema(
    tags=["Guest — Notifications"], summary="Отметить уведомление как прочитанное"
)
class NotificationReadView(APIView):
    permission_classes = [IsGuest]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, event_user=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": "Не найдено."}, status=status.HTTP_404_NOT_FOUND)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────────────
# Limit helpers
# ─────────────────────────────────────────────────────


def _check_and_hold_limit(event_user, menu_item, quantity: int) -> str | None:
    """
    Attempts to deduct `quantity` from guest limits.
    Returns error message string if limit exceeded, else None.
    Modifies GuestLimitUsage immediately (acts as a hold).
    """
    try:
        guest_profile = event_user.guest_profile
    except Exception:
        return None  # no guest profile = no limit restriction

    role = getattr(guest_profile, "role", None)
    if not role:
        return None

    try:
        role_item = GuestRoleItem.objects.get(role=role, menu_item=menu_item)
    except GuestRoleItem.DoesNotExist:
        return f"«{menu_item.name}» не входит в ваш пакет."

    usage, _ = GuestLimitUsage.objects.get_or_create(
        event_guest=guest_profile, menu_item=menu_item
    )

    if usage.used_quantity + quantity > role_item.max_quantity:
        remaining = role_item.max_quantity - usage.used_quantity
        return (
            f"«{menu_item.name}»: доступно {remaining} из {role_item.max_quantity}. "
            f"Запрошено: {quantity}."
        )

    usage.used_quantity += quantity
    usage.save(update_fields=["used_quantity"])
    return None


def _release_limit(event_user, menu_item, quantity: int) -> None:
    """Return `quantity` back to guest limits (on cancel/modification)."""
    try:
        guest_profile = event_user.guest_profile
    except Exception:
        return

    usage = GuestLimitUsage.objects.filter(
        event_guest=guest_profile, menu_item=menu_item
    ).first()
    if usage:
        usage.used_quantity = max(0, usage.used_quantity - quantity)
        usage.save(update_fields=["used_quantity"])
