"""DRF permission classes for role-based access control."""

from rest_framework.permissions import BasePermission


class IsOrganizer(BasePermission):
    """Only Django staff/superusers (organizers)."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_staff", False)
        )


class IsEventUser(BasePermission):
    """Only EventUser instances (guests or staff)."""

    def has_permission(self, request, view):
        from apps.api.models import EventUser

        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, EventUser)
        )


class IsGuest(BasePermission):
    """Only EventUsers with role=guest."""

    def has_permission(self, request, view):
        from apps.api.models import EventUser

        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, EventUser)
            and request.user.role == EventUser.Role.GUEST
        )


class IsStaff(BasePermission):
    """Only EventUsers with role=staff."""

    def has_permission(self, request, view):
        from apps.api.models import EventUser

        return bool(
            request.user
            and request.user.is_authenticated
            and isinstance(request.user, EventUser)
            and request.user.role == EventUser.Role.STAFF
        )


class IsOrganizerOrStaff(BasePermission):
    """Organizers or staff — for stall management."""

    def has_permission(self, request, view):
        from apps.api.models import EventUser

        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_staff", False):
            return True
        return isinstance(user, EventUser) and user.role == EventUser.Role.STAFF
