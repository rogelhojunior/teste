from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from contract.choices import TIPOS_PRODUTO
from contract.constants import EnumTipoProduto


class ParametrosProduto(models.Model):
    tipoProduto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.FGTS,
    )
    cet_mes = models.DecimalField(
        verbose_name='CET mês', decimal_places=2, max_digits=12, null=True, blank=True
    )
    cet_ano = models.DecimalField(
        verbose_name='CET ano', decimal_places=2, max_digits=12, null=True, blank=True
    )
    valor_tac = models.DecimalField(
        verbose_name='TAC', decimal_places=2, max_digits=12, null=True, blank=True
    )
    taxa_minima = models.DecimalField(
        verbose_name='Taxa Minima',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    taxa_maxima = models.DecimalField(
        verbose_name='Taxa Maxima',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    teto_inss = models.DecimalField(
        verbose_name='Taxa teto INSS',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
        help_text='Utilizado apenas em Port+Refin',
    )

    taxa_minima_recalculo = models.DecimalField(
        verbose_name='Taxa minima do recálculo',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    valor_minimo_parcela = models.DecimalField(
        verbose_name='Valor Mínimo da Parcela',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_maximo_parcela = models.DecimalField(
        verbose_name='Valor Máximo da Parcela',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    valor_minimo_emprestimo = models.DecimalField(
        verbose_name='Valor Mínimo do Emprestimo',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    valor_maximo_emprestimo = models.DecimalField(
        verbose_name='Valor Máximo do Emprestimo',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    quantidade_minima_parcelas = models.IntegerField(
        verbose_name='Quantidade Mínima de Parcelas', null=True, blank=True
    )

    quantidade_maxima_parcelas = models.IntegerField(
        verbose_name='Quantidade Máxima de Parcelas', null=True, blank=True
    )

    idade_minima = models.IntegerField(
        verbose_name='Idade Mínima', null=True, blank=True
    )
    idade_maxima = models.IntegerField(
        verbose_name='Idade Máxima', null=True, blank=True
    )
    valor_de_seguranca_proposta = models.DecimalField(
        verbose_name='Valor de Segurança da Proposta',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    dias_limite_para_desembolso = models.IntegerField(
        verbose_name='Dias Limite Para Desembolso', null=True, blank=True
    )
    valor_minimo_parcela_simulacao = models.DecimalField(
        verbose_name='Valor Mínimo da Parcela',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    quantidade_dias_uteis_base_simulacao = models.IntegerField(
        verbose_name='Quantidade de Dias Úteis Base Para Simulação',
        null=True,
        blank=True,
    )
    meses_para_adicionar_quando_dias_uteis_menor_igual_base = models.IntegerField(
        verbose_name='Meses Para Adicionar Quando A Quantidade de Dias Úteis for Menor ou Igual a Base',
        null=True,
        blank=True,
    )
    meses_para_adicionar_quando_dias_uteis_maior_base = models.IntegerField(
        verbose_name='Meses Para Adicionar Quando A Quantidade de Dias Úteis for Maior que a Base',
        null=True,
        blank=True,
    )
    dia_vencimento_padrao_simulacao = models.IntegerField(
        verbose_name='Dia de Vencimento Padrão Para a Simulação', null=True, blank=True
    )
    valor_liberado_cliente_operacao_min = models.DecimalField(
        verbose_name='Valor Mínimo Operação Liberado Para o Cliente',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_liberado_cliente_operacao_max = models.DecimalField(
        verbose_name='Valor Máximo Operação Liberado Para o Cliente',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_minimo_margem = models.DecimalField(
        verbose_name='Valor minimo da margem',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    data_inicio_vencimento = models.IntegerField(
        verbose_name='Data Vencimento QITECH',
        null=True,
        blank=True,
        help_text='Dia do primeiro vencimento QITECH',
    )
    prazo_maximo = models.IntegerField(
        verbose_name='Prazo maximo da proposta',
        null=True,
        blank=True,
        help_text='Valor em meses',
    )
    prazo_minimo = models.IntegerField(
        verbose_name='Prazo minimo da proposta',
        null=True,
        blank=True,
        help_text='Valor em meses',
    )
    idade_especie_87 = models.IntegerField(
        verbose_name='Idade maxima da Especie 87',
        null=True,
        blank=True,
        help_text='Valor em anos',
    )
    aprovar_automatico = models.BooleanField(
        verbose_name='Aprovação Automática de Contratos?', default=False
    )
    taxa_proposta_margem_livre = models.DecimalField(
        verbose_name='Taxa da proposta de margem livre',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
        help_text='Taxa em %',
    )
    multa_contrato_margem_livre = models.DecimalField(
        verbose_name='Multa do contrato de margem livre',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
        help_text='Multa em %',
    )

    valor_troco_minimo = models.DecimalField(
        verbose_name='Valor do Troco Mínimo',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )

    percentual_maximo_aprovacao = models.DecimalField(
        verbose_name='Aprovação - Até:',
        decimal_places=2,
        max_digits=5,
        null=True,
        blank=True,
    )

    percentual_maximo_pendencia = models.DecimalField(
        verbose_name='Pendência Corban - Até:',
        decimal_places=2,
        max_digits=5,
        null=True,
        blank=True,
    )

    percentual_variacao_troco_recalculo = models.DecimalField(
        verbose_name='Percentual de Variação do Troco para o Recálculo',
        help_text='Valor de 0 a 100 (%)',
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
        decimal_places=2,
        max_digits=5,
        null=True,
        blank=True,
    )

    permite_oferta_cartao_inss = models.BooleanField(
        verbose_name='Permite oferta de Cartão INSS', default=False
    )

    class Meta:
        verbose_name = '4. Parametro Produto'
        verbose_name_plural = '4. Parametros Produtos'

    def __str__(self):
        if int(self.tipoProduto) == EnumTipoProduto.FGTS:
            return 'FGTS'
        if int(self.tipoProduto) == EnumTipoProduto.INSS_REPRESENTANTE_LEGAL:
            return 'INSS_REPRESENTANTE_LEGAL'
        if int(self.tipoProduto) == EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE:
            return 'CARTAO_BENEFICIO_REPRESENTANTE'
        if int(self.tipoProduto) == EnumTipoProduto.PAB:
            return 'PAB'
        if int(self.tipoProduto) == EnumTipoProduto.INSS_CORBAN:
            return 'INSS_CORBAN'
        if int(self.tipoProduto) == EnumTipoProduto.INSS:
            return 'INSS'
        if int(self.tipoProduto) == EnumTipoProduto.CARTAO_BENEFICIO:
            return 'CARTAO_BENEFICIO'
        if int(self.tipoProduto) == EnumTipoProduto.CARTAO_CONSIGNADO:
            return 'CARTAO_CONSIGNADO'
        if int(self.tipoProduto) == EnumTipoProduto.SIAPE:
            return 'SIAPE'
        if int(self.tipoProduto) == EnumTipoProduto.EXERCITO:
            return 'EXERCITO'
        if int(self.tipoProduto) == EnumTipoProduto.MARINHA:
            return 'MARINHA'
        if int(self.tipoProduto) == EnumTipoProduto.AERONAUTICA:
            return 'AERONAUTICA'
        if int(self.tipoProduto) == EnumTipoProduto.PORTABILIDADE:
            return 'PORTABILIDADE'
        if int(self.tipoProduto) == EnumTipoProduto.CONSIGNADO:
            return 'CONSIGNADO'
        if int(self.tipoProduto) == EnumTipoProduto.MARGEM_LIVRE:
            return 'MARGEM_LIVRE'
        if int(self.tipoProduto) == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            return 'PORTABILIDADE_REFINANCIAMENTO'
