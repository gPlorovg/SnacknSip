"""Serializers for organizer-facing endpoints."""

from rest_framework import serializers

from apps.api.models import Event, Menu, MenuItem, Order, Stall
from apps.api.models.guest_roles import GuestRole, GuestRoleItem
from apps.api.models.users import EventUser


# ─────────────────────────────────────────────────────
# Event
# ─────────────────────────────────────────────────────


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "code",
            "name",
            "location",
            "start_time",
            "end_time",
            "is_open",
            "closed_at",
            "created_at",
        ]
        read_only_fields = ["id", "code", "is_open", "closed_at", "created_at"]


class EventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["name", "location", "start_time", "end_time"]


# ─────────────────────────────────────────────────────
# Stall
# ─────────────────────────────────────────────────────


class OrgStallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stall
        fields = ["id", "name", "abbr", "menu", "status"]
        read_only_fields = ["id"]

    def validate_abbr(self, value):
        return value.upper()


class OrgStallCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stall
        fields = ["name", "abbr", "menu"]

    def validate_abbr(self, value):
        if value:
            return value.upper()
        return value


# ─────────────────────────────────────────────────────
# Menu
# ─────────────────────────────────────────────────────


class MenuItemSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = MenuItem
        fields = ["id", "name", "description", "price", "image"]
        read_only_fields = ["id"]


class MenuSerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = Menu
        fields = ["id", "name", "items"]
        read_only_fields = ["id"]


class MenuCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ["name"]


# ─────────────────────────────────────────────────────
# Guest roles
# ─────────────────────────────────────────────────────


class GuestRoleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestRoleItem
        fields = ["id", "menu_item", "max_quantity"]
        read_only_fields = ["id"]


class GuestRoleSerializer(serializers.ModelSerializer):
    items = GuestRoleItemSerializer(source="allowed_items", many=True, read_only=True)

    class Meta:
        model = GuestRole
        fields = ["id", "name", "items"]
        read_only_fields = ["id"]


class GuestRoleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestRole
        fields = ["name"]


# ─────────────────────────────────────────────────────
# Users (EventUser management)
# ─────────────────────────────────────────────────────


class EventUserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventUser
        fields = [
            "id",
            "login",
            "telegram_username",
            "telegram_id",
            "name",
            "role",
            "is_blocked",
        ]


class EventUserCreateSerializer(serializers.Serializer):
    """Create a new EventUser. Password auto-generated if login provided."""

    name = serializers.CharField()
    role = serializers.ChoiceField(choices=EventUser.Role.choices)
    login = serializers.EmailField(
        required=False,
        allow_null=True,
        help_text="Email для входа по паролю.",
    )
    telegram_username = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Telegram username (без @). Орг добавляет по нему.",
    )

    def validate(self, data):
        if not data.get("login") and not data.get("telegram_username"):
            raise serializers.ValidationError(
                "Укажите хотя бы один идентификатор: login (email) или telegram_username."
            )
        return data


class EventUserDetailSerializer(serializers.ModelSerializer):
    """Detailed view including decrypted password (for organizer only)."""

    plain_password = serializers.SerializerMethodField()

    class Meta:
        model = EventUser
        fields = [
            "id",
            "login",
            "telegram_username",
            "telegram_id",
            "name",
            "role",
            "is_blocked",
            "plain_password",
        ]

    def get_plain_password(self, obj) -> str | None:
        if obj.password_encrypted:
            return obj.get_plain_password()
        return None


class BlockUserSerializer(serializers.Serializer):
    is_blocked = serializers.BooleanField()


# ─────────────────────────────────────────────────────
# Assign role to guest
# ─────────────────────────────────────────────────────


class AssignRoleSerializer(serializers.Serializer):
    guest_id = serializers.IntegerField()
    role_id = serializers.IntegerField()


# ─────────────────────────────────────────────────────
# Orders (read-only for organizer)
# ─────────────────────────────────────────────────────


class OrgOrderSerializer(serializers.ModelSerializer):
    from apps.api.serializers.guest import OrderItemSerializer

    items = OrderItemSerializer(many=True, read_only=True)
    guest_name = serializers.CharField(source="guest.name", read_only=True)
    stall_name = serializers.CharField(source="stall.name", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "guest_name",
            "stall_name",
            "items",
            "cancel_note",
            "created_at",
            "updated_at",
        ]
