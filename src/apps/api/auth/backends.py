"""
Custom JWT authentication backend for EventUser.
Full implementation in Этап 3 — this is a working stub.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication


class EventUserJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that supports both Django User (organizers)
    and EventUser (guests/staff) based on token claims.
    Full per-event validation and closed_at check added in Этап 3.
    """

    pass
