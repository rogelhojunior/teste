from api_log.constants import EnumStatusCCB

STATUS_CCB = (
    (EnumStatusCCB.PENDING_SUBIMISSION.value, 'pending_subimission'),
    (EnumStatusCCB.PENDING_RESPONSE.value, 'pending_response'),
    (EnumStatusCCB.PENDING_ACCEPTANCE.value, 'pending_acceptance'),
    (EnumStatusCCB.ACCEPTED.value, 'accepted'),
    (EnumStatusCCB.CANCELED.value, 'canceled'),
    (EnumStatusCCB.RETAINED.value, 'retained'),
    (EnumStatusCCB.SETTLEMENT_SENT.value, 'settlement_sent'),
    (
        EnumStatusCCB.PENDING_SETTLMENTE_CONFIMATION.value,
        'pending_settlement_confirmation',
    ),
    (EnumStatusCCB.PAID.value, 'paid'),
    (EnumStatusCCB.REJECTED.value, ' rejected'),
    (EnumStatusCCB.SIGNATURE_RECEIVED.value, ' signature_received'),
)
