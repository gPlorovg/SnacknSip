"""Authentication serializers."""

from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from apps.api.auth.tokens import get_tokens_for_event_user, get_tokens_for_organizer
from apps.api.models import Event, EventUser

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    """
    Universal login serializer.

    - With event_code: authenticates EventUser (guest/staff)
    - Without event_code: authenticates Django User (organizer)
    """

    login = serializers.CharField(
        help_text="Email для гостя/персонала, username для орга"
    )
    password = serializers.CharField(write_only=True)
    event_code = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Код мероприятия (для гостей и персонала)",
    )

    def validate(self, data):
        login = data["login"]
        password = data["password"]
        event_code = data.get("event_code", "").strip()

        if event_code:
            return self._validate_event_user(login, password, event_code)
        else:
            return self._validate_organizer(login, password)

    def _validate_event_user(self, login: str, password: str, event_code: str) -> dict:
        # Find event
        try:
            event = Event.objects.get(code=event_code)
        except Event.DoesNotExist:
            raise serializers.ValidationError({"event_code": "Мероприятие не найдено."})

        if not event.is_open:
            raise serializers.ValidationError({"event_code": "Мероприятие закрыто."})

        # Find user by login (email) within this event
        try:
            event_user = EventUser.objects.get(event=event, login__iexact=login)
        except EventUser.DoesNotExist:
            raise serializers.ValidationError({"login": "Неверный логин или пароль."})

        if not event_user.check_password(password):
            raise serializers.ValidationError({"login": "Неверный логин или пароль."})

        if event_user.is_blocked:
            raise serializers.ValidationError(
                {"non_field_errors": "Вы заблокированы. Обратитесь к организатору."}
            )

        tokens = get_tokens_for_event_user(event_user, event)
        return {
            "tokens": tokens,
            "event_user": event_user,
            "event": event,
        }

    def _validate_organizer(self, login: str, password: str) -> dict:
        # login is username for organizers
        user = authenticate(username=login, password=password)
        if not user:
            raise serializers.ValidationError({"login": "Неверный логин или пароль."})
        if not user.is_staff:
            raise serializers.ValidationError(
                {"login": "Доступ запрещён. Используйте event_code для входа."}
            )
        tokens = get_tokens_for_organizer(user)
        return {"tokens": tokens, "user": user}


class TelegramLoginSerializer(serializers.Serializer):
    """
    Telegram-based login for guests and staff.
    Requires X-Bot-Token header (validated in view).

    Flow:
    1. Find by telegram_id (fast path — repeat visits)
    2. Find by telegram_username (first visit — org added user by username)
       → automatically links telegram_id for future logins
    """

    event_code = serializers.CharField()
    telegram_id = serializers.IntegerField()
    telegram_username = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="@username из Telegram (без @). Нужен при первом входе для привязки.",
    )

    def validate(self, data):
        event_code = data["event_code"]
        telegram_id = data["telegram_id"]
        telegram_username = data.get("telegram_username", "").strip().lstrip("@")

        # Find event
        try:
            event = Event.objects.get(code=event_code)
        except Event.DoesNotExist:
            raise serializers.ValidationError({"event_code": "Мероприятие не найдено."})

        if not event.is_open:
            raise serializers.ValidationError({"event_code": "Мероприятие закрыто."})

        # 1. Fast path: find by telegram_id (repeat visitor)
        event_user = EventUser.objects.filter(
            event=event, telegram_id=telegram_id
        ).first()

        # 2. First visit: find by telegram_username, link telegram_id
        if not event_user and telegram_username:
            event_user = EventUser.objects.filter(
                event=event,
                telegram_username__iexact=telegram_username,
            ).first()
            if event_user:
                event_user.telegram_id = telegram_id
                event_user.save(update_fields=["telegram_id"])

        if not event_user:
            raise serializers.ValidationError(
                {
                    "telegram_id": (
                        "Пользователь не найден в этом мероприятии. "
                        "Обратитесь к организатору."
                    )
                }
            )

        if event_user.is_blocked:
            raise serializers.ValidationError(
                {"non_field_errors": "Вы заблокированы. Обратитесь к организатору."}
            )

        tokens = get_tokens_for_event_user(event_user, event)
        return {
            "tokens": tokens,
            "event_user": event_user,
            "event": event,
        }
