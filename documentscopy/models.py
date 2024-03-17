from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from contract.choices import TIPOS_PRODUTO
from contract.constants import EnumTipoProduto
from contract.products.cartao_beneficio.models.convenio import Convenios
from core.choices import UFS
from core.constants import EnumGrauCorban, EnumUF
from custom_auth.models import Corban

from .choices import BPOOptions, CorbanTableOptions


class UF(models.Model):
    uf = models.SmallIntegerField(
        verbose_name='UF',
        choices=UFS,
        default=EnumUF.AC,
        unique=True,
    )

    def __str__(self):
        return self.get_uf_display()


class Product(models.Model):
    product = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.FGTS,
        unique=True,
    )

    def __str__(self):
        return self.get_product_display()


class ParameterBase(models.Model):
    products = models.ManyToManyField(Product, verbose_name='Produtos')
    entities = models.ManyToManyField(Convenios, verbose_name='Entidades', blank=True)
    corbans = models.ManyToManyField(
        Corban,
        related_name='%(app_label)s_%(class)s_corbans',
        limit_choices_to={'corban_type': EnumGrauCorban.CORBAN_MASTER},
        blank=True,
    )
    stores = models.ManyToManyField(
        Corban,
        related_name='%(app_label)s_%(class)s_stores',
        verbose_name='Lojas',
        blank=True,
    )

    class Meta:
        abstract = True


class UnicoParameterFaceMatch(models.Model):
    # TODO Refactor to RangeField when move to Postgres
    score_from = models.DecimalField(
        verbose_name='De',
        max_digits=5,
        decimal_places=2,
        validators=[MaxValueValidator(1000)],
    )
    score_to = models.DecimalField(
        verbose_name='Até',
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(-99.9), MaxValueValidator(1000)],
    )
    corban_action = models.IntegerField(
        verbose_name='Ação',
        default=CorbanTableOptions.APPROVE,
        choices=CorbanTableOptions.choices,
    )
    parameter = models.ForeignKey(
        'documentscopy.UnicoParameter',
        verbose_name='Parametro',
        on_delete=models.CASCADE,
        null=True,
    )

    class Meta:
        verbose_name = 'Biometria Facial'
        verbose_name_plural = 'Biometria Facial'


class UnicoParameter(ParameterBase):
    class Meta:
        verbose_name = 'Parametro Unico'
        verbose_name_plural = 'Parametro Unico'


class BPORow(models.Model):
    bpo = models.IntegerField(
        verbose_name='BPO',
        default=BPOOptions.SERASA,
        choices=BPOOptions.choices,
    )

    # TODO Refactor to RangeField when move to Postgres
    amount_from = models.DecimalField(
        verbose_name='R$ Inicial',
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    amount_to = models.DecimalField(
        verbose_name='R$ Final',
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    parameter = models.ForeignKey(
        'documentscopy.BPOConfig',
        verbose_name='Parametro',
        on_delete=models.CASCADE,
        null=True,
    )

    class Meta:
        verbose_name = 'BPOs'
        verbose_name_plural = 'BPOs'


class BPOConfig(ParameterBase):
    # TODO Refactor to RangeField when move to Postgres
    age_from = models.IntegerField(verbose_name='Idade - Mínima', null=True, blank=True)
    age_to = models.IntegerField(verbose_name='Idade - Máxima', null=True, blank=True)

    # TODO Refactor to RangeField when move to Postgres
    score_from = models.IntegerField(
        verbose_name='Score - Mínimo', null=True, blank=True
    )
    score_to = models.IntegerField(verbose_name='Score - Máximo', null=True, blank=True)

    ufs = models.ManyToManyField(UF, verbose_name='UFs', blank=True)

    class Meta:
        verbose_name = 'Distribuidor de BPOs'
        verbose_name_plural = 'Distribuidor de BPOs'


class SerasaProtocol(models.Model):
    cpf = models.CharField(max_length=11, verbose_name='CPF', null=True, blank=False)
    contract = models.ForeignKey(
        'contract.Contrato',
        verbose_name='Contrato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='serasa_protocol_contract',
    )
    protocol = models.CharField(
        max_length=11, verbose_name='Protocolo BRFlow', null=True, blank=False
    )
    result = models.CharField(
        max_length=200, verbose_name='Resultado', null=True, blank=False
    )
    processed = models.BooleanField(default=False)


class MostProtocol(models.Model):
    cpf = models.CharField(max_length=14, verbose_name='CPF', null=True, blank=False)
    contract = models.ForeignKey(
        'contract.Contrato',
        verbose_name='Contrato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='most_protocol_contract',
    )
    protocol = models.CharField(
        max_length=50, verbose_name='Protocolo MOST', null=True, blank=False
    )
    result = models.CharField(
        max_length=200, verbose_name='Resultado', null=True, blank=False
    )
    processed = models.BooleanField(default=False)
