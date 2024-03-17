"""This module implements class Installment."""

NOT_SETTLED_STATUSES = [
    'opened',
    'waiting_payment',
    'overdue',
    'unmonitored',
]


class Installment:
    """
    En: This class represents one installment. When the GET request is sent
    to Qi Tech the response contains several installments inside the key
    'data.installments', this class abstracts each item inside this list.

    Pt-BR:En: Esta classe representa uma parcela. Quando uma solicitação
    GET é enviada para a Qi Tech, a resposta contém várias parcelas dentro
    da chave 'data.installments'. Essa classe abstrai cada item dentro dessa
    lista.
    """

    def __init__(self, data: dict) -> None:
        self.data = data
        self.present_amount = data['present_amount']
        self.status = data['installment_status']['enumerator']
        self.total_amount = data['total_amount']

    def __str__(self) -> str:
        return f'Installment {self.status} {self.present_amount}'

    @property
    def is_settled(self) -> bool:
        """
        En: is this installment settled?
        PT: essa parcela esta quitada?
        """
        return self.status not in NOT_SETTLED_STATUSES
