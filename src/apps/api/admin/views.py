"""Custom views for organizer-specific admin workflows."""

from __future__ import annotations

import csv
import io
import secrets
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.api.admin.forms import BatchMenuImageUploadForm, VisitorCsvImportForm
from apps.api.models import (
    Event,
    EventGuest,
    EventUser,
    GuestRole,
    MenuItem,
    Order,
    OrderItem,
)
from apps.api.models.orders import OrderStatus

try:
    from unfold.views import BaseDashboardView
except (
    ImportError
):  # pragma: no cover - fallback for environments without django-unfold
    BaseDashboardView = TemplateView


@dataclass(slots=True)
class VisitorCsvRow:
    name: str
    role: str
    login: str | None
    telegram_username: str | None
    guest_role: GuestRole | None


def _parse_ids(raw_ids: str) -> list[int]:
    return [int(value) for value in raw_ids.split(",") if value.strip().isdigit()]


class OrganizerDashboardView(BaseDashboardView):
    """Simple organizer dashboard with registration and revenue charts."""

    template_name = "admin/organizer/dashboard.html"
    admin_site: Any = None

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        request: HttpRequest = self.request
        user = request.user

        since = (timezone.now() - timedelta(days=13)).date()
        labels = [(since + timedelta(days=offset)).isoformat() for offset in range(14)]

        registrations = (
            EventUser.objects.filter(event__organizer=user, created_at__date__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )
        registrations_by_day = {
            row["day"].isoformat(): row["total"]
            for row in registrations
            if row["day"] is not None
        }

        revenue_query = (
            OrderItem.objects.filter(
                order__event__organizer=user,
                order__status=OrderStatus.COMPLETED,
                removed=False,
                order__created_at__date__gte=since,
            )
            .annotate(day=TruncDate("order__created_at"))
            .values("day")
            .annotate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") * F("menu_item__price"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )
            )
            .order_by("day")
        )
        revenue_by_day = {
            row["day"].isoformat(): float(row["total"] or Decimal("0"))
            for row in revenue_query
            if row["day"] is not None
        }

        registrations_series = [registrations_by_day.get(day, 0) for day in labels]
        revenue_series = [revenue_by_day.get(day, 0.0) for day in labels]

        events_qs = Event.objects.filter(organizer=user)
        completed_orders_period = Order.objects.filter(
            event__organizer=user,
            status=OrderStatus.COMPLETED,
            created_at__date__gte=since,
        ).count()
        revenue_total_period = float(sum(revenue_series))

        top_regs = {
            row["event_id"]: row["total"]
            for row in EventUser.objects.filter(
                event__organizer=user,
                created_at__date__gte=since,
            )
            .values("event_id")
            .annotate(total=Count("id"))
        }
        top_revenue = {
            row["order__event_id"]: float(row["total"] or Decimal("0"))
            for row in OrderItem.objects.filter(
                order__event__organizer=user,
                order__status=OrderStatus.COMPLETED,
                removed=False,
                order__created_at__date__gte=since,
            )
            .values("order__event_id")
            .annotate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantity") * F("menu_item__price"),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                )
            )
        }
        top_orders = {
            row["event_id"]: row["total"]
            for row in Order.objects.filter(
                event__organizer=user,
                status=OrderStatus.COMPLETED,
                created_at__date__gte=since,
            )
            .values("event_id")
            .annotate(total=Count("id"))
        }

        top_events = []
        for event in events_qs.only("id", "name", "code"):
            top_events.append(
                {
                    "id": event.id,
                    "name": event.name,
                    "code": event.code,
                    "registrations": top_regs.get(event.id, 0),
                    "completed_orders": top_orders.get(event.id, 0),
                    "revenue": top_revenue.get(event.id, 0.0),
                }
            )
        top_events.sort(
            key=lambda item: (item["revenue"], item["registrations"]), reverse=True
        )

        avg_check = (
            revenue_total_period / completed_orders_period
            if completed_orders_period
            else 0.0
        )

        context.update(
            {
                **self.admin_site.each_context(request),
                "title": "Статистика организатора",
                "period_days": 14,
                "chart_data": {
                    "labels": labels,
                    "registrations": registrations_series,
                    "revenue": revenue_series,
                },
                "kpis": {
                    "events_total": events_qs.count(),
                    "events_open": events_qs.filter(is_open=True).count(),
                    "registrations_period": sum(registrations_series),
                    "completed_orders_period": completed_orders_period,
                    "revenue_period": revenue_total_period,
                    "avg_check_period": avg_check,
                },
                "top_events": top_events[:5],
            }
        )
        return context


class MenuItemBatchUploadView(View):
    """Assign one uploaded image per selected menu item."""

    template_name = "admin/organizer/menuitem_batch_upload.html"
    admin_site: Any = None

    def get(self, request: HttpRequest) -> HttpResponse:
        raw_ids = request.GET.get("ids", "")
        item_ids = _parse_ids(raw_ids)

        items = MenuItem.objects.filter(
            id__in=item_ids,
            menu__event__organizer=request.user,
        ).select_related("menu", "menu__event")

        if not item_ids or not items.exists():
            messages.error(
                request, "Нужно выбрать хотя бы одну доступную позицию меню."
            )
            return redirect(reverse("organizer_admin:api_menuitem_changelist"))

        form = BatchMenuImageUploadForm(
            initial={"item_ids": ",".join(map(str, item_ids))}
        )
        context = {
            **self.admin_site.each_context(request),
            "title": "Массовая установка изображений",
            "form": form,
            "items": items,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        form = BatchMenuImageUploadForm(request.POST, request.FILES)
        item_ids = _parse_ids(request.POST.get("item_ids", ""))
        item_map = {
            item.id: item
            for item in MenuItem.objects.filter(
                id__in=item_ids,
                menu__event__organizer=request.user,
            )
        }

        if not form.is_valid() or not item_map:
            messages.error(request, "Проверьте выбранные позиции и файлы.")
            context = {
                **self.admin_site.each_context(request),
                "title": "Массовая установка изображений",
                "form": form,
                "items": item_map.values(),
            }
            return render(request, self.template_name, context)

        items_ordered = [
            item_map[item_id] for item_id in item_ids if item_id in item_map
        ]
        uploads = request.FILES.getlist("images")

        if len(uploads) != len(items_ordered):
            messages.error(
                request,
                "Количество файлов должно совпадать с количеством выбранных позиций меню.",
            )
            context = {
                **self.admin_site.each_context(request),
                "title": "Массовая установка изображений",
                "form": form,
                "items": items_ordered,
            }
            return render(request, self.template_name, context)

        updated_total = 0
        with transaction.atomic():
            for item, upload in zip(items_ordered, uploads, strict=False):
                item.image = upload
                item.save(update_fields=["image"])
                updated_total += 1

        messages.success(request, f"Изображения обновлены для {updated_total} позиций.")
        return redirect(reverse("organizer_admin:api_menuitem_changelist"))


class VisitorCsvImportView(View):
    """Import visitors from CSV with row-level validation and optional dry run."""

    template_name = "admin/organizer/visitor_csv_import.html"
    admin_site: Any = None

    def get(self, request: HttpRequest) -> HttpResponse:
        form = VisitorCsvImportForm(
            organizer=request.user,
            initial={"event": request.GET.get("event_id")},
        )
        context = {
            **self.admin_site.each_context(request),
            "title": "Импорт посетителей из CSV",
            "form": form,
            "errors": [],
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        form = VisitorCsvImportForm(request.POST, request.FILES, organizer=request.user)
        errors: list[str] = []

        if not form.is_valid():
            context = {
                **self.admin_site.each_context(request),
                "title": "Импорт посетителей из CSV",
                "form": form,
                "errors": errors,
            }
            return render(request, self.template_name, context)

        event = form.cleaned_data["event"]
        csv_file = form.cleaned_data["csv_file"]
        dry_run = form.cleaned_data["dry_run"]

        content = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        headers = set(reader.fieldnames or [])

        required_headers = {"name"}
        optional_headers = {"login", "telegram_username", "role", "guest_role"}
        missing = required_headers - headers

        if missing:
            errors.append(
                f"Отсутствуют обязательные колонки: {', '.join(sorted(missing))}."
            )

        unknown_headers = headers - (required_headers | optional_headers)
        if unknown_headers:
            errors.append(f"Неизвестные колонки: {', '.join(sorted(unknown_headers))}.")

        rows_to_create: list[VisitorCsvRow] = []
        if not errors:
            rows_to_create, errors = self._validate_rows(
                reader=reader, event_id=event.id
            )

        if errors:
            messages.error(request, "CSV содержит ошибки. Импорт не выполнен.")
            context = {
                **self.admin_site.each_context(request),
                "title": "Импорт посетителей из CSV",
                "form": form,
                "errors": errors,
            }
            return render(request, self.template_name, context)

        if dry_run:
            messages.success(
                request,
                f"Dry-run OK: валидно {len(rows_to_create)} строк. Сохранение не выполнялось.",
            )
            context = {
                **self.admin_site.each_context(request),
                "title": "Импорт посетителей из CSV",
                "form": form,
                "errors": [],
            }
            return render(request, self.template_name, context)

        with transaction.atomic():
            created = self._persist_rows(event_id=event.id, rows=rows_to_create)

        messages.success(request, f"Импорт завершен. Создано пользователей: {created}.")
        return redirect(reverse("organizer_admin:api_eventuser_changelist"))

    @staticmethod
    def _validate_rows(
        *, reader: csv.DictReader, event_id: int
    ) -> tuple[list[VisitorCsvRow], list[str]]:
        errors: list[str] = []
        result: list[VisitorCsvRow] = []

        seen_login: set[str] = set()
        seen_tg: set[str] = set()

        for line_num, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            login = (row.get("login") or "").strip().lower() or None
            telegram_username = (row.get("telegram_username") or "").strip().lstrip(
                "@"
            ) or None
            role = (row.get("role") or EventUser.Role.GUEST).strip().lower()
            guest_role_name = (row.get("guest_role") or "").strip()

            if not name:
                errors.append(f"Строка {line_num}: поле 'name' обязательно.")

            if role not in {EventUser.Role.GUEST, EventUser.Role.STAFF}:
                errors.append(
                    f"Строка {line_num}: role должен быть guest или staff, получено '{role}'."
                )

            if role == EventUser.Role.STAFF and guest_role_name:
                errors.append(
                    f"Строка {line_num}: guest_role можно указывать только для role=guest."
                )

            if not login and not telegram_username:
                errors.append(
                    f"Строка {line_num}: нужен хотя бы один идентификатор (login или telegram_username)."
                )

            if login:
                try:
                    validate_email(login)
                except Exception:
                    errors.append(
                        f"Строка {line_num}: login '{login}' не является корректным email."
                    )
                if login in seen_login:
                    errors.append(
                        f"Строка {line_num}: duplicate login '{login}' внутри файла."
                    )
                seen_login.add(login)
                if EventUser.objects.filter(event_id=event_id, login=login).exists():
                    errors.append(f"Строка {line_num}: login '{login}' уже существует.")

            guest_role_obj: GuestRole | None = None
            if telegram_username:
                if telegram_username in seen_tg:
                    errors.append(
                        f"Строка {line_num}: duplicate telegram_username '{telegram_username}' внутри файла."
                    )
                seen_tg.add(telegram_username)
                if EventUser.objects.filter(
                    event_id=event_id,
                    telegram_username=telegram_username,
                ).exists():
                    errors.append(
                        f"Строка {line_num}: telegram_username '{telegram_username}' уже существует."
                    )

            if guest_role_name:
                guest_role_obj = GuestRole.objects.filter(
                    event_id=event_id,
                    name=guest_role_name,
                ).first()
                if guest_role_obj is None:
                    errors.append(
                        f"Строка {line_num}: роль гостя '{guest_role_name}' не найдена в мероприятии."
                    )
                if role != EventUser.Role.GUEST:
                    guest_role_obj = None

            result.append(
                VisitorCsvRow(
                    name=name,
                    role=role,
                    login=login,
                    telegram_username=telegram_username,
                    guest_role=guest_role_obj,
                )
            )

        return result, errors

    @staticmethod
    def _persist_rows(*, event_id: int, rows: list[VisitorCsvRow]) -> int:
        created = 0
        for row in rows:
            event_user = EventUser(
                event_id=event_id,
                login=row.login,
                telegram_username=row.telegram_username,
                name=row.name,
                role=row.role,
            )
            if row.login:
                # Auto-generate password for records imported with email login.
                event_user.set_password(secrets.token_urlsafe(9))
            event_user.save()
            created += 1

            if event_user.role == EventUser.Role.GUEST:
                EventGuest.objects.create(
                    event_id=event_id,
                    event_user=event_user,
                    role=row.guest_role,
                )
        return created
