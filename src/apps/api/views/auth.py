"""Authentication views."""

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as SimpleJWTRefreshView

from apps.api.serializers.auth import LoginSerializer, TelegramLoginSerializer


def _token_response(validated: dict) -> dict:
    """Build a unified token response payload."""
    tokens = validated["tokens"]
    event_user = validated.get("event_user")
    event = validated.get("event")
    user = validated.get("user")

    payload = {
        "access": tokens["access"],
        "refresh": tokens["refresh"],
    }

    if event_user:
        payload["user"] = {
            "id": event_user.id,
            "name": event_user.name,
            "login": event_user.login,
            "role": event_user.role,
        }
        payload["event"] = {
            "id": event.id,
            "code": event.code,
            "name": event.name,
        }
    elif user:
        payload["user"] = {
            "id": user.id,
            "username": user.username,
            "role": "organizer",
        }

    return payload


class _TokenResponseSerializer(drf_serializers.Serializer):
    """Inline response schema for Swagger docs."""

    access = drf_serializers.CharField()
    refresh = drf_serializers.CharField()
    user = drf_serializers.DictField(child=drf_serializers.CharField(), required=False)
    event = drf_serializers.DictField(child=drf_serializers.CharField(), required=False)


class _RefreshResponseSerializer(drf_serializers.Serializer):
    access = drf_serializers.CharField()
    refresh = drf_serializers.CharField(
        required=False,
        help_text="Новый refresh при ROTATE_REFRESH_TOKENS — клиент должен сохранить.",
    )


class _RefreshRequestSerializer(drf_serializers.Serializer):
    refresh = drf_serializers.CharField()


@extend_schema(
    tags=["Auth"],
    summary="Логин (все роли)",
    description="С event_code — для гостей и персонала. Без event_code — для организаторов.",
    request=LoginSerializer,
    responses={200: _TokenResponseSerializer},
    examples=[
        OpenApiExample(
            name="Успешный логин гостя",
            value={
                "access": "eyJhbGciOiJIUzI1NiIn...",
                "refresh": "eyJhbGciOiJIUzI1NiIsInR5...",
                "user": {
                    "id": 1,
                    "name": "Иван",
                    "login": "ivan@test.ru",
                    "role": "guest",
                },
                "event": {"id": 1, "code": "TECH24", "name": "IT Conf 2024"},
            },
            response_only=True,
            status_codes=["200"],
        )
    ],
)
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            _token_response(serializer.validated_data), status=status.HTTP_200_OK
        )


@extend_schema(
    tags=["Auth"],
    summary="Telegram логин",
    description="Только для бота. Требует заголовок X-Bot-Token.",
    parameters=[
        OpenApiParameter(
            name="X-Bot-Token",
            location=OpenApiParameter.HEADER,
            required=True,
            type=str,
            description="Секретный токен бота (из .env BOT_SECRET_TOKEN)",
        )
    ],
    request=TelegramLoginSerializer,
    responses={200: _TokenResponseSerializer},
    examples=[
        OpenApiExample(
            name="Telegram WebApp дата",
            value={
                "initData": "query_id=...&user=%7B%22id%22%3A123...",
                "invite_code": "SECRET42",
            },
            request_only=True,
        ),
        OpenApiExample(
            name="Успешная авторизация ТГ Гостя",
            value={
                "access": "eyJhbGci...",
                "refresh": "eyJhb...",
                "user": {"id": 1, "name": "Pavel", "login": "@durov", "role": "guest"},
                "event": {"id": 1, "code": "TECH24"},
            },
            response_only=True,
            status_codes=["200"],
        ),
    ],
)
class TelegramLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        bot_token = request.headers.get("X-Bot-Token", "")
        expected = settings.BOT_SECRET_TOKEN

        if not expected:
            return Response(
                {"detail": "Telegram login is not configured on this server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if bot_token != expected:
            return Response(
                {"detail": "Forbidden."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TelegramLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            _token_response(serializer.validated_data), status=status.HTTP_200_OK
        )


@extend_schema(
    tags=["Auth"],
    summary="Обновить access token",
    description=(
        "При ROTATE_REFRESH_TOKENS в ответе может быть новый refresh — сохраните его; "
        "старый refresh после ротации попадает в blacklist."
    ),
    request=_RefreshRequestSerializer,
    responses={200: _RefreshResponseSerializer},
)
class RefreshView(SimpleJWTRefreshView):
    """Стандартный refresh SimpleJWT (ротация + blacklist совместимы с настройками)."""

    permission_classes = [AllowAny]


@extend_schema(
    tags=["Auth"],
    summary="Выйти (инвалидировать refresh token)",
    request=_RefreshRequestSerializer,
    responses={204: None},
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
