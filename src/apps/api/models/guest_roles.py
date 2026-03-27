"""Guest role and limit tracking models."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class GuestRole(models.Model):
    """Named role within an event (VIP, Press, Speaker, etc.)."""

    event = models.ForeignKey(
        "api.Event",
        on_delete=models.CASCADE,
        related_name="guest_roles",
        verbose_name="Мероприятие",
    )
    name = models.CharField(max_length=100, verbose_name="Название роли")

    class Meta:
        verbose_name = "Роль гостя"
        verbose_name_plural = "Роли гостей"
        unique_together = [("event", "name")]

    def __str__(self) -> str:
        return f"{self.name} @ {self.event.code}"


class GuestRoleItem(models.Model):
    """Defines how many of a specific menu item a role can order, and at what discount."""

    role = models.ForeignKey(
        GuestRole,
        on_delete=models.CASCADE,
        related_name="allowed_items",
        verbose_name="Роль",
    )
    menu_item = models.ForeignKey(
        "api.MenuItem",
        on_delete=models.CASCADE,
        related_name="role_limits",
        verbose_name="Позиция меню",
    )
    max_quantity = models.PositiveIntegerField(
        verbose_name="Максимальное количество",
        validators=[MinValueValidator(1)],
    )
    discount_pct = models.PositiveIntegerField(
        default=100,
        verbose_name="Скидка (%)",
        help_text="100 = бесплатно",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        verbose_name = "Лимит позиции для роли"
        verbose_name_plural = "Лимиты позиций для ролей"
        unique_together = [("role", "menu_item")]

    def __str__(self) -> str:
        return f"{self.role.name}: {self.menu_item.name} x{self.max_quantity}"


class GuestLimitUsage(models.Model):
    """
    Tracks how many of each item a guest has used (hold + finalized).
    Used for limit checking during order creation.
    Returned (decremented) on any cancellation or modification.
    """

    event_guest = models.ForeignKey(
        "api.EventGuest",
        on_delete=models.CASCADE,
        related_name="limit_usages",
        verbose_name="Гость",
    )
    menu_item = models.ForeignKey(
        "api.MenuItem",
        on_delete=models.CASCADE,
        related_name="guest_usages",
        verbose_name="Позиция меню",
    )
    used_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Использовано (hold + выдано)",
    )

    class Meta:
        verbose_name = "Использование лимита"
        verbose_name_plural = "Использование лимитов"
        unique_together = [("event_guest", "menu_item")]

    def __str__(self) -> str:
        return f"{self.event_guest} — {self.menu_item.name}: {self.used_quantity}"

    def remaining(self) -> int:
        """How many more the guest can order."""
        try:
            limit = self.event_guest.role.allowed_items.get(menu_item=self.menu_item)
            return max(0, limit.max_quantity - self.used_quantity)
        except Exception:
            return 0
