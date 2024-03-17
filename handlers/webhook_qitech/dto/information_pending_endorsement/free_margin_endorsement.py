"""
This Python module defines the `FreeMarginEndorsementDTO` class, a Data Transfer Object (DTO)
for handling free margin endorsements in credit operations. It's specifically designed for
processing and validating collateral-related webhooks. The module structures the DTO to
accurately represent the expected JSON payload in a Pythonic format, ensuring that the incoming
data adheres to the expected schema and types.

The `FreeMarginEndorsementDTO` class includes attributes for the webhook type, a unique key for
the credit operation, the event time, and a detailed data structure for the collateral. Nested
classes within the main DTO class, such as `Data`, `CollateralData`, `LastResponse`, and `Error`,
further define the structure of the collateral data, including its type, constitution status,
reservation status, and any errors in the last response.

The module is essential for ensuring that the webhook data for credit operation endorsements
related to collateral is accurately captured and processed, facilitating the automation and
validation of credit operations in financial systems.

Example Payload for Reference:
{
  "webhook_type":"credit_operation.collateral",
  "key":"<CREDIT-OPERATION-KEY>",
  "event_time":"2022-11-24T15:42:12",
  "data":{
    "collateral_type":"social_security",
    "collateral_constituted":false,
    "collateral_data":{
      "status":"pending_reservation",
      "last_response":{
        "errors":[
          {
            "enumerator":"consignable_margin_excceded"
          }
        ]
      },
      "last_response_event_datetime":"2023-05-22T19:13:02Z",
      "reservation_method":"new_credit"
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
    status: Literal['pending_reservation']
    last_response: LastResponse
    last_response_event_datetime: datetime
    reservation_method: Literal['new_credit']


class Data(StrictBaseModel):
    collateral_type: Literal['social_security']
    collateral_constituted: bool
    collateral_data: CollateralData


class FreeMarginEndorsementDTO(StrictBaseModel):
    webhook_type: Literal['credit_operation.collateral']
    key: str
    event_time: datetime
    data: Data
