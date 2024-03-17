"""
This Python module defines the `PortabilityEndorsementDTO` class, a Data Transfer Object (DTO)
specifically created for handling portability endorsements in credit transfer proposals. The DTO
is structured to capture and validate incoming JSON data related to credit transfer proposals
that involve portability as the credit operation type.

The `PortabilityEndorsementDTO` class encompasses attributes to represent the webhook type, a
unique proposal key, the event's timestamp, and a detailed data structure about the credit
operation and its collateral. This data structure includes the type of credit operation, the
unique key of the credit operation, details about the collateral (type, constitution status, and
additional collateral data), and other relevant information.

Nested within the main class are other classes such as `WebhookData`, `CollateralData`,
`LastResponse`, and `ErrorInfo`, each defining specific aspects of the credit operation and
collateral details. These include the status of the collateral, any errors in the last response,
and the timestamp of the last response.

This module plays a crucial role in ensuring accurate data handling and validation for webhooks
related to portability endorsements in credit transfer proposals. It helps automate and validate
the process in financial systems, facilitating the management of credit operations involving
collateral.

Example Payload for Reference:
{
  "webhook_type": "credit_transfer.proposal.collateral",
  "proposal_key": "<PROPOSAL-KEY>",
  "event_datetime": "2022-11-24T15:42:12",
  "data": {
    "credit_operation_type": "portability",
    "credit_operation_key": "<CREDIT-OPERATION-KEY>",
    "collateral_type": "social_security",
    "collateral_constituted": false,
    "collateral_data": {
      "status": "pending_reservation",
      "last_response": {
        "errors": [{
          "enumerator": "consignable_margin_excceded"
        }]
      },
      "last_response_event_datetime": "2023-05-22T19:13:02Z",
      "reservation_method": "new_credit",
    }
  }
}
"""

from datetime import datetime
from typing import Literal

from pydantic import UUID4, conlist

from handlers.webhook_qitech.dto import WEBHOOK_ENDORSEMENT_ERRORS_TYPE
from handlers.webhook_qitech.dto.information_pending_endorsement import StrictBaseModel


class ErrorInfo(StrictBaseModel):
    enumerator: WEBHOOK_ENDORSEMENT_ERRORS_TYPE


class LastResponse(StrictBaseModel):
    errors: conlist(ErrorInfo, min_length=1)


class CollateralData(StrictBaseModel):
    status: Literal['pending_reservation']
    last_response: LastResponse
    last_response_event_datetime: datetime
    reservation_method: Literal['new_credit', 'portability', 'refinancing']


class WebhookData(StrictBaseModel):
    credit_operation_type: Literal['portability']
    credit_operation_key: str
    collateral_type: Literal['social_security']
    collateral_constituted: bool
    collateral_data: CollateralData


class PortabilityEndorsementDTO(StrictBaseModel):
    webhook_type: Literal['credit_transfer.proposal.collateral']
    proposal_key: UUID4
    event_datetime: datetime
    data: WebhookData

    def to_dict(self):
        self.model_dump()
