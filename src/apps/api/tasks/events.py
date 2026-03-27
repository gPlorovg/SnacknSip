"""Celery tasks for event lifecycle management."""

import logging

from celery import shared_task
from django.utils import timezone

from apps.api.models import Event

logger = logging.getLogger(__name__)


@shared_task
def auto_close_events():
    """
    Close events that have passed their end_time.
    Runs periodically via Celery Beat.
    """
    now = timezone.now()
    events_to_close = Event.objects.filter(is_open=True, end_time__lte=now)

    count = 0
    for event in events_to_close:
        event.close()
        logger.info(f"Auto-closed event: {event.code} ({event.name})")
        count += 1

    return f"Closed {count} events."
