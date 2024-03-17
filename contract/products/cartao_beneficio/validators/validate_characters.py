from django.core.exceptions import ValidationError

from contract.constants import EnumTipoProduto


def validate_max_length(value):
    max_length = 3
    value_str = str(value)
    if len(value_str) > max_length:
        raise ValidationError('O valor não pode ter mais de 3 caracteres.')


def validate_tipo_produto(value):
    if value not in [
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ]:
        raise ValidationError(
            'O tipo de produto deve ser CARTAO BENEFICIO ou CONSIGNADO.'
        )
