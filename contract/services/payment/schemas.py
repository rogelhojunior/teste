from dataclasses import dataclass
from typing import Optional


@dataclass
class PaymentRequestDTO:
    cpf: str
    branch: str
    account_number: str
    account_type: int
    ispb: int
    value: float
    id_crontract: int
    name: str
    dock_id: Optional[str]
