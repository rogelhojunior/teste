from datetime import datetime
from typing import Optional, Union

from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from utils.date import calculate_end_date_by_months


def is_contract_end_date_valid(
    benefit_end_date: Union[datetime.date, datetime],
    months: int,
    initial_date: Optional[datetime] = None,
):
    """
    Verifies if benefit end date and contract params are valid,
     given in100 data, contract months and initial date.
    Args:
        benefit_end_date: Benefit end date
        months: Contract months
        initial_date: Contract date, default None (will be replaced by timezone.localdate()
    Returns:
        bool: Contract params valid or not. Default True if benefit_end_date is not supplied.
    """
    if benefit_end_date:
        return benefit_end_date >= calculate_end_date_by_months(
            months=months,
            initial_date=initial_date,
        )
    return True


def validate_client_installments_number(
    numero_beneficio: str,
    installments_number: int,
    in100: Optional[DadosIn100] = None,
) -> tuple[bool, str]:
    if (
        in100 := in100
        or DadosIn100.objects.filter(numero_beneficio=numero_beneficio).first()
    ):
        is_valid = is_contract_end_date_valid(
            in100.data_expiracao_beneficio,
            installments_number,
        )
        error_message = (
            '' if is_valid else 'Prazo do empréstimo maior que o prazo do benefício'
        )
        return is_valid, error_message

    return True, ''
