from typing import Literal

WEBHOOK_ENDORSEMENT_ERRORS_TYPE = Literal[
    'consignable_margin_excceded',
    'benefit_blocked_by_tbm',
    'benefit_blocked_by_beneficiary',
    'invalid_disbursement_account',
    'reservation_already_included',
    'benefit_blocked_by_granting_process',
    'processing_payroll',
    'invalid_cbc',
    'first_name_mismatch',
    'legal_representative_document_number_mismatch',
    'invalid_state',
    'operation_not_allowed_on_this_reservation_status',
    'invalid_contract_date',
    'required_fields_missing',
    'cbc_missing',
    'contract_number_missing',
    'benefit_number_missing',
    'invalid_bank_code',
    'exceeded_number_of_allowed_contracts',
    'invalid_image_format',
    'operation_not_allowed_IR',
    'wrong_bank_code_destination',
    'wrong_benefit_number_on_portability',
    'invalid_contract_total_amount',
]
