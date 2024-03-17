import logging.config
import os
from datetime import timedelta
from pathlib import Path

from decouple import config

from core.celery import app as celery_app
from core.common.enums import EnvironmentEnum, EnvironmentType

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = os.path.dirname(__file__)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/
ASGI_APPLICATION = 'core.asgi.application'

# ENVIRONMENT VARIABLES
ENVIRONMENT: EnvironmentType = config('ENVIRONMENT')

HOMOLOG_ENVIRONMENT_FLAGS: tuple = (
    EnvironmentEnum.LOCAL.value,
    EnvironmentEnum.DEV.value,
    EnvironmentEnum.STAGE.value,
)


ADMIN_NAME = config('ADMIN_NAME')
ADMIN_EMAIL = config('ADMIN_EMAIL').split(',')

CONST_HUB_URL = config('CONST_HUB_URL')

SSO_API_URL = config('SSO_API_URL')
USUARIO_API_SSO = config('USUARIO_API_SSO')
PASSWORD_API_SSO = config('PASSWORD_API_SSO')

HUB_API_URL = config('HUB_API_URL')
HUB_AVERBADORA_URL = config('HUB_AVERBADORA_URL')
HUB_ANALISE_CONTRATO_URL = config('HUB_ANALISE_CONTRATO_URL')
DNG_API_URL = config('DNG_API_URL')

BANKSOFT_USER = config('BANKSOFT_USER')
BANKSOFT_PASS = config('BANKSOFT_PASS')
URL_BANKSOFT = config('URL_BANKSOFT')
URL_COMISSAO = config('URL_COMISSAO')

CONST_CNPJ_CEDENTE = config('CONST_CNPJ_CEDENTE')
CONST_CNPJ_CESSIONARIO = config('CONST_CNPJ_CESSIONARIO')
CONST_CNPJ_AMIGOZ = config('CONST_CNPJ_AMIGOZ')

URL_TEMSAUDE = config('URL_TEMSAUDE')
URL_TOKEN_ZEUS = config('URL_TOKEN_ZEUS')
TEMSAUDE_COMPANYID = config('TEMSAUDE_COMPANYID')
TEMSAUDE_APIKEY = config('TEMSAUDE_APIKEY')
TEMSAUDE_CODONIX = config('TEMSAUDE_CODONIX')

URL_UNICO = config('URL_UNICO')
ISS_UNICO = config('ISS_UNICO')
URL_UNICO_SERVICES = config('URL_UNICO_SERVICES')
UNICO_API_KEY = config('UNICO_API_KEY')
UNICO_PRIVATE_KEY = config('UNICO_PRIVATE_KEY').replace('\\n', '\n')
UNICO_PRIVATE_KEY_PATH = config('UNICO_PRIVATE_KEY_PATH')

QITECH_INTEGRATION_KEY = config('QITECH_INTEGRATION_KEY')
QITECH_CLIENT_PRIVATE_KEY = config('QITECH_CLIENT_PRIVATE_KEY').replace('\\n', '\n')
QITECH_DATE_FORMAT = config('QITECH_DATE_FORMAT')
QITECH_BASE_ENDPOINT_URL = config('QITECH_BASE_ENDPOINT_URL')
QITECH_ENDPOINT_DEBT_SIMULATION = config('QITECH_ENDPOINT_DEBT_SIMULATION')
QITECH_USER = '30620610000159'
AXES_FAILURE_LIMIT = config(
    'AXES_FAILURE_LIMIT', cast=int
)  # Número de tentativas de login falhas permitidas
AXES_LOCK_OUT_AT_FAILURE = config(
    'AXES_LOCK_OUT_AT_FAILURE', default=False, cast=bool
)  # Desativar o bloqueio de IP

SECRET_KEY = config('SECRET_KEY')

REDIS_HOST = config('REDIS_HOST')
REDIS_PORT = config('REDIS_PORT', cast=int)

# ONE_SIGNAL_APP_ID = config('ONE_SIGNAL_APP_ID')
# ONE_SIGNAL_REST_API_KEY = config('ONE_SIGNAL_REST_API_KEY')
# ONE_SIGNAL_USER_AUTH_KEY = config('ONE_SIGNAL_USER_AUTH_KEY')

BASE_URL = config('BASE_URL')

CLIENT_ID_ZENVIA = config('CLIENT_ID_ZENVIA')
CLIENT_SECRET_ZENVIA = config('CLIENT_SECRET_ZENVIA')
JOURNEY_ID_ZENVIA = config('JOURNEY_ID_ZENVIA')
URL_ENVIO_ZENVIA = config('URL_ENVIO_ZENVIA')

if ENVIRONMENT in ('STAGING', 'PROD'):
    import sentry_sdk

    sentry_sdk.init(
        dsn=config('SENTRY_DSN_URL'),
        enable_tracing=True,
        traces_sample_rate=float(0),
        environment=ENVIRONMENT,
    )

GENREALI_FTP_USER = config('GENREALI_FTP_USER')
GENREALI_FTP_PASSWORD = config('GENREALI_FTP_PASSWORD')
GENREALI_FTP_HOST = config('GENREALI_FTP_HOST')
GENREALI_FTP_PORT = config('GENREALI_FTP_PORT')
GENERALI_FTP_PATH = config('GENERALI_FTP_PATH')

CELERY_TIMEZONE = config('CELERY_TIMEZONE')
CELERY_TASK_TRACK_STARTED = config(
    'CELERY_TASK_TRACK_STARTED', default=False, cast=bool
)
CELERY_TASK_TIME_LIMIT = config('CELERY_TASK_TIME_LIMIT', cast=int)
CELERY_BROKER_URL = config('CELERY_BROKER_URL')

DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS').split(',')

BUCKET_DEFAULT = config('BUCKET_DEFAULT')
BUCKET_NAME_AMIGOZ = config('BUCKET_NAME_AMIGOZ')
BUCKET_NAME_PORTABILIDADE = config('BUCKET_NAME_PORTABILIDADE')
BUCKET_NAME_INSS = config('BUCKET_NAME_INSS')
BUCKET_NAME_TERMOS = config('BUCKET_NAME_TERMOS')
BUCKET_NAME_TERMOS_IN100 = config('BUCKET_NAME_TERMOS_IN100')
BUCKET_STORAGE = config('BUCKET_STORAGE')
BUCKET_SEGUROS = config('BUCKET_SEGUROS')
BUCKET_TERMOS_DEFAULT = config('BUCKET_TERMOS_DEFAULT')

SITE_ID = config('SITE_ID', cast=int)

LOGGING_SOURCE_TOKEN = config('LOGGING_SOURCE_TOKEN')

DB_DEFAULT_ENGINE = config('DB_DEFAULT_ENGINE')
DB_DEFAULT_NAME = config('DB_DEFAULT_NAME')
FACETEC_PUBLIC_FACE_SCAN_ENCRYPTION_KEY = config(
    'FACETEC_PUBLIC_FACE_SCAN_ENCRYPTION_KEY'
)
FACETEC_DEVICE_KEY_IDENTIFIER = config('FACETEC_DEVICE_KEY_IDENTIFIER')
DB_DEFAULT_USER = config('DB_DEFAULT_USER')
FACE_MATCH_API_ENDPOINT = config('FACE_MATCH_API_ENDPOINT')
FACE_MATCH_CONFIA_API_ENDPOINT = config('FACE_MATCH_CONFIA_API_ENDPOINT')
AWS_USER_DOCS_BUCKET_NAME = config('AWS_USER_DOCS_BUCKET_NAME')
DB_DEFAULT_PASSWORD = config('DB_DEFAULT_PASSWORD')
DB_DEFAULT_HOST = config('DB_DEFAULT_HOST')
DB_DEFAULT_PORT = config('DB_DEFAULT_PORT', default=0, cast=int)

AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')

DOCK_URL_TOKEN = config('DOCK_URL_TOKEN')
DOCK_URL_BASE = config('DOCK_URL_BASE')
DOCK_CLIENT_ID = config('DOCK_CLIENT_ID')
DOCK_CLIENT_PASSWORD = config('DOCK_CLIENT_PASSWORD')

EMAIL_HABILITA_EMAIL = config('EMAIL_HABILITA_EMAIL', default=False, cast=bool)
EMAIL_LOGO = config('EMAIL_LOGO')
EMAIL_HABILITAR_SSL = config('EMAIL_HABILITAR_SSL', default=False, cast=bool)
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORTA = config('EMAIL_PORTA', cast=int)
EMAIL_REMETENTE = config('EMAIL_REMETENTE')
EMAIL_USUARIO = config('EMAIL_USUARIO')
EMAIL_SENHA = config('EMAIL_SENHA')
EMAIL_TI = config('EMAIL_TI')

# AS CONFIGURACOES CORRETAS PARA O USO
# DO SEND_EMAIL DO DJANGO.


BANNER_EMAIL = config('BANNER_EMAIL')
SUPPORT_EMAIL = config('SUPPORT_EMAIL', EMAIL_TI)

WSS_AUTH_UUID = config('WSS_AUTH_UUID')
URL_PUBLISH_WEBSOCKETS = config('URL_PUBLISH_WEBSOCKETS')

EMAIL_BACKEND = config('EMAIL_BACKEND')
DEFAULT_FROM_EMAIL = config('EMAIL_USUARIO')
EMAIL_HOST_USER = config('EMAIL_USUARIO')
EMAIL_HOST_PASSWORD = config('EMAIL_SENHA')
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORTA', cast=int)
EMAIL_USE_TLS = True

FRONT_LOGIN = config('FRONT_LOGIN')

ORIGIN_CLIENT = config('ORIGIN_CLIENT')
URL_BRB_BASE = config('URL_BRB_BASE')

LANGUAGE_CODE = config('LANGUAGE_CODE')
TIME_ZONE = config('TIME_ZONE')
USE_I18N = config('USE_I18N', default=False, cast=bool)
USE_L10N = config('USE_L10N', default=False, cast=bool)
USE_TZ = config('USE_TZ', default=False, cast=bool)

URL_FORMALIZACAO_CLIENTE = config('URL_FORMALIZACAO_CLIENTE')

MAX_CONTRACT_ACTIVE_AMOUNT: int = config(
    'MAX_CONTRACT_ACTIVE_AMOUNT', default=13, cast=int
)

WHITE_PAYMENTS_API_ENDPOINT = config('WHITE_PAYMENTS_API_ENDPOINT')

COGNITO_USERNAME = config('COGNITO_USERNAME')
COGNITO_PASSWORD = config('COGNITO_PASSWORD')
# Short URL
AWS3_LINK_SHORTENER_API_KEY: str = config('AWS3_LINK_SHORTENER_API_KEY')
SHORT_URL_DEFAULT_EXPIRATION_TIME_IN_HOURS: int = config(
    'SHORT_URL_DEFAULT_EXPIRATION_TIME_IN_HOURS', default=168, cast=int
)
WHITE_SEGUROS_API_ENDPOINT = config('WHITE_SEGUROS_API_ENDPOINT')

# Application definition

INSTALLED_APPS = [
    # django apps
    'admin_interface',
    'colorfield',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sessions',
    # 3rd party apps
    'auditlog',
    'axes',
    'ckeditor',
    'corsheaders',
    'django_celery_beat',
    'django_recaptcha',
    'import_export',
    'rangefilter',
    'rest_framework',
    'rest_framework_api_key',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    # local apps
    'custom_auth.apps.CustomAuthConfig',
    'core.apps.CoreConfig',
    'contract.apps.ContractConfig',
    'contract.products.cartao_beneficio.apps.CartaoBeneficioConfig',
    'contract.products.consignado_inss.apps.INSSConfig',
    'contract.products.portabilidade.apps.PortabilidadeConfig',
    'api_log',
    'auditoria',
    'documentscopy',
    'simulacao.apps.SimulacaoConfig',
    'gestao_comercial',
    'api_caller',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
]

USE_DJANGO_JQUERY = True

SILENCED_SYSTEM_CHECKS = ['django_recaptcha.recaptcha_test_key_error']

# Captcha
RECAPTCHA_PUBLIC_KEY = config('RECAPTCHA_PUBLIC_KEY')
RECAPTCHA_PRIVATE_KEY = config('RECAPTCHA_PRIVATE_KEY')

# Sabemi
SABEMI_SEGUROS_API_KEY = config('SABEMI_SEGUROS_API_KEY')


if ENVIRONMENT in ('LOCAL', 'DEV', 'STAGING'):
    INSTALLED_APPS.append('django_extensions')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
    'core.middlewares.session_expiration.DynamicSessionTimeoutMiddleware',
    'core.middleware_session.OneSessionPerUserMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'custom_auth.my_context_processor.front_login',
            ],
        },
    },
]

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

WSGI_APPLICATION = 'core.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': DB_DEFAULT_ENGINE,
        'NAME': DB_DEFAULT_NAME,
        'USER': DB_DEFAULT_USER,
        'PASSWORD': DB_DEFAULT_PASSWORD,
        'HOST': DB_DEFAULT_HOST,
        'PORT': DB_DEFAULT_PORT,
        'OPTIONS': {
            'charset': 'utf8',
            'use_unicode': True,
        },
    },
}


if ENVIRONMENT == 'PROD':
    DB_AUDIT_ENGINE = config('DB_AUDIT_ENGINE')
    DB_AUDIT_NAME = config('DB_AUDIT_NAME')
    DB_AUDIT_USER = config('DB_AUDIT_USER')
    DB_AUDIT_PASSWORD = config('DB_AUDIT_PASSWORD')
    DB_AUDIT_HOST = config('DB_AUDIT_HOST')
    DB_AUDIT_PORT = config('DB_AUDIT_PORT')

    DATABASES['audit'] = {
        'ENGINE': DB_AUDIT_ENGINE,
        'NAME': DB_AUDIT_NAME,
        'USER': DB_AUDIT_USER,
        'PASSWORD': DB_AUDIT_PASSWORD,
        'HOST': DB_AUDIT_HOST,
        'PORT': DB_AUDIT_PORT,
        'OPTIONS': {
            'charset': 'utf8',
            'use_unicode': True,
        },
    }

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        },
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'core.validators.CustomPasswordValidator',
    },
]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = '/home/staticfiles/core'

STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

MEDIA_URL = config('MEDIA_URL')
MEDIA_ROOT = os.path.join(PROJECT_DIR, 'media')

CORS_ORIGIN_ALLOW_ALL = True
CORS_EXPOSE_HEADERS = [
    'Content-Disposition',
]

X_FRAME_OPTIONS = 'SAMEORIGIN'

AUTH_USER_MODEL = 'custom_auth.UserProfile'


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'core.middlewares.session_expiration.CustomJWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_PERMISSION_CLASSES': ('core.permissions.IsAuthenticatedAndChecked',),
    'PAGE_SIZE': 20,
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
}

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''


__all__ = ('celery_app',)

LOGGING_CONFIG = None
logging.getLogger('requests').setLevel(logging.ERROR)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'base': {'format': '{name} ({levelname}) :: {message}', 'style': '{'}
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'base'},
        'logtail': {
            'class': 'logtail.LogtailHandler',
            'formatter': 'base',
            'source_token': LOGGING_SOURCE_TOKEN,
        },
    },
    'loggers': {
        'digitacao': {'handlers': ['console', 'logtail'], 'level': 'INFO'},
        'cliente': {'handlers': ['console', 'logtail'], 'level': 'INFO'},
        'webhookqitech': {'handlers': ['console', 'logtail'], 'level': 'INFO'},
        'celery': {
            'handlers': ['console', 'logtail'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


logging.config.dictConfig(LOGGING)

STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'access_key': AWS_ACCESS_KEY_ID,
            'secret_key': AWS_SECRET_ACCESS_KEY,
            'bucket_name': BUCKET_STORAGE,
            'location': 'originacao/',
        },
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
