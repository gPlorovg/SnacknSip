"""Dedicated organizer admin site (Unfold-based when available)."""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from apps.api.admin.views import (
    MenuItemBatchUploadView,
    OrganizerDashboardView,
    VisitorCsvImportView,
)
from apps.api.models import (
    Event,
    EventGuest,
    EventUser,
    GuestLimitUsage,
    GuestRole,
    GuestRoleItem,
    Menu,
    MenuItem,
    Notification,
    Order,
    OrderItem,
    Stall,
    StallMenuItem,
    StallStaff,
)

try:
    from unfold.admin import ModelAdmin
    from unfold.sites import UnfoldAdminSite
except (
    ImportError
):  # pragma: no cover - fallback for environments without django-unfold
    from django.contrib.admin import AdminSite as UnfoldAdminSite
    from django.contrib.admin import ModelAdmin


class OrganizerAdminAuthenticationForm(AuthenticationForm):
    """Allow login only for Django users who are organizers and not is_staff."""

    def confirm_login_allowed(self, user) -> None:
        super().confirm_login_allowed(user)
        if getattr(user, "is_staff", False):
            raise ValidationError(
                "Стандартная админка доступна только staff-пользователям.",
                code="invalid_login",
            )
        if not hasattr(user, "organizer_profile"):
            raise ValidationError(
                "Доступ только для организаторов.", code="invalid_login"
            )


class OrganizerAdminSite(UnfoldAdminSite):
    """Separate admin surface for organizer workflows."""

    site_header = "SnacknSip Organizer"
    site_title = "Organizer Admin"
    index_title = "Панель организатора"
    login_form = OrganizerAdminAuthenticationForm

    def has_permission(self, request: HttpRequest) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_staff", False)
            and hasattr(user, "organizer_profile")
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "stats/",
                self.admin_view(OrganizerDashboardView.as_view(admin_site=self)),
                name="stats",
            )
        ]
        return custom_urls + urls


organizer_admin_site = OrganizerAdminSite(name="organizer_admin")


class OrganizerAccessMixin:
    """Allow organizer users to work in this admin without Django staff model perms."""

    owner_lookup = "event__organizer"

    @staticmethod
    def _is_organizer_user(request: HttpRequest) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_staff", False)
            and hasattr(user, "organizer_profile")
        )

    def _obj_belongs_to_user(self, obj, user) -> bool:
        current = obj
        for part in self.owner_lookup.split("__"):
            current = getattr(current, part, None)
            if current is None:
                return False
        return current == user

    def has_module_permission(self, request: HttpRequest) -> bool:
        return self._is_organizer_user(request)

    def has_view_permission(self, request: HttpRequest, obj=None) -> bool:
        if not self._is_organizer_user(request):
            return False
        return obj is None or self._obj_belongs_to_user(obj, request.user)

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        if not self._is_organizer_user(request):
            return False
        return obj is None or self._obj_belongs_to_user(obj, request.user)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return self._is_organizer_user(request)

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        if not self._is_organizer_user(request):
            return False
        return obj is None or self._obj_belongs_to_user(obj, request.user)


class OrganizerScopeMixin(OrganizerAccessMixin):
    """Restrict admin data to records owned by request.user organizer profile."""

    owner_lookup = "event__organizer"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        queryset = super().get_queryset(request)
        return queryset.filter(**{self.owner_lookup: request.user})


@admin.register(Event, site=organizer_admin_site)
class OrganizerEventAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "organizer"
    list_display = ("code", "name", "is_open", "start_time", "end_time")
    search_fields = ("code", "name")
    list_filter = ("is_open",)
    readonly_fields = (
        "code",
        "created_at",
        "closed_at",
        "deeplink_tg_link",
        "deeplink_web_link",
        "qr_tg_link",
        "qr_web_link",
    )
    actions = ["go_to_csv_import"]

    @admin.display(description="Ссылка Telegram")
    def deeplink_tg_link(self, obj: Event) -> str:
        return format_html(
            '<a href="{}" target="_blank">{}</a>', obj.deeplink_tg, obj.deeplink_tg
        )

    @admin.display(description="Ссылка Web")
    def deeplink_web_link(self, obj: Event) -> str:
        return format_html(
            '<a href="{}" target="_blank">{}</a>', obj.deeplink_web, obj.deeplink_web
        )

    @admin.display(description="QR Telegram")
    def qr_tg_link(self, obj: Event) -> str:
        qr_url = f"/api/organizer/events/{obj.code}/qr/?target=tg"
        return format_html('<a href="{}" target="_blank">Открыть QR PNG</a>', qr_url)

    @admin.display(description="QR Web")
    def qr_web_link(self, obj: Event) -> str:
        qr_url = f"/api/organizer/events/{obj.code}/qr/?target=web"
        return format_html('<a href="{}" target="_blank">Открыть QR PNG</a>', qr_url)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def get_queryset(self, request: HttpRequest) -> QuerySet[Event]:
        return super().get_queryset(request).filter(organizer=request.user)

    def save_model(
        self,
        request: HttpRequest,
        obj: Event,
        form,
        change: bool,
    ) -> None:
        if change and obj.organizer_id != request.user.id:
            raise PermissionDenied("Нельзя редактировать чужое мероприятие.")
        obj.organizer = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-visitors/",
                self.admin_site.admin_view(
                    VisitorCsvImportView.as_view(admin_site=self.admin_site)
                ),
                name="api_event_import_visitors",
            )
        ]
        return custom_urls + urls

    @admin.action(description="Импортировать посетителей из CSV")
    def go_to_csv_import(
        self, request: HttpRequest, queryset: QuerySet[Event]
    ) -> HttpResponseRedirect:
        if queryset.count() != 1:
            self.message_user(
                request,
                "Выберите ровно одно мероприятие для импорта CSV.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect(reverse("organizer_admin:api_event_changelist"))

        event = queryset.first()
        assert event is not None
        url = reverse("organizer_admin:api_event_import_visitors")
        return HttpResponseRedirect(f"{url}?{urlencode({'event_id': event.id})}")


@admin.register(Menu, site=organizer_admin_site)
class OrganizerMenuAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "event__organizer"
    list_display = ("name", "event")
    list_filter = ("event",)
    search_fields = ("name", "event__name", "event__code")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "event":
            kwargs["queryset"] = Event.objects.filter(organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(MenuItem, site=organizer_admin_site)
class OrganizerMenuItemAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "menu__event__organizer"
    list_display = ("name", "menu", "price")
    list_filter = ("menu__event",)
    search_fields = ("name", "menu__name")
    actions = ["go_to_batch_photo_upload"]

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "menu":
            kwargs["queryset"] = Menu.objects.filter(event__organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(
        self,
        request: HttpRequest,
        obj: MenuItem,
        form,
        change: bool,
    ) -> None:
        if obj.menu.event.organizer_id != request.user.id:
            raise PermissionDenied("Можно работать только со своими меню.")
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "batch-photo-upload/",
                self.admin_site.admin_view(
                    MenuItemBatchUploadView.as_view(admin_site=self.admin_site)
                ),
                name="api_menuitem_batch_upload",
            )
        ]
        return custom_urls + urls

    @admin.action(description="Массово установить изображение")
    def go_to_batch_photo_upload(
        self,
        request: HttpRequest,
        queryset: QuerySet[MenuItem],
    ) -> HttpResponseRedirect:
        if not queryset.exists():
            self.message_user(
                request,
                "Выберите хотя бы одну позицию меню.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect(
                reverse("organizer_admin:api_menuitem_changelist")
            )

        ids = ",".join(str(pk) for pk in queryset.values_list("pk", flat=True))
        url = reverse("organizer_admin:api_menuitem_batch_upload")
        return HttpResponseRedirect(f"{url}?{urlencode({'ids': ids})}")


@admin.register(EventUser, site=organizer_admin_site)
class OrganizerEventUserAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "event__organizer"
    list_display = ("name", "login", "telegram_username", "role", "event", "is_blocked")
    list_filter = ("role", "is_blocked", "event")
    search_fields = ("name", "login", "telegram_username")
    readonly_fields = ("password_hash", "telegram_id", "created_at", "updated_at")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "event":
            kwargs["queryset"] = Event.objects.filter(organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(
        self,
        request: HttpRequest,
        obj: EventUser,
        form,
        change: bool,
    ) -> None:
        if obj.event.organizer_id != request.user.id:
            raise PermissionDenied(
                "Можно создавать пользователей только в своих мероприятиях."
            )
        if obj.login and not obj.password_hash:
            obj.set_password(secrets.token_urlsafe(9))
        super().save_model(request, obj, form, change)


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


@admin.register(EventGuest, site=organizer_admin_site)
class OrganizerEventGuestAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "event__organizer"
    list_display = ("event_user", "event", "role")
    list_filter = ("event", "role")
    search_fields = ("event_user__login", "event_user__name", "event__code")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "event":
            kwargs["queryset"] = Event.objects.filter(organizer=request.user)
        elif db_field.name == "event_user":
            kwargs["queryset"] = EventUser.objects.filter(event__organizer=request.user)
        elif db_field.name == "role":
            kwargs["queryset"] = GuestRole.objects.filter(event__organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Stall, site=organizer_admin_site)
class OrganizerStallAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "event__organizer"
    list_display = ("name", "abbr", "event", "menu", "status")
    list_filter = ("event", "status")
    search_fields = ("name", "abbr", "event__code")
    inlines = [StallMenuItemInline]

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "event":
            kwargs["queryset"] = Event.objects.filter(organizer=request.user)
        elif db_field.name == "menu":
            kwargs["queryset"] = Menu.objects.filter(event__organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(StallMenuItem, site=organizer_admin_site)
class OrganizerStallMenuItemAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "stall__event__organizer"
    list_display = ("stall", "menu_item", "is_available")
    list_filter = ("stall__event", "is_available")
    search_fields = ("stall__name", "menu_item__name")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "stall":
            kwargs["queryset"] = Stall.objects.filter(event__organizer=request.user)
        elif db_field.name == "menu_item":
            kwargs["queryset"] = MenuItem.objects.filter(
                menu__event__organizer=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(StallStaff, site=organizer_admin_site)
class OrganizerStallStaffAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "stall__event__organizer"
    list_display = ("event_user", "stall")
    search_fields = ("event_user__login", "event_user__name", "stall__name")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "stall":
            kwargs["queryset"] = Stall.objects.filter(event__organizer=request.user)
        elif db_field.name == "event_user":
            kwargs["queryset"] = EventUser.objects.filter(
                event__organizer=request.user,
                role=EventUser.Role.STAFF,
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(GuestRole, site=organizer_admin_site)
class OrganizerGuestRoleAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "event__organizer"
    list_display = ("name", "event")
    list_filter = ("event",)
    search_fields = ("name", "event__code", "event__name")
    inlines = [GuestRoleItemInline]

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "event":
            kwargs["queryset"] = Event.objects.filter(organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(GuestRoleItem, site=organizer_admin_site)
class OrganizerGuestRoleItemAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "role__event__organizer"
    list_display = ("role", "menu_item", "max_quantity", "discount_pct")
    list_filter = ("role__event", "role")
    search_fields = ("role__name", "menu_item__name")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "role":
            kwargs["queryset"] = GuestRole.objects.filter(event__organizer=request.user)
        elif db_field.name == "menu_item":
            kwargs["queryset"] = MenuItem.objects.filter(
                menu__event__organizer=request.user
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(GuestLimitUsage, site=organizer_admin_site)
class OrganizerGuestLimitUsageAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "event_guest__event__organizer"
    list_display = ("event_guest", "menu_item", "used_quantity")
    list_filter = ("event_guest__event",)
    search_fields = ("event_guest__event_user__login", "menu_item__name")


@admin.register(Order, site=organizer_admin_site)
class OrganizerOrderAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "event__organizer"
    list_display = ("order_number", "guest", "stall", "status", "created_at")
    list_filter = ("status", "event")
    search_fields = ("order_number", "guest__login", "stall__name")
    readonly_fields = ("order_number", "created_at", "updated_at")
    inlines = [OrderItemInline]

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "event":
            kwargs["queryset"] = Event.objects.filter(organizer=request.user)
        elif db_field.name == "guest":
            kwargs["queryset"] = EventUser.objects.filter(event__organizer=request.user)
        elif db_field.name == "stall":
            kwargs["queryset"] = Stall.objects.filter(event__organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Notification, site=organizer_admin_site)
class OrganizerNotificationAdmin(OrganizerScopeMixin, ModelAdmin):
    owner_lookup = "order__event__organizer"
    list_display = ("event_user", "order", "order_status", "is_read", "created_at")
    list_filter = ("is_read", "order_status")
    search_fields = ("event_user__login", "order__order_number", "message")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        if db_field.name == "event_user":
            kwargs["queryset"] = EventUser.objects.filter(event__organizer=request.user)
        elif db_field.name == "order":
            kwargs["queryset"] = Order.objects.filter(event__organizer=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
