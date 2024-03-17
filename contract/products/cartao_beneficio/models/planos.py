from ckeditor.fields import RichTextField
from django.db import models
from django.db.models import ProtectedError

from contract.choices import TIPOS_ARQUVIOS, TIPOS_PLANO

BOOL_CHOICES = (
    (1, 'SIM'),
    (0, 'NÃO'),
)


class Planos(models.Model):
    nome = models.CharField(verbose_name='Nome do plano', max_length=300, null=True)
    tipo_plano = models.SmallIntegerField(
        verbose_name='Tipo de Plano', choices=TIPOS_PLANO, blank=False, null=True
    )
    tipo_termo = models.SmallIntegerField(
        verbose_name='Tipo de Termo', choices=TIPOS_ARQUVIOS, blank=True, null=True
    )
    seguradora = models.ForeignKey(
        'cartao_beneficio.Seguradoras',
        on_delete=models.SET_NULL,
        verbose_name='Seguradora',
        null=True,
        blank=True,
    )
    codigo_plano = models.CharField(
        verbose_name='Código do Plano', max_length=300, null=True, blank=True
    )
    codigo_sucursal = models.CharField(
        verbose_name='Código Sucursal', max_length=300, null=True, blank=True
    )
    codigo_ramo = models.CharField(
        verbose_name='Código Ramo', max_length=300, null=True, blank=True
    )
    codigo_operacao = models.CharField(
        verbose_name='Código de Operação', max_length=300, null=True, blank=True
    )
    codigo_produto = models.CharField(
        verbose_name='Código do Produto', max_length=300, null=True, blank=True
    )
    apolice = models.CharField(
        verbose_name='Apólice', max_length=300, null=True, blank=True
    )
    carencia = models.IntegerField(
        verbose_name='Carência (dias)', null=True, blank=True
    )

    iof = models.DecimalField(
        verbose_name='IOF (%)',
        decimal_places=2,
        max_digits=12,
        blank=True,
        null=True,
        default=0,
    )
    valor_segurado = models.CharField(
        verbose_name='Valor Segurado (R$)',
        max_length=12,
        blank=True,
        null=True,
        default=0,
    )
    porcentagem_premio = models.DecimalField(
        verbose_name='Porcentagem do prémio BRUTO com base no limite do cartão',
        decimal_places=2,
        max_digits=12,
        blank=True,
        null=True,
        default=0,
    )
    porcentagem_premio_liquido = models.DecimalField(
        verbose_name='Porcentagem do prémio LIQUIDO com base no limite do cartão',
        decimal_places=2,
        max_digits=12,
        blank=True,
        null=True,
        default=0,
    )
    quantidade_parcelas = models.IntegerField(
        verbose_name='Quantidade de Parcelas',
        blank=True,
        null=True,
        default=0,
    )
    renovacao_automatica = models.IntegerField(
        verbose_name='Renovação Automática?', choices=BOOL_CHOICES, default=None
    )
    possui_termo_contratacao = models.IntegerField(
        verbose_name='Possui termo de contratação?', choices=BOOL_CHOICES, default=None
    )
    descricao_plano = RichTextField(
        verbose_name='Detalhes',
        null=True,
        blank=True,
    )
    obrigatorio = models.IntegerField(
        verbose_name='Plano obrigatório?', choices=BOOL_CHOICES, default=None
    )
    gratuito = models.IntegerField(
        verbose_name='Plano gratuito?', choices=BOOL_CHOICES, default=None
    )
    ativo = models.BooleanField(verbose_name='Ativo?', default=False)

    def __str__(self):
        return f'{str(self.pk)}-{self.nome}' or ''

    def get_tipo_plano_display(self):
        return dict(TIPOS_PLANO).get(self.tipo_plano)

    @property
    def get_renovacao_automatica(self):
        return bool(self.renovacao_automatica)

    @property
    def get_possui_termo_contratacao(self):
        return bool(self.possui_termo_contratacao)

    @property
    def get_obrigatorio(self):
        return bool(self.obrigatorio)

    def delete(self, *args, **kwargs):
        if self.contrato_planos.exists():
            raise ProtectedError(
                'Este plano está relacionado a um ou mais contrato e não pode ser deletado.',
                self.contrato_planos.all(),
            )
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = '2. Parâmetros - Plano'
        verbose_name_plural = '2. Parâmetros - Planos'


class PlanosContrato(models.Model):
    contrato = models.ForeignKey(
        'contract.Contrato',
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_planos_contratados',
    )
    plano = models.ForeignKey(
        'cartao_beneficio.Planos',
        verbose_name='Plano',
        related_name='plano_contrato_contratado',
        blank=True,
        on_delete=models.CASCADE,
    )
    valor_plano = models.DecimalField(
        verbose_name='Valor pago cliente (R$)',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    numero_sorte = models.CharField(
        verbose_name='Numero de sorteio seguro',
        max_length=12,
        blank=True,
        null=True,
        default=0,
    )

    class Meta:
        verbose_name = 'Plano'
        verbose_name_plural = 'Planos'
