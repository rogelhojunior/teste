class PendingRatioNotSupportedException(Exception):
    def __init__(self, endorsement_error_type: str):
        self.message = f'Pending reason "{endorsement_error_type}" is not valid for internal treatment.'
        self.endorsement_error_type: str = endorsement_error_type
        super().__init__(self.message)
