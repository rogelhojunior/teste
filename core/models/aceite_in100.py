from django.db import models

from contract.choices import TIPOS_PRODUTO
from contract.constants import EnumTipoProduto
from core.choices import CANAL_AUTORIZACAO_DIGITAL
from core.constants import EnumCanalAutorizacaoDigital
from handlers.aws_boto3 import Boto3Manager


class AceiteIN100(models.Model):
    nome_cliente = models.CharField(
        max_length=100, verbose_name='Nome do Cliente', null=True, blank=True
    )
    cpf_cliente = models.CharField(
        max_length=100, verbose_name='CPF', null=True, blank=False
    )
    canal = models.IntegerField(
        verbose_name='Canal',
        choices=CANAL_AUTORIZACAO_DIGITAL,
        default=EnumCanalAutorizacaoDigital.DIGITAL_VIA_CORRESPONDENTE,
    )
    hash_assinatura = models.CharField(
        max_length=100, verbose_name='Hash da Assinatura', null=True, blank=False
    )
    data_aceite = models.DateField(
        verbose_name='Data aceite', auto_now_add=True, blank=True, null=True
    )
    data_vencimento_aceite = models.DateField(
        verbose_name='Data de vencimento do aceite', null=True, blank=False
    )
    token_in100 = models.CharField(
        max_length=500, verbose_name='Token IN100', null=True, blank=False
    )
    data_criacao_token = models.DateField(
        verbose_name='Data de criação do Token', null=True, blank=False
    )
    data_vencimento_token = models.DateField(
        verbose_name='Data de vencimento do Token', null=True, blank=False
    )

    cbc_if_pagadora = models.IntegerField(
        verbose_name='cbcIfPagadora', null=True, blank=True
    )
    agencia_pagadora = models.IntegerField(
        verbose_name='agenciaPagadora', null=True, blank=True
    )
    conta_corrente = models.CharField(
        verbose_name='contaCorrente', null=True, blank=True, max_length=255
    )
    UFAPS = models.CharField(
        verbose_name='ufPagamento', null=True, blank=True, max_length=255
    )
    DV_conta_corrente = models.CharField(
        verbose_name='DVContaCorrente', null=True, blank=True, max_length=255
    )
    produto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.CARTAO_BENEFICIO,
    )

    def __str__(self):
        return self.cpf_cliente or ''

    @property
    def nome_(self):
        return f'{self.cpf_cliente}'

    class Meta:
        verbose_name = 'Aceite IN100'
        verbose_name_plural = '6. Aceite IN100'


class DocumentoAceiteIN100(models.Model):
    aceite_in100 = models.ForeignKey(
        AceiteIN100,
        max_length=100,
        verbose_name='Aceite IN100',
        blank=False,
        on_delete=models.CASCADE,
    )
    nome_anexo = models.CharField(verbose_name='Nome do anexo', max_length=300)
    anexo_url = models.URLField(
        verbose_name='URL do documento', max_length=500, null=True, blank=True
    )
    criado_em = models.DateField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return self.aceite_in100.cpf_cliente or ''

    @property
    def nome_(self):
        return f'{self.aceite_in100.cpf_cliente}'

    @property
    def get_attachment_url(self) -> str:
        boto3_manager = Boto3Manager()
        return boto3_manager.get_url_with_new_expiration(self.anexo_url)

    class Meta:
        verbose_name = 'Documento Aceite'
        verbose_name_plural = 'Documento Aceite'


class HistoricoAceiteIN100(models.Model):
    aceite_original = models.ForeignKey(
        AceiteIN100, verbose_name='Aceite Original', on_delete=models.CASCADE
    )
    canal = models.IntegerField(
        verbose_name='Canal',
        choices=CANAL_AUTORIZACAO_DIGITAL,
        default=EnumCanalAutorizacaoDigital.DIGITAL_VIA_CORRESPONDENTE,
    )
    hash_assinatura = models.CharField(
        max_length=100, verbose_name='Hash da Assinatura', null=True, blank=False
    )
    data_aceite = models.DateField(verbose_name='Data aceite', blank=True, null=True)
    data_vencimento_aceite = models.DateField(
        verbose_name='Data de vencimento do aceite', null=True, blank=False
    )
    produto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.CARTAO_BENEFICIO,
    )

    class Meta:
        verbose_name = 'Histórico de Aceite'
        verbose_name_plural = 'Históricos de Aceite'


class DadosBeneficioIN100(models.Model):
    aceite = models.ForeignKey(
        AceiteIN100, verbose_name='Aceite', on_delete=models.CASCADE
    )
    numero_beneficio = models.CharField(
        max_length=100, verbose_name='Numero Benefício', null=True, blank=False
    )
    cpf = models.CharField(max_length=11, verbose_name='CPF', null=True, blank=False)
    nome_beneficiario = models.CharField(
        max_length=255, verbose_name='Nome Beneficiario', null=True, blank=False
    )
    codigo_situacao_beneficio = models.IntegerField(
        verbose_name='Código Situação Benefício', null=True, blank=False
    )
    descricao_situacao_beneficio = models.CharField(
        max_length=255,
        verbose_name='Descrição Situação Benefício',
        null=True,
        blank=False,
    )
    codigo_especie_beneficio = models.IntegerField(
        verbose_name='Código Espécie Benefício', null=True, blank=False
    )
    descricao_especie_beneficio = models.CharField(
        max_length=255,
        verbose_name='Descrição Espécie Benefício',
        null=True,
        blank=False,
    )
    concessao_judicial = models.BooleanField(verbose_name='Concessão Judicial')
    uf_pagamento = models.CharField(
        max_length=2, verbose_name='UF Pagamento', null=True, blank=False
    )
    codigo_tipo_credito = models.IntegerField(
        verbose_name='Código Tipo Crédito', null=True, blank=False
    )
    descricao_tipo_credito = models.CharField(
        max_length=255, verbose_name='Descrição Tipo Crédito', null=True, blank=False
    )
    cbc_if_pagadora = models.IntegerField(
        verbose_name='CBC IF Pagadora', null=True, blank=False
    )
    agencia_pagadora = models.IntegerField(
        verbose_name='Agência Pagadora', null=True, blank=False
    )
    conta_corrente = models.CharField(
        max_length=20, verbose_name='Conta Corrente', null=True, blank=False
    )
    possui_representante_legal = models.BooleanField(
        verbose_name='Possui Representante Legal'
    )
    possui_procurador = models.BooleanField(verbose_name='Possui Procurador')
    possui_entidade_representacao = models.BooleanField(
        verbose_name='Possui Entidade Representação'
    )
    codigo_pensao_alimenticia = models.IntegerField(
        verbose_name='Código Pensão Alimentícia', null=True, blank=False
    )
    descricao_pensao_alimenticia = models.CharField(
        max_length=255,
        verbose_name='Descrição Pensão Alimentícia',
        null=True,
        blank=False,
    )
    bloqueado_para_emprestimo = models.BooleanField(
        verbose_name='Bloqueado Para Empréstimo'
    )
    margem_disponivel = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Margem Disponível'
    )
    margem_disponivel_cartao = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Margem Disponível Cartão'
    )
    valor_limite_cartao = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Valor Limite Cartão'
    )
    qtd_emprestimos_ativos_suspensos = models.IntegerField(
        verbose_name='Qtd. Empréstimos Ativos Suspensos'
    )
    qtd_emprestimos_ativos = models.IntegerField(verbose_name='Qtd. Empréstimos Ativos')
    qtd_emprestimos_suspensos = models.IntegerField(
        verbose_name='Qtd. Empréstimos Suspensos'
    )
    qtd_emprestimos_refin = models.IntegerField(verbose_name='Qtd. Empréstimos Refin')
    qtd_emprestimos_porta = models.IntegerField(verbose_name='Qtd. Empréstimos Porta')
    data_consulta = models.DateField(verbose_name='Data Consulta')
    elegivel_emprestimo = models.BooleanField(verbose_name='Elegível Empréstimo')
    margem_disponivel_rcc = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Margem Disponível RCC'
    )
    valor_limite_rcc = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Valor Limite RCC'
    )
    valor_liquido = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Valor Líquido'
    )
    valor_comprometido = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Valor Comprometido'
    )
    valor_maximo_comprometimento = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Valor Máximo Comprometimento'
    )

    class Meta:
        verbose_name = 'Dado Benefício'
        verbose_name_plural = 'Dados Benefício'
