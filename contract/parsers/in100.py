from typing import Optional

from pydantic import BaseModel
from translate import Translator


class In100Benefit(BaseModel):
    """
    Model to validate and
    """

    key: str
    benefit_status: str
    name: str
    state: str
    birth_date: str
    type: str
    value: float
    liquid_value: float
    margin_value: float
    bank_account: str
    agency_number: str
    alimony_status: str
    has_judicial_concession: bool
    has_entity_representation: bool
    concession_date: str
    has_attorney: bool
    available_loan_amount: float
    benefit_quota_expiration_date: Optional[str]


def translate_text_to_uppercase(text: str, lang: str = 'pt') -> str:
    """
    Translates given word to
    Args:
        text: Text to be translated
        lang: Language translated return.

    Returns:
        str: Translated word in upper case
    """
    text = text.replace('_', ' ')
    return Translator(to_lang=lang).translate(text).upper()


def parse_in100_data(data: dict) -> In100Benefit:
    """
    Function to parse data in100 dict to In100Benefit object.

    Better than use lists in return
    Args:
        In100Benefit: In100Benefit object with specified fields

    Returns:

    """
    key = data.get('key', {})
    benefit_data = data.get('data', {})
    disbursement_bank_acount = benefit_data.get('disbursement_bank_account', {})

    return In100Benefit(
        key=key,
        benefit_status=translate_text_to_uppercase(data.get('status')),
        name=benefit_data.get('name'),
        state=benefit_data.get('state'),
        birth_date=benefit_data.get('birth_date'),
        type=benefit_data.get('assistance_type'),
        value=benefit_data.get('benefit_card', {}).get('balance'),
        liquid_value=benefit_data.get('benefit_card', {}).get('limit'),
        margin_value=benefit_data.get('consigned_credit', {}).get('balance'),
        bank_account=disbursement_bank_acount.get('bank_code'),
        agency_number=disbursement_bank_acount.get('account_branch'),
        alimony_status=translate_text_to_uppercase(benefit_data.get('alimony')),
        has_judicial_concession=benefit_data.get('has_judicial_concession'),
        has_entity_representation=benefit_data.get('has_entity_representation'),
        concession_date=benefit_data.get('grant_date'),
        has_attorney=benefit_data.get('has_power_of_attorney'),
        available_loan_amount=benefit_data.get('available_total_balance'),
        benefit_quota_expiration_date=benefit_data.get('benefit_quota_expiration_date'),
    )
