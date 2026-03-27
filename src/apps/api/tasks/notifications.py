"""Celery tasks for sending notifications."""

import logging

from celery import shared_task

from apps.api.models import Notification

logger = logging.getLogger(__name__)


@shared_task
def send_push_notification(notification_id: int):
    """
    Mock task to send a push/Telegram notification.
    In production, this would use a Bot API, FCM, or WebSockets.
    """
    try:
        notification = Notification.objects.select_related("event_user").get(
            pk=notification_id
        )
    except Notification.DoesNotExist:
        logger.warning(f"Notification {notification_id} not found.")
        return

    # TODO: Integrate with Telegram Bot API or FCM
    # Example:
    # if notification.event_user.telegram_id:
    #     bot.send_message(notification.event_user.telegram_id, notification.message)

    user_ident = (
        notification.event_user.telegram_username or notification.event_user.login
    )
    logger.info(f"[PUSH MOCK] To {user_ident}: {notification.message}")

    return f"Sent mock push to {user_ident}"
