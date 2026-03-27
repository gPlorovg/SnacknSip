"""Order and OrderItem models."""

from django.db import models


class OrderStatus(models.TextChoices):
    CREATED = "created", "Создан"
    PREPARING = "preparing", "Готовится"
    READY = "ready", "Готов"
    COMPLETED = "completed", "Выдан"
    CANCELLED = "cancelled", "Отменён"
    MODIFIED = "modified", "Изменён"


# Valid status transitions
ORDER_TRANSITIONS: dict[str, list[str]] = {
    OrderStatus.CREATED: [
        OrderStatus.PREPARING,
        OrderStatus.CANCELLED,
        OrderStatus.MODIFIED,
    ],
    OrderStatus.PREPARING: [
        OrderStatus.READY,
        OrderStatus.CANCELLED,
        OrderStatus.MODIFIED,
    ],
    OrderStatus.READY: [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
    OrderStatus.COMPLETED: [],
    OrderStatus.CANCELLED: [],
    OrderStatus.MODIFIED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
}


class Order(models.Model):
    """A guest's order at a stall."""

    event = models.ForeignKey(
        "api.Event",
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Мероприятие",
    )
    guest = models.ForeignKey(
        "api.EventUser",
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Гость",
    )
    stall = models.ForeignKey(
        "api.Stall",
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Точка выдачи",
    )
    status = models.CharField(
        max_length=15,
        choices=OrderStatus.choices,
        default=OrderStatus.CREATED,
        verbose_name="Статус",
    )
    order_number = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        verbose_name="Номер заказа",
        help_text="Формат: TECH24-KFN-007",
    )
    cancel_note = models.TextField(blank=True, verbose_name="Причина отмены")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_number} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    def _generate_order_number(self) -> str:
        """Generate TECH24-KFN-007 style order number."""
        count = Order.objects.filter(stall=self.stall).count() + 1
        return f"{self.event.code}-{self.stall.abbr}-{count:03d}"

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in ORDER_TRANSITIONS.get(self.status, [])

    @property
    def active_items(self):
        return self.items.filter(removed=False)


class OrderItem(models.Model):
    """A single line item in an order."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заказ",
    )
    menu_item = models.ForeignKey(
        "api.MenuItem",
        on_delete=models.CASCADE,
        related_name="order_items",
        verbose_name="Позиция меню",
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    removed = models.BooleanField(
        default=False,
        verbose_name="Убрана из заказа",
        help_text="Устанавливается при стоп-листе или ручной модификации",
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self) -> str:
        status = "[REMOVED]" if self.removed else ""
        return f"{self.menu_item.name} x{self.quantity} {status}"
