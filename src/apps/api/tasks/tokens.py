"""Celery tasks for token management."""

import logging
from io import StringIO

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def flush_expired_tokens():
    """
    Remove expired JWT tokens from the simplejwt blacklist.
    Runs periodically via Celery Beat.
    """
    out = StringIO()
    try:
        call_command("flushexpiredtokens", stdout=out)
        result = out.getvalue().strip()
        logger.info(f"Flushed expired tokens: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to flush expired tokens: {e}")
        return str(e)
