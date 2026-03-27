"""Notification model for order status updates."""

from django.db import models


class Notification(models.Model):
    """In-app notification for an EventUser about an order status change."""

    event_user = models.ForeignKey(
        "api.EventUser",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Получатель",
    )
    order = models.ForeignKey(
        "api.Order",
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Заказ",
    )
    message = models.TextField(verbose_name="Текст уведомления")
    order_status = models.CharField(
        max_length=15,
        verbose_name="Статус заказа на момент уведомления",
    )
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{'✓' if self.is_read else '○'}] {self.event_user.login}: {self.message[:50]}"
