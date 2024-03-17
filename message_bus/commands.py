from enum import Enum


class EventCommands(Enum):
    """Enumeration of expected events that the SQS consumer can process."""

    SEND_FACE_MATCHED_RESPONSE = 'Send_face_matched_response'
    SEND_FACE_MATCHING_REQUEST = 'Send_face_match_request'
