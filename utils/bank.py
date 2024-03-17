import logging

from rest_framework.exceptions import ValidationError

from core.constants import EnumTipoConta
from core.models import BancosBrasileiros, Cliente
from core.models.cliente import DadosBancarios


def get_brazilian_bank(bank_code: str):
    """
    Gets brazilian bank from given bank_code
    Raises:
        ValidationError if bank does not exists on database
    Args:
        bank_code: Bank code (with 3 digits)

    Returns:
        BancosBrasileiros object

    """
    try:
        return BancosBrasileiros.objects.get(codigo=bank_code)
    except BancosBrasileiros.DoesNotExist as e:
        logging.error(
            f'Erro ao obter o banco brasileiro'
            f' Este banco ({bank_code}) não está cadastrado no sistema'
        )
        raise ValidationError('Este banco não está cadastrado no sistema!!') from e


def get_client_bank_data(
    client: Cliente,
    account_type: tuple = (
        EnumTipoConta.CORRENTE_PESSOA_FISICA,
        EnumTipoConta.POUPANCA_PESSOA_FISICA,
    ),
) -> DadosBancarios:
    """
    Returns first client bank
    Args:
        client: Cliente instance
        account_type: account types, default CORRENTE_PESSOA_FISICA ou POUPANCA_PESSOA_FISICA

    Returns:
        DadosBancarios object from specified client

    """
    try:
        if bank_data := DadosBancarios.objects.filter(
            cliente=client,
            conta_tipo__in=account_type,
        ).first():
            return bank_data
        else:
            raise DadosBancarios.DoesNotExist
    except DadosBancarios.DoesNotExist as e:
        logging.error(
            f'Erro ao obter dados bancários do cliente ({client.id}).'
            f' Este cliente não possui dados bancários cadastrados dos tipos informados.'
        )
        raise ValidationError(
            'Este cliente não possui dados bancários cadastrados!!'
        ) from e
