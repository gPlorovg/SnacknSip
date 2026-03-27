"""API URL routing — views added incrementally each phase."""

from django.urls import path

from apps.api.views.auth import LoginView, LogoutView, RefreshView, TelegramLoginView

urlpatterns = [
    # Этап 3: Auth
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/telegram/", TelegramLoginView.as_view(), name="auth-telegram"),
    path("auth/refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
]
