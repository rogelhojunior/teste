from enum import Enum


class EnumStatusCCB(Enum):
    PENDING_SUBIMISSION = 0
    PENDING_RESPONSE = 1
    PENDING_ACCEPTANCE = 2
    ACCEPTED = 3
    CANCELED = 4
    RETAINED = 5
    SETTLEMENT_SENT = 6
    PENDING_SETTLMENTE_CONFIMATION = 7
    PAID = 8
    REJECTED = 9
    SIGNATURE_RECEIVED = 10
    COLLATERAL = 11
    GENERATING = 12
