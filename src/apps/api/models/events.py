"""Event-related models: Event, EventGuest, StallStaff."""

import random
import string

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import UniqueConstraint
from django.utils import timezone

User = get_user_model()


def _generate_event_code() -> str:
    """Generate a unique 6-character alphanumeric event code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


class Event(models.Model):
    """A SnacknSip event (conference, festival, etc.)."""

    code = models.CharField(
        max_length=6,
        unique=True,
        editable=False,
        verbose_name="Код мероприятия",
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    location = models.CharField(
        max_length=500, blank=True, verbose_name="Место проведения"
    )
    organizer_contacts = models.TextField(
        blank=True, verbose_name="Контакты организатора"
    )
    organizer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="organized_events",
        verbose_name="Организатор",
    )
    start_time = models.DateTimeField(verbose_name="Начало")
    end_time = models.DateTimeField(verbose_name="Конец")
    is_open = models.BooleanField(
        default=False,
        verbose_name="Открыто",
        help_text="Управляется вручную. Celery Beat автоматически закрывает по end_time.",
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время закрытия",
        help_text="Используется для немедленной инвалидации JWT токенов.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"
        ordering = ["-start_time"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._get_unique_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _get_unique_code() -> str:
        code = _generate_event_code()
        while Event.objects.filter(code=code).exists():
            code = _generate_event_code()
        return code

    def open(self):
        self.is_open = True
        self.closed_at = None
        self.save(update_fields=["is_open", "closed_at"])

    def close(self):
        self.is_open = False
        self.closed_at = timezone.now()
        self.save(update_fields=["is_open", "closed_at"])

    @property
    def deeplink_tg(self) -> str:
        return f"https://t.me/SnacknSipBot?start={self.code}"

    @property
    def deeplink_web(self) -> str:
        from django.conf import settings

        base = getattr(settings, "WEB_BASE_URL", "https://snacknsip.ru")
        return f"{base}/event/{self.code}"


class EventGuest(models.Model):
    """Connects an EventUser (guest) to their GuestRole within an event."""

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="guests",
        verbose_name="Мероприятие",
    )
    event_user = models.OneToOneField(
        "api.EventUser",
        on_delete=models.CASCADE,
        related_name="guest_profile",
        verbose_name="Пользователь",
    )
    role = models.ForeignKey(
        "api.GuestRole",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guests",
        verbose_name="Роль гостя",
    )

    class Meta:
        verbose_name = "Гость мероприятия"
        verbose_name_plural = "Гости мероприятий"

    def __str__(self) -> str:
        return f"{self.event_user.login} @ {self.event.code}"


class StallStaff(models.Model):
    """Connects an EventUser (staff) to exactly one Stall."""

    event_user = models.OneToOneField(
        "api.EventUser",
        on_delete=models.CASCADE,
        related_name="staff_profile",
        verbose_name="Пользователь",
    )
    stall = models.ForeignKey(
        "api.Stall",
        on_delete=models.CASCADE,
        related_name="staff_members",
        verbose_name="Точка выдачи",
    )

    class Meta:
        verbose_name = "Персонал точки"
        verbose_name_plural = "Персонал точек"
        constraints = [
            UniqueConstraint(fields=["event_user"], name="unique_staff_per_user"),
        ]

    def __str__(self) -> str:
        return f"{self.event_user.login} → {self.stall.name}"
