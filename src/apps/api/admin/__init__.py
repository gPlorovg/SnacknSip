"""Admin registrations for all SnacknSip models."""

from django.contrib import admin

from apps.api.models import (
    Event,
    EventGuest,
    GuestLimitUsage,
    GuestRole,
    GuestRoleItem,
    Menu,
    MenuItem,
    Notification,
    Order,
    OrderItem,
    OrganizerProfile,
    Stall,
    StallMenuItem,
    StallStaff,
)
from apps.api.models.users import EventUser


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("menu_item", "quantity", "removed")


class GuestRoleItemInline(admin.TabularInline):
    model = GuestRoleItem
    extra = 1


class StallMenuItemInline(admin.TabularInline):
    model = StallMenuItem
    extra = 0


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user__email")
    raw_id_fields = ("user",)


@admin.register(EventUser)
class EventUserAdmin(admin.ModelAdmin):
    list_display = (
        "login",
        "telegram_username",
        "name",
        "event",
        "role",
        "is_available_display",
        "telegram_id",
    )
    list_filter = ("role", "is_blocked", "event")
    search_fields = ("login", "telegram_username", "name")
    readonly_fields = ("password_hash", "telegram_id", "created_at", "updated_at")

    @admin.display(description="Доступен", boolean=True)
    def is_available_display(self, obj):
        return not obj.is_blocked


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organizer", "is_open", "start_time", "end_time")
    list_filter = ("is_open",)
    search_fields = ("code", "name")
    readonly_fields = ("code", "closed_at", "created_at")


@admin.register(EventGuest)
class EventGuestAdmin(admin.ModelAdmin):
    list_display = ("event_user", "event", "role")
    list_filter = ("event",)
    raw_id_fields = ("event_user",)


@admin.register(StallStaff)
class StallStaffAdmin(admin.ModelAdmin):
    list_display = ("event_user", "stall")
    raw_id_fields = ("event_user",)


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("name", "event")
    list_filter = ("event",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "menu", "price")
    list_filter = ("menu__event",)
    search_fields = ("name",)


@admin.register(Stall)
class StallAdmin(admin.ModelAdmin):
    list_display = ("name", "abbr", "event", "menu", "status")
    list_filter = ("event", "status")
    inlines = [StallMenuItemInline]


@admin.register(GuestRole)
class GuestRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "event")
    list_filter = ("event",)
    inlines = [GuestRoleItemInline]


@admin.register(GuestLimitUsage)
class GuestLimitUsageAdmin(admin.ModelAdmin):
    list_display = ("event_guest", "menu_item", "used_quantity")
    list_filter = ("event_guest__event",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "guest", "stall", "status", "created_at")
    list_filter = ("status", "stall__event")
    search_fields = ("order_number",)
    readonly_fields = ("order_number", "created_at", "updated_at")
    inlines = [OrderItemInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("event_user", "order", "order_status", "is_read", "created_at")
    list_filter = ("is_read", "order_status")
