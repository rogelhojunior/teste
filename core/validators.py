from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from pycpfcnpj import cpfcnpj
from rest_framework import serializers


def checar_cpf(value):
    if value and not cpfcnpj.validate(value):
        raise serializers.ValidationError('Número CPF inválido.')


def checar_cep(value):
    if len(value) < 8:
        raise serializers.ValidationError('Número de CEP inválido.')


class CustomPasswordValidator:
    def validate(self, password, user=None):
        if not any(char.isdigit() for char in password):
            raise ValidationError(
                _(
                    'Sua senha deve conter pelo menos um número, uma letra maiúscula, '
                    'uma letra minúscula e um caractere especial.'
                ),
                code='password_no_number',
            )

        if not any(char.isalpha() and char.islower() for char in password):
            raise ValidationError(
                _(
                    'Sua senha deve conter pelo menos um número, uma letra maiúscula, '
                    'uma letra minúscula e um caractere especial.'
                ),
                code='password_no_lower',
            )

        if not any(char.isalpha() and char.isupper() for char in password):
            raise ValidationError(
                _(
                    'Sua senha deve conter pelo menos um número, uma letra maiúscula, '
                    'uma letra minúscula e um caractere especial.'
                ),
                code='password_no_upper',
            )

        if all(char.isalnum() for char in password):
            raise ValidationError(
                _(
                    'Sua senha deve conter pelo menos um número, uma letra maiúscula, '
                    'uma letra minúscula e um caractere especial.'
                ),
                code='password_no_special',
            )
        # Adicione a verificação para evitar a reutilização da senha atual
        if user and check_password(password, user.password):
            raise ValidationError(
                _('A nova senha não deve ser igual a senha anterior.'),
                code='password_reused',
            )

    def get_help_text(self):
        return _(
            'Sua senha deve conter pelo menos um número, uma letra maiúscula, '
            'uma letra minúscula e um caractere especial.'
        )
