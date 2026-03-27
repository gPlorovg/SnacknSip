"""Custom JWT token classes with per-event claims."""

from rest_framework_simplejwt.tokens import RefreshToken


def get_tokens_for_organizer(user) -> dict:
    """Generate JWT pair for a Django User (organizer/superuser)."""
    refresh = RefreshToken.for_user(user)
    refresh["role"] = "organizer"
    refresh["user_type"] = "django_user"
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def get_tokens_for_event_user(event_user, event) -> dict:
    """
    Generate JWT pair for an EventUser (guest or staff).
    Adds event-scoped claims required for per-request authorization.
    """
    refresh = RefreshToken()
    # Identity
    refresh["user_type"] = "event_user"
    refresh["event_user_id"] = event_user.id
    # Event scope
    refresh["event_id"] = event.id
    refresh["event_code"] = event.code
    # Role
    refresh["role"] = event_user.role  # "guest" | "staff"

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
