from django.db import models

from .enums import BPO


class CorbanTableOptions(models.IntegerChoices):
    APPROVE = 0, 'Aprovar'
    PENDING = 1, 'Análise Mesa'
    DISAPPROVE = 2, 'Reprovar'


class BPOOptions(models.IntegerChoices):
    SERASA = BPO.SERASA.value, 'Serasa'
