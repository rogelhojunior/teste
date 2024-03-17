from django.core.validators import MinLengthValidator

from utils.models import SetUpModel
from django.db import models

from utils.validators import CellphoneValidator


class Testemunha(SetUpModel):
    cliente = models.ForeignKey(
        to='Cliente',
        verbose_name='Cliente',
        on_delete=models.PROTECT,
        related_name='testemunhas',
    )

    contratos = models.ManyToManyField(
        to='contract.Contrato',
        verbose_name='Contrato',
        related_name='testemunhas',
    )

    nome = models.CharField(max_length=255)
    cpf = models.CharField(max_length=11, validators=[MinLengthValidator(11)])
    data_nascimento = models.DateField()
    telefone = models.CharField(
        max_length=11,
        verbose_name='Telefone',
        validators=[CellphoneValidator()],
    )

    class Meta:
        db_table = 'testemunha'
        verbose_name = 'Testemunha'
        verbose_name_plural = 'Testemunhas'

    def __str__(self):
        return self.nome
