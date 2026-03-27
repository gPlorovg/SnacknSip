"""Stall models: Stall and StallMenuItem (per-stall stop-list)."""

from django.db import models


class StallStatus(models.TextChoices):
    OPEN = "open", "Открыта"
    CLOSED = "closed", "Закрыта"


class Stall(models.Model):
    """A food/drink point at an event."""

    event = models.ForeignKey(
        "api.Event",
        on_delete=models.CASCADE,
        related_name="stalls",
        verbose_name="Мероприятие",
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    abbr = models.CharField(
        max_length=3,
        verbose_name="Аббревиатура",
        help_text="3 символа для номера заказа, например KFN для Кофейня",
    )
    menu = models.ForeignKey(
        "api.Menu",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stalls",
        verbose_name="Меню",
    )
    status = models.CharField(
        max_length=10,
        choices=StallStatus.choices,
        default=StallStatus.CLOSED,
        verbose_name="Статус",
    )

    class Meta:
        verbose_name = "Точка выдачи"
        verbose_name_plural = "Точки выдачи"
        unique_together = [("event", "abbr")]

    def __str__(self) -> str:
        return f"{self.name} [{self.abbr}] @ {self.event.code}"

    @property
    def is_open(self) -> bool:
        return self.status == StallStatus.OPEN

    def save(self, *args, **kwargs):
        if not self.abbr and self.name:
            self.abbr = self.name[:3].upper()
        super().save(*args, **kwargs)


class StallMenuItem(models.Model):
    """
    Per-stall stop-list: each stall manages availability of menu items independently.
    Auto-created when a menu is assigned to a stall.
    """

    stall = models.ForeignKey(
        Stall,
        on_delete=models.CASCADE,
        related_name="stall_items",
        verbose_name="Точка",
    )
    menu_item = models.ForeignKey(
        "api.MenuItem",
        on_delete=models.CASCADE,
        related_name="stall_items",
        verbose_name="Позиция меню",
    )
    is_available = models.BooleanField(
        default=True,
        verbose_name="Доступно",
        help_text="False = в стоп-листе на этой точке",
    )

    class Meta:
        verbose_name = "Доступность позиции на точке"
        verbose_name_plural = "Стоп-лист точек"
        unique_together = [("stall", "menu_item")]

    def __str__(self) -> str:
        status = "✓" if self.is_available else "✗"
        return f"{status} {self.menu_item.name} @ {self.stall.name}"
