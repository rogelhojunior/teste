"""
This Python module defines the `RefinancingEndorsementDTO` class, a Data Transfer Object (DTO)
intended for handling refinancing endorsements in credit operations. The DTO is tailored to
accurately process and validate JSON payloads specific to refinancing scenarios involving
collateral.

The `RefinancingEndorsementDTO` class includes attributes for identifying the webhook type, a
unique key for the credit operation, the event timestamp, and detailed data about the collateral
involved in the refinancing operation. This data comprises the collateral type, its constitution
status, and extensive collateral data, such as status, last response, and reservation method.

Nested within are classes like `WebhookData`, `CollateralData`, `LastResponse`, and `ErrorInfo`.
These classes provide a structured representation of the collateral details, including its status,
any errors in the last response, and the timestamp of the last response event. The `CollateralData`
class specifically handles the reservation method set to 'refinancing', marking the unique nature
of these credit operations.

This module is crucial in ensuring the efficient and accurate processing of refinancing-related
webhooks in credit operations. It aids in automating and validating the refinancing process in
financial systems, particularly in managing the complexities associated with collateral in
refinancing scenarios.

Example Payload for Reference:
{
  "webhook_type": "credit_operation.collateral",
  "key": "<CREDIT-OPERATION-KEY>",
  "event_time": "2022-11-24T15:42:12",
  "data": {
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
      "reservation_method": "refinancing",
    }
  }
}
"""

from datetime import datetime
from typing import Literal

from pydantic import conlist

from handlers.webhook_qitech.dto import WEBHOOK_ENDORSEMENT_ERRORS_TYPE
from handlers.webhook_qitech.dto.information_pending_endorsement import StrictBaseModel


class ErrorInfo(StrictBaseModel):
    enumerator: WEBHOOK_ENDORSEMENT_ERRORS_TYPE


class LastResponse(StrictBaseModel):
    errors: conlist(ErrorInfo, min_length=1)


class CollateralData(StrictBaseModel):
    status: str
    last_response: LastResponse
    last_response_event_datetime: datetime
    reservation_method: Literal['refinancing']


class WebhookData(StrictBaseModel):
    collateral_type: str
    collateral_constituted: bool
    collateral_data: CollateralData


class RefinancingEndorsementDTO(StrictBaseModel):
    webhook_type: Literal['credit_operation.collateral']
    key: str
    event_time: datetime
    data: WebhookData

    def to_dict(self):
        return self.model_dump()
