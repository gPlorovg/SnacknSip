"""API URL routing."""

from django.urls import path

from apps.api.views.auth import LoginView, LogoutView, RefreshView, TelegramLoginView
from apps.api.views.guest import (
    NotificationListView,
    NotificationReadView,
    OrderDetailView,
    OrderListView,
    OrderStatusView,
    StallDetailView,
    StallListView,
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
]
