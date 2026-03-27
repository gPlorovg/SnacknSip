"""
Custom JWT authentication backend for EventUser and Organizer.
Supports two user types via 'user_type' claim in the JWT payload.
"""

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

User = get_user_model()


class EventUserJWTAuthentication(JWTAuthentication):
    """
    Authenticates requests using JWT tokens.

    - user_type == "django_user"  → standard Django User (organizer)
    - user_type == "event_user"   → EventUser (guest/staff)

    For EventUser tokens also validates:
    - Event is still open (is_open=True)
    - Token was issued after the last event close (closed_at check)
    """

    def get_user(self, validated_token):
        user_type = validated_token.get("user_type", "django_user")

        if user_type == "event_user":
            return self._get_event_user(validated_token)

        # Default: Django User (organizer)
        return super().get_user(validated_token)

    def _get_event_user(self, token):
        from apps.api.models import Event, EventUser

        event_user_id = token.get("event_user_id")
        event_id = token.get("event_id")

        if not event_user_id or not event_id:
            raise InvalidToken("Token missing required event claims.")

        # Validate event state
        try:
            event = Event.objects.only("id", "is_open", "closed_at").get(pk=event_id)
        except Event.DoesNotExist:
            raise AuthenticationFailed("Event not found.")

        if not event.is_open:
            raise AuthenticationFailed(
                "Мероприятие закрыто. Обратитесь к организатору."
            )

        # Invalidate tokens issued before event was closed and re-opened
        # token["iat"] is set automatically by simplejwt as a Unix timestamp
        if event.closed_at:
            token_iat = token.get("iat", 0)
            closed_ts = event.closed_at.timestamp()
            if token_iat < closed_ts:
                raise AuthenticationFailed(
                    "Сессия истекла: мероприятие было закрыто. Войдите снова."
                )

        # Load EventUser
        try:
            event_user = EventUser.objects.select_related("event").get(
                pk=event_user_id, event_id=event_id
            )
        except EventUser.DoesNotExist:
            raise AuthenticationFailed("Пользователь не найден.")

        if event_user.is_blocked:
            raise AuthenticationFailed("Вы заблокированы. Обратитесь к организатору.")

        # Attach event to user for use in views/permissions
        event_user._event = event
        event_user._token_role = token.get("role", event_user.role)
        return event_user
