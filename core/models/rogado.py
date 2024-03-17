from django.db import models

from contract.constants import EnumGrauParentesco
from utils.models import SetUpModel
from utils.validators import CellphoneValidator
from django.core.validators import MinLengthValidator


class Rogado(SetUpModel):
    cliente = models.ForeignKey(
        to='Cliente',
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        related_name='rogados',
        null=True,
    )
    nome = models.CharField(max_length=255)
    cpf = models.CharField(max_length=11, validators=[MinLengthValidator(11)])
    data_nascimento = models.DateField()
    grau_parentesco = models.IntegerField(choices=EnumGrauParentesco.choices())
    telefone = models.CharField(
        max_length=11,
        verbose_name='Telefone',
        validators=[CellphoneValidator()],
    )

    class Meta:
        db_table = 'rogado'
        verbose_name = 'Rogado'
        verbose_name_plural = 'Rogados'

    def __str__(self):
        return self.nome
