"""Management command to seed test event data for manual environments."""

from __future__ import annotations

import csv
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.api.models import Event, EventUser


class Command(BaseCommand):
    help = "Create a test event with guest/staff users and export credentials to CSV."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--organizer-id", type=int, help="Django User id of organizer"
        )
        parser.add_argument(
            "--organizer-username",
            type=str,
            help="Django User username of organizer",
        )
        parser.add_argument(
            "--organizer-email",
            type=str,
            help="Django User email of organizer",
        )
        parser.add_argument(
            "--event-code",
            type=str,
            help="Reuse existing event by code or set code for new event",
        )
        parser.add_argument(
            "--event-name",
            type=str,
            default="Тестовое мероприятие",
            help="Event name for a new event",
        )
        parser.add_argument(
            "--location",
            type=str,
            default="Москва, ул. Примерная, 10",
            help="Event location for a new event",
        )
        parser.add_argument(
            "--contacts",
            type=str,
            default="Email: organizer@example.com, Телефон: +7 999 123-45-67",
            help="Organizer contacts for a new event",
        )
        parser.add_argument(
            "--guests",
            type=int,
            default=45,
            help="How many guest users to create",
        )
        parser.add_argument(
            "--staff",
            type=int,
            default=5,
            help="How many staff users to create",
        )
        parser.add_argument(
            "--duration-hours",
            type=int,
            default=3,
            help="Duration for newly created event",
        )
        parser.add_argument(
            "--csv-path",
            type=str,
            default="/tmp/event_users_{event_code}.csv",
            help="Absolute or relative CSV path. Supports {event_code} template.",
        )
        parser.add_argument(
            "--login-domain",
            type=str,
            default="test.local",
            help="Email domain for generated users",
        )
        parser.add_argument(
            "--reset-existing-users",
            action="store_true",
            help="Delete existing EventUser in selected event before seeding",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        organizer = self._resolve_organizer(options)
        event = self._resolve_or_create_event(organizer=organizer, options=options)

        created_rows: list[dict[str, str]] = []
        with transaction.atomic():
            if options["reset_existing_users"]:
                deleted_count, _ = EventUser.objects.filter(event=event).delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Удалены существующие пользователи мероприятия: {deleted_count}"
                    )
                )

            created_rows.extend(
                self._create_users(
                    event=event,
                    role=EventUser.Role.GUEST,
                    count=options["guests"],
                    prefix="guest",
                    domain=options["login_domain"],
                )
            )
            created_rows.extend(
                self._create_users(
                    event=event,
                    role=EventUser.Role.STAFF,
                    count=options["staff"],
                    prefix="staff",
                    domain=options["login_domain"],
                )
            )

        csv_path = self._write_csv(options["csv_path"], event.code, created_rows)
        self._print_summary(event=event, csv_path=csv_path, rows=created_rows)

    def _resolve_organizer(self, options: dict[str, Any]):
        User = get_user_model()
        organizer_id = options.get("organizer_id")
        organizer_username = options.get("organizer_username")
        organizer_email = options.get("organizer_email")

        if not any([organizer_id, organizer_username, organizer_email]):
            raise CommandError(
                "Укажите организатора: --organizer-id или --organizer-username или --organizer-email"
            )

        users = User.objects.all()
        if organizer_id:
            users = users.filter(id=organizer_id)
        elif organizer_username:
            users = users.filter(username=organizer_username)
        elif organizer_email:
            users = users.filter(email=organizer_email)

        organizer = users.first()
        if organizer is None:
            raise CommandError("Организатор не найден по указанному фильтру.")
        if not hasattr(organizer, "organizer_profile"):
            raise CommandError(
                "Пользователь найден, но не имеет OrganizerProfile. Создайте профиль организатора."
            )
        return organizer

    def _resolve_or_create_event(self, organizer, options: dict[str, Any]) -> Event:
        event_code = options.get("event_code")

        if event_code:
            event = Event.objects.filter(code=event_code).first()
            if event is not None:
                if event.organizer_id != organizer.id:
                    raise CommandError(
                        "Мероприятие с этим code принадлежит другому организатору."
                    )
                return event

        start_time = timezone.now()
        end_time = start_time + timedelta(hours=options["duration_hours"])

        event = Event(
            name=options["event_name"],
            location=options["location"],
            organizer_contacts=options["contacts"],
            organizer=organizer,
            start_time=start_time,
            end_time=end_time,
        )
        if event_code:
            event.code = event_code.upper()
        event.save()
        return event

    def _create_users(
        self,
        *,
        event: Event,
        role: str,
        count: int,
        prefix: str,
        domain: str,
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if count <= 0:
            return rows

        existing_logins = set(
            EventUser.objects.filter(event=event)
            .exclude(login__isnull=True)
            .values_list("login", flat=True)
        )

        index = 1
        while len(rows) < count:
            login = f"{prefix}{index:02d}@{domain}".lower()
            index += 1
            if login in existing_logins:
                continue

            user, plain_password = EventUser.create_with_password(
                event=event,
                login=login,
                name=f"{'Гость' if role == EventUser.Role.GUEST else 'Персонал'} {len(rows) + 1}",
                role=role,
            )
            rows.append(
                {
                    "login": user.login or "",
                    "password": plain_password,
                    "role": role,
                    "event_code": event.code,
                }
            )
            existing_logins.add(login)
        return rows

    def _write_csv(
        self,
        template_path: str,
        event_code: str,
        rows: list[dict[str, str]],
    ) -> Path:
        resolved = template_path.format(event_code=event_code)
        csv_path = Path(resolved)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["login", "password", "role", "event_code"],
            )
            writer.writeheader()
            writer.writerows(rows)

        return csv_path

    def _print_summary(
        self, *, event: Event, csv_path: Path, rows: list[dict[str, str]]
    ) -> None:
        self.stdout.write(self.style.SUCCESS("Тестовые данные созданы."))
        self.stdout.write(f"Event ID: {event.id}")
        self.stdout.write(f"Event code: {event.code}")
        self.stdout.write(f"Event name: {event.name}")
        self.stdout.write(f"CSV: {csv_path}")
        self.stdout.write(f"Создано пользователей: {len(rows)}")
        self.stdout.write(f"Telegram deeplink: {event.deeplink_tg}")
        self.stdout.write(f"Web deeplink: {event.deeplink_web}")
