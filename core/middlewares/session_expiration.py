from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from core.models import BackofficeConfigs
from custom_auth.models import TokenSession


class DynamicSessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and (
            dynamic_timeout := self.get_dynamic_session_timeout()
        ):
            request.session.set_expiry(dynamic_timeout)
        return self.get_response(request)

    def get_dynamic_session_timeout(self) -> timezone.datetime:
        if backoffice_configs := BackofficeConfigs.objects.first():
            return timezone.now() + timezone.timedelta(
                minutes=backoffice_configs.session_expiration_time
            )


class CustomJWTAuthentication(JWTAuthentication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        if self.is_valid_access_token(raw_token.decode('UTF-8')):
            return super().authenticate(request)

        raise InvalidToken()

    def is_valid_access_token(self, token):
        return TokenSession.objects.filter(access=token).exists()
