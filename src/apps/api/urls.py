"""API URL routing."""

from django.urls import path

from apps.api.views.auth import LoginView, LogoutView, RefreshView, TelegramLoginView
from apps.api.views.guest import (
    GuestLimitsView,
    NotificationListView,
    NotificationReadView,
    OrderDetailView,
    OrderListView,
    OrderStatusView,
    StallDetailView,
    StallListView,
)
from apps.api.views.organizer import (
    AssignGuestRoleView,
    CloseEventView,
    EventDetailView,
    EventListView,
    OpenEventView,
    OrgGuestRoleItemView,
    OrgGuestRoleListView,
    OrgMenuItemDetailView,
    OrgMenuItemListView,
    OrgMenuListView,
    OrgOrderListView,
    OrgStallDetailView,
    OrgStallListView,
    OrgUserDetailView,
    OrgUserListView,
)
from apps.api.views.staff import (
    AutoRedistributeView,
    BulkCancelOrdersView,
    CloseStallView,
    ManualRedistributeView,
    MyStallView,
    OpenStallView,
    StallMenuView,
    StallOrderListView,
    ToggleMenuItemView,
    UpdateOrderStatusView,
)

urlpatterns = [
    # ── Auth ─────────────────────────────────────────────────
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/telegram/", TelegramLoginView.as_view(), name="auth-telegram"),
    path("auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    # ── Guest: Stalls ─────────────────────────────────────────
    path("stalls/", StallListView.as_view(), name="stall-list"),
    path("stalls/<int:pk>/", StallDetailView.as_view(), name="stall-detail"),
    # ── Guest: Orders ─────────────────────────────────────────
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/<int:pk>/status/", OrderStatusView.as_view(), name="order-status"),
    # ── Guest: Notifications ──────────────────────────────────
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/<int:pk>/read/",
        NotificationReadView.as_view(),
        name="notification-read",
    ),
    # ── Guest: Me ─────────────────────────────────────────────
    path("me/limits/", GuestLimitsView.as_view(), name="guest-limits"),
    # ── Staff: Stall management ───────────────────────────────
    path("staff/stall/", MyStallView.as_view(), name="staff-my-stall"),
    path("staff/stall/open/", OpenStallView.as_view(), name="staff-stall-open"),
    path("staff/stall/close/", CloseStallView.as_view(), name="staff-stall-close"),
    # ── Staff: Menu / Stop-list ───────────────────────────────
    path("staff/menu/", StallMenuView.as_view(), name="staff-menu"),
    path(
        "staff/menu/<int:item_id>/",
        ToggleMenuItemView.as_view(),
        name="staff-menu-toggle",
    ),
    # ── Staff: Orders ─────────────────────────────────────────
    path("staff/orders/", StallOrderListView.as_view(), name="staff-order-list"),
    path(
        "staff/orders/<int:pk>/",
        UpdateOrderStatusView.as_view(),
        name="staff-order-update",
    ),
    # ── Staff/Org: Redistribution ─────────────────────────────
    path(
        "staff/orders/redistribute/",
        AutoRedistributeView.as_view(),
        name="staff-auto-redistribute",
    ),
    path(
        "staff/orders/<int:pk>/redistribute/",
        ManualRedistributeView.as_view(),
        name="staff-manual-redistribute",
    ),
    path(
        "staff/orders/cancel-all/",
        BulkCancelOrdersView.as_view(),
        name="staff-bulk-cancel",
    ),
    # ── Organizer: Events ─────────────────────────────────────
    path("org/events/", EventListView.as_view(), name="org-event-list"),
    path(
        "org/events/<int:event_id>/", EventDetailView.as_view(), name="org-event-detail"
    ),
    path(
        "org/events/<int:event_id>/open/",
        OpenEventView.as_view(),
        name="org-event-open",
    ),
    path(
        "org/events/<int:event_id>/close/",
        CloseEventView.as_view(),
        name="org-event-close",
    ),
    # ── Organizer: Stalls ─────────────────────────────────────
    path(
        "org/events/<int:event_id>/stalls/",
        OrgStallListView.as_view(),
        name="org-stall-list",
    ),
    path(
        "org/events/<int:event_id>/stalls/<int:stall_id>/",
        OrgStallDetailView.as_view(),
        name="org-stall-detail",
    ),
    # ── Organizer: Menus ──────────────────────────────────────
    path(
        "org/events/<int:event_id>/menus/",
        OrgMenuListView.as_view(),
        name="org-menu-list",
    ),
    path(
        "org/events/<int:event_id>/menus/<int:menu_id>/items/",
        OrgMenuItemListView.as_view(),
        name="org-menu-item-list",
    ),
    path(
        "org/events/<int:event_id>/menus/<int:menu_id>/items/<int:item_id>/",
        OrgMenuItemDetailView.as_view(),
        name="org-menu-item-detail",
    ),
    # ── Organizer: Users ──────────────────────────────────────
    path(
        "org/events/<int:event_id>/users/",
        OrgUserListView.as_view(),
        name="org-user-list",
    ),
    path(
        "org/events/<int:event_id>/users/<int:user_id>/",
        OrgUserDetailView.as_view(),
        name="org-user-detail",
    ),
    # ── Organizer: Roles ──────────────────────────────────────
    path(
        "org/events/<int:event_id>/roles/",
        OrgGuestRoleListView.as_view(),
        name="org-role-list",
    ),
    path(
        "org/events/<int:event_id>/roles/<int:role_id>/items/",
        OrgGuestRoleItemView.as_view(),
        name="org-role-item",
    ),
    path(
        "org/events/<int:event_id>/roles/assign/",
        AssignGuestRoleView.as_view(),
        name="org-role-assign",
    ),
    # ── Organizer: Orders ─────────────────────────────────────
    path(
        "org/events/<int:event_id>/orders/",
        OrgOrderListView.as_view(),
        name="org-order-list",
    ),
]
