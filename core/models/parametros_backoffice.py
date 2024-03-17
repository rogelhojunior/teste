from django.db import models

from contract.choices import TIPOS_CONTRATO, TIPOS_PRODUTO
from contract.constants import EnumTipoContrato, EnumTipoProduto


class ParametrosBackoffice(models.Model):
    nome = models.CharField(verbose_name='Nome', max_length=300, null=True)
    tipoProduto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.FGTS,
    )
    tipoContrato = models.SmallIntegerField(
        verbose_name='Tipo de Contrato',
        choices=TIPOS_CONTRATO,
        default=EnumTipoContrato.PORTABILIDADE,
    )
    quantidade_contratos_por_cliente = models.SmallIntegerField(
        verbose_name='Quantidade de contratos por clientes', default=0
    )
    valor_tac = models.DecimalField(
        verbose_name='Valor Tac', decimal_places=7, max_digits=12, null=True, blank=True
    )
    limitacao_iof = models.DecimalField(
        verbose_name='Limitação de IOF', decimal_places=7, max_digits=12, null=True
    )
    taxa_iof_diario = models.DecimalField(
        verbose_name='Porcentagem IOF diário',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    taxa_iof_adicional = models.DecimalField(
        verbose_name='Porcentagem IOF adicional',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    taxa_iof_seguro = models.DecimalField(
        verbose_name=' Porcentagem  IOF + seguro',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    # valor_outros = models.DecimalField(verbose_name="Outros valores", decimal_places=7, max_digits=12, blank=True,
    #                                    default=0, null=True)
    url_formalizacao = models.CharField(
        verbose_name='URL para envio de formalização',
        null=True,
        blank=False,
        max_length=300,
        default='',
    )
    celulares_por_contrato = models.IntegerField(
        verbose_name='Número de telefones iguais permitidos por CPF',
        null=True,
        blank=False,
        default=2,
    )
    texto_sms_formalizacao = models.CharField(
        verbose_name='Texto SMS formalização',
        null=True,
        blank=False,
        max_length=70,
        help_text='Limite de caracteres limitado à 70 para envio do SMS.',
        default='',
    )
    enviar_comissionamento = models.BooleanField(
        verbose_name='Enviar para Comissionamento?', default=True
    )
    geolocalizacao_exigida = models.BooleanField(
        verbose_name='Geolocalização Exigida?', default=True
    )

    ativo = models.BooleanField(verbose_name='Ativo?', default=False)

    def __str__(self):
        return self.nome or ''

    @property
    def nome_(self):
        return f'{self.nome}'

    @property
    def valor_iof_adicional(self):
        return float(self.taxa_iof_adicional / 100)

    @property
    def valor_iof_diario(self):
        return float(self.taxa_iof_diario / 100)

    @property
    def valor_iof_seguro(self):
        return float(self.taxa_iof_seguro / 100)

    class Meta:
        verbose_name = '3. Parametro BackOffice'
        verbose_name_plural = '3. Parametros BackOffice'
