"""User models: global organizer profile and per-event user accounts."""

import secrets
import string

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint

User = get_user_model()


class OrganizerProfile(models.Model):
    """Global organizer — linked to a Django User (is_staff=True)."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="organizer_profile",
    )

    class Meta:
        verbose_name = "Организатор"
        verbose_name_plural = "Организаторы"

    def __str__(self) -> str:
        return f"Organizer: {self.user.username}"


def _generate_password(length: int = 8) -> str:
    """Generate a secure human-readable password."""
    alphabet = string.ascii_letters + string.digits + "!@#$&"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _encrypt_password(plain: str) -> bytes:
    """Encrypt password with Fernet for organizer view."""
    key = settings.FERNET_KEY
    if not key:
        return b""
    f = Fernet(key.encode() if isinstance(key, str) else key)
    return f.encrypt(plain.encode())


def _decrypt_password(encrypted: bytes) -> str:
    """Decrypt Fernet-encrypted password."""
    key = settings.FERNET_KEY
    if not key or not encrypted:
        return ""
    f = Fernet(key.encode() if isinstance(key, str) else key)
    return f.decrypt(encrypted).decode()


class EventUserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_blocked=False)

    def guests(self):
        return self.filter(role=EventUser.Role.GUEST)

    def staff(self):
        return self.filter(role=EventUser.Role.STAFF)


class EventUser(models.Model):
    """
    Per-event user account for guests and staff.

    Constraint: at least one of (password_hash, telegram_id) must be set.
    login = email, unique per event.
    """

    class Role(models.TextChoices):
        GUEST = "guest", "Гость"
        STAFF = "staff", "Персонал"

    event = models.ForeignKey(
        "api.Event",
        on_delete=models.CASCADE,
        related_name="users",
        verbose_name="Мероприятие",
    )
    login = models.EmailField(
        verbose_name="Email (логин)",
        blank=True,
        null=True,
        help_text="Email для входа по паролю. Обязательно если нет telegram_username.",
    )
    password_hash = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Хэш пароля",
    )
    password_encrypted = models.BinaryField(
        blank=True,
        null=True,
        verbose_name="Зашифрованный пароль (для орга)",
    )
    telegram_username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Telegram username",
        help_text="@username в Telegram. Орг добавляет по username.",
    )
    telegram_id = models.BigIntegerField(
        blank=True,
        null=True,
        verbose_name="Telegram ID",
        help_text="Заполняется автоматически ботом при первом входе.",
    )
    name = models.CharField(max_length=255, verbose_name="Имя")
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.GUEST,
        verbose_name="Роль",
    )
    is_blocked = models.BooleanField(
        default=False,
        verbose_name="Заблокирован",
        help_text="True = заблокирован, False = активен",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventUserQuerySet.as_manager()

    # --- DRF / Django auth protocol ---
    # Required so DRF's IsAuthenticated and other permissions work
    is_authenticated = True
    is_anonymous = False
    is_staff = False  # EventUsers are never Django staff
    is_superuser = False

    class Meta:
        verbose_name = "Пользователь мероприятия"
        verbose_name_plural = "Пользователи мероприятий"
        constraints = [
            # login (email) уникален внутри event если указан
            UniqueConstraint(
                fields=["event", "login"],
                condition=Q(login__isnull=False),
                name="unique_event_login",
            ),
            # telegram_username уникален внутри event если указан
            UniqueConstraint(
                fields=["event", "telegram_username"],
                condition=Q(telegram_username__isnull=False),
                name="unique_event_telegram_username",
            ),
            # telegram_id уникален внутри event если указан
            UniqueConstraint(
                fields=["event", "telegram_id"],
                condition=Q(telegram_id__isnull=False),
                name="unique_event_telegram_id",
            ),
            # Хотя бы один основной идентификатор обязателен
            CheckConstraint(
                condition=Q(login__isnull=False) | Q(telegram_username__isnull=False),
                name="event_user_has_primary_identifier",
            ),
        ]

    def __str__(self) -> str:
        identifier = self.login or (
            f"@{self.telegram_username}"
            if self.telegram_username
            else f"tg:{self.telegram_id}"
        )
        return f"{identifier} @ {self.event.code}"

    def save(self, *args, **kwargs):
        # Always store telegram_username without @ prefix
        if self.telegram_username:
            self.telegram_username = self.telegram_username.strip().lstrip("@")
        super().save(*args, **kwargs)

    def set_password(self, plain: str) -> str:
        """Hash and encrypt password. Returns plain for one-time display."""
        from django.contrib.auth.hashers import make_password

        self.password_hash = make_password(plain)
        self.password_encrypted = _encrypt_password(plain)
        return plain

    def check_password(self, plain: str) -> bool:
        from django.contrib.auth.hashers import check_password

        if not self.password_hash:
            return False
        return check_password(plain, self.password_hash)

    def get_plain_password(self) -> str:
        """Decrypt password for organizer view."""
        return _decrypt_password(
            bytes(self.password_encrypted) if self.password_encrypted else b""
        )

    @classmethod
    def create_with_password(
        cls, event, login: str, name: str, role: str = Role.GUEST
    ) -> tuple["EventUser", str]:
        """Create EventUser with a generated password. Returns (instance, plain_password)."""
        plain = _generate_password()
        user = cls(event=event, login=login, name=name, role=role)
        user.set_password(plain)
        user.save()
        return user, plain
