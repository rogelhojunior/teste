from enum import Enum


class QiTechEndorsementErrorEnum(str, Enum):
    CONSIGNABLE_MARGIN_EXCEEDED = 'consignable_margin_excceded'
    BENEFIT_BLOCKED_BY_TBM = 'benefit_blocked_by_tbm'
    BENEFIT_BLOCKED_BY_BENEFICIARY = 'benefit_blocked_by_beneficiary'
    INVALID_DISBURSEMENT_ACCOUNT = 'invalid_disbursement_account'
    RESERVATION_ALREADY_INCLUDED = 'reservation_already_included'
    BENEFIT_BLOCKED_BY_GRANTING_PROCESS = 'benefit_blocked_by_granting_process'
    PROCESSING_PAYROLL = 'processing_payroll'
    INVALID_CBC = 'invalid_cbc'
    FIRST_NAME_MISMATCH = 'first_name_mismatch'
    LEGAL_REPRESENTATIVE_DOCUMENT_NUMBER_MISMATCH = (
        'legal_representative_document_number_mismatch'
    )
    INVALID_STATE = 'invalid_state'
    OPERATION_NOT_ALLOWED_ON_THIS_RESERVATION_STATUS = (
        'operation_not_allowed_on_this_reservation_status'
    )
    INVALID_CONTRACT_DATE = 'invalid_contract_date'
    REQUIRED_FIELDS_MISSING = 'required_fields_missing'
    CBC_MISSING = 'cbc_missing'
    CONTRACT_NUMBER_MISSING = 'contract_number_missing'
    BENEFIT_NUMBER_MISSING = 'benefit_number_missing'
    INVALID_BANK_CODE = 'invalid_bank_code'
    EXCEEDED_NUMBER_OF_ALLOWED_CONTRACTS = 'exceeded_number_of_allowed_contracts'
    INVALID_IMAGE_FORMAT = 'invalid_image_format'
    OPERATION_NOT_ALLOWED_IR = 'operation_not_allowed_IR'
    WRONG_BANK_CODE_DESTINATION = 'wrong_bank_code_destination'
    WRONG_BENEFIT_NUMBER_ON_PORTABILITY = 'wrong_benefit_number_on_portability'
    INVALID_CONTRACT_TOTAL_AMOUNT = 'invalid_contract_total_amount'


class PendencyReasonEnum(str, Enum):
    BANK_NUMBER = 'Número do Banco'
    BANK_DETAILS = 'Dados Bancários'
    CLIENT_NAME = 'Nome do Cliente'
    STATE = 'UF'
    BENEFIT_NUMBER = 'Número do Benefício'
    MARGIN_EXCEEDED = 'Margem Excedida'
