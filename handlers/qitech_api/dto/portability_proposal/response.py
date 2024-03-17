from typing import List, Optional, Union

from pydantic import field_validator

from handlers.qitech_api.dto.portability_proposal import StrictBaseModel


class Address(StrictBaseModel):
    city: str
    complement: Optional[str] = None
    neighborhood: str
    number: str
    postal_code: str
    state: str
    street: str


class Phone(StrictBaseModel):
    area_code: str
    country_code: str
    number: str


class Borrower(StrictBaseModel):
    address: Address
    birth_date: str
    document_identification_date: str
    document_identification_number: str
    document_identification_type: str
    email: Optional[str] = None
    gender: str
    individual_document_number: str
    is_pep: bool
    marital_status: str
    mother_name: str
    name: str
    nationality: str
    person_type: str
    phone: Phone
    related_party_key: str
    role_type: str


class CollateralData(StrictBaseModel):
    benefit_number: int
    state: str


class Collateral(StrictBaseModel):
    collateral_data: CollateralData
    collateral_type: str


class OriginOperation(StrictBaseModel):
    contract_number: str
    ispb_number: str
    last_due_balance: float


class ContractFee(StrictBaseModel):
    amount: float
    amount_type: str
    fee_amount: float
    fee_type: str


class ExternalContractFee(StrictBaseModel):
    amount: float
    amount_released: float
    amount_type: str
    cofins_amount: int
    csll_amount: int
    description: Optional[str] = None
    fee_amount: float
    fee_type: str
    irrf_amount: int
    net_fee_amount: float
    pis_amount: int
    tax_amount: float


class Installment(StrictBaseModel):
    business_due_date: str
    calendar_days: int
    due_date: str
    due_principal: float
    installment_number: int
    pre_fixed_amount: float
    principal_amortization_amount: float
    total_amount: float
    workdays: int


class PrefixedInterestRate(StrictBaseModel):
    annual_rate: float
    daily_rate: float
    interest_base: str
    monthly_rate: float


class DisbursementOption(StrictBaseModel):
    annual_cet: float
    cet: float
    contract_fee_amount: float
    contract_fees: List[ContractFee]
    disbursed_issue_amount: float
    disbursement_date: str
    external_contract_fee_amount: float
    external_contract_fees: List[ExternalContractFee]
    installments: List[Installment]
    issue_amount: float
    number_of_installments: int
    prefixed_interest_rate: PrefixedInterestRate
    total_iof: float


class PortabilityCreditOperation(StrictBaseModel):
    collateral_is_constituted: bool
    contract_number: Union[str, int]  # BYX0000000001
    credit_operation_key: str
    credit_operation_status: str
    disbursement_accounts: List
    disbursement_options: List[DisbursementOption]
    document_key: str
    document_url: str
    final_disbursement_amount: float
    signed_url: Optional[str] = None

    @field_validator('contract_number')
    @classmethod
    def format_contract_number(cls, value):
        if isinstance(value, str) and value.startswith('BYX'):
            return int(value[3:])
        elif isinstance(value, (str, int)):
            return value
        raise ValueError('Invalid format for contract_number')


class PortabilityProposalDTO(StrictBaseModel):
    borrower: Borrower
    collaterals: List[Collateral]
    origin_operation: OriginOperation
    portability_credit_operation: PortabilityCreditOperation
    proposal_key: str
    proposal_number: str
    proposal_status: str

    def to_dict(self):
        return self.model_dump()
