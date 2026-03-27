"""Serializers for staff-facing endpoints."""

from rest_framework import serializers

from apps.api.models import Order, Stall
from apps.api.models.orders import ORDER_TRANSITIONS, OrderStatus
from apps.api.models.stalls import StallMenuItem
from apps.api.serializers.guest import OrderItemSerializer


class StallStatusSerializer(serializers.ModelSerializer):
    """Full stall info for staff."""

    class Meta:
        model = Stall
        fields = ["id", "name", "abbr", "status"]
        read_only_fields = ["id", "name", "abbr"]


class StallMenuItemSerializer(serializers.ModelSerializer):
    """Menu item with current stop-list status for this stall."""

    menu_item_id = serializers.IntegerField(source="menu_item.id", read_only=True)
    name = serializers.CharField(source="menu_item.name", read_only=True)
    price = serializers.DecimalField(
        source="menu_item.price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = StallMenuItem
        fields = ["id", "menu_item_id", "name", "price", "is_available"]


class ToggleMenuItemSerializer(serializers.Serializer):
    """Request body for toggling item availability."""

    is_available = serializers.BooleanField()


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Staff updates order status."""

    status = serializers.ChoiceField(choices=OrderStatus.choices)
    cancel_note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        order = self.context.get("order")
        if order and not order.can_transition_to(data["status"]):
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Нельзя перевести из «{order.status}» в «{data['status']}». "
                        f"Доступные переходы: {ORDER_TRANSITIONS.get(order.status, [])}"
                    )
                }
            )
        return data


class StaffOrderSerializer(serializers.ModelSerializer):
    """Order as seen by staff."""

    items = OrderItemSerializer(many=True, read_only=True)
    guest_name = serializers.CharField(source="guest.name", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "guest_name",
            "items",
            "cancel_note",
            "created_at",
            "updated_at",
        ]


class RedistributeOrderSerializer(serializers.Serializer):
    """
    Request body for manual order redistribution to another stall.
    Items can optionally be adjusted.
    """

    target_stall_id = serializers.IntegerField()
