"""This module implements util functions for insert_portability_proposal"""

from contract.models.contratos import Contrato


def fill_zeros_on_right_until_length_equal(n: int, s: str) -> str:
    return s.rjust(n, '0')


def clear_dots_and_hyphens(s: str) -> str:
    s = s.replace('.', '')
    return s.replace('-', '')


def get_contract_using_token(token) -> Contrato:
    return Contrato.objects.get(token_contrato=token)


def is_valid_url(url: str) -> bool:
    return bool(url.startswith('http'))
