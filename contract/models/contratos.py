"""This module implements models related to contracts"""

# built in imports
import uuid
from typing import List

# django imports
from django.apps import apps
from django.conf import settings
from django.db import models
from django.utils.html import format_html

# local imports
from api_log.choices import STATUS_CCB
from api_log.constants import EnumStatusCCB
from contract.choices import (
    CONTRATO_STATUS,
    TIPO_VINCULO_SIAPE,
    TIPOS_CONTRATO,
    TIPOS_MARGEM,
    TIPOS_PRODUTO,
)
from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.choices import STATUS_NAME
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import Convenios
from core.utils import upload_to_s3
from custom_auth.models import CorbanBase

from .PaymentRefusedIncomingData import PaymentRefusedIncomingData


class ContratoManager(models.Manager):
    """
    Manager são usados para retornar algumas consultas por padrão.
    Ex: Contrato.objects.entrada()
    Retorna todos os contratos no status entrada, definido abaixo:
    """

    def portabilidade(self):
        # Contratos de portabilidade
        return super().get_queryset().filter(tipo_produto=EnumTipoProduto.PORTABILIDADE)

    def cartao_beneficio(self):
        # Contratos de cartao beneficio
        return (
            super().get_queryset().filter(tipo_produto=EnumTipoProduto.CARTAO_BENEFICIO)
        )

    def cartao_consignado(self):
        # Contratos de cartao beneficio
        return (
            super()
            .get_queryset()
            .filter(tipo_produto=EnumTipoProduto.CARTAO_CONSIGNADO)
        )

    def saque_complementar(self):
        # Contratos de saque complementar
        return (
            super()
            .get_queryset()
            .filter(tipo_produto=EnumTipoProduto.SAQUE_COMPLEMENTAR)
        )

    def aguardando_in100_digitacao(self):
        return super().get_queryset().filter(contrato_portabilidade__status=42)

    def aguardando_in100_recalculo(self):
        return super().get_queryset().filter(contrato_portabilidade__status=43)

    def in100_retornada_recalculo(self):
        return super().get_queryset().filter(contrato_portabilidade__status=44)

    def saldo_retornado(self):
        return super().get_queryset().filter(contrato_portabilidade__status=33)

    def aguardando_averbacao(self):
        return super().get_queryset().filter(contrato_portabilidade__status=37)

    def recusado(self):
        return super().get_queryset().filter(contrato_portabilidade__status=41)

    def aguardando_pagamento(self):
        return super().get_queryset().filter(contrato_portabilidade__status=34)

    def finalizado(self):
        return super().get_queryset().filter(contrato_portabilidade__status=38)


class Contrato(CorbanBase):
    tipo_produto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.FGTS,
    )  # tipo de produto
    cd_parceiro = models.CharField(
        verbose_name='Cód. parceiro',
        max_length=200,
        null=True,
        blank=True,
        default=None,
        help_text='Código do contrato no parceiro.',
    )  # cd do Parceiro
    latitude = models.CharField(
        verbose_name='Latitude',
        max_length=200,
        null=True,
        blank=True,
    )
    longitude = models.CharField(
        verbose_name='Longitude',
        max_length=200,
        null=True,
        blank=True,
    )
    hash_assinatura = models.CharField(
        verbose_name='Hash assinatura',
        max_length=200,
        null=True,
        blank=True,
    )
    ip_publico_assinatura = models.CharField(
        verbose_name='IP assinatura',
        max_length=200,
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        'core.Cliente', on_delete=models.PROTECT, null=True, blank=True
    )
    status = models.SmallIntegerField(
        choices=CONTRATO_STATUS, default=EnumContratoStatus.DIGITACAO, db_index=True
    )
    token_contrato = models.UUIDField(
        verbose_name='Token do contrato', unique=True, default=uuid.uuid4, editable=True
    )
    cd_contrato_tipo = models.SmallIntegerField(
        verbose_name='Tipo do contrato', choices=TIPOS_CONTRATO
    )
    taxa = models.DecimalField(
        verbose_name='Taxa da operação',
        decimal_places=5,
        max_digits=12,
        null=True,
        blank=True,
    )
    taxa_efetiva_ano = models.DecimalField(
        verbose_name='Taxa efetiva ao ano da operação',
        decimal_places=5,
        max_digits=12,
        help_text='Taxa considerada no contrato',
        null=True,
        blank=True,
    )
    taxa_efetiva_mes = models.DecimalField(
        verbose_name='Taxa efetiva ao mês da operação',
        decimal_places=5,
        max_digits=12,
        help_text='Taxa considerada no contrato',
        null=True,
        blank=True,
    )
    vr_tac = models.DecimalField(
        verbose_name='Valor TAC', decimal_places=5, max_digits=12, null=True, blank=True
    )
    vr_iof = models.DecimalField(
        verbose_name='Taxa IOF (%)',
        decimal_places=5,
        max_digits=12,
        null=True,
        blank=True,
    )
    vr_iof_adicional = models.DecimalField(
        verbose_name='Taxa do IOF Adiciona (%)',
        decimal_places=5,
        max_digits=12,
        null=True,
        blank=True,
    )
    vr_iof_seguro = models.DecimalField(
        verbose_name='Valor IOF + seguro',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    vr_iof_total = models.DecimalField(
        verbose_name='Valor total de IOF (R$)',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    cet_mes = models.DecimalField(
        verbose_name='Taxa CET ao mês da operação',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    cet_ano = models.DecimalField(
        verbose_name='Taxa CET ao ano da operação',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    vr_liberado_cliente = models.DecimalField(
        verbose_name='Valor liberado Cliente',
        decimal_places=5,
        max_digits=12,
        null=True,
        blank=True,
    )
    limite_pre_aprovado = models.DecimalField(
        verbose_name='Valor do limite pré-aprovado',
        decimal_places=5,
        max_digits=20,
        null=True,
        blank=True,
    )
    vencimento_fatura = models.CharField(
        verbose_name='Dia do vencimento da fatura', null=True, blank=True, max_length=2
    )
    seguro = models.BooleanField(verbose_name='Possui seguro?', default=False)
    vr_seguro = models.DecimalField(
        verbose_name='Valor do seguro',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    taxa_seguro = models.DecimalField(
        verbose_name='Taxa do seguro prestamista',
        decimal_places=5,
        max_digits=12,
        null=True,
        blank=True,
    )
    contrato_assinado = models.BooleanField(
        verbose_name='Contrato assinado?', default=False
    )
    contrato_pago = models.BooleanField(verbose_name='Contrato pago?', default=False)
    cancelada = models.BooleanField(verbose_name='Reserva cancelada?', default=False)
    url_formalizacao = models.CharField(
        verbose_name='URL Formalização', null=True, blank=True, max_length=255
    )

    url_formalizacao_rogado = models.CharField(
        verbose_name='URL de Formalização do Rogado',
        null=True,
        blank=False,
        max_length=300,
        default='',
    )
    link_formalizacao_criado_em = models.DateTimeField(
        verbose_name='Criação do link de formalização', null=True, blank=True
    )
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(
        verbose_name='última atualização', auto_now=True
    )
    enviado_documento_pessoal = models.BooleanField(
        verbose_name='Documento pessoal enviado?', default=False
    )
    pendente_documento = models.BooleanField(
        verbose_name='Documento pessoal pendente?', default=False
    )
    campos_pendentes = models.CharField(
        verbose_name='Campos pendentes?',
        default='',
        max_length=500,
        null=True,
        blank=True,
    )
    enviado_comprovante_residencia = models.BooleanField(
        verbose_name='Comprovante de residência enviado?', default=False
    )
    pendente_endereco = models.BooleanField(
        verbose_name='Comprovante de residência pendente?', default=False
    )
    selfie_enviada = models.BooleanField(verbose_name='Selfie enviada?', default=False)
    selfie_pendente = models.BooleanField(
        verbose_name='Selfie pendente?', default=False
    )
    contracheque_enviado = models.BooleanField(
        verbose_name='Contracheque enviado?', default=False
    )
    contracheque_pendente = models.BooleanField(
        verbose_name='Contracheque pendente?', default=False
    )
    adicional_enviado = models.BooleanField(
        verbose_name='Documento adicional enviado?', default=False
    )
    adicional_pendente = models.BooleanField(
        verbose_name='Documento adicional pendente?', default=False
    )
    regras_validadas = models.BooleanField(
        verbose_name='Regras validadas?', default=False
    )
    token_envelope = models.UUIDField(
        verbose_name='Token do envelope', unique=False, editable=True, null=True
    )
    dt_pagamento_contrato = models.DateField(
        verbose_name='Data Pagamento',
        null=True,
        blank=True,
        help_text='Data de pagamento do contrato',
    )
    contrato_digitacao_manual = models.BooleanField(
        verbose_name='Digitação manual?', default=False
    )
    contrato_digitacao_manual_validado = models.BooleanField(
        verbose_name='Digitação manual validado?', default=False
    )
    plano = models.ManyToManyField(
        'cartao_beneficio.Planos',
        verbose_name='Planos',
        related_name='contrato_planos',
        blank=True,
    )
    is_ccb_generated = models.BooleanField(
        verbose_name='A CCB foi gerada?', default=False
    )
    is_main_proposal = models.BooleanField(
        'Proposta principal do envelope?',
        null=True,
        blank=True,
        default=True,
    )
    numero_beneficio = models.CharField(
        max_length=100, verbose_name='Numero Benefício', null=True, blank=True
    )
    contrato_cross_sell = models.BooleanField(
        verbose_name='Contrato cross sell?', default=False, null=True, blank=True
    )
    rogado = models.ForeignKey(
        'core.Rogado',
        verbose_name='Rogado',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    objects = ContratoManager()

    @property
    def last_status(self) -> StatusContrato:
        """Get the last status registered."""
        last = StatusContrato.objects.filter(contrato=self).last()
        if last is not None:
            return last
        message = 'There is no StatusContrato record for this contract.'
        raise StatusContrato.DoesNotExist(message)

    @property
    def tipo_produto_(self):
        return self.tipo_produto or ''

    @property
    def chave_proposta(self):
        match self.tipo_produto:
            case EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                return getattr(self.get_refin(), 'chave_proposta', None)
            case EnumTipoProduto.PORTABILIDADE:
                return getattr(self.get_portability(), 'chave_proposta', None)
            case EnumTipoProduto.MARGEM_LIVRE:
                return (getattr(self.get_margem_livre(), 'chave_proposta', None),)

    @property
    def get_total_parcela(self):
        return sum(parcela.vr_parcela for parcela in self.parcela_set.all())

    @property
    def vr_tac_(self):
        return self.vr_tac or 0

    @property
    def get_total_iof_tac(self):
        return self.vr_liberado_cliente + self.vr_iof + self.vr_tac_

    @property
    def custo_operacao_(self):
        return float(self.vr_liberado_cliente) * 0.06

    """ Taxas em porcentagem"""

    @property
    def taxa_(self):
        return self.taxa * 100 if self.taxa else ''

    @property
    def taxa_efetiva_mes_(self):
        return self.taxa_efetiva_mes * 100

    @property
    def taxa_efetiva_ano_(self):
        return self.taxa_efetiva_ano * 100

    @property
    def cet_am_(self):
        return self.cet_mes * 100

    @property
    def cet_aa_(self):
        return self.cet_ano * 100

    @property
    def cliente_info(self):
        return format_html(
            '<a class="related-widget-wrapper-link view-related" id="view_id_cliente" data-href-template="/admin/core/cliente/__fk__/change/?_to_field=id" title="View selected Cliente" href="/admin/core/cliente/431/change/?_to_field=id"><img src="/static/admin/img/icon-viewlink.svg" alt="Visualizar"></a>'
        )

    @property
    def get_status_produto(self):
        """
        Retorna o status do contrato de acordo com o tipo de produto
        """
        if self.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            return self.contrato_cartao_beneficio.first().get_status_display()
        elif self.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            return self.contrato_portabilidade.first().get_status_display()
        elif self.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            if (
                self.contrato_portabilidade.first().status
                != ContractStatus.INT_FINALIZADO.value
            ):
                return self.contrato_portabilidade.first().get_status_display()
            return self.contrato_refinanciamento.first().get_status_display()
        elif self.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            return self.contrato_saque_complementar.first().get_status_display()
        elif self.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            return self.contrato_margem_livre.first().get_status_display()
        return '-'

        # TODO: Realizar as demais validações quando os outros tipos de contratos forem criados

    @property
    def envelope(self):
        EnvelopeContratos = apps.get_model('contract', 'EnvelopeContratos')
        return EnvelopeContratos.objects.get(token_envelope=self.token_envelope)

    @property
    def attachments(self) -> List[AnexoContrato]:
        return AnexoContrato.objects.filter(contrato=self)

    @property
    def bucket_name(self) -> str:
        if self.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
            EnumTipoProduto.SAQUE_COMPLEMENTAR,
        ):
            return settings.BUCKET_NAME_AMIGOZ

        if self.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            return settings.BUCKET_NAME_PORTABILIDADE

        if self.tipo_produto in (
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_CORBAN,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
            EnumTipoProduto.MARGEM_LIVRE,
        ):
            return settings.BUCKET_NAME_INSS

    @property
    def is_active(self) -> bool:
        return self.status in (
            EnumContratoStatus.DIGITACAO,
            EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
            EnumContratoStatus.FORMALIZADO,
            EnumContratoStatus.MESA,
            EnumContratoStatus.EM_AVERBACAO,
        )

    def get_status_display(self):
        return dict(CONTRATO_STATUS).get(self.status)

    def get_tipo_produto_display(self):
        return dict(TIPOS_PRODUTO).get(self.tipo_produto)

    def get_cd_contrato_tipo_display(self):
        return dict(TIPOS_CONTRATO).get(self.cd_contrato_tipo)

    def __str__(self):
        return f'{self.pk}'

    def get_free_margin(self):
        try:
            return MargemLivre.objects.get(contrato=self)
        except MargemLivre.DoesNotExist:
            return None

    def is_there_a_pending_account(self) -> bool:
        if self.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            if free_margin := self.get_free_margin():
                return bool(free_margin.is_there_a_pending_account())
            return False
        elif self.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            refinancing = self.get_refin()
            return bool(refinancing.is_there_a_pending_account())

    def get_pending_account(self):
        if self.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            product = self.get_free_margin()
            return product.get_pending_account()
        elif self.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            product = self.get_refin()
        else:
            raise NotImplementedError(
                f'Produto {self.get_tipo_produto_display()} não mapeado!'
            )
        return product.get_pending_account()

    class Meta:
        verbose_name = 'Contrato'
        verbose_name_plural = '1. Contratos'
        indexes = [
            models.Index(fields=['token_contrato']),
            models.Index(fields=['status']),
        ]
        ordering = ('-ultima_atualizacao', 'status')

    def get_last_status(self) -> StatusContrato:
        """Given one contract, query for all the contract status and returns the last one found."""
        return StatusContrato.objects.filter(contrato=self).last()

    def clean_formalizacao_url_when_status_is_rejected(self):
        """Replace the content of the field 'url_formalizacao' by on hiphen when contract last
        status is rejected."""
        status = self.get_last_status(self)
        if status.is_rejected():
            self.url_formalizacao = '-'
            self.save()

    def get_portability(self):
        """Given one contract, query the portability record for the contract and return it."""
        try:
            return Portabilidade.objects.get(contrato=self)
        except Portabilidade.DoesNotExist:
            return None

    def get_margem_livre(self):
        try:
            return MargemLivre.objects.get(contrato=self)
        except MargemLivre.DoesNotExist:
            return None

    def get_refin(self):
        """Given one contract, query the refinancing record for the contract and return it."""
        try:
            return Refinanciamento.objects.get(contrato=self)
        except Refinanciamento.DoesNotExist:
            return None

    def generate_reason_url_formalizacao_not_available(self) -> str:
        """Generates the reason why the url_formalizacao is not available. If available
        returns empty string."""
        reason = ''

        if self.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            client = self.cliente
            in100 = client.get_first_in100()

            if in100 and in100.retornou_IN100:
                status = self.get_last_status()
                portability = self.get_portability()

                if not in100.does_in100_specie_exists():
                    reason = 'Especie não cadastrada'

                elif in100.is_inelegible_or_blocked():
                    reason = 'Beneficio Bloqueado ou Cessado'

                elif status.is_rejected():
                    reason = status.descricao_mesa

                elif not portability.sucesso_insercao_proposta:
                    reason = 'Proposta de portabilidade não foi inserida sucesso. '
                    reason += f'Mensagem: {portability.insercao_sem_sucesso}'

            else:
                reason = 'Aguardando Retorno da IN 100'

        return reason

    def is_there_any_client_formalization_status(self):
        return StatusContrato.objects.filter(
            contrato=self,
            nome=ContractStatus.FORMALIZACAO_CLIENTE.value,
        ).exists()

    def is_still_inserting_proposal(self) -> bool:
        if self.tipo_produto == EnumTipoProduto.PORTABILIDADE and (
            portability := self.get_portability()
        ):
            return portability.is_proposal_being_inserted
        else:
            return False


class ReservaDeMargem(models.Model):
    contrato = models.ForeignKey(
        Contrato, verbose_name='Contrato', on_delete=models.CASCADE
    )
    anexo = models.FileField(
        verbose_name='Anexo', null=True, blank=True, upload_to='contrato'
    )
    nome_anexo = models.CharField(
        verbose_name='Nome do anexo', max_length=300, null=True, blank=True
    )

    anexo_url = models.URLField(
        verbose_name='URL do documento', max_length=500, null=True, blank=True
    )
    protocolo = models.CharField(
        verbose_name='Protocolo da Averbadora', max_length=255, null=True, blank=True
    )

    criado_em = models.DateField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return f'{self.contrato}'

    class Meta:
        verbose_name = 'Reserva de Margem'
        verbose_name_plural = 'Reserva de Margens'

    def save(self, *args, **kwargs):
        # Verificando se há um anexo sendo salvo
        if self.anexo and hasattr(self.anexo, 'file'):
            # Peguando as informações necessárias do arquivo
            nome_anexo = self.anexo.name.rsplit('.', 1)[0]
            extensao = self.anexo.name.rsplit('.', 1)[1]

            url = upload_to_s3(
                self.anexo.file, nome_anexo, extensao, str(self.contrato.token_contrato)
            )
            self.anexo_url = url

            # Limpando o campo anexo para evitar salvar o arquivo no banco de dados local
            self.nome_anexo = self.anexo.name
            self.anexo = None

        super(ReservaDeMargem, self).save(*args, **kwargs)


class CartaoBeneficio(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_cartao_beneficio',
    )
    status = models.SmallIntegerField(
        verbose_name='Status do Contrato',
        choices=STATUS_NAME,
        null=True,
        blank=True,
        default=ContractStatus.ANDAMENTO_SIMULACAO.value,
    )
    convenio = models.ForeignKey(
        Convenios,
        verbose_name='Convenio',
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name='cartao_convenio',
    )
    folha = models.CharField(
        verbose_name='Folha/Espécie de Benefício', null=True, blank=True, max_length=500
    )
    folha_compra = models.CharField(
        verbose_name='Folha compra', null=True, blank=True, max_length=500
    )
    folha_saque = models.CharField(
        verbose_name='Folha saque', null=True, blank=True, max_length=500
    )
    verba = models.CharField(verbose_name='Verba', null=True, blank=True, max_length=15)
    verba_compra = models.CharField(
        verbose_name='Verba compra', null=True, blank=True, max_length=15
    )
    verba_saque = models.CharField(
        verbose_name='Verba saque', null=True, blank=True, max_length=15
    )
    numero_contrato_averbadora = models.IntegerField(
        verbose_name='Número do contrato - Retorno Averbadora', null=True, blank=True
    )
    possui_saque = models.BooleanField(
        verbose_name='Possui Saque Rotativo?', default=False
    )
    saque_parcelado = models.BooleanField(
        verbose_name='Possui Saque Parcelado?', default=False
    )
    possui_saque_complementar = models.BooleanField(
        verbose_name='Possui saque complementar?', default=False
    )
    valor_disponivel_saque = models.DecimalField(
        verbose_name='Valor disponível para saque',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_saque = models.DecimalField(
        verbose_name='Valor do saque',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_parcela = models.DecimalField(
        verbose_name='Valor da parcela',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    qtd_parcela_saque_parcelado = models.IntegerField(
        verbose_name='Quantidade de Parcelas Contratadas', null=True, blank=True
    )
    valor_financiado = models.DecimalField(
        verbose_name='Valor Total Financiado',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_total_a_pagar = models.DecimalField(
        verbose_name='Valor Total a Pagar',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    codigo_instituicao = models.IntegerField(
        verbose_name='Código da Instituição', null=True, blank=True
    )
    carencia = models.IntegerField(verbose_name='Carência', null=True, blank=True)
    reserva = models.CharField(
        verbose_name='Número da Reserva', null=True, blank=True, max_length=255
    )
    numero_proposta_banksoft = models.CharField(
        verbose_name='Numero da Proposta (Banksoft)',
        null=True,
        blank=True,
        max_length=15,
    )

    retorno_solicitacao_saque = models.CharField(
        verbose_name='Retorno solicitação saque', null=True, blank=True, max_length=255
    )

    senha_servidor = models.CharField(
        verbose_name='Senha Servidor', max_length=100, null=True, blank=True
    )

    tipo_margem = models.SmallIntegerField(
        verbose_name='Tipo Margem Contratada',
        choices=TIPOS_MARGEM,
        null=True,
        blank=True,
    )

    tipo_cartao = models.CharField(
        verbose_name='Tipo Cartão', max_length=100, null=True, blank=True
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
        return f'{self.contrato}'

    def get_status_display(self):
        return dict(STATUS_NAME).get(self.status)

    # def save(self, *args, **kwargs):
    #     # Verificar se numero_proposta_banksoft foi alterado
    #     if self.pk is not None:  # garantir que não é uma nova instância
    #         original = CartaoBeneficio.objects.get(pk=self.pk)
    #         if self.numero_proposta_banksoft != original.numero_proposta_banksoft:
    #             self.numero_proposta_banksoft = self.numero_proposta_banksoft
    #
    #     # Então chame o método save() da superclasse
    #     super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Cartão Benefício'
        verbose_name_plural = 'Cartão Benefício'


class SaqueComplementar(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_saque_complementar',
    )
    status = models.SmallIntegerField(
        verbose_name='Status do contrato',
        choices=STATUS_NAME,
        null=True,
        blank=True,
        default=ContractStatus.ANDAMENTO_SIMULACAO.value,
    )
    saque_parcelado = models.BooleanField(
        verbose_name='Possui saque parcelado?', default=False
    )
    possui_saque = models.BooleanField(
        verbose_name='Possui saque rotativo?', default=False
    )
    valor_parcela = models.DecimalField(
        verbose_name='Valor da parcela',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    qtd_parcela_saque_parcelado = models.IntegerField(
        verbose_name='Quantidade de parcelas', null=True, blank=True
    )
    valor_saque = models.DecimalField(
        verbose_name='Valor saque',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    valor_disponivel_saque = models.DecimalField(
        verbose_name='Valor disponível para saque',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_lancado_fatura = models.DecimalField(
        verbose_name='Valor total financiado',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_total_a_pagar = models.DecimalField(
        verbose_name='Valor total a Pagar',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    numero_proposta_banksoft = models.CharField(
        verbose_name='Numero da proposta (Banksoft)',
        null=True,
        blank=True,
        max_length=15,
    )

    retorno_solicitacao_saque = models.CharField(
        verbose_name='Retorno solicitação saque', null=True, blank=True, max_length=255
    )

    data_solicitacao = models.DateField(
        verbose_name='Data Solicitação',
        null=True,
        blank=True,
    )
    id_cliente_cartao = models.ForeignKey(
        'core.ClienteCartaoBeneficio',
        verbose_name='ID Cliente Cartão',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cliente_cartao_contrato_saque_complementar',
    )

    def get_status_display(self):
        return dict(STATUS_NAME).get(self.status)

    # def save(self, *args, **kwargs):
    #     # Verificar se numero_proposta_banksoft foi alterado
    #     if self.pk is not None:  # garantir que não é uma nova instância
    #         original = SaqueComplementar.objects.get(pk=self.pk)
    #         if self.numero_proposta_banksoft != original.numero_proposta_banksoft:
    #             self.numero_proposta_banksoft = self.numero_proposta_banksoft
    #
    #     # Então chame o método save() da superclasse
    #     super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Saque Complementar'
        verbose_name_plural = 'Saque Complementar'


class MargemLivre(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_margem_livre',
    )
    status = models.SmallIntegerField(
        verbose_name='Status do Contrato',
        choices=STATUS_NAME,
        null=True,
        blank=True,
        default=ContractStatus.ANDAMENTO_SIMULACAO.value,
    )
    vr_contrato = models.DecimalField(
        verbose_name='Valor Contrato',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
        help_text='Indica o valor do contrato',
    )
    chave_proposta = models.CharField(
        verbose_name='Chave proposta',
        max_length=200,
        null=True,
        blank=True,
        help_text='Chave da Proposta de Margem Livre na QITECH',
    )
    qtd_parcelas = models.IntegerField(
        verbose_name='Quantidade de Parcelas', null=True, blank=True
    )
    vr_parcelas = models.DecimalField(
        verbose_name='Valor das Parcelas',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    vr_liberado_cliente = models.DecimalField(
        verbose_name='Valor a Pagar',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
        help_text='Indica o valor liberado para o cliente',
    )
    taxa_contrato_recalculada = models.DecimalField(
        verbose_name='Taxa Contrato Recalculada',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_parcela_recalculada = models.DecimalField(
        verbose_name='Valor da Parcela Recalculada',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    ccb_gerada = models.BooleanField(
        verbose_name='CCB Gerada pela QITECH?',
        default=False,
        help_text='Indica se a CCB foi gerada',
    )
    CPF_dados_divergentes = models.BooleanField(
        verbose_name='CPF irregular na receita?',
        default=False,
        help_text='Indica se o CPF está Irregular na Receita Federal',
    )
    sucesso_insercao_proposta = models.BooleanField(
        verbose_name='Sucesso na inserção proposta(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a proposta foi inserida com sucesso',
    )
    insercao_sem_sucesso = models.TextField(
        verbose_name='Motivo de erro na insercao QITECH',
        null=True,
        blank=True,
        help_text='Caso a insercao não foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_envio_assinatura = models.BooleanField(
        verbose_name='Sucesso Assinatura(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio da assinatura foi realizado com sucesso',
    )
    motivo_envio_assinatura = models.CharField(
        verbose_name='Motivo Assinatura QITECH',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de assinatura não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_frente_cnh = models.BooleanField(
        verbose_name='Sucesso FRENTE/CNH(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento(FRENTE/CNH) foi realizado com sucesso',
    )
    motivo_envio_documento_frente_cnh = models.CharField(
        verbose_name='Motivo FRENTE/CNH(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (FRENTE/CNH) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_verso = models.BooleanField(
        verbose_name='Sucesso VERSO(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento(VERSO) foi realizado com sucesso',
    )
    motivo_envio_documento_verso = models.CharField(
        verbose_name='Motivo VERSO(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (VERSO) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_selfie = models.BooleanField(
        verbose_name='Sucesso SELFIE(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento (SELFIE) foi realizado com sucesso',
    )
    motivo_envio_documento_selfie = models.CharField(
        verbose_name='Motivo SELFIE(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (SELFIE) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_documentos_linkados = models.BooleanField(
        verbose_name='Sucesso CONEXÃO DOCUMENTOS(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a conexão dos documentos com a proposta foi realizada com sucesso',
    )
    motivo_documentos_linkados = models.CharField(
        verbose_name='Motivo CONEXÃO DOCUMENTOS(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a conexão dos documentos com a proposta não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_submissao_proposta = models.BooleanField(
        verbose_name='Sucesso SUBMISSÃO PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a submissão da proposta foi realizada com sucesso',
    )
    motivo_submissao_proposta = models.CharField(
        verbose_name='Motivo SUBMISSÃO PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a submissão da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_aceite_proposta = models.BooleanField(
        verbose_name='Sucesso ACEITE PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o aceite da proposta foi realizada com sucesso',
    )
    motivo_aceite_proposta = models.CharField(
        verbose_name='Motivo ACEITE PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o ACEITE da proposta nao foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_recusa_proposta = models.BooleanField(
        verbose_name='Sucesso RECUSA PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a recusa da proposta foi realizada com sucesso',
    )
    motivo_recusa_proposta = models.CharField(
        verbose_name='Motivo RECUSA PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a RECUSA da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_reapresentacao_pagamento = models.BooleanField(
        verbose_name='Sucesso REAPRESENTAÇÃO do Refinanciamento(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se houve sucesso na REAPRESENTAÇÃO(QITECH)',
    )
    motivo_reapresentacao_pagamento = models.CharField(
        verbose_name='Motivo REAPRESENTAÇÃO(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a REAPRESENTAÇÃO da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    cd_retorno_averbacao = models.BooleanField(
        verbose_name='Retorno averbação ', null=True, blank=True
    )
    codigo_dataprev = models.CharField(
        verbose_name='Código Dataprev',
        max_length=150,
        null=True,
        blank=True,
    )
    descricao_dataprev = models.CharField(
        verbose_name='Descrição Dataprev',
        max_length=150,
        null=True,
        blank=True,
    )
    dt_retorno_dataprev = models.DateField(
        verbose_name='Data de retorno do Dataprev', null=True, blank=True
    )
    dt_vencimento_primeira_parcela = models.DateField(
        verbose_name='Data de vencimento da primeira parcela',
        default='2023-09-20',  # Defina a data padrão desejada, como '2023-09-20'
    )
    dt_vencimento_ultima_parcela = models.DateField(
        verbose_name='Data de vencimento da última parcela',
        default='2023-12-31',  # Defina a data padrão desejada, como '2023-12-31'
    )
    vr_tarifa_cadastro = models.IntegerField(
        verbose_name='Valor da tarifa de cadastro',
        default=0,  # Defina o valor padrão desejado, como 0
    )
    fl_seguro = models.BooleanField(
        verbose_name='Possui Seguro?',
        default=False,  # Defina True ou False, dependendo do valor padrão desejado
    )
    vr_seguro = models.IntegerField(
        verbose_name='Valor do Seguro',
        default=0,  # Defina o valor padrão desejado, como 0
    )
    dt_liberado_cliente = models.DateTimeField(
        verbose_name='Data de liberação do cliente',
        default='2023-09-20 12:00:00',  # Defina a data e hora padrão desejada, como '2023-09-20 12:00:00'
    )
    related_party_key = models.CharField(
        verbose_name='Related_Party_Key', max_length=200, null=True, blank=True
    )
    dt_envio_proposta_CIP = models.DateField(
        verbose_name='Data de envio da proposta(CIP)',
        null=True,
        blank=True,
        help_text='Data de envio do aceite da proposta para a CIP',
    )
    collateral_key = models.CharField(
        verbose_name='Collateral_Key', max_length=200, null=True, blank=True
    )
    document_key_QiTech_CCB = models.CharField(
        verbose_name='Numero do Documento CCB', max_length=200, null=True, blank=True
    )
    document_key_QiTech_Frente_ou_CNH = models.CharField(
        verbose_name='Chave do Documento Pessoal Frente/CNH',
        max_length=200,
        null=True,
        blank=True,
    )
    document_key_QiTech_Verso = models.CharField(
        verbose_name='Chave do Documento Pessoal Verso',
        max_length=200,
        null=True,
        blank=True,
    )
    document_key_QiTech_Selfie = models.CharField(
        verbose_name='Chave da Selfie', max_length=200, null=True, blank=True
    )
    dt_desembolso = models.DateField(
        verbose_name='Data de Desembolso',
        null=True,
        blank=True,
        help_text='Data de Desembolso da Operação',
    )
    dt_averbacao = models.DateField(
        verbose_name='Data de Averbação',
        null=True,
        blank=True,
        help_text='Data de Averbação da Operação',
    )
    payment_refused_incoming_data = models.ForeignKey(
        PaymentRefusedIncomingData,
        verbose_name='Dados do cancelamento do pagamento',
        on_delete=models.SET_NULL,
        related_name='margem_livre_dados_pagamento_recusado',
        null=True,
        default=None,
    )
    objects = ContratoManager()

    @property
    def falha_no_pagamento(self) -> bool:
        return self.payment_refused_incoming_data is not None

    @property
    def motivo_falha_no_pagamento(self) -> str:
        return self.payment_refused_incoming_data.reason_description

    def __str__(self):
        return f'{self.contrato}'

    class Meta:
        verbose_name = 'Margem Livre'
        verbose_name_plural = 'Margem Livre'

    def is_there_a_pending_account(self) -> bool:
        return (
            self.payment_refused_incoming_data is not None
            and self.payment_refused_incoming_data.bank_data is not None
        )

    def get_pending_account(self):
        return self.payment_refused_incoming_data.bank_data


class Portabilidade(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_portabilidade',
    )
    status = models.SmallIntegerField(
        verbose_name='Status do Contrato',
        choices=STATUS_NAME,
        null=True,
        blank=True,
        default=ContractStatus.ANDAMENTO_SIMULACAO.value,
    )
    banco = models.CharField(
        verbose_name='Banco', null=False, blank=True, max_length=100
    )
    numero_beneficio = models.CharField(
        verbose_name='Benefício', null=False, blank=True, max_length=100
    )
    especie = models.CharField(
        verbose_name='Especie', null=False, blank=True, max_length=100
    )
    numero_contrato = models.CharField(
        verbose_name='Número Contrato', null=True, blank=True, max_length=100
    )
    saldo_devedor = models.DecimalField(
        verbose_name='Saldo Devedor',
        decimal_places=2,
        max_digits=20,
        null=False,
        blank=True,
    )
    prazo = models.IntegerField(verbose_name='Prazo', null=False, blank=True)
    taxa = models.DecimalField(
        verbose_name='Taxa',
        null=True,
        blank=True,
        default=None,
        decimal_places=7,
        max_digits=12,
    )
    parcela_digitada = models.DecimalField(
        verbose_name='Parcela Digitada',
        decimal_places=2,
        max_digits=20,
        null=False,
        blank=True,
    )
    nova_parcela = models.DecimalField(
        verbose_name='Nova Parcela',
        decimal_places=2,
        max_digits=20,
        null=False,
        blank=True,
    )
    chave_proposta = models.CharField(
        verbose_name='Chave proposta', max_length=200, null=True, blank=True
    )
    numero_parcelas_atrasadas = models.IntegerField(
        verbose_name='Número de parcelas atrasadas', null=True, blank=True
    )
    chave_operacao = models.CharField(
        verbose_name='Chave da Operação',
        max_length=200,
        null=True,
        blank=True,
        help_text='credit operation key',
    )
    status_ccb = models.SmallIntegerField(
        verbose_name='Status', null=True, blank=True, choices=STATUS_CCB
    )
    CPF_dados_divergentes = models.BooleanField(
        verbose_name='CPF irregular na receita?',
        default=False,
        help_text='Indica se o CPF está Irregular na Receita Federal',
    )
    numero_portabilidade = models.CharField(
        verbose_name='Número portabilidade - Qitech',
        null=True,
        blank=True,
        max_length=200,
    )
    document_key_QiTech_Frente_ou_CNH = models.CharField(
        verbose_name='Chave do Documento Pessoal Frente/CNH',
        max_length=200,
        null=True,
        blank=True,
    )
    document_key_QiTech_Verso = models.CharField(
        verbose_name='Chave do Documento Pessoal Verso',
        max_length=200,
        null=True,
        blank=True,
    )
    document_key_QiTech_CCB = models.CharField(
        verbose_name='Chave do Documento CCB', max_length=200, null=True, blank=True
    )
    document_key_QiTech_Selfie = models.CharField(
        verbose_name='Chave da Selfie', max_length=200, null=True, blank=True
    )
    related_party_key = models.CharField(
        verbose_name='Related_Party_Key', max_length=200, null=True, blank=True
    )
    numero_portabilidade_CTC_CIP = models.CharField(
        verbose_name='Numero da Portabilidade CTC/CIP',
        max_length=200,
        null=True,
        blank=True,
    )
    saldo_devedor_atualizado = models.DecimalField(
        verbose_name='Saldo Devedor Atualizado',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    numero_parcela_atualizada = models.IntegerField(
        verbose_name='Numero Parcelas Atualizada', null=True, blank=True
    )
    taxa_contrato_original = models.DecimalField(
        verbose_name='Taxa Contrato Original',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    taxa_contrato_recalculada = models.DecimalField(
        verbose_name='Taxa Contrato Recalculada',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_parcela_original = models.DecimalField(
        verbose_name='Valor da Parcela Original',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_parcela_recalculada = models.DecimalField(
        verbose_name='Valor da Parcela Recalculada',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    motivo_recusa = models.CharField(
        verbose_name='Motivo de Recusa do CTC/CIP',
        max_length=200,
        null=True,
        blank=True,
    )
    ccb_gerada = models.BooleanField(
        verbose_name='CCB Gerada pela QITECH?',
        default=False,
        help_text='Indica se a CCB foi gerada',
    )
    sucesso_insercao_proposta = models.BooleanField(
        verbose_name='Sucesso na inserção proposta(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a proposta foi inserida com sucesso',
    )
    insercao_sem_sucesso = models.TextField(
        verbose_name='Motivo de erro na insercao QITECH',
        null=True,
        blank=True,
        help_text='Caso a insercao não foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_envio_assinatura = models.BooleanField(
        verbose_name='Sucesso Assinatura(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio da assinatura foi realizado com sucesso',
    )
    motivo_envio_assinatura = models.CharField(
        verbose_name='Motivo Assinatura QITECH',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de assinatura não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_frente_cnh = models.BooleanField(
        verbose_name='Sucesso FRENTE/CNH(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento(FRENTE/CNH) foi realizado com sucesso',
    )
    motivo_envio_documento_frente_cnh = models.CharField(
        verbose_name='Motivo FRENTE/CNH(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (FRENTE/CNH) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_verso = models.BooleanField(
        verbose_name='Sucesso VERSO(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento(VERSO) foi realizado com sucesso',
    )
    motivo_envio_documento_verso = models.CharField(
        verbose_name='Motivo VERSO(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (VERSO) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_selfie = models.BooleanField(
        verbose_name='Sucesso SELFIE(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento (SELFIE) foi realizado com sucesso',
    )
    motivo_envio_documento_selfie = models.CharField(
        verbose_name='Motivo SELFIE(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (SELFIE) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_documentos_linkados = models.BooleanField(
        verbose_name='Sucesso CONEXÃO DOCUMENTOS(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a conexão dos documentos com a proposta foi realizada com sucesso',
    )
    motivo_documentos_linkados = models.CharField(
        verbose_name='Motivo CONEXÃO DOCUMENTOS(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a conexão dos documentos com a proposta não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_submissao_proposta = models.BooleanField(
        verbose_name='Sucesso SUBMISSÃO PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a submissão da proposta foi realizada com sucesso',
    )
    motivo_submissao_proposta = models.CharField(
        verbose_name='Motivo SUBMISSÃO PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a submissão da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_aceite_proposta = models.BooleanField(
        verbose_name='Sucesso ACEITE PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o aceite da proposta foi realizada com sucesso',
    )
    motivo_aceite_proposta = models.CharField(
        verbose_name='Motivo ACEITE PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o ACEITE da proposta nao foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_recusa_proposta = models.BooleanField(
        verbose_name='Sucesso RECUSA PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a recusa da proposta foi realizada com sucesso',
    )
    motivo_recusa_proposta = models.CharField(
        verbose_name='Motivo RECUSA PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a RECUSA da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    codigo_dataprev = models.CharField(
        verbose_name='Código Dataprev',
        max_length=150,
        null=True,
        blank=True,
    )
    descricao_dataprev = models.CharField(
        verbose_name='Descrição Dataprev',
        max_length=150,
        null=True,
        blank=True,
    )
    dt_retorno_dataprev = models.DateField(
        verbose_name='Data de retorno do Dataprev', null=True, blank=True
    )
    dt_envio_proposta_CIP = models.DateField(
        verbose_name='Data de envio da proposta(CIP)',
        null=True,
        blank=True,
        help_text='Data de envio do aceite da proposta para a CIP',
    )
    dt_recebimento_saldo_devedor = models.DateField(
        verbose_name='Data de recebimento do saldo devedor(CIP)',
        null=True,
        blank=True,
        help_text='Data de recebimento do saldo devedor(CIP)',
    )
    banco_atacado = models.CharField(
        verbose_name='Banco Atacado',
        max_length=300,
        null=True,
        blank=True,
        help_text='Banco que estamos portando o Contrato',
    )
    dt_recusa_retido = models.DateField(
        verbose_name='Data de RECUSA/RETIDO',
        null=True,
        blank=True,
        help_text='Data de recusa/retido (CIP)',
    )
    is_proposal_being_inserted = models.BooleanField(default=False)

    dt_primeiro_pagamento = models.DateField(
        verbose_name='Data do primeiro pagamento',
        null=True,
        blank=True,
        help_text='Data do primeiro pagamento',
    )

    dt_ultimo_pagamento = models.DateField(
        verbose_name='Data do último pagamento',
        null=True,
        blank=True,
        help_text='Data do último pagamento',
    )

    def get_status_ccb_qi_tech(self):
        return dict(STATUS_CCB).get(self.status_ccb)

    def __str__(self):
        return f'{self.contrato}'

    def flag_status_as_inserting_proposal(self) -> None:
        self.is_proposal_being_inserted = True
        self.save()

    def unflag_status_as_inserting_proposal(self) -> None:
        self.is_proposal_being_inserted = False
        self.save()

    def flag_successfully_inserted_proposal(self) -> None:
        self.unflag_status_as_inserting_proposal()
        self.sucesso_insercao_proposta = True
        self.save()

    def flag_unsuccessfully_inserted_proposal(self, data: dict[str, any]) -> None:
        self.unflag_status_as_inserting_proposal()
        self.sucesso_insercao_proposta = False
        self.insercao_sem_sucesso = data
        self.save()

    def flag_ccb_status_as_generated(self) -> None:
        self.ccb_gerada = True
        self.save()

    def update_data_on_qi_tech_success_response(
        self, related_party_key: str, proposal_key: str
    ) -> None:
        self.related_party_key = related_party_key
        self.chave_proposta = proposal_key
        self.status_ccb = EnumStatusCCB.PENDING_SUBIMISSION.value

    class Meta:
        verbose_name = 'Portabilidade'
        verbose_name_plural = 'Portabilidade'


class RetornoSaque(models.Model):
    contrato = models.ForeignKey(
        Contrato, on_delete=models.CASCADE, null=True, blank=True
    )
    NumeroProposta = models.CharField(
        verbose_name='Número da proposta', max_length=300, null=True, blank=True
    )
    valorTED = models.DecimalField(
        verbose_name='Valor TED',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
        default=0,
    )
    Status = models.CharField(
        verbose_name='Status', max_length=300, null=True, blank=True
    )
    Banco = models.CharField(
        verbose_name='Banco', max_length=300, null=True, blank=True
    )
    Agencia = models.CharField(
        verbose_name='Agência', max_length=300, null=True, blank=True
    )
    Conta = models.CharField(
        verbose_name='Conta', max_length=300, null=True, blank=True
    )
    DVConta = models.CharField(
        verbose_name='Dígito Verificador', max_length=300, null=True, blank=True
    )
    CPFCNPJ = models.CharField(
        verbose_name='CPF / CNPJ', max_length=300, null=True, blank=True
    )
    DtCriacao = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    Observacao = models.TextField(verbose_name='Observacao', null=True, blank=True)

    class Meta:
        verbose_name = 'Retorno Saque'
        verbose_name_plural = 'Retorno Saque'


class Refinanciamento(models.Model):
    contrato = models.ForeignKey(
        Contrato,
        verbose_name='Contrato',
        on_delete=models.CASCADE,
        related_name='contrato_refinanciamento',
    )
    status = models.SmallIntegerField(
        verbose_name='Status do Contrato',
        choices=STATUS_NAME,
        null=True,
        blank=True,
        default=ContractStatus.ANDAMENTO_SIMULACAO.value,
    )
    banco = models.CharField(
        verbose_name='Banco', null=False, blank=True, max_length=100
    )
    numero_beneficio = models.CharField(
        verbose_name='Benefício', null=False, blank=True, max_length=100
    )
    especie = models.CharField(
        verbose_name='Especie', null=False, blank=True, max_length=100
    )
    numero_contrato = models.CharField(
        verbose_name='Número Contrato', null=True, blank=True, max_length=100
    )
    saldo_devedor = models.DecimalField(
        verbose_name='Saldo Devedor',
        decimal_places=2,
        max_digits=20,
        null=False,
        blank=True,
    )
    troco = models.DecimalField(
        verbose_name='Troco',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    troco_recalculado = models.DecimalField(
        verbose_name='Troco recalculado',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_total = models.DecimalField(
        verbose_name='Valor da Refinanciamento',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_total_recalculado = models.DecimalField(
        verbose_name='Valor do Refinanciamento Recalculado',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    prazo = models.IntegerField(verbose_name='Prazo', null=False, blank=True)
    taxa = models.DecimalField(
        verbose_name='Taxa',
        null=True,
        blank=True,
        default=None,
        decimal_places=7,
        max_digits=12,
    )
    parcela_digitada = models.DecimalField(
        verbose_name='Parcela Digitada',
        decimal_places=2,
        max_digits=20,
        null=False,
        blank=True,
    )
    nova_parcela = models.DecimalField(
        verbose_name='Nova Parcela',
        decimal_places=2,
        max_digits=20,
        null=False,
        blank=True,
    )
    chave_proposta = models.CharField(
        verbose_name='Chave proposta', max_length=200, null=True, blank=True
    )
    chave_operacao = models.CharField(
        verbose_name='Chave da Operação',
        max_length=200,
        null=True,
        blank=True,
        help_text='credit operation key',
    )
    status_ccb = models.SmallIntegerField(
        verbose_name='Status', null=True, blank=True, choices=STATUS_CCB
    )
    CPF_dados_divergentes = models.BooleanField(
        verbose_name='CPF irregular na receita?',
        default=False,
        help_text='Indica se o CPF está Irregular na Receita Federal',
    )
    numero_refinanciamento = models.CharField(
        verbose_name='Número refinanciamento - Qitech',
        null=True,
        blank=True,
        max_length=200,
    )
    document_key_QiTech_Frente_ou_CNH = models.CharField(
        verbose_name='Chave do Documento Pessoal Frente/CNH',
        max_length=200,
        null=True,
        blank=True,
    )
    document_key_QiTech_Verso = models.CharField(
        verbose_name='Chave do Documento Pessoal Verso',
        max_length=200,
        null=True,
        blank=True,
    )
    document_key_QiTech_CCB = models.CharField(
        verbose_name='Chave do Documento CCB', max_length=200, null=True, blank=True
    )
    document_key_QiTech_Selfie = models.CharField(
        verbose_name='Chave da Selfie', max_length=200, null=True, blank=True
    )
    related_party_key = models.CharField(
        verbose_name='Related_Party_Key', max_length=200, null=True, blank=True
    )
    numero_refinanciamento_CTC_CIP = models.CharField(
        verbose_name='Numero do Refinanciamento CTC/CIP',
        max_length=200,
        null=True,
        blank=True,
    )
    saldo_devedor_atualizado = models.DecimalField(
        verbose_name='Saldo Devedor Atualizado',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    numero_parcela_atualizada = models.IntegerField(
        verbose_name='Numero Parcelas Atualizada', null=True, blank=True
    )
    taxa_contrato_original = models.DecimalField(
        verbose_name='Taxa Contrato Original',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    taxa_contrato_recalculada = models.DecimalField(
        verbose_name='Taxa Contrato Recalculada',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_parcela_original = models.DecimalField(
        verbose_name='Valor da Parcela Original',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_parcela_recalculada = models.DecimalField(
        verbose_name='Valor da Parcela Recalculada',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    margem_liberada = models.DecimalField(
        verbose_name='Margem Liberaada',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    motivo_recusa = models.CharField(
        verbose_name='Motivo de Recusa do CTC/CIP',
        max_length=200,
        null=True,
        blank=True,
    )
    ccb_gerada = models.BooleanField(
        verbose_name='CCB Gerada pela QITECH?',
        default=False,
        help_text='Indica se a CCB foi gerada',
    )
    sucesso_insercao_proposta = models.BooleanField(
        verbose_name='Sucesso na inserção proposta(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a proposta foi inserida com sucesso',
    )
    insercao_sem_sucesso = models.TextField(
        verbose_name='Motivo de erro na insercao QITECH',
        null=True,
        blank=True,
        help_text='Caso a insercao não foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_envio_assinatura = models.BooleanField(
        verbose_name='Sucesso Assinatura(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio da assinatura foi realizado com sucesso',
    )
    motivo_envio_assinatura = models.CharField(
        verbose_name='Motivo Assinatura QITECH',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de assinatura não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_frente_cnh = models.BooleanField(
        verbose_name='Sucesso FRENTE/CNH(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento(FRENTE/CNH) foi realizado com sucesso',
    )
    motivo_envio_documento_frente_cnh = models.CharField(
        verbose_name='Motivo FRENTE/CNH(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (FRENTE/CNH) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_verso = models.BooleanField(
        verbose_name='Sucesso VERSO(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento(VERSO) foi realizado com sucesso',
    )
    motivo_envio_documento_verso = models.CharField(
        verbose_name='Motivo VERSO(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (VERSO) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_envio_documento_selfie = models.BooleanField(
        verbose_name='Sucesso SELFIE(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o envio do documento (SELFIE) foi realizado com sucesso',
    )
    motivo_envio_documento_selfie = models.CharField(
        verbose_name='Motivo SELFIE(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio de documento (SELFIE) não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_documentos_linkados = models.BooleanField(
        verbose_name='Sucesso CONEXÃO DOCUMENTOS(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a conexão dos documentos com a proposta foi realizada com sucesso',
    )
    motivo_documentos_linkados = models.CharField(
        verbose_name='Motivo CONEXÃO DOCUMENTOS(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a conexão dos documentos com a proposta não foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_submissao_proposta = models.BooleanField(
        verbose_name='Sucesso SUBMISSÃO PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a submissão da proposta foi realizada com sucesso',
    )
    motivo_submissao_proposta = models.CharField(
        verbose_name='Motivo SUBMISSÃO PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a submissão da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_aceite_proposta = models.BooleanField(
        verbose_name='Sucesso ACEITE REFINANCIAMENTO(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se o aceite do REFINANCIAMENTO foi realizada com sucesso',
    )
    motivo_aceite_proposta = models.CharField(
        verbose_name='Motivo ACEITE REFINANCIAMENTO(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o ACEITE do REFINANCIAMENTO nao foi bem sucedido aqui aparece o motivo do erro',
    )
    sucesso_recusa_proposta = models.BooleanField(
        verbose_name='Sucesso RECUSA PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a recusa da proposta foi realizada com sucesso',
    )
    sucesso_desembolso_refinanciamento = models.BooleanField(
        verbose_name='Sucesso Desembolso Refinanciamento(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se houve o desembolso do refinanciamento pela QITECH',
    )
    motivo_desembolso_proposta = models.CharField(
        verbose_name='Motivo DESEMBOLSO(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o DESEMBOLSO da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_reapresentacao_pagamento = models.BooleanField(
        verbose_name='Sucesso REAPRESENTAÇÃO do Refinanciamento(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se houve sucesso na REAPRESENTAÇÃO(QITECH)',
    )
    motivo_reapresentacao_pagamento = models.CharField(
        verbose_name='Motivo REAPRESENTAÇÃO(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a REAPRESENTAÇÃO da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    motivo_recusa_proposta = models.CharField(
        verbose_name='Motivo RECUSA PROPOSTA(QITECH)',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a RECUSA da proposta nao foi bem sucedida aqui aparece o motivo do erro',
    )
    codigo_dataprev = models.CharField(
        verbose_name='Código Dataprev',
        max_length=150,
        null=True,
        blank=True,
    )
    descricao_dataprev = models.CharField(
        verbose_name='Descrição Dataprev',
        max_length=150,
        null=True,
        blank=True,
    )
    dt_retorno_dataprev = models.DateField(
        verbose_name='Data de retorno do Dataprev', null=True, blank=True
    )
    dt_envio_proposta_CIP = models.DateField(
        verbose_name='Data de envio da proposta(CIP)',
        null=True,
        blank=True,
        help_text='Data de envio do aceite da proposta para a CIP',
    )
    dt_recebimento_saldo_devedor = models.DateField(
        verbose_name='Data de recebimento do saldo devedor(CIP)',
        null=True,
        blank=True,
        help_text='Data de recebimento do saldo devedor(CIP)',
    )
    banco_atacado = models.CharField(
        verbose_name='Banco Atacado',
        max_length=300,
        null=True,
        blank=True,
        help_text='Banco que estamos refinanciando o Contrato',
    )
    dt_recusa_retido = models.DateField(
        verbose_name='Data de RECUSA/RETIDO',
        null=True,
        blank=True,
        help_text='Data de recusa/retido (CIP)',
    )
    is_proposal_being_inserted = models.BooleanField(default=False)
    sucesso_finalizada_proposta = models.BooleanField(
        verbose_name='Sucesso FINALIZAÇÃO PROPOSTA(QITECH)',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a finalização da proposta foi realizada com sucesso',
    )

    disbursement_account_digit = models.CharField(
        verbose_name='Dígito da conta',
        null=True,
        blank=True,
        max_length=300,
    )

    disbursement_account_number = models.CharField(
        verbose_name='Número da conta',
        null=True,
        blank=True,
        max_length=300,
    )

    disbursement_ispb = models.CharField(
        verbose_name='ISPB do banco',
        null=True,
        blank=True,
        max_length=300,
        help_text='ISPB – Identificador do Sistema de Pagamentos Brasileiro',
    )

    disbursement_branch_number = models.CharField(
        verbose_name='Número da agência',
        null=True,
        blank=True,
        max_length=300,
    )

    credit_operation_status = models.CharField(
        verbose_name='Status da operação de crédito',
        null=True,
        blank=True,
        max_length=255,
    )

    fine_configuration = models.JSONField(
        verbose_name='Fine configuration',
        null=True,
        blank=True,
    )

    document_url_qitech_ccb = models.URLField(
        verbose_name='Link da CCB',
        null=True,
        blank=True,
    )
    dt_desembolso = models.DateField(
        verbose_name='Data de Desembolso',
        null=True,
        blank=True,
        help_text='Data de Desembolso da Operação',
    )
    dt_averbacao = models.DateField(
        verbose_name='Data de Averbação',
        null=True,
        blank=True,
        help_text='Data de Averbação da Operação',
    )

    payment_refused_incoming_data = models.OneToOneField(
        'PaymentRefusedIncomingData',
        verbose_name='Dados do cancelamento do pagamento',
        on_delete=models.SET_NULL,
        related_name='refinanciamento',
        null=True,
        blank=True,
    )

    dt_primeiro_pagamento = models.DateField(
        verbose_name='Data do primeiro pagamento',
        null=True,
        blank=True,
        help_text='Data do primeiro pagamento',
    )

    dt_ultimo_pagamento = models.DateField(
        verbose_name='Data do último pagamento',
        null=True,
        blank=True,
        help_text='Data do último pagamento',
    )

    def get_status_ccb_qi_tech(self):
        return dict(STATUS_CCB).get(self.status_ccb)

    def __str__(self):
        return f'{self.contrato}'

    def flag_status_as_inserting_proposal(self) -> None:
        self.is_proposal_being_inserted = True
        self.save()

    def unflag_status_as_inserting_proposal(self) -> None:
        self.is_proposal_being_inserted = False
        self.save()

    def flag_successfully_inserted_proposal(self) -> None:
        self.sucesso_insercao_proposta = True
        self.save()

    def flag_sucessfully_disbursed_proposal(self) -> None:
        self.sucesso_desembolso_refinanciamento = True
        self.save()

    def flag_sucessfully_finalized_proposal(self) -> None:
        self.sucesso_finalizada_proposta = True
        self.save()

    def flag_ccb_status_as_generated(self) -> None:
        self.ccb_gerada = True
        self.save()

    def update_data_on_qi_tech_success_response(
        self, related_party_key: str, proposal_key: str
    ) -> None:
        self.related_party_key = related_party_key
        self.chave_proposta = proposal_key
        self.status_ccb = EnumStatusCCB.PENDING_SUBIMISSION.value

    def is_there_a_pending_account(self) -> bool:
        if self.payment_refused_incoming_data is not None:
            return bool(self.payment_refused_incoming_data.bank_data)
        return False

    def get_pending_account(self):
        return self.payment_refused_incoming_data.bank_data

    class Meta:
        verbose_name = 'Refinanciamento'
        verbose_name_plural = 'Refinanciamentos'
