# custom_token_generator.py

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import base36_to_int, int_to_base36

from core.models import BackofficeConfigs


class CustomPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_token_with_timestamp(self, user, timestamp, secret):
        ts_b36 = int_to_base36(timestamp)
        hash_string = salted_hmac(
            self.key_salt,
            self._make_hash_value(user, timestamp),
            secret=secret,
            algorithm=self.algorithm,
        ).hexdigest()[::2]  # Reduzir o tamanho do URL.

        return f'{ts_b36}-{hash_string}'

    def check_token(self, user, token):
        if not user or not token:
            return False

        try:
            ts_b36, _ = token.split('-')
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        configs = BackofficeConfigs.objects.first()
        expiration_days = configs.email_password_expiration_days
        expiration_seconds = expiration_days * 24 * 3600

        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, ts, secret),
                token,
            ):
                break
        else:
            return False

        return self._num_seconds(self._now()) - ts <= expiration_seconds

    # As funções _num_seconds, _now e _make_hash_value permanecem inalteradas.


custom_token_generator = CustomPasswordResetTokenGenerator()
