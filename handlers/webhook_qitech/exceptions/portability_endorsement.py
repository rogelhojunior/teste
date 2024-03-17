from handlers.webhook_qitech.dto import WEBHOOK_ENDORSEMENT_ERRORS_TYPE


class PortabilityProposalNotValidException(Exception):
    def __init__(self, endorsement_error_type: WEBHOOK_ENDORSEMENT_ERRORS_TYPE):
        self.message: str = (
            f'Portability proposal status {endorsement_error_type} not valid.'
        )
        super().__init__(self.message)
