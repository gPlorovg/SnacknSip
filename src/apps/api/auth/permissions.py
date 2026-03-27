"""DRF permission classes for role-based access control."""

from rest_framework.permissions import BasePermission


class IsOrganizer(BasePermission):
    """
    Django Users who have an OrganizerProfile.
    Does NOT require is_staff — organizers have no Django Admin access.
    Only superusers can access Django Admin.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Must be a Django User (not an EventUser)
        from apps.api.models import EventUser

        if isinstance(request.user, EventUser):
            return False
        # Must have an OrganizerProfile
        return hasattr(request.user, "organizer_profile")


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
