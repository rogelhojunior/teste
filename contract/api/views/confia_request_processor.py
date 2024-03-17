"""This module implements the class ConfiaRequestProcessor."""

# local
from contract.models.envelope_contratos import EnvelopeContratos

from .unico_request_processor import UnicoRequestProcessor

# constants
CONFIA_RULE_DESCRIPTION = 'Regra Score CONFIA'


class ConfiaRequestProcessor(UnicoRequestProcessor):
    """
    This class abstracts the request incoming fro Confia, containing the
    status and score data.

    Attributes:
        request (rest_framework.request.Request): the incoming request.
        data (dict): the serialized data inside the request.
        envelope (EnvelopeContratos): the envelope referred by data.id
            keys inside incoming request data.
    """

    def get_envelope(self) -> EnvelopeContratos:
        """Get envelope using property id_processo"""
        return EnvelopeContratos.objects.get(id_processo_confia=self.id_processo)
