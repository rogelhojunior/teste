"""This module implements function insert_portability_proposal"""

# third party imports
from logging import getLogger

from celery import shared_task

# local imports
from .qitech_proposal_inserter import QiTechProposalInserter

logger = getLogger(__name__)


@shared_task
def insert_portability_proposal(contract_token):
    """Submit a new proposal to Qi Tech financial and include the CCB
    provided by them in the contract attachments in our database."""
    try:
        QiTechProposalInserter(contract_token).insert_proposal()
    except Exception:
        logger.exception('Someting wrong with insert_portability_proposal')
