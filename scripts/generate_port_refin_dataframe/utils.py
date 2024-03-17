"""
This module implements useful functions for the script generate_port_refin_dataframe.
"""

# built-in
from datetime import datetime
import os
from contract.constants import EnumTipoProduto
from contract.models.contratos import Contrato
from core.admin_actions.qitech_operation_data_interface import (
    QiTechOperationDataInterface,
)

# locals
from handlers.qitech_api.qi_tech_getter import QiTechGetter

# globals
OUTPUT_PATH = '~/Downloads'
DEFAULT_FILE_NAME = 'PORT_REFIN_REPORT'
qi_getter = QiTechGetter()


def get_output_path(args: list) -> str:
    """
    Build an output path based on the given argument.
    """
    file_path = ''
    if args:
        arg = args[0]
        if os.path.isdir(arg):
            file_path = os.path.join(arg, generate_file_name())
        else:
            file_path = arg

    else:
        file_path = os.path.join(OUTPUT_PATH, generate_file_name())

    return file_path


def generate_file_name():
    suffix = datetime.now().strftime('%x-%X')
    suffix = suffix.replace('/', '-')
    suffix = suffix.replace(':', '-')
    file_name = f'{DEFAULT_FILE_NAME}_{suffix}.xlsx'
    return file_name


def validate_path(file_path: str):
    """
    Is this path valid to create a file?

    Raises:
        - FileExistsError: when file already exists;
        - FileNotFoundError: when the directory does not exists;
        - TypeError: when extension is different than xlsx.
    """
    # check if files already exists
    if os.path.isfile(file_path):
        raise FileExistsError('The file already exists')

    # check if directory exists
    dir_path = os.path.dirname(file_path)
    if os.path.isdir(dir_path):
        raise FileNotFoundError('The directory does not exists')

    # check extension
    _, extension = os.path.splitext(file_path)
    if extension != '.xlsx':
        raise TypeError('File must be a xlsx')


def get_contracts():
    """
    Query contracts.
    """
    queryset = Contrato.objects.filter(
        tipo_produto=EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
    )
    return queryset


def calculate_endorsed_dataprev(operation_key):
    readable_dataprev_status = ''
    if not operation_key:
        return 'Refin sem operação'

    qi_tech_data = qi_getter.get_debt(operation_key)
    data_interface = QiTechOperationDataInterface(qi_tech_data)
    if not data_interface.is_valid:
        readable_dataprev_status = 'Invalid Qi Tech response'

    else:
        readable_dataprev_status = (
            'yes' if data_interface.is_endorsed_on_dataprev else 'no'
        )

    return readable_dataprev_status


def calculate_qi_tech_status(proposal_key) -> str:
    if not proposal_key:
        return 'Proposal key is None'

    qi_tech_data = qi_getter.get_credit_transfer(proposal_key)

    return qi_tech_data.get('proposal_status') or 'Não retornado'


def calculate_last_tentative_port(proposal_key) -> tuple:
    return calculate_last_tentative(qi_getter.get_port_collateral, proposal_key)


def calculate_last_tentative_refin(proposal_key) -> tuple:
    return calculate_last_tentative(qi_getter.get_refin_collateral, proposal_key)


def calculate_last_tentative(get_function, proposal_key: str):
    if not proposal_key:
        return 'Proposal key is None', 'Proposal key is None'

    data = get_function(proposal_key)
    status = extract_collateral_status(data)
    date = extract_collateral_date(data)
    return status, date


def extract_collateral_status(data: dict) -> str:
    try:
        if 'success' in data['collateral_data']['last_response']:
            return data['collateral_data']['last_response']['success'][0]['enumerator']
        elif 'errors' in data['collateral_data']['last_response']:
            return data['collateral_data']['last_response']['errors'][0]['enumerator']
        else:
            raise KeyError('"success" or "errors" keys are not present')

    except (KeyError, IndexError, TypeError):
        return 'Impossible to extract'


def extract_collateral_date(data: dict) -> str:
    return data.get('collateral_data', {}).get(
        'last_response_event_datetime', 'Impossible to extract'
    )
