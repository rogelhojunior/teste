"""
This module implements the class QiTechOperationDataInterface.
"""

# third
from schema import And, Schema, SchemaError, SchemaMissingKeyError, Use

# local
from .installment import Installment


# docs: https://docs.qitech.com.br/documentation/emissao_de_divida/status_de_uma_divida
CREDIT_OPERATION_STATUSES = [
    'waiting_signature',
    'signature_finished',
    'signed',
    'issued',
    'disbursed',
    'opened',
    'settled',
    'canceled',
    'canceled_permanently',
]

# docs: https://docs.qitech.com.br/documentation/webhooks/parcelas
INSTALLMENT_STATUSES = [
    'opened',
    'paid',
    'waiting_payment',
    'paid_early',
    'paid_partial',
    'overdue',
    'paid_partial_overdue',
    'paid_overdue',
    'unmonitored',
]

DATA_SCHEMA = Schema(
    {
        'credit_operation_status': And(
            dict,
            Schema(
                {
                    'enumerator': And(str, lambda s: s in CREDIT_OPERATION_STATUSES),
                },
                ignore_extra_keys=True,
            ),
        ),
        'installments': And(list, Use(list), lambda e: len(e) > 0),
        'number_of_installments': int,
        'collateral_constituted': bool,
    },
    ignore_extra_keys=True,
)

INSTALLMENT_SCHEMA = Schema(
    {
        'present_amount': Use(float),
        'installment_status': And(
            dict,
            Schema(
                {
                    'enumerator': And(str, lambda s: s in INSTALLMENT_STATUSES),
                },
                ignore_extra_keys=True,
            ),
        ),
        'total_amount': Use(float),
    },
    ignore_extra_keys=True,
)


class QiTechOperationDataInterface:
    """
    This class works like a interface between the action resimular_por_refin
    and the data returned by Qi Tech.
    """

    def __init__(self, data: dict) -> None:
        self.data = None
        self.error_message = ''

        try:
            self.data = data['data']
        except KeyError:
            msg = self.build_missing_field_warning_msg('data')
            self.error_message = msg

    @property
    def is_valid(self) -> bool:
        try:
            DATA_SCHEMA.validate(self.data)
            for installment in self.data['installments']:
                INSTALLMENT_SCHEMA.validate(installment)
            self.validate_all_total_amount_are_equal()
        except (SchemaError, SchemaMissingKeyError) as e:
            msg = f'Invalid QI Tech data: {str(e)}'
            self.error_message = msg
            return False

        return True

    @property
    def is_settled(self) -> bool:
        """
        En: Is this operation settled?
        Pt-BR: A operação esta quitada?
        """
        return self.data['credit_operation_status']['enumerator'] == 'settled'

    @property
    def is_endorsed_on_dataprev(self) -> bool:
        return self.data['collateral_constituted']

    def build_missing_field_warning_msg(self, field_name: str) -> str:
        msg = f'There is no "{field_name}" key inside Qi Tech response.'
        msg += ' This data key is necessary to apply data rules.'
        return msg

    def validate_all_total_amount_are_equal(self) -> None:
        """
        En: Check if all total_amount values inside installments list are equal,
        raising an SchemaError when not.
        Pt: Verifique se todos os valores de total_amount dentro da lista de
        installments são iguais, lançando um SchemaError quando não forem.
        """
        values = [n['total_amount'] for n in self.data['installments']]
        if len(set(values)) != 1:
            msg = 'All total_amount values in the installments list must be equal'
            raise SchemaError(msg)

    def get_amount_sum(self) -> float:
        """
        En:Rules for calculating the outstanding balance:

        1. If the transaction is already settled: in this case, simply
        extract the "installments[0].present_amount." That
        is, the key "installments" is a list, so you just need to take the
        first item from the list and extract the key "present_amount" within the
        "installment_payment" key.
        2. If the transaction is not settled: it is necessary to sum the
        "present_amount" of all "installments[n].present_amount."
        3. If the transaction is partially settled: the same procedure as in
        item 2, but only the outstanding installments need to be summed.
        The outstanding installments will have one of these statuses:
            - "opened"
            - "waiting_payment"
            - "overdue"

        pt-BR: Regras para o cálculo do saldo devedor:

        1. Se a operação já está quitada: nesse caso basta extrair o
        "installments[0].present_amount", isso é, a
        chave "installments" é uma lista, basta pegar o primeiro item
        da lista e extrair as a chave "present_amount" dentro da chave
        "installment_payment";
        2. Se a operação não esta quitada: necessário somar o "present_amount"
        de todos os "installments[n].present_amount";
        3. Se a operação estiver quitada parcialmente: mesmo procedimento
        do item 2, mas é necessário somar apenas as parcelas não quitadas.
        As parcelas não quitadas assumirão um desses status:
            - "opened"
            - "waiting_payment"
            - "overdue"
        """
        installments = [Installment(item) for item in self.data['installments']]
        if self.is_settled:
            return installments[0].present_amount

        amount_sum = 0.0
        for installment in installments:
            if not installment.is_settled:
                amount_sum += installment.present_amount

        return amount_sum

    def get_number_of_installments(self) -> int:
        return self.data['number_of_installments']

    def get_total_amount(self) -> float:
        return self.data['installments'][0]['total_amount']
