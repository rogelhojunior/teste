from django.apps import AppConfig


class CustomAuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'custom_auth'
    verbose_name = '2. Usuários e CORBANs'

    def ready(self):
        import custom_auth.signals  # noqa : F401
