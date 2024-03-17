"""This class implements classes related to Cliente model."""

# imports
import logging
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# local imports
from contract.choices import TIPO_VINCULO_SIAPE, TIPOS_MARGEM, TIPOS_PRODUTO
from contract.constants import EnumTipoProduto, EnumEscolaridade
from contract.products.cartao_beneficio.models.convenio import Convenios
from core.utils import import_module_by_path

from ..choices import (
    TIPOS_CLIENTE,
    TIPOS_CONTA,
    TIPOS_DOCUMENTO,
    TIPOS_PAGAMENTO,
    TIPOS_RESIDENCIA,
    UFS,
)
from ..constants import EnumTipoCliente

logger = logging.getLogger('digitacao')


class Cliente(models.Model):
    id_unico = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, verbose_name='ID Único'
    )
    id_confia = models.UUIDField(
        editable=False, unique=True, verbose_name='ID Confia', null=True, blank=True
    )
    tipo_cliente = models.SmallIntegerField(
        verbose_name='Tipo', choices=TIPOS_CLIENTE, default=EnumTipoCliente.CLIENTE
    )
    nome_cliente = models.CharField(
        verbose_name='Nome do cliente', max_length=200, blank=False, null=False
    )
    nu_cpf = models.CharField(
        verbose_name='Número CPF do cliente', max_length=14, null=True, blank=True
    )
    dt_nascimento = models.DateField(
        verbose_name='Data de nascimento', null=True, blank=True
    )
    sexo = models.CharField(
        verbose_name='Sexo do cliente', max_length=50, null=True, blank=True
    )
    estado_civil = models.CharField(
        verbose_name='Estado civil', max_length=50, null=True, blank=True
    )
    nome_mae = models.CharField(
        verbose_name='Nome da mãe do cliente', max_length=200, null=True, blank=True
    )
    nome_pai = models.CharField(
        verbose_name='Nome do Pai do cliente', max_length=200, null=True, blank=True
    )

    # DOCUMENTACAO
    documento_tipo = models.SmallIntegerField(
        verbose_name='Tipo de documento', choices=TIPOS_DOCUMENTO, null=True, blank=True
    )
    documento_numero = models.CharField(
        verbose_name='Número do documento do cliente',
        max_length=20,
        null=True,
        blank=True,
        help_text='Número do documento selecionado acima',
    )
    documento_data_emissao = models.DateField(
        verbose_name='Data de emissão do documento',
        null=True,
        blank=True,
    )
    documento_orgao_emissor = models.CharField(
        verbose_name='Órgão emissor do documento',
        max_length=10,
        null=True,
        blank=True,
    )
    documento_uf = models.SmallIntegerField(
        verbose_name='UF de emissão do documento', choices=UFS, null=True, blank=True
    )

    # NACIONALIDADE
    naturalidade = models.CharField(
        verbose_name='Cidade de Naturalidade do cliente',
        max_length=200,
        null=True,
        blank=True,
    )
    nacionalidade = models.CharField(
        verbose_name='País do cliente',
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )

    # PROFISSAO
    ramo_atividade = models.CharField(
        verbose_name='Ramo de atividade', max_length=100, null=True, blank=True
    )
    tipo_profissao = models.CharField(
        verbose_name='Tipo de profissão', max_length=100, null=True, blank=True
    )
    renda = models.DecimalField(
        verbose_name='Renda', decimal_places=2, max_digits=12, null=True, blank=True
    )
    vr_patrimonio = models.DecimalField(
        verbose_name='Valor do Patrimônio',
        null=True,
        blank=True,
        default=None,
        decimal_places=2,
        max_digits=12,
    )
    possui_procurador = models.BooleanField(default=False, null=True, blank=True)
    ppe = models.BooleanField(
        default=False,
        verbose_name='Pessoa Politicamente Exposta',
        null=True,
        blank=True,
    )

    # ENDERECO
    tipo_logradouro = models.CharField(
        verbose_name='Tipo do Logradouro',
        null=True,
        blank=True,
        default=None,
        max_length=20,
    )
    endereco_residencial_tipo = models.SmallIntegerField(
        verbose_name='Tipo da residência',
        choices=TIPOS_RESIDENCIA,
        null=True,
        blank=True,
    )
    endereco_logradouro = models.CharField(
        verbose_name='Endereço residencial do cliente',
        max_length=200,
        null=True,
        blank=True,
    )
    endereco_numero = models.CharField(
        verbose_name='Número da residência do cliente',
        max_length=10,
        null=True,
        blank=True,
    )
    endereco_complemento = models.CharField(
        verbose_name='Complemento da residência do cliente',
        max_length=200,
        null=True,
        blank=True,
    )
    endereco_bairro = models.CharField(
        verbose_name='Bairro de residência do cliente',
        max_length=200,
        null=True,
        blank=True,
    )
    endereco_cidade = models.CharField(
        verbose_name='Cidade de residência do cliente',
        max_length=200,
        null=True,
        blank=True,
    )
    endereco_uf = models.CharField(
        verbose_name='UF de residência do cliente',
        max_length=2,
        null=True,
        blank=True,
    )
    endereco_cep = models.CharField(
        verbose_name='CEP da residência do cliente', max_length=20
    )
    tempo_residencia = models.CharField(
        verbose_name='Tempo de residência do cliente',
        max_length=30,
        null=True,
        blank=True,
        default=None,
    )

    # CONTATO
    email = models.CharField(
        verbose_name='E-mail do cliente', max_length=200, null=True, blank=True
    )
    telefone_celular = models.CharField(
        max_length=15, verbose_name='DDD + número com 9 dígitos', null=True, blank=True
    )
    telefone_residencial = models.CharField(
        max_length=15, verbose_name='DDD + número com 8 dígitos', null=True, blank=True
    )

    # Conjuge
    conjuge_nome = models.CharField(
        verbose_name='Nome do(a) cônjuge',
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )
    conjuge_cpf = models.CharField(
        verbose_name='CPF do(a) cônjuge',
        max_length=20,
        null=True,
        blank=True,
        default=None,
    )
    conjuge_data_nascimento = models.DateField(
        verbose_name='Data de nascimento do(a) cônjuge',
        null=True,
        blank=True,
        default=None,
    )
    cd_familiar_unico = models.CharField(
        verbose_name='Cód. familiar único',
        max_length=20,
        null=True,
        blank=True,
        default=None,
        help_text='Utilizado no PAB.',
    )
    form_ed_financeira = models.BooleanField(
        verbose_name='Questionário de Educação Financeira preenchido',
        default=False,
        null=True,
        blank=True,
        help_text='Utilizado no PAB',
    )
    IP_Cliente = models.CharField(
        verbose_name='IP Publico do Cliente',
        max_length=50,
        null=True,
        blank=True,
        default=None,
        help_text='Utilizado na CCB.',
    )
    salario_liquido = models.DecimalField(
        verbose_name='Salário Liquido',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    escolaridade = models.IntegerField(
        verbose_name='Escolaridade',
        choices=EnumEscolaridade.choices(),
        null=True,
        blank=True,
    )

    def __init__(self, *args, **kwargs):
        super(Cliente, self).__init__(*args, **kwargs)

        self.__original_state = self.__dict__.copy()

    def __str__(self):
        return self.nome_cliente

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = '1. Clientes'

    def get_first_in100(self) -> 'DadosIn100':  # noqa: F821
        return self.cliente_in100.first()

    def _validate_unique_nu_cpf(self):
        if Cliente.objects.filter(nu_cpf=self.nu_cpf).exclude(pk=self.pk).first():
            raise ValidationError(f'Client with nu_cpf {self.nu_cpf} already exists.')

    def save(self, *args, **kwargs):
        self._validate_unique_nu_cpf()
        super().save(*args, **kwargs)
        self.__original_state = self.__dict__.copy()

    def has_changed(self, field):
        return self.__original_state[field] != self.__dict__[field]

    # history = AuditlogHistoryField()
    def get_documento_uf_display(self):
        return dict(UFS).get(self.documento_uf)

    def get_documento_tipo_display(self):
        return dict(TIPOS_DOCUMENTO).get(self.documento_tipo)

    def get_tipo_cliente_display(self):
        return dict(TIPOS_CLIENTE).get(self.tipo_cliente)

    def get_endereco_residencial_tipo_display(self):
        return dict(TIPOS_RESIDENCIA).get(self.endereco_residencial_tipo)

    @property
    def getEstadoCivil(self):
        return {
            'SOLTEIRO': 1,
            'CASADO': 2,
            'DESQUITADO': 3,
            'DIVORCIADO': 4,
            'VIÚVO': 5,
        }.get(self.estado_civil.upper(), 9)

    @property
    def endereco_complemento_(self):
        return self.endereco_complemento or ''

    @property
    def renda_(self):
        return self.renda or 0

    @property
    def nu_cpf_(self):
        return self.nu_cpf.replace('-', '').replace('.', '')

    @property
    def telefone_ddd(self):
        prefixo, numero = '', ''
        if self.telefone_celular:
            # Remove caracteres especiais
            telefone = (
                self.telefone_celular.replace('(', '').replace(')', '').replace('-', '')
            )

            # Verifica se o número está completamente desformatado e assume o padrão brasileiro de 11 dígitos para celulares
            # (2 dígitos para DDD + 9 dígitos para o número)
            if len(telefone) == 11:
                prefixo = telefone[:2]
                numero = telefone[2:]
            else:
                prefixo, numero = telefone.split(' ', 1)

        return prefixo, numero


class ClienteCartaoBeneficio(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=False,
        related_name='cliente_dados_cartao_beneficio',
    )
    tipo_produto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.CARTAO_BENEFICIO,
    )
    convenio = models.ForeignKey(
        Convenios,
        verbose_name='Convenio',
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name='cliente_convenio',
    )
    contrato = models.ForeignKey(
        'contract.Contrato',
        verbose_name='Contrato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cliente_cartao_contrato',
    )
    senha_portal = models.CharField(
        verbose_name='Senha Portal Servidor', null=True, blank=True, max_length=30
    )
    numero_matricula = models.CharField(
        verbose_name='Número Matrícula', null=True, blank=True, max_length=30
    )
    folha = models.CharField(
        verbose_name='Número da Folha', null=True, blank=True, max_length=255
    )
    folha_saque = models.CharField(
        verbose_name='Folha Saque', null=True, blank=True, max_length=30
    )
    folha_compra = models.CharField(
        verbose_name='Folha Compra', null=True, blank=True, max_length=30
    )
    verba = models.CharField(
        verbose_name='Número da Verba', null=True, blank=True, max_length=30
    )
    verba_compra = models.CharField(
        verbose_name='Verba Compra', null=True, blank=True, max_length=30
    )
    verba_saque = models.CharField(
        verbose_name='Verba Saque', null=True, blank=True, max_length=30
    )
    reserva = models.CharField(
        verbose_name='Número da Reserva', null=True, blank=True, max_length=30
    )
    reserva_compra = models.CharField(
        verbose_name='Número da Reserva (Margem Compra)',
        null=True,
        blank=True,
        max_length=30,
    )
    reserva_saque = models.CharField(
        verbose_name='Número da Reserva (Margem Saque)',
        null=True,
        blank=True,
        max_length=30,
    )
    prazo = models.IntegerField(verbose_name='Prazo', null=True, blank=True)
    margem_atual = models.DecimalField(
        verbose_name='Margem atual',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    margem_compra = models.DecimalField(
        verbose_name='Margem compra',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    margem_saque = models.DecimalField(
        verbose_name='Margem saque',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    id_registro_dock = models.CharField(
        verbose_name='ID do registro na Dock', null=True, blank=True, max_length=50
    )
    id_conta_dock = models.CharField(
        verbose_name='ID Conta Dock', null=True, blank=True, max_length=20
    )
    id_cartao_dock = models.CharField(
        verbose_name='ID do cartão na Dock', null=True, blank=True, max_length=50
    )
    id_endereco_dock = models.CharField(
        verbose_name='ID do endereço na Dock', null=True, blank=True, max_length=50
    )
    id_telefone_dock = models.CharField(
        verbose_name='ID do telefone na Dock', null=True, blank=True, max_length=50
    )
    status_dock = models.CharField(
        verbose_name='Status da conta', null=True, blank=True, max_length=20
    )
    cartao_tem_saude = models.CharField(
        verbose_name='ID do cartão na Tem Saude', null=True, blank=True, max_length=50
    )
    token_usuario_tem_saude = models.CharField(
        verbose_name='ID do usuario na Tem Saude', null=True, blank=True, max_length=300
    )
    numero_cartao_dock = models.CharField(
        verbose_name='Número do Cartão', null=True, blank=True, max_length=50
    )
    nome_impresso_dock = models.CharField(
        verbose_name='Nome Impresso', null=True, blank=True, max_length=255
    )
    tipo_margem = models.SmallIntegerField(
        verbose_name='Tipo Margem',
        choices=TIPOS_MARGEM,
        null=True,
        blank=True,
    )
    limite_pre_aprovado = models.DecimalField(
        verbose_name='Valor do limite pré-aprovado',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    limite_pre_aprovado_saque = models.DecimalField(
        verbose_name='Valor do limite pré-aprovado (Margem Saque)',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    limite_pre_aprovado_compra = models.DecimalField(
        verbose_name='Valor do limite pré-aprovado (Margem Compra)',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    instituidor = models.CharField(
        verbose_name='Instituidor', null=True, blank=True, max_length=12
    )
    convenio_siape = models.CharField(
        verbose_name='Covenio - SIAPE', null=True, blank=True, max_length=255
    )
    classificacao_siape = models.CharField(
        verbose_name='Classificação - SIAPE', null=True, blank=True, max_length=255
    )
    tipo_vinculo_siape = models.SmallIntegerField(
        verbose_name='Tipo de Vinculo - SIAPE',
        choices=TIPO_VINCULO_SIAPE,
        null=True,
        blank=True,
    )

    def __str__(self):
        customer_name = self.cliente.nome_cliente if self.cliente else ''
        return f'{str(self.pk)} {customer_name}'

    class Meta:
        verbose_name = 'Cartão'
        verbose_name_plural = 'Cartões'


class ClienteInss(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=False,
        related_name='cliente_dados_inss',
    )
    cd_cliente_parceiro = models.CharField(
        verbose_name='Cód. parceiro',
        max_length=200,
        null=True,
        blank=True,
        default=None,
        help_text='Código do cliente no parceiro.',
    )  # noqa
    nome_beneficio = models.CharField(
        verbose_name='Nome do benefício', max_length=255, null=True, blank=True
    )
    nu_beneficio = models.CharField(
        verbose_name='Número do benefício', max_length=255, null=True, blank=True
    )
    uf_beneficio = models.CharField(
        verbose_name='UF do benefício', max_length=20, null=True, blank=True
    )
    cd_familiar_unico = models.CharField(
        verbose_name='Cód. familiar único',
        max_length=20,
        null=True,
        blank=True,
        default=None,
        help_text='Utilizado no PAB.',
    )

    form_ed_financeira = models.BooleanField(
        verbose_name='Questionário de Educação Financeira preenchido',
        default=False,
        help_text='Utilizado no PAB',
    )

    def __str__(self):
        return self.cliente.nome_cliente

    class Meta:
        verbose_name = 'INSS'
        verbose_name_plural = 'INSS'


class DadosBancarios(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=False,
        related_name='cliente_dados_bancarios',
    )
    conta_tipo = models.SmallIntegerField(
        verbose_name='Tipo de conta', choices=TIPOS_CONTA, null=True, blank=True
    )
    conta_banco = models.CharField(
        verbose_name='Número do banco', null=True, blank=True, max_length=255
    )
    conta_agencia = models.CharField(
        verbose_name='Número da agência', null=True, blank=True, max_length=255
    )
    conta_numero = models.CharField(
        verbose_name='Número da conta', null=True, blank=True, max_length=255
    )
    conta_digito = models.CharField(
        verbose_name='Dígito da conta', null=True, blank=True, max_length=255
    )
    conta_cpf_titular = models.CharField(
        verbose_name='CPF do Titular', null=True, blank=True, max_length=15
    )
    conta_tipo_pagamento = models.SmallIntegerField(
        verbose_name='Tipo de pagamento', choices=TIPOS_PAGAMENTO, null=True, blank=True
    )
    retornado_in100 = models.BooleanField(
        verbose_name='Dado bancário retornado da IN100?',
        null=True,
        blank=True,
        default=False,
    )
    updated_at = models.DateTimeField(verbose_name='Data de Atualização', auto_now=True)

    def get_conta_tipo_display(self):
        return dict(TIPOS_CONTA).get(self.conta_tipo)

    @property
    def conta_numero_(self):
        return self.conta_numero or 0

    @property
    def conta_digito_(self):
        return self.conta_digito or ''

    def __str__(self):
        return str(self.conta_cpf_titular)

    class Meta:
        verbose_name = 'Dado Bancário'
        verbose_name_plural = 'Dados Bancários'

    def __init__(self, *args, **kwargs):
        super(DadosBancarios, self).__init__(*args, **kwargs)
        self.__original_state = self.__dict__.copy()

    def has_changed(self, field):
        return self.__original_state[field] != self.__dict__[field]


class RepresentanteLegal(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=False,
        related_name='cliente_representantes',
    )
    representanteLegal = models.ForeignKey(
        Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name='representante',
    )

    def __str__(self):
        return f'{self.cliente.nome_cliente} - {self.representanteLegal.nome_cliente}'

    class Meta:
        verbose_name = 'Represenante Legal'
        verbose_name_plural = 'Representantes Legais'


@receiver(post_save, sender=Cliente)
def handle_post_save(sender, instance, created, **kwargs):
    logger = logging.getLogger('cliente')
    if created:
        logger.info(f'{instance.id_unico} - Cliente criado com sucesso.')

    try:
        if cliente_cartao := ClienteCartaoBeneficio.objects.filter(
            cliente=instance
        ).first():
            script = 'handlers/dock_formalizacao.py'
            dock_formalizacao = import_module_by_path(script)

            if cliente_cartao.id_endereco_dock is not None:
                # Checando se algum campo de endereço foi alterado
                endereco_fields = [
                    'cep',
                    'logradouro',
                    'numero',
                    'bairro',
                    'complemento',
                    'uf',
                    'cidade',
                ]
                if any(
                    instance.has_changed(f'endereco_{endereco_field}')
                    for endereco_field in endereco_fields
                ):
                    dock_formalizacao.atualizar_endereco_dock(instance, cliente_cartao)
                    dock_formalizacao.atualizar_endereco_correspondencia_dock(
                        instance, cliente_cartao
                    )

            if cliente_cartao.id_telefone_dock is not None:
                # Checando se o campo de telefone foi alterado
                if instance.has_changed('telefone_celular'):
                    dock_formalizacao.atualizar_telefone_dock(instance, cliente_cartao)
    except Exception:
        logger.exception(
            'Something wrong when replicating information to the dock.',
            extra={'id_unico': instance.id_unico},
        )
