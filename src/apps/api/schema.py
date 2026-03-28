"""drf-spectacular extensions for custom API schema integration."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class EventUserJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Expose custom JWT authenticator as Bearer auth in OpenAPI schema."""

    target_class = "apps.api.auth.backends.EventUserJWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
