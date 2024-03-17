import contextlib

from django.http import JsonResponse
from rest_framework import status
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken

from .constants import WHITELIST_IDENTIFIERS
from .models import TokenSession, UserProfile
from .utils import check_password_expiration, extract_last_part_of_url, get_reset_link


def handle_new_refresh_token(identifier, request):
    user = UserProfile.objects.filter(identifier=identifier).first()
    if identifier not in WHITELIST_IDENTIFIERS:
        if not check_password_expiration(user, request):
            return JsonResponse(
                {
                    'detail': 'Foi verificado que sua senha expirou, um e-mail foi enviado com mais informações'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.is_initial_password:
            return JsonResponse(
                {
                    'detail': 'Troca de senha necessária',
                    'change_password': True,
                    'reset_token': extract_last_part_of_url(get_reset_link(user)),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    if session := TokenSession.objects.filter(user=user).first():
        revoke_jwt_token(session.token)

    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)

    TokenSession.objects.update_or_create(
        user=user, defaults={'token': str(refresh), 'access': access}
    )

    return JsonResponse({
        'refresh': str(refresh),
        'access': access,
    })


def handle_new_access_token(refresh, access):
    if session := TokenSession.objects.filter(token=refresh).first():
        session.access = access
        session.save()

        return {
            'refresh': str(refresh),
            'access': str(access),
        }

    raise InvalidToken()


def revoke_jwt_token(token):
    with contextlib.suppress(Exception):
        token = RefreshToken(token)
        token.blacklist()
