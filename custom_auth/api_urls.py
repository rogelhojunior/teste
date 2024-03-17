from django.contrib import admin
from django.urls import path

from . import views as auth_views
from .views import (
    AtualizarSenhaAPIView,
    CustomPasswordResetView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    EnvioDocumentosUsuario,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    UserAPIView,
)

admin.autodiscover()
admin.site.site_header = 'Back office '
admin.site.index_title = 'Administração'
admin.site.site_title = 'Back office'

urlpatterns = [
    path('permissoes-usuario/', UserAPIView.as_view()),
    path('save-address/', auth_views.save_address, name='save_address'),
    path(
        'set-principal-address/',
        auth_views.set_principal_address,
        name='set_principal_address',
    ),
    path(
        'get-principal-address/',
        auth_views.get_principal_address,
        name='get_principal_address',
    ),
    path('register/', auth_views.registration_view, name='api_register'),
    path('login/', auth_views.login_view, name='api_login'),
    path('check/', auth_views.check_user_view, name='api_check_user'),
    path('enviar-documentos/', EnvioDocumentosUsuario.as_view()),
    path(
        'change-password/', auth_views.change_user_password, name='api_change_password'
    ),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('atualizar-senha', AtualizarSenhaAPIView.as_view(), name='update-password'),
    path(
        'password-reset/',
        CustomPasswordResetView.as_view(),
        name='password_request_reset',
    ),
    path(
        'password-request-reset/',
        PasswordResetRequestView.as_view(),
        name='password_reset_front_request',
    ),
    path(
        'password-reset-confirm/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(),
        name='password_reset_front_confirm',
    ),
]
