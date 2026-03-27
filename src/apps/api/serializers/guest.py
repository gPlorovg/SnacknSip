"""Serializers for guest-facing endpoints."""

from rest_framework import serializers

from apps.api.models import MenuItem, Notification, Order, OrderItem, Stall
from apps.api.models.stalls import StallMenuItem


class MenuItemSerializer(serializers.ModelSerializer):
    is_available = serializers.SerializerMethodField(
        help_text="Доступно на этой точке (не в стоп-листе)"
    )

    class Meta:
        model = MenuItem
        fields = ["id", "name", "description", "price", "image", "is_available"]

    def get_is_available(self, obj) -> bool:
        # stall injected by view via serializer context
        stall = self.context.get("stall")
        if stall is None:
            return True
        stall_item = StallMenuItem.objects.filter(stall=stall, menu_item=obj).first()
        if stall_item is None:
            return True  # not in stop-list → available
        return stall_item.is_available


class StallListSerializer(serializers.ModelSerializer):
    """Compact stall info for list view."""

    class Meta:
        model = Stall
        fields = ["id", "name", "abbr", "status"]


class StallDetailSerializer(serializers.ModelSerializer):
    """Stall with its menu items (stop-list applied)."""

    menu_items = serializers.SerializerMethodField()

    class Meta:
        model = Stall
        fields = ["id", "name", "abbr", "status", "menu_items"]

    def get_menu_items(self, stall) -> list:
        if not stall.menu:
            return []
        items = stall.menu.items.all()
        return MenuItemSerializer(
            items,
            many=True,
            context={**self.context, "stall": stall},
        ).data


class OrderItemInputSerializer(serializers.Serializer):
    """One line in the order request."""

    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=50)


class CreateOrderSerializer(serializers.Serializer):
    """Request body for POST /orders/."""

    stall_id = serializers.IntegerField()
    items = OrderItemInputSerializer(many=True, min_length=1)


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source="menu_item.name", read_only=True)
    menu_item_price = serializers.DecimalField(
        source="menu_item.price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "menu_item_id",
            "menu_item_name",
            "menu_item_price",
            "quantity",
            "removed",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    stall_name = serializers.CharField(source="stall.name", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "stall_id",
            "stall_name",
            "status",
            "items",
            "cancel_note",
            "created_at",
            "updated_at",
        ]


class OrderStatusSerializer(serializers.ModelSerializer):
    """Lightweight status-only response for polling."""

    class Meta:
        model = Order
        fields = ["id", "order_number", "status", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "message", "order_id", "order_status", "is_read", "created_at"]
