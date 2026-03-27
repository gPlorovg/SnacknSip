"""Menu models: Menu and MenuItem."""

from django.db import models


class Menu(models.Model):
    """A collection of items served at an event. Can be shared across multiple stalls."""

    name = models.CharField(max_length=255, verbose_name="Название меню")
    event = models.ForeignKey(
        "api.Event",
        on_delete=models.CASCADE,
        related_name="menus",
        verbose_name="Мероприятие",
    )

    class Meta:
        verbose_name = "Меню"
        verbose_name_plural = "Меню"

    def __str__(self) -> str:
        return f"{self.name} ({self.event.code})"


class MenuItem(models.Model):
    """A single item in a menu. Stop-list availability is tracked per stall in StallMenuItem."""

    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Меню",
    )
    name = models.CharField(max_length=255, verbose_name="Название")
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Цена",
        help_text="0 = бесплатно в рамках лимитов роли",
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    image = models.ImageField(
        upload_to="menu-items/",
        blank=True,
        null=True,
        verbose_name="Изображение",
    )

    class Meta:
        verbose_name = "Позиция меню"
        verbose_name_plural = "Позиции меню"

    def __str__(self) -> str:
        return f"{self.name} ({self.menu.name})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # Add StallMenuItem for every stall that uses this menu
            from apps.api.models.stalls import StallMenuItem  # avoid circular import

            stalls = self.menu.stalls.all()
            to_create = [
                StallMenuItem(stall=stall, menu_item=self, is_available=True)
                for stall in stalls
            ]
            if to_create:
                StallMenuItem.objects.bulk_create(to_create, ignore_conflicts=True)
