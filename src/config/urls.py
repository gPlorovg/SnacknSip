"""URL configuration for SnacknSip."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.api.admin.organizer import organizer_admin_site

urlpatterns = [
    path("admin/", admin.site.urls),
    path("organizer-admin/", organizer_admin_site.urls),
    # API docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API
    path("api/", include("apps.api.urls")),
]
