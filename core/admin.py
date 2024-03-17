import logging
from datetime import datetime, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta
from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.options import csrf_protect_m
from django.db.models import Q
from django.db.models.query import QuerySet
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from import_export import fields, resources
from import_export.admin import ExportMixin, ImportExportModelAdmin
from import_export.forms import ExportForm
from import_export.widgets import ManyToManyWidget
from rangefilter.filters import DateTimeRangeFilterBuilder
from rest_framework.request import Request
from core.models import BeneficiosContratado, Rogado, Testemunha, RegraTeimosinhaINSS

from api_log.constants import EnumStatusCCB
from api_log.models import RealizaReserva, StatusCobrancaDock
from contract.admin import contrato_resource_export
from contract.constants import (
    STATUS_REPROVADOS,
    EnumContratoStatus,
    EnumSeguradoras,
    EnumTipoMargem,
    EnumTipoPlano,
    EnumTipoProduto,
    NomeAverbadoras,
)
from contract.models.anexo_antifraude import AnexoAntifraude
from contract.models.anexo_contrato import AnexoContrato
from contract.models.regularizacao_contrato import RegularizacaoContrato
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
    ReservaDeMargem,
    RetornoSaque,
    SaqueComplementar,
)
from contract.models.envelope_contratos import EnvelopeContratos
from contract.models.report_settings import ReportSettings
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.admin import RegrasIdadeInline, SubOrgaoInline
from contract.products.cartao_beneficio.choices import STATUS_NAME
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import (
    ClassificacaoSiape,
    Convenios,
    ConvenioSiape,
    EspecieBeneficioINSS,
    FontePagadora,
    OpcoesParcelamento,
    PensaoAlimenticiaINSS,
    ProdutoConvenio,
    Seguros,
    SituacaoBeneficioINSS,
    TipoVinculoSiape,
)
from contract.products.cartao_beneficio.models.planos import PlanosContrato
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.consignado_inss.models.especie import EspecieIN100
from contract.products.consignado_inss.models.inss_beneficio import INSSBeneficioTipo
from contract.products.consignado_inss.models.log_webhook_qitech import LogWebHookQiTech
from contract.products.portabilidade.models.taxa import Taxa
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from contract.services.payment.payment_manager import PaymentManager
from contract.tasks import (
    ExporPortabilityRefinancingReport,
    ExportBenefitCardReport,
    ExportFreeMarginReport,
    ExportPortabilityReport,
    export_contracts,
)
from contract.views import link_formalizacao_envelope
from contract.views import STATUS_APROVADOS, STATUS_PENDENTE
from core import settings
from core.admin_actions.resimular_port_refin.resimular_port_refin_action_executer import (
    ResimularPortRefinActionExecuter,
)
from core.choices import TIPOS_PAGAMENTO
from core.common.enums import BrazilianStatesEnum, EnvironmentEnum
from core.dict_change_list import StatusAndProducts
from core.models import (
    BackofficeConfigs,
    BancosBrasileiros,
    Cliente,
    DossieINSS,
    ParametrosBackoffice,
    Parcela,
    InformativoCancelamentoPlano,
)
from core.models.aceite_in100 import (
    AceiteIN100,
    DadosBeneficioIN100,
    DocumentoAceiteIN100,
    HistoricoAceiteIN100,
)
from core.models.anexo_cliente import AnexoCliente
from core.models.cliente import ClienteCartaoBeneficio, ClienteInss, DadosBancarios
from core.models.parametro_produto import ParametrosProduto
from core.models.termos_de_uso import TermosDeUso
from core.resources import DossieINSSResource
from core.settings import ENVIRONMENT
from core.tasks import (
    envia_info_inss_pine,
    validar_contrato_assync,
    gerar_token_e_buscar_beneficio,
)
from core.tasks.insert_free_margin_proposal import insert_free_margin_proposal
from core.tasks.insert_portability_proposal import insert_portability_proposal
from core.tasks.repair_attachments import AttachmentRepairer
from core.utils import (
    ProductQueryGenerator,
    alterar_status,
    calcular_idade,
    extract_request_options_int_list,
    formatar_valor_grande,
    unify_querysets,
)
from custom_auth.models import FeatureToggle, Produtos, UserProfile
from handlers.banksoft import atualizar_dados_bancarios, comissionamento_banksoft
from handlers.brb import atualizacao_cadastral, envio_dossie, retorno_saque
from handlers.criar_dados_planos import escrever_arquivo_generali
from handlers.dock_consultas import limites_disponibilidades
from handlers.dock_formalizacao import (
    ajustes_financeiros,
    criar_individuo_dock,
    lancamento_saque_parcelado_fatura,
)
from handlers.facil import cancela_reserva
from handlers.in100_cartao import cancela_reserva_dataprev_pine
from handlers.neoconsig import Neoconsig
from handlers.portabilidade_in100 import consulta_beneficio_in100_portabilidade
from handlers.quantum import cancela_reserva_quantum
from handlers.serpro import Serpro
from handlers.solicitar_cobranca_dock import solicitar_cobranca
from handlers.submete_proposta_portabilidade import (
    refuse_product_proposal_qitech,
)
from handlers.tem_saude import adesao, gerar_token_zeus
from handlers.webhook_qitech import API_qitech_documentos, API_qitech_envio_assinatura
from handlers.zetra import Zetra
from simulacao.models import ComissaoTaxa, FaixaIdade
from simulacao.models.Data import Data
from utils.bank import get_client_bank_data
from documentscopy.models import SerasaProtocol
from documentscopy.services import process_serasa_protocol

BENEFIT_CARD = {
    EnumTipoProduto.CARTAO_BENEFICIO,
    EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
    EnumTipoProduto.CARTAO_CONSIGNADO,
    EnumTipoProduto.SAQUE_COMPLEMENTAR,
}
PORTABILITY = {EnumTipoProduto.PORTABILIDADE}
FREE_MARGIN = {EnumTipoProduto.MARGEM_LIVRE}
PORTABILITY_REFINANCING = {EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO}


class ReservaDeMargemInline(admin.StackedInline):
    model = ReservaDeMargem

    def get_extra(self, request, obj=None, **kwargs):
        # Se o objeto ainda não existir, quer dizer que é uma adição nova
        if obj is None:
            return 1

        # Se já existe um relacionamento salvo, então não mostre o extra.
        return 0 if self.model.objects.filter(contrato=obj).exists() else 1

    fieldsets = (
        (
            'DADOS DA AVERBADORA',
            {'fields': (('protocolo',),)},
        ),
        (
            'DADOS DO ANEXO',
            {
                'fields': (
                    ('anexo',),
                    (
                        'nome_anexo',
                        'anexo_url_',
                    ),
                    ('criado_em',),
                )
            },
        ),
    )

    readonly_fields = ('anexo_url_', 'criado_em', 'nome_anexo')

    def anexo_url_(self, obj):
        """
        Retorna o link e thumbnail de visualização para acesso aos anexos dos contratos
        """
        if obj.anexo_url:
            if '.PDF' in obj.nome_anexo.upper():
                return format_html(
                    f'<a href="{obj.anexo_url}" target="_blank"><img src="/static/admin/img/pdf.png" title="Acessar PDF" height="48"></a>'
                )
            elif (
                '.PNG' in obj.nome_anexo.upper()
                or 'JPG' in obj.nome_anexo.upper()
                or 'JPEG' in obj.nome_anexo.upper()
            ):
                return format_html(
                    f'<a href="{obj.anexo_url}" target="_blank"><img src="{obj.anexo_url}" height="80"  title="Acessar imagem" style="border-radius:5px;"></a>'
                )
            else:
                return format_html(
                    f'<a href="{obj.anexo_url}" target="_blank"><img src="/static/admin/img/file.png" title="Acessar documento" height="48"></a>'
                )
        return '-'


class CustomExportForm(ExportForm):
    data_inicio = forms.DateField(required=False, label='Data de Início')
    data_fim = forms.DateField(required=False, label='Data de Fim')


class StatusCobranca(admin.TabularInline):
    model = StatusCobrancaDock
    extra = 0
    max_num = 0
    can_delete = False

    readonly_fields = [field.name for field in StatusCobrancaDock._meta.fields]


class RetornoCancelamentoInline(admin.TabularInline):
    model = InformativoCancelamentoPlano

    extra = 0
    max_num = 0
    can_delete = False

    readonly_fields = [
        field.name for field in InformativoCancelamentoPlano._meta.fields
    ]


class RogadoInline(admin.TabularInline):
    model = Rogado

    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = ['nome', 'grau_parentesco', 'cpf', 'data_nascimento', 'telefone']


class RetornoBeneficioInline(admin.TabularInline):
    model = BeneficiosContratado
    exclude = ('valor_plano',)

    extra = 0
    max_num = 0
    can_delete = False

    fieldsets = (
        (
            'Informações do Contrato',
            {
                'fields': (
                    'id',
                    'id_conta_dock',
                    'id_cartao_dock',
                    'contrato_emprestimo',
                ),
            },
        ),
        (
            'Informações do Plano',
            {
                'fields': ('nome_operadora', 'tipo_plano', 'obrigatorio'),
            },
        ),
        (
            'Valores',
            {
                'fields': (
                    ('format_valor_plano'),
                    ('format_premio_bruto'),
                    ('format_premio_liquido'),
                ),
            },
        ),
        (
            'Outras Informações',
            {
                'fields': (
                    'identificacao_segurado',
                    'nome_plano',
                    'validade',
                    'renovacao_automatica',
                    'qtd_arrecadacao',
                    'carencia',
                    'status',
                ),
            },
        ),
    )

    def format_valor_plano(self, obj):
        if obj.valor_plano is not None:
            return f'R$ {obj.valor_plano}'
        return None

    def format_premio_bruto(self, obj):
        if obj.premio_bruto is not None:
            return f'R$ {obj.premio_bruto}'
        return None

    def format_premio_liquido(self, obj):
        if obj.premio_bruto is not None:
            try:
                valor = formatar_valor_grande(float(obj.premio_liquido))
                return f'R$ {valor}'
            except Exception:
                return 'R$ 0.00'
        return None

    format_premio_bruto.short_description = 'Prêmio Bruto'
    format_premio_liquido.short_description = 'Prêmio Líquido'
    format_valor_plano.short_description = 'Valor Segurado'

    readonly_fields = [field.name for field in BeneficiosContratado._meta.fields] + [
        'format_valor_plano',
        'format_premio_bruto',
        'format_premio_liquido',
    ]

    class Media:
        js = ('admin/custom_admin.js',)


class ProdutoCartaoBeneficio(admin.StackedInline):
    model = CartaoBeneficio
    extra = 0

    def cliente_dados_bancarios(self, obj):
        try:
            last_bank_data = obj.contrato.cliente.cliente_dados_bancarios.last()
        except DadosBancarios.DoesNotExist:
            return 'Nenhum Dado Bancário'

        return format_html(
            f'{last_bank_data}&nbsp; <a class="related-widget-wrapper-link view-related" id="view_id_dados_bancarios" data-href-template="/admin/core/cliente/__fk__/change/?_to_field=id&_changelist_filters=q%3Daderbal#dados-bancarios" title="View selected Dados Bancarios" href="/admin/core/cliente/{obj.contrato.cliente.pk}/change/?_to_field=id&_changelist_filters=q%3Daderbal#dados-bancarios"><img src="/static/admin/img/icon-viewlink.svg" alt="Visualizar"></a>'
        )

    def get_last_bank_data(self, obj):
        try:
            return obj.contrato.cliente.cliente_dados_bancarios.last()
        except DadosBancarios.DoesNotExist:
            return None

    def get_last_realizar_reserva(self, obj):
        try:
            filters = {}
            if obj.reserva:
                filters['reserva'] = obj.reserva
            return obj.contrato.cliente.realiza_reserva_cliente.filter(**filters).last()
        except RealizaReserva.DoesNotExist:
            return None

    def cliente_conta_tipo(self, obj):
        last_bank_data = self.get_last_bank_data(obj)
        return (
            last_bank_data.get_conta_tipo_display()
            if last_bank_data
            else 'Nenhum Dado Bancário'
        )

    def cliente_conta_banco(self, obj):
        last_bank_data = self.get_last_bank_data(obj)
        return last_bank_data.conta_banco if last_bank_data else 'Nenhum Dado Bancário'

    def cliente_conta_agencia(self, obj):
        last_bank_data = self.get_last_bank_data(obj)
        return (
            last_bank_data.conta_agencia if last_bank_data else 'Nenhum Dado Bancário'
        )

    def cliente_conta_numero(self, obj):
        last_bank_data = self.get_last_bank_data(obj)
        return last_bank_data.conta_numero if last_bank_data else 'Nenhum Dado Bancário'

    def cliente_conta_digito(self, obj):
        last_bank_data = self.get_last_bank_data(obj)
        return last_bank_data.conta_digito if last_bank_data else 'Nenhum Dado Bancário'

    def cliente_conta_cpf_titular(self, obj):
        last_bank_data = self.get_last_bank_data(obj)
        return (
            last_bank_data.conta_cpf_titular
            if last_bank_data
            else 'Nenhum Dado Bancário'
        )

    def cliente_conta_tipo_pagamento(self, obj):
        last_bank_data = self.get_last_bank_data(obj)
        return (
            dict(TIPOS_PAGAMENTO).get(last_bank_data.conta_tipo_pagamento)
            if last_bank_data
            else 'Nenhum Dado Bancário'
        )

    def cliente_reserva_codigo_retorno(self, obj):
        last_reserva = self.get_last_realizar_reserva(obj)
        return last_reserva.codigo_retorno if last_reserva else 'Nenhuma Reserva'

    def cliente_reserva_descricao(self, obj):
        if last_reserva := self.get_last_realizar_reserva(obj):
            return last_reserva.descricao or 'Inclusão efetuada com sucesso'
        else:
            return 'Nenhuma Reserva'

    def cliente_reserva_numero(self, obj):
        if last_reserva := self.get_last_realizar_reserva(obj):
            return last_reserva.reserva or 'Não possui reserva'
        else:
            return 'Nenhuma Reserva'

    # Dados Bancários
    cliente_dados_bancarios.short_description = 'CPF Relacionado'
    cliente_conta_tipo.short_description = 'Tipo de conta'
    cliente_conta_banco.short_description = 'Número do banco'
    cliente_conta_agencia.short_description = 'Número da agência'
    cliente_conta_numero.short_description = 'Número da conta'
    cliente_conta_digito.short_description = 'Dígito da conta'
    cliente_conta_cpf_titular.short_description = 'CPF do Titular'
    cliente_conta_tipo_pagamento.short_description = 'Tipo de pagamento'
    cliente_reserva_codigo_retorno.short_description = 'Código de Retorno'
    cliente_reserva_descricao.short_description = 'Descrição Reserva'

    fieldsets = (
        (
            'DADOS DA AVERBADORA',
            {
                'fields': (
                    (
                        'convenio',
                        'status',
                    ),
                    (
                        'folha',
                        'folha_compra',
                        'folha_saque',
                    ),
                    (
                        'verba',
                        'verba_compra',
                        'verba_saque',
                    ),
                    (
                        'senha_servidor',
                        'tipo_margem',
                        'numero_contrato_averbadora',
                    ),
                )
            },
        ),
        (
            'DADOS DO CONTRATO',
            {
                'fields': (
                    (
                        'possui_saque',
                        'saque_parcelado',
                        'possui_saque_complementar',
                    ),
                    (
                        'valor_disponivel_saque',
                        'valor_saque',
                        'valor_parcela',
                    ),
                    (
                        'qtd_parcela_saque_parcelado',
                        'valor_financiado',
                        'valor_total_a_pagar',
                    ),
                    ('tipo_cartao'),
                )
            },
        ),
        (
            'DADOS BANCÁRIOS DO CLIENTE',
            {
                'fields': (
                    (
                        'cliente_dados_bancarios',
                        'cliente_conta_tipo',
                    ),
                    (
                        'cliente_conta_banco',
                        'cliente_conta_agencia',
                    ),
                    (
                        'cliente_conta_numero',
                        'cliente_conta_digito',
                    ),
                    (
                        'cliente_conta_cpf_titular',
                        'cliente_conta_tipo_pagamento',
                    ),
                )
            },
        ),
        (
            'DADOS RESERVA',
            {
                'fields': (
                    (
                        'cliente_reserva_codigo_retorno',
                        'cliente_reserva_descricao',
                        'reserva',
                    ),
                ),
                'classes': ('collapse',),
            },
        ),
        (
            'DADOS BANKSOFT',
            {
                'fields': (
                    ('retorno_solicitacao_saque',),
                    ('numero_proposta_banksoft',),
                ),
                'classes': ('collapse',),
            },
        ),
        (
            'DADOS ADICIONAIS',
            {
                'fields': (
                    (
                        'codigo_instituicao',
                        'carencia',
                    ),
                    ('instituidor',),
                    ('convenio_siape', 'classificacao_siape', 'tipo_vinculo_siape'),
                ),
                'classes': ('collapse',),
            },
        ),
    )

    readonly_fields = (
        'convenio',
        'status',
        'folha',
        'folha_compra',
        'folha_saque',
        'verba',
        'verba_compra',
        'verba_saque',
        'possui_saque',
        'saque_parcelado',
        'possui_saque_complementar',
        'numero_contrato_averbadora',
        'valor_disponivel_saque',
        'valor_saque',
        'valor_parcela',
        'cliente_reserva_codigo_retorno',
        'cliente_reserva_descricao',
        'reserva',
        'retorno_solicitacao_saque',
        'codigo_instituicao',
        'carencia',
        'numero_proposta_banksoft',
        'qtd_parcela_saque_parcelado',
        'valor_financiado',
        'valor_total_a_pagar',
        'cliente_dados_bancarios',
        'cliente_conta_tipo',
        'cliente_conta_banco',
        'cliente_conta_agencia',
        'cliente_conta_numero',
        'cliente_conta_digito',
        'cliente_conta_cpf_titular',
        'cliente_conta_tipo_pagamento',
        'cliente_reserva_codigo_retorno',
        'cliente_reserva_descricao',
        'senha_servidor',
        'tipo_cartao',
        'tipo_margem',
        'tipo_cartao',
        'instituidor',
        'convenio_siape',
        'classificacao_siape',
        'tipo_vinculo_siape',
    )

    def get_readonly_fields(self, request, obj=None):
        # A lista de usuários que podem editar os campos.

        allowed_users = [
            '13345722674',
        ]

        if request.user.identifier in allowed_users:
            return (
                'convenio',
                'folha',
                'folha_compra',
                'folha_saque',
                'verba',
                'verba_compra',
                'verba_saque',
                'possui_saque',
                'saque_parcelado',
                'possui_saque_complementar',
                'numero_contrato_averbadora',
                'valor_disponivel_saque',
                'valor_saque',
                'valor_parcela',
                'cliente_reserva_codigo_retorno',
                'cliente_reserva_descricao',
                'reserva',
                'retorno_solicitacao_saque',
                'codigo_instituicao',
                'carencia',
                'numero_proposta_banksoft',
                'qtd_parcela_saque_parcelado',
                'valor_financiado',
                'valor_total_a_pagar',
                'cliente_dados_bancarios',
                'cliente_conta_tipo',
                'cliente_conta_banco',
                'cliente_conta_agencia',
                'cliente_conta_numero',
                'cliente_conta_digito',
                'cliente_conta_cpf_titular',
                'cliente_conta_tipo_pagamento',
                'cliente_reserva_codigo_retorno',
                'cliente_reserva_descricao',
                'senha_servidor',
                'tipo_cartao',
                'tipo_margem',
                'tipo_cartao',
                'instituidor',
                'convenio_siape',
                'classificacao_siape',
                'tipo_vinculo_siape',
            )
        else:
            return self.readonly_fields


class ProdutoSaqueComplementar(admin.StackedInline):
    model = SaqueComplementar
    extra = 0

    fieldsets = (
        (
            'CONTRATO SAQUE',
            {
                'fields': (
                    ('status',),
                    (
                        'saque_parcelado',
                        'possui_saque',
                    ),
                    (
                        'valor_parcela',
                        'qtd_parcela_saque_parcelado',
                    ),
                    (
                        'valor_saque',
                        'valor_disponivel_saque',
                    ),
                    (
                        'valor_lancado_fatura',
                        'valor_total_a_pagar',
                    ),
                    (
                        'data_solicitacao',
                        'id_cliente_cartao',
                    ),
                )
            },
        ),
        (
            'DADOS BANKSOFT',
            {
                'fields': (
                    ('retorno_solicitacao_saque',),
                    ('numero_proposta_banksoft',),
                ),
                'classes': ('collapse',),
            },
        ),
    )
    readonly_fields = (
        'status',
        'saque_parcelado',
        'possui_saque',
        'valor_parcela',
        'qtd_parcela_saque_parcelado',
        'valor_saque',
        'valor_disponivel_saque',
        'valor_lancado_fatura',
        'valor_total_a_pagar',
        'numero_proposta_banksoft',
        'data_solicitacao',
        'id_cliente_cartao',
        'retorno_solicitacao_saque',
    )

    def get_readonly_fields(self, request, obj=None):
        # A lista de usuários que podem editar os campos.

        allowed_users = [
            '13345722674',
        ]

        if request.user.identifier in allowed_users:
            return (
                'saque_parcelado',
                'possui_saque',
                'valor_parcela',
                'qtd_parcela_saque_parcelado',
                'valor_saque',
                'valor_disponivel_saque',
                'valor_lancado_fatura',
                'valor_total_a_pagar',
                'numero_proposta_banksoft',
                'data_solicitacao',
                'id_cliente_cartao',
                'retorno_solicitacao_saque',
            )
        else:
            return self.readonly_fields


class ProdutoMargemLivre(admin.StackedInline):
    model = MargemLivre

    fieldsets = (
        (
            'STATUS',
            {'fields': (('status',),)},
        ),
        (
            'DADOS DA MARGEM LIVRE',
            {
                'fields': (
                    (
                        'vr_contrato',
                        'vr_liberado_cliente',
                        'vr_seguro',
                        'vr_tarifa_cadastro',
                        'CPF_dados_divergentes',
                    ),
                )
            },
        ),
        (
            'DADOS DA PROPOSTA',
            {
                'fields': (
                    (
                        'chave_proposta',
                        'ccb_gerada',
                        'fl_seguro',
                    ),
                    (
                        'document_key_QiTech_CCB',
                        'collateral_key',
                        'related_party_key',
                    ),
                    ('dt_envio_proposta_CIP',),
                )
            },
        ),
        (
            'DADOS DAS PARCELAS',
            {
                'fields': (
                    (
                        'qtd_parcelas',
                        'vr_parcelas',
                    ),
                    (
                        'dt_vencimento_primeira_parcela',
                        'dt_vencimento_ultima_parcela',
                        'dt_desembolso',
                    ),
                )
            },
        ),
        (
            'DADOS RETORNADOS DO DATAPREV',
            {
                'fields': (
                    (
                        'codigo_dataprev',
                        'dt_retorno_dataprev',
                    ),
                    ('descricao_dataprev',),
                )
            },
        ),
        (
            "RESPOSTAS API's QITECH",
            {
                'fields': (
                    ('sucesso_insercao_proposta', 'insercao_sem_sucesso'),
                    ('sucesso_submissao_proposta', 'motivo_submissao_proposta'),
                    ('sucesso_aceite_proposta', 'motivo_aceite_proposta'),
                    ('sucesso_recusa_proposta', 'motivo_recusa_proposta'),
                    ('display_falha_no_pagamento', 'display_motivo_falha_no_pagamento'),
                    (
                        'sucesso_reapresentacao_pagamento',
                        'motivo_reapresentacao_pagamento',
                    ),
                ),
                'classes': ('collapse',),
            },
        ),
        (
            "RESPOSTAS API's DE DOCUMENTOS QITECH",
            {
                'fields': (
                    ('sucesso_envio_assinatura', 'motivo_envio_assinatura'),
                    (
                        'sucesso_envio_documento_frente_cnh',
                        'motivo_envio_documento_frente_cnh',
                    ),
                    ('sucesso_envio_documento_verso', 'motivo_envio_documento_verso'),
                    ('sucesso_envio_documento_selfie', 'motivo_envio_documento_selfie'),
                    ('sucesso_documentos_linkados', 'motivo_documentos_linkados'),
                ),
                'classes': ('collapse', 'envelope'),
            },
        ),
        (
            'DADOS DE DESEMBOLSO',
            {
                'fields': (
                    ('url', 'amount', 'description'),
                    ('transaction_key', 'origin_transaction_key', 'destination_name'),
                    ('destination_type', 'destination_branch', 'destination_purpose'),
                    (
                        'destination_document',
                        'destination_bank_ispb',
                        'destination_branch_digit',
                    ),
                    (
                        'destination_account_digit',
                        'destination_account_number',
                        'payment_date',
                    ),
                ),
                'classes': ('collapse',),
            },
        ),
    )

    # Disbursement fields
    def _get_disbursement_account_field(self, obj, field_name):
        return (
            getattr(obj.disbursement_account, field_name)
            if hasattr(obj, 'disbursement_account')
            else '-'
        )

    def url(self, obj):
        return self._get_disbursement_account_field(obj, 'url')

    def amount(self, obj):
        return self._get_disbursement_account_field(obj, 'amount')

    def description(self, obj):
        return self._get_disbursement_account_field(obj, 'description')

    def transaction_key(self, obj):
        return self._get_disbursement_account_field(obj, 'transaction_key')

    def origin_transaction_key(self, obj):
        return self._get_disbursement_account_field(obj, 'origin_transaction_key')

    def destination_name(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_name')

    def destination_type(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_type')

    def destination_branch(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_branch')

    def destination_purpose(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_purpose')

    def destination_document(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_document')

    def destination_bank_ispb(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_bank_ispb')

    def destination_branch_digit(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_branch_digit')

    def destination_account_digit(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_account_digit')

    def destination_account_number(self, obj):
        return self._get_disbursement_account_field(obj, 'destination_account_number')

    def payment_date(self, obj):
        return self._get_disbursement_account_field(obj, 'payment_date')

    url.short_description = _('URL')
    amount.short_description = _('Amount')
    description.short_description = _('Description')
    transaction_key.short_description = _('Transaction Key')
    origin_transaction_key.short_description = _('Origin Transaction Key')
    destination_name.short_description = _('Destination Name')
    destination_type.short_description = _('Destination Type')
    destination_branch.short_description = _('Destination Branch')
    destination_purpose.short_description = _('Destination Purpose')
    destination_document.short_description = _('Destination Document')
    destination_bank_ispb.short_description = _('Destination Bank ISPB')
    destination_branch_digit.short_description = _('Destination Branch Digit')
    destination_account_digit.short_description = _('Destination Account Digit')
    destination_account_number.short_description = _('Destination Account Number')
    payment_date.short_description = _('Payment Date')

    readonly_fields = [
        'display_falha_no_pagamento',
        'display_motivo_falha_no_pagamento',
        'url',
        'amount',
        'description',
        'transaction_key',
        'origin_transaction_key',
        'destination_name',
        'destination_type',
        'destination_branch',
        'destination_purpose',
        'destination_document',
        'destination_bank_ispb',
        'destination_branch_digit',
        'destination_account_digit',
        'destination_account_number',
        'payment_date',
    ]

    def has_change_permission(self, request, obj=None):
        return False

    # falha no pagamento
    def display_falha_no_pagamento(self, obj):
        return transform_boolean_in_django_icon(obj.falha_no_pagamento)

    display_falha_no_pagamento.short_description = 'Ocorreu falha no pagamento ?'

    # motivo_falha_no_pagamento
    def display_motivo_falha_no_pagamento(self, obj):
        return obj.motivo_falha_no_pagamento

    display_motivo_falha_no_pagamento.short_description = 'Motivo da falha do pagamento'

    extra = 0


def transform_boolean_in_django_icon(boolean_var: bool) -> str:
    """Transform a boolean in a pretty Django icon for booleans, returning the HTML behind."""
    return format_html(
        '<div title="{}">'
        '<img src="/static/admin/img/icon-{}.svg" alt="{}" title="{}" />'
        '</div>',
        'Hehe title',
        'yes' if boolean_var else 'no',
        boolean_var,
        boolean_var,
    )


class ProdutoPortabilidade(admin.StackedInline):
    model = Portabilidade
    extra = 0
    fieldsets = (
        (
            'STATUS',
            {'fields': (('status',),)},
        ),
        (
            'BANCO',
            {
                'fields': (
                    ('banco',),
                    ('numero_beneficio', 'especie'),
                )
            },
        ),
        (
            'PROPOSTA DIGITADA',
            {
                'fields': (
                    (
                        'numero_contrato',
                        'saldo_devedor',
                        'prazo',
                        'taxa_formatada',
                    ),
                    (
                        'parcela_digitada',
                        'nova_parcela',
                    ),
                    ('CPF_dados_divergentes',),
                )
            },
        ),
        (
            'DADOS QITECH',
            {
                'fields': (
                    ('chave_proposta',),
                    ('chave_operacao',),
                    (
                        'numero_portabilidade',
                        'related_party_key',
                    ),
                )
            },
        ),
        (
            'DADOS RETORNADOS DO DATAPREV',
            {
                'fields': (
                    (
                        'codigo_dataprev',
                        'dt_retorno_dataprev',
                    ),
                    ('descricao_dataprev',),
                )
            },
        ),
        (
            'DADOS RETORNADOS DA CIP',
            {
                'fields': (
                    (
                        'numero_portabilidade_CTC_CIP',
                        'saldo_devedor_atualizado',
                        'numero_parcela_atualizada',
                        'numero_parcelas_atrasadas',
                        'taxa_contrato_original',
                        'valor_parcela_original',
                    ),
                    ('motivo_recusa', 'banco_atacado'),
                    ('dt_envio_proposta_CIP', 'dt_recebimento_saldo_devedor'),
                )
            },
        ),
        (
            'DADOS RECALCULO',
            {
                'fields': (
                    (
                        'taxa_contrato_recalculada',
                        'valor_parcela_recalculada',
                    ),
                )
            },
        ),
        (
            "RESPOSTAS API's QITECH",
            {
                'fields': (
                    ('sucesso_insercao_proposta', 'insercao_sem_sucesso'),
                    ('sucesso_submissao_proposta', 'motivo_submissao_proposta'),
                    ('sucesso_aceite_proposta', 'motivo_aceite_proposta'),
                    ('sucesso_recusa_proposta', 'motivo_recusa_proposta'),
                ),
                'classes': ('collapse',),
            },
        ),
        (
            "RESPOSTAS API's DE DOCUMENTOS QITECH",
            {
                'fields': (
                    ('sucesso_envio_assinatura', 'motivo_envio_assinatura'),
                    (
                        'sucesso_envio_documento_frente_cnh',
                        'motivo_envio_documento_frente_cnh',
                    ),
                    ('sucesso_envio_documento_verso', 'motivo_envio_documento_verso'),
                    ('sucesso_envio_documento_selfie', 'motivo_envio_documento_selfie'),
                    ('sucesso_documentos_linkados', 'motivo_documentos_linkados'),
                ),
                'classes': ('collapse', 'envelope'),
            },
        ),
    )
    readonly_fields = (
        'status',
        'banco',
        'numero_beneficio',
        'especie',
        'numero_contrato',
        'saldo_devedor',
        'prazo',
        'taxa_formatada',
        'parcela_digitada',
        'nova_parcela',
        'CPF_dados_divergentes',
        'chave_proposta',
        'chave_operacao',
        'numero_portabilidade',
        'related_party_key',
        'codigo_dataprev',
        'dt_retorno_dataprev',
        'descricao_dataprev',
        'numero_portabilidade_CTC_CIP',
        'saldo_devedor_atualizado',
        'numero_parcela_atualizada',
        'taxa_contrato_original',
        'valor_parcela_original',
        'motivo_recusa',
        'taxa_contrato_recalculada',
        'valor_parcela_recalculada',
        'sucesso_insercao_proposta',
        'insercao_sem_sucesso',
        'sucesso_submissao_proposta',
        'motivo_submissao_proposta',
        'sucesso_aceite_proposta',
        'motivo_aceite_proposta',
        'sucesso_recusa_proposta',
        'motivo_recusa_proposta',
        'sucesso_envio_assinatura',
        'motivo_envio_assinatura',
        'sucesso_envio_documento_frente_cnh',
        'motivo_envio_documento_frente_cnh',
        'sucesso_envio_documento_verso',
        'motivo_envio_documento_verso',
        'sucesso_envio_documento_selfie',
        'motivo_envio_documento_selfie',
        'sucesso_documentos_linkados',
        'motivo_documentos_linkados',
        'dt_envio_proposta_CIP',
        'dt_recebimento_saldo_devedor',
        'banco_atacado',
        'numero_parcelas_atrasadas',
    )

    @admin.display(description='Taxa')
    def taxa_formatada(self, obj):
        return '%.2f' % obj.taxa if obj.taxa else 0


class ProdutoRefinanciamento(admin.StackedInline):
    model = Refinanciamento
    extra = 0

    fieldsets = (
        (
            '',
            {'fields': (('byx_contract_id',),)},
        ),
        (
            'STATUS',
            {'fields': (('status',),)},
        ),
        (
            'PROPOSTA DIGITADA',
            {
                'fields': (
                    (
                        'saldo_devedor',
                        'taxa_formatada',
                    ),
                    (
                        'troco',
                        'valor_total',
                    ),
                )
            },
        ),
        (
            'DADOS DAS PARCELAS',
            {
                'fields': (
                    (
                        'parcela_digitada',
                        'nova_parcela',
                        'prazo',
                    ),
                    (
                        'dt_desembolso',
                        'dt_averbacao',
                    ),
                    (
                        'dt_primeiro_pagamento',
                        'dt_ultimo_pagamento',
                    ),
                )
            },
        ),
        (
            'DADOS QITECH',
            {
                'fields': (
                    ('chave_proposta',),
                    ('chave_operacao',),
                    (
                        'numero_refinanciamento',
                        'related_party_key',
                    ),
                )
            },
        ),
        (
            'DADOS RETORNADOS DO DATAPREV',
            {
                'fields': (
                    (
                        'codigo_dataprev',
                        'dt_retorno_dataprev',
                    ),
                    ('descricao_dataprev',),
                )
            },
        ),
        (
            'DADOS RECALCULO',
            {
                'fields': (
                    (
                        'troco_recalculado',
                        'valor_total_recalculado',
                        'taxa_contrato_recalculada',
                    ),
                )
            },
        ),
        (
            "RESPOSTAS API's QITECH",
            {
                'fields': (
                    ('sucesso_aceite_proposta', 'motivo_aceite_proposta'),
                    (
                        'sucesso_reapresentacao_pagamento',
                        'motivo_reapresentacao_pagamento',
                    ),
                ),
                'classes': ('collapse',),
            },
        ),
    )
    readonly_fields = (
        'byx_contract_id',
        'status',
        'banco',
        'numero_beneficio',
        'especie',
        'numero_contrato',
        'saldo_devedor',
        'prazo',
        'taxa_formatada',
        'parcela_digitada',
        'nova_parcela',
        'CPF_dados_divergentes',
        'chave_proposta',
        'chave_operacao',
        'numero_refinanciamento',
        'related_party_key',
        'codigo_dataprev',
        'dt_retorno_dataprev',
        'descricao_dataprev',
        'numero_refinanciamento_CTC_CIP',
        'saldo_devedor_atualizado',
        'numero_parcela_atualizada',
        'taxa_contrato_original',
        'valor_parcela_original',
        'motivo_recusa',
        'troco',
        'valor_total',
        'troco_recalculado',
        'valor_total_recalculado',
        'dt_desembolso',
        'dt_averbacao',
        'dt_primeiro_pagamento',
        'dt_ultimo_pagamento',
        'taxa_contrato_recalculada',
        'sucesso_aceite_proposta',
        'motivo_aceite_proposta',
        'sucesso_reapresentacao_pagamento',
        'motivo_reapresentacao_pagamento',
    )

    @admin.display(description='Número do Contrato')
    def byx_contract_id(self, obj) -> str:
        return 'BYX9' + str(obj.contrato.id).rjust(10, '0')

    @admin.display(description='Taxa')
    def taxa_formatada(self, obj):
        return '%.2f' % obj.taxa if obj.taxa else 0


class ValidacaoContratoInline(admin.TabularInline):
    model = ValidacaoContrato
    extra = 0
    readonly_fields = (
        'mensagem_observacao',
        'checked',
        'data_criacao',
        'retorno_hub',
    )


class StatusContratoInline(admin.TabularInline):
    model = StatusContrato
    extra = 0
    list_display = (
        'nome',
        ' descricao_mesa',
        'data_fase_inicial',
        'data_fase_final',
        'created_by',
    )
    exclude = ('descricao_inicial', 'descricao_originacao', 'original_proposals_status')
    readonly_fields = (
        'nome',
        'descricao_inicial',
        'descricao_front',
        'descricao_mesa',
        'data_fase_inicial',
        'data_fase_final',
        'created_by',
    )

    def get_readonly_fields(self, request, obj=None):
        # A lista de usuários que podem editar os campos.

        allowed_users = [
            '13345722674',
        ]

        if request.user.identifier in allowed_users:
            return []
        else:
            return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    extra = 0


class AnexoContratoInline(admin.TabularInline):
    model = AnexoContrato
    exclude = ('nome_anexo', 'anexo_extensao')
    readonly_fields = ('tipo_anexo', 'anexo_url_', 'active')

    fields = ('tipo_anexo', 'anexo_url_', 'active')

    def anexo_url_(self, obj):
        """
        Retorna o link e thumbnail de visualização para acesso aos anexos dos contratos
        """
        if anexo_url := obj.get_attachment_url:
            if obj.anexo_extensao.upper() == 'PDF':
                return format_html(
                    f'<a href="{anexo_url}" target="_blank"><img src="/static/admin/img/pdf.png" title="Acessar PDF" height="48"></a>'
                )
            elif obj.anexo_extensao.upper() in ['PNG', 'JPG', 'JPEG']:
                return format_html(
                    f'<a href="{anexo_url}" target="_blank"><img src="{anexo_url}" height="80"  title="Acessar imagem" style="border-radius:5px;"></a>'
                )
            else:
                return format_html(
                    f'<a href="{anexo_url}" target="_blank"><img src="/static/admin/img/file.png" title="Acessar documento" height="48"></a>'
                )
        return '-'

    extra = 0


class AnexoAntifraudeInline(admin.StackedInline):
    model = AnexoAntifraude
    fieldsets = (
        (
            'ANALISE ANTIFRAUDE',
            {
                'fields': (('nome_anexo', 'anexado_em'),),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.groups.filter(name='Analise Mesa').exists():
            fieldsets += (
                (
                    'DOCUMENTO',
                    {
                        'fields': (
                            'anexo_url',
                            'exibir_arquivo',
                        ),
                    },
                ),
            )
        else:
            fieldsets += (
                (
                    'DOCUMENTO',
                    {
                        'fields': (
                            'anexo_url',
                            'arquivo',
                        ),
                    },
                ),
            )
        return fieldsets

    readonly_fields = (
        'anexo_url',
        'exibir_arquivo',
        'nome_anexo',
        'anexado_em',
    )

    @admin.display(description='URL do documento')
    def attachment_url(self, obj):
        return obj.get_attachment_url

    def exibir_arquivo(self, obj):
        if obj.arquivo:
            # Substitua 'visualizar' pelo texto que você deseja exibir para o link.
            return format_html(
                '<a href="{}" target="_blank">Visualizar</a>', obj.arquivo.url
            )
        else:
            return 'Nenhum arquivo anexado'

    exibir_arquivo.short_description = 'Arquivo'

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if request.user.groups.filter(name='Analise Mesa').exists():
            return ('anexado_em',)
        return readonly_fields

    def has_change_permission(self, request, obj=None):
        return bool(request.user.groups.filter(name='Analise Mesa').exists())

    def has_add_permission(self, request, obj=None):
        return bool(request.user.groups.filter(name='Analise Mesa').exists())

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.groups.filter(name='Analise Mesa').exists())

    extra = 0


class AnexoClienteInline(admin.TabularInline):
    model = AnexoCliente
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        return (
            'cliente',
            'nome_anexo',
            'anexo_extensao',
            'attachment_url',
            'anexado_em',
        )

    @admin.display(description='URL do documento')
    def attachment_url(self, obj):
        return obj.get_attachment_url


class EspecieIN100Admin(ImportExportModelAdmin):
    model = EspecieIN100
    extra = 0


class DadosIN100Inline(admin.StackedInline):
    model = DadosIn100
    extra = 0
    fieldsets = (
        (
            'DADOS IN100',
            {
                'fields': (
                    ('balance_request_key',),
                    (
                        'in100_data_autorizacao',
                        'data_retorno_in100',
                    ),
                    ('retornou_IN100', 'validacao_in100_recalculo', 'tipo_retorno'),
                ),
            },
        ),
        (
            'DADOS DO CARTÃO BENEFÍCIO  ',
            {
                'fields': (
                    (
                        'margem_livre_cartao_beneficio',
                        'limite_cartao_beneficio',
                    ),
                ),
            },
        ),
        (
            'DADOS DO CARTÃO CONSIGNADO',
            {
                'fields': (
                    (
                        'margem_livre_cartao_consignado',
                        'limite_cartao_consignado',
                    ),
                ),
            },
        ),
        (
            'DADOS DO EMPRESTIMO CONSIGNADO',
            {
                'fields': (('valor_margem',),),
            },
        ),
        (
            'DADOS DO BENEFICIO',
            {
                'fields': (
                    (
                        'data_final_beneficio',
                        'data_expiracao_beneficio',
                        'dt_expedicao_beneficio',
                    ),
                    (
                        'situacao_beneficio',
                        'cd_beneficio_tipo',
                        'uf_beneficio',
                        'numero_beneficio',
                    ),
                    (
                        'situacao_pensao',
                        'valor_beneficio',
                        'qt_total_emprestimos',
                        'qt_total_emprestimos_suspensos',
                        'margem_total_beneficio',
                    ),
                    (
                        'concessao_judicial',
                        'possui_representante_legal',
                        'possui_procurador',
                        'possui_entidade_representante',
                        'descricao_recusa',
                        'ultimo_exame_medico',
                    ),
                ),
            },
        ),
        (
            'DADOS DA CHAMADA',
            {
                'fields': (
                    'sucesso_chamada_in100',
                    'chamada_sem_sucesso',
                    'sucesso_envio_termo_in100',
                    'envio_termo_sem_sucesso',
                ),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        return (
            'balance_request_key',
            'in100_data_autorizacao',
            'sucesso_chamada_in100',
            'chamada_sem_sucesso',
            'sucesso_envio_termo_in100',
            'envio_termo_sem_sucesso',
            'situacao_beneficio',
            'cd_beneficio_tipo',
            'uf_beneficio',
            'numero_beneficio',
            'situacao_pensao',
            'valor_margem',
            'valor_beneficio',
            'valor_liquido',
            'qt_total_emprestimos',
            'concessao_judicial',
            'possui_representante_legal',
            'possui_procurador',
            'possui_entidade_representante',
            'descricao_recusa',
            'ultimo_exame_medico',
            'dt_expedicao_beneficio',
            'retornou_IN100',
            'tipo_retorno',
            'validacao_in100_recalculo',
            'vr_disponivel_emprestimo',
            'data_retorno_in100',
            'margem_livre_cartao_beneficio',
            'limite_cartao_beneficio',
            'margem_livre_cartao_consignado',
            'limite_cartao_consignado',
            'data_expiracao_beneficio',
            'dt_expedicao_beneficio',
            'data_final_beneficio',
            'data_expiracao_beneficio',
            'margem_total_beneficio',
            'qt_total_emprestimos_suspensos',
        )


class ProdutoInssCliente(admin.StackedInline):
    model = ClienteInss
    readonly_fields = (
        'cliente',
        'nome_beneficio',
        'nu_beneficio',
        'uf_beneficio',
        'cd_familiar_unico',
        'form_ed_financeira',
        'cd_cliente_parceiro',
    )
    extra = 0


class ProdutoCartaoBenefioCliente(admin.StackedInline):
    model = ClienteCartaoBeneficio
    fieldsets = (
        (
            'INFORMAÇÕES CARTÃO',
            {
                'fields': (
                    (
                        'contrato',
                        'tipo_produto',
                        'tipo_margem',
                    ),
                    (
                        'limite_pre_aprovado',
                        'limite_pre_aprovado_saque',
                        'limite_pre_aprovado_compra',
                    ),
                )
            },
        ),
        (
            'DADOS DE CADASTRO',
            {
                'fields': (
                    (
                        'numero_matricula',
                        'senha_portal',
                        'convenio',
                    ),
                    (
                        'instituidor',
                        'convenio_siape',
                        'classificacao_siape',
                        'tipo_vinculo_siape',
                    ),
                )
            },
        ),
        (
            'DADOS DE MARGEM',
            {
                'fields': (
                    (
                        'margem_atual',
                        'folha',
                        'verba',
                        'reserva',
                    ),
                    (
                        'margem_compra',
                        'folha_compra',
                        'verba_compra',
                        'reserva_compra',
                    ),
                    (
                        'margem_saque',
                        'folha_saque',
                        'verba_saque',
                        'reserva_saque',
                    ),
                )
            },
        ),
        (
            'DADOS DOCK',
            {
                'fields': (
                    (
                        'id_registro_dock',
                        'id_conta_dock',
                        'id_cartao_dock',
                    ),
                    (
                        'id_endereco_dock',
                        'id_telefone_dock',
                    ),
                    (
                        'nome_impresso_dock',
                        'numero_cartao_dock',
                    ),
                    ('status_dock',),
                )
            },
        ),
    )

    readonly_fields = (
        'tipo_produto',
        'tipo_margem',
        'contrato',
        'cliente',
        'senha_portal',
        'numero_matricula',
        'folha',
        'folha_compra',
        'folha_saque',
        'verba',
        'verba_compra',
        'verba_saque',
        'reserva',
        'reserva_compra',
        'reserva_saque',
        'reserva',
        'prazo',
        'margem_atual',
        'margem_compra',
        'margem_saque',
        'id_registro_dock',
        'id_conta_dock',
        'id_cartao_dock',
        'id_endereco_dock',
        'id_telefone_dock',
        'numero_cartao_dock',
        'nome_impresso_dock',
        'status_dock',
        'cartao_tem_saude',
        'token_usuario_tem_saude',
        'convenio',
        'limite_pre_aprovado',
        'limite_pre_aprovado_saque',
        'limite_pre_aprovado_compra',
        'instituidor',
        'convenio_siape',
        'classificacao_siape',
        'tipo_vinculo_siape',
    )

    extra = 0

    def get_readonly_fields(self, request, obj=None):
        # A lista de usuários que podem editar os campos.
        allowed_users = [
            '37302263809',
        ]

        if request.user.identifier == '13345722674':
            return (
                'tipo_produto',
                'tipo_margem',
                'contrato',
                'cliente',
                'senha_portal',
                'numero_matricula',
                'folha',
                'folha_compra',
                'folha_saque',
                'verba',
                'verba_compra',
                'verba_saque',
                'reserva',
                'reserva_compra',
                'reserva_saque',
                'reserva',
                'prazo',
                'id_registro_dock',
                'id_conta_dock',
                'id_cartao_dock',
                'id_endereco_dock',
                'id_telefone_dock',
                'numero_cartao_dock',
                'nome_impresso_dock',
                'status_dock',
                'cartao_tem_saude',
                'token_usuario_tem_saude',
                'convenio',
                'limite_pre_aprovado',
                'limite_pre_aprovado_saque',
                'limite_pre_aprovado_compra',
                'instituidor',
                'convenio_siape',
                'classificacao_siape',
                'tipo_vinculo_siape',
            )
        return [] if request.user.identifier in allowed_users else self.readonly_fields


class DadosBancariosInline(admin.StackedInline):
    model = DadosBancarios
    readonly_fields = (
        'cliente',
        'conta_tipo',
        'conta_banco',
        'conta_agencia',
        'conta_numero',
        'conta_digito',
        'conta_cpf_titular',
        'conta_tipo_pagamento',
    )
    extra = 0

    def get_readonly_fields(self, request, obj: Optional[DadosBancarios] = None):
        allowed_users = ['12851331612', '04568144183']
        if request.user.identifier in allowed_users:
            return []

        readonly_fields = super().get_readonly_fields(request, obj)
        if obj is not None:
            contratos = obj.contrato_set.all()
            for contrato in contratos:
                cartoes_beneficio = contrato.contrato_cartao_beneficio.all()
                if any(
                    cartao_beneficio.status
                    in [
                        ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                    ]
                    for cartao_beneficio in cartoes_beneficio
                ):
                    return ()

                saque_complementar = contrato.contrato_saque_complementar.all()
                if any(
                    saque.status
                    in [
                        ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value,
                    ]
                    for saque in saque_complementar
                ):
                    return ()

        return readonly_fields


class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome_cliente', 'nu_cpf', 'id_confia')
    search_fields = (
        'nome_cliente',
        'nu_cpf',
    )
    exclude = ('IP_Cliente',)
    inlines = [
        ProdutoCartaoBenefioCliente,
        ProdutoInssCliente,
        DadosBancariosInline,
        DadosIN100Inline,
        AnexoClienteInline,
        RetornoBeneficioInline,
        StatusCobranca,
        RetornoCancelamentoInline,
        RogadoInline,
    ]

    fieldsets = (
        (
            'DADOS PESSOAIS',
            {
                'fields': (
                    'tipo_cliente',
                    'nome_cliente',
                    'nu_cpf',
                    'dt_nascimento',
                    'sexo',
                    'estado_civil',
                    'nome_mae',
                    'nome_pai',
                    'escolaridade',
                ),
            },
        ),
        (
            'DOCUMENTAÇÃO',
            {
                'fields': (
                    'documento_tipo',
                    'documento_numero',
                    'documento_data_emissao',
                    'documento_orgao_emissor',
                    'documento_uf',
                ),
            },
        ),
        (
            'NACIONALIDADE',
            {
                'fields': (
                    'naturalidade',
                    'nacionalidade',
                ),
            },
        ),
        (
            'PROFISSÃO',
            {
                'fields': (
                    'ramo_atividade',
                    'tipo_profissao',
                    'renda',
                    'vr_patrimonio',
                    'possui_procurador',
                    'ppe',
                ),
            },
        ),
        (
            'ENDEREÇO',
            {
                'fields': (
                    'tipo_logradouro',
                    'endereco_residencial_tipo',
                    'endereco_logradouro',
                    'endereco_numero',
                    'endereco_complemento',
                    'endereco_bairro',
                    'endereco_cidade',
                    'endereco_uf',
                    'endereco_cep',
                    'tempo_residencia',
                ),
            },
        ),
        (
            'CONTATO',
            {
                'fields': (
                    'email',
                    'telefone_celular',
                    'telefone_residencial',
                ),
            },
        ),
        (
            'CONJUGUE',
            {
                'fields': (
                    'conjuge_nome',
                    'conjuge_cpf',
                    'conjuge_data_nascimento',
                ),
            },
        ),
    )
    change_form_template = 'admin/cliente/tela_cliente_admin.html'
    change_list_template = 'admin/cliente/change_list_clientes.html'

    def get_readonly_fields(self, request, obj=None):
        allowed_users = ['37302263809', '13345722674']
        if request.user.identifier in allowed_users:
            return []  # Aqui, nenhum campo é somente leitura para esses usuários.
        return (
            (
                'tipo_cliente',
                'nome_cliente',
                'nu_cpf',
                'dt_nascimento',
                'sexo',
                'estado_civil',
                'nome_pai',
                'naturalidade',
                'nacionalidade',
                'ramo_atividade',
                'tipo_profissao',
                'renda',
                'vr_patrimonio',
                'possui_procurador',
                'ppe',
                'tipo_logradouro',
                'endereco_residencial_tipo',
                'endereco_logradouro',
                'endereco_numero',
                'endereco_complemento',
                'endereco_bairro',
                'endereco_cidade',
                'endereco_uf',
                'endereco_cep',
                'email',
                'telefone_celular',
                'telefone_residencial',
                'conjuge_nome',
                'conjuge_data_nascimento',
                'cd_familiar_unico',
                'form_ed_financeira',
                'IP_Cliente',
                'conjuge_cpf',
                'tempo_residencia',
                'escolaridade',
            )
            if request.user.groups.filter(name='Analise Mesa').exists()
            else (
                'tipo_cliente',
                'nome_cliente',
                'nu_cpf',
                'dt_nascimento',
                'sexo',
                'estado_civil',
                'nome_pai',
                'naturalidade',
                'nacionalidade',
                'ramo_atividade',
                'tipo_profissao',
                'renda',
                'vr_patrimonio',
                'possui_procurador',
                'ppe',
                'tipo_logradouro',
                'endereco_residencial_tipo',
                'endereco_logradouro',
                'endereco_numero',
                'endereco_complemento',
                'endereco_bairro',
                'endereco_cidade',
                'endereco_uf',
                'endereco_cep',
                'email',
                'telefone_celular',
                'telefone_residencial',
                'conjuge_nome',
                'conjuge_data_nascimento',
                'cd_familiar_unico',
                'form_ed_financeira',
                'IP_Cliente',
                'conjuge_cpf',
                'tempo_residencia',
                'nome_mae',
                'documento_tipo',
                'documento_numero',
                'documento_data_emissao',
                'documento_orgao_emissor',
                'documento_uf',
                'escolaridade',
            )
        )

    def has_delete_permission(self, request, obj=None):
        return True


class ParcelaInline(admin.TabularInline):
    model = Parcela
    readonly_fields = (
        'nuParcela',
        'dtVencimento',
        'vrParcela',
        'recebido_facta',
        'paga',
        'dtPagamento',
        'vrPago',
        'vrJuros',
        'vrMulta',
        'cdOrigemBaixa',
        'dtCompra',
        'vrParcelaVencimento',
        'vrCompra',
        'vrPrincipalParcela',
        'saldoDevedorParcela',
        'txNegociacao',
        'vrCessaoFIDC',
        'dtUltimaAtualizacao',
        'nuCodParceiro',
    )


class LogWebHookQiTechInline(admin.TabularInline):
    model = LogWebHookQiTech
    extra = 0


class RetornoSaqueInline(admin.TabularInline):
    model = RetornoSaque
    fields = (
        'NumeroProposta',
        'valorTED',
        'Status',
        'Observacao',
    )
    readonly_fields = (
        'NumeroProposta',
        'valorTED',
        'Status',
        'Observacao',
    )
    extra = 0


class PlanosContratoInline(admin.TabularInline):
    model = PlanosContrato
    fields = (
        'contrato',
        'plano',
        'valor_plano',
    )
    readonly_fields = (
        'contrato',
        'plano',
        'valor_plano',
    )
    extra = 0


class TestemunhaInline(admin.TabularInline):
    model = Testemunha.contratos.through
    verbose_name = 'Testemunha'
    verbose_name_plural = 'Testemunhas'

    extra = 0
    max_num = 0
    can_delete = False
    fields = ['nome', 'cpf', 'data_nascimento', 'telefone']
    readonly_fields = ['nome', 'cpf', 'data_nascimento', 'telefone']

    def nome(self, obj):
        return obj.testemunha.nome

    def cpf(self, obj):
        return obj.testemunha.cpf

    def data_nascimento(self, obj):
        return obj.testemunha.data_nascimento

    def telefone(self, obj):
        return obj.testemunha.telefone


class RegularizacaoContratoInline(admin.TabularInline):
    model = RegularizacaoContrato
    readonly_fields = (
        'tipo_pendencia',
        'data_pendencia',
        'mensagem_pendencia',
        'anexo_url_pendencia_',
        'nome_pendencia',
        'mensagem_regularizacao',
        'data_regularizacao',
        'anexo_url_regularizacao_',
        'nome_regularizacao',
    )

    fields = (
        'tipo_pendencia',
        'data_pendencia',
        'mensagem_pendencia',
        'anexo_url_pendencia_',
        'nome_pendencia',
        'mensagem_regularizacao',
        'data_regularizacao',
        'anexo_url_regularizacao_',
        'nome_regularizacao',
    )

    def anexo_url_pendencia_(self, obj):
        """
        Retorna o link e thumbnail de visualização para acesso aos anexos dos contratos
        """
        if anexo_url_pendencia := obj.get_attachment_url_pendencia_url:
            if obj.anexo_extensao_pendencia.upper() == 'PDF':
                return format_html(
                    f'<a href="{anexo_url_pendencia}" target="_blank"><img src="/static/admin/img/pdf.png" title="Acessar PDF" height="48"></a>'
                )
            elif obj.anexo_extensao_pendencia.upper() in ['PNG', 'JPG', 'JPEG']:
                return format_html(
                    f'<a href="{anexo_url_pendencia}" target="_blank"><img src="{anexo_url_pendencia}" height="80"  title="Acessar imagem" style="border-radius:5px;"></a>'
                )
            else:
                return format_html(
                    f'<a href="{anexo_url_pendencia}" target="_blank"><img src="/static/admin/img/file.png" title="Acessar documento" height="48"></a>'
                )
        return '-'

    def anexo_url_regularizacao_(self, obj):
        """
        Retorna o link e thumbnail de visualização para acesso aos anexos dos contratos
        """
        if anexo_url_regularizacao := obj.get_attachment_url_regularizacao:
            if obj.anexo_extensao_regularizacao.upper() == 'PDF':
                return format_html(
                    f'<a href="{anexo_url_regularizacao}" target="_blank"><img src="/static/admin/img/pdf.png" title="Acessar PDF" height="48"></a>'
                )
            elif obj.anexo_extensao_regularizacao.upper() in ['PNG', 'JPG', 'JPEG']:
                return format_html(
                    f'<a href="{anexo_url_regularizacao}" target="_blank"><img src="{anexo_url_regularizacao}" height="80"  title="Acessar imagem" style="border-radius:5px;"></a>'
                )
            else:
                return format_html(
                    f'<a href="{anexo_url_regularizacao}" target="_blank"><img src="/static/admin/img/file.png" title="Acessar documento" height="48"></a>'
                )
        return '-'

    extra = 0


class StatusListFilter(admin.SimpleListFilter):
    title = _('Status')  # Nome que será exibido na interface de administração
    parameter_name = 'status'  # Nome do parâmetro na URL

    def lookups(self, request, model_admin):
        return (
            (
                '65',
                _('VALIDAÇÕES AUTOMÁTICAS'),
            ),
            (
                '33',
                _('SALDO RETORNADO'),
            ),  # Você pode adicionar outras opções de filtro aqui
            (
                '37',
                _('AGUARDANDO AVERBACAO'),
            ),  # Você pode adicionar outras opções de filtro aqui
            (
                '41',
                _('REPROVADO CIP/REC'),
            ),  # Você pode adicionar outras opções de filtro aqui
            (
                '34',
                _('CONFIRMA PAGAMENTO'),
            ),  # Você pode adicionar outras opções de filtro aqui
            ('38', _('FINALIZADO')),  # Você pode adicionar outras opções de filtro aqui
            *(
                (status, status_name)
                for status, status_name in sorted(
                    STATUS_NAME, key=lambda status: status[1]
                )
            ),
        )

    def queryset(self, request, queryset):
        if self.value() == '13':
            return queryset.filter(
                Q(contrato_portabilidade__status=13)
                | Q(contrato_margem_livre__status=13)
                | Q(contrato_refinanciamento__status=13)
            ).order_by('ultima_atualizacao')
        elif self.value() == '19':
            return queryset.filter(
                Q(contrato_portabilidade__status=19)
                | Q(contrato_margem_livre__status=19)
                | Q(contrato_refinanciamento__status=19)
            ).order_by('ultima_atualizacao')
        elif self.value() == '33':
            ids_contratos_status = (
                StatusContrato.objects.filter(
                    nome=ContractStatus.SALDO_RETORNADO.value,
                    data_fase_inicial__date=timezone.localdate(),
                )
                .values_list('contrato_id', flat=True)
                .distinct()
            )
            return queryset.filter(
                Q(
                    contrato_portabilidade__status__in=(
                        STATUS_APROVADOS + STATUS_REPROVADOS + STATUS_PENDENTE
                    )
                )
                & Q(
                    id__in=ids_contratos_status
                )  # Usa os IDs dos contratos obtidos anteriormente
            ).order_by('ultima_atualizacao')
        elif self.value() == '34':
            return queryset.filter(
                Q(contrato_portabilidade__status=34)
                | Q(contrato_margem_livre__status=34)
                | Q(contrato_refinanciamento__status=34)
            ).order_by('ultima_atualizacao')
        elif self.value() == '37':
            return queryset.filter(
                Q(contrato_portabilidade__status=37)
                | Q(contrato_margem_livre__status=37)
                | Q(contrato_refinanciamento__status=37)
            ).order_by('ultima_atualizacao')
        elif self.value() == '38':
            return queryset.filter(
                Q(contrato_portabilidade__status=38)
                | Q(contrato_margem_livre__status=38)
                | Q(contrato_refinanciamento__status=38)
            ).order_by('ultima_atualizacao')
        elif self.value() == '41':
            return queryset.filter(
                Q(contrato_portabilidade__status__in=STATUS_REPROVADOS)
                | Q(contrato_margem_livre__status__in=STATUS_REPROVADOS)
                | Q(contrato_refinanciamento__status__in=STATUS_REPROVADOS)
            ).order_by('ultima_atualizacao')

        elif self.value() == '42':
            return queryset.filter(
                Q(contrato_portabilidade__status=42)
                | Q(contrato_margem_livre__status=42)
                | Q(contrato_refinanciamento__status=42)
            ).order_by('ultima_atualizacao')
        elif self.value() == '43':
            return queryset.filter(
                Q(contrato_portabilidade__status=43)
                | Q(contrato_margem_livre__status=43)
                | Q(contrato_refinanciamento__status=43)
            ).order_by('ultima_atualizacao')
        elif self.value() == '44':
            return queryset.filter(
                Q(contrato_portabilidade__status=44)
                | Q(contrato_margem_livre__status=44)
                | Q(contrato_refinanciamento__status=44)
            ).order_by('ultima_atualizacao')
        elif self.value() == '55':
            return queryset.filter(contrato_refinanciamento__status=55)
        elif self.value() == '56':
            return queryset.filter(contrato_refinanciamento__status=56)
        elif self.value() == '58':
            return queryset.filter(contrato_refinanciamento__status=58)
        elif self.value() == '65':
            return queryset.filter(
                Q(contrato_portabilidade__status=65)
                | Q(contrato_margem_livre__status=65)
                | Q(contrato_refinanciamento__status=65)
            ).order_by('ultima_atualizacao')
        elif self.value() == '1000':
            ids_contratos_status = (
                StatusContrato.objects.filter(
                    nome=ContractStatus.SALDO_RETORNADO.value,
                    data_fase_inicial__date=timezone.localdate(),
                )
                .values_list('contrato_id', flat=True)
                .distinct()
            )
            return queryset.filter(
                Q(contrato_portabilidade__status__in=STATUS_APROVADOS)
                & Q(
                    id__in=ids_contratos_status
                )  # Usa os IDs dos contratos obtidos anteriormente
            ).order_by('ultima_atualizacao')
        elif self.value() == '1001':
            ids_contratos_status = (
                StatusContrato.objects.filter(
                    nome=ContractStatus.SALDO_RETORNADO.value,
                    data_fase_inicial__date=timezone.localdate(),
                )
                .values_list('contrato_id', flat=True)
                .distinct()
            )
            return queryset.filter(
                Q(contrato_portabilidade__status__in=STATUS_PENDENTE)
                & Q(
                    id__in=ids_contratos_status
                )  # Usa os IDs dos contratos obtidos anteriormente
            ).order_by('ultima_atualizacao')
        elif self.value() == '1002':
            ids_contratos_status = (
                StatusContrato.objects.filter(
                    nome=ContractStatus.SALDO_RETORNADO.value,
                    data_fase_inicial__date=timezone.localdate(),
                )
                .values_list('contrato_id', flat=True)
                .distinct()
            )
            return queryset.filter(
                Q(contrato_portabilidade__status__in=STATUS_REPROVADOS)
                & Q(
                    id__in=ids_contratos_status
                )  # Usa os IDs dos contratos obtidos anteriormente
            ).order_by('ultima_atualizacao')
        elif self.value():
            return queryset.filter(
                Q(contrato_cartao_beneficio__status=int(self.value()))
                | Q(contrato_saque_complementar__status=int(self.value()))
                | Q(contrato_portabilidade__status=int(self.value()))
                | Q(contrato_refinanciamento__status=int(self.value()))
                | Q(contrato_margem_livre__status=int(self.value()))
            ).order_by('ultima_atualizacao')
        return queryset


class ConvenioListFilter(admin.SimpleListFilter):
    title = 'Convênios - Cartão'
    parameter_name = 'convenio'

    def lookups(self, request, model_admin):
        return tuple(
            CartaoBeneficio.objects.select_related('convenio')
            .filter(convenio__isnull=False)
            .values_list('convenio_id', 'convenio__nome')
            .distinct()
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value and value.isdigit():
            cartao_beneficios_id = list(
                CartaoBeneficio.objects.select_related('convenio', 'contrato')
                .filter(convenio__id=int(value))
                .values_list('contrato__pk', flat=True)
            )
            queryset = queryset.filter(pk__in=cartao_beneficios_id)
        return queryset


class ContratoAdmin(ImportExportModelAdmin):
    change_list_template = 'admin/contract/contrato/change_list.html'
    export_template_name = 'admin/export_pages/export_contratos.html'
    ContratoResource = contrato_resource_export(isFront=False)
    resource_class = ContratoResource
    export_form = CustomExportForm
    inlines = [
        ProdutoCartaoBeneficio,
        ProdutoSaqueComplementar,
        ProdutoMargemLivre,
        ProdutoPortabilidade,
        ProdutoRefinanciamento,
        AnexoContratoInline,
        AnexoAntifraudeInline,
        ParcelaInline,
        StatusContratoInline,
        ValidacaoContratoInline,
        LogWebHookQiTechInline,
        RetornoSaqueInline,
        ReservaDeMargemInline,
        RegularizacaoContratoInline,
        PlanosContratoInline,
        TestemunhaInline,
    ]

    def changelist_view(self, request, extra_context=None):
        products_status = StatusAndProducts()

        if extra_context is None:
            extra_context = {}

        extra_context['change_list_product'] = products_status._assemble_products()
        extra_context['change_list_status'] = products_status._assemble_status()

        return super().changelist_view(request, extra_context=extra_context)

    def get_actions(self, request):
        return super().get_actions(request)

    def convert_init_date(self, data_str) -> datetime:
        return datetime.strptime(data_str, '%Y-%m-%d')

    def convert_end_date(self, data_str) -> datetime:
        return datetime.strptime(data_str, '%Y-%m-%d').replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

    def get_file_name(self, request: Request) -> str:
        """Based on the parameters received in the request object
        build a specific file name to set on the email attachment name
        without extension."""

        def get_enum_tipo_produto_name(number):
            for name, value in EnumTipoProduto.__dict__.items():
                if isinstance(value, int) and value == number:
                    return name
            return ''

        # build selected product titles
        product_set = extract_request_options_int_list(request, 'tipo_produto')
        product_titles = '-'.join([get_enum_tipo_produto_name(n) for n in product_set])

        # build data
        date_str = localtime().strftime('%Y-%m-%d')
        filename = f'{product_titles}-{date_str}'
        return filename

    def export_action(self, request):
        if getattr(self.get_export_form, 'is_original', False):
            form_type = self.get_export_form_class()
        else:
            form_type = self.get_export_form()
        formats = self.get_export_formats()
        form = form_type(
            formats, request.POST or None, resources=self.get_export_resource_classes()
        )
        if form.is_valid():
            # get queryset
            queryset = self.get_export_queryset(request)
            queryset_pks = list(queryset.values_list('pk', flat=True))

            # get file_name
            file_name = self.get_file_name(request)

            # get email Subject and Body from database
            report_settings = ReportSettings.objects.first()
            subject = ''
            body = ''

            if report_settings is None:
                subject = 'Relatório_BYX'
                body = 'Segue relatório dos contratos no período selecionado.'
            else:
                subject = report_settings.subject
                body = report_settings.msg_email

            # export report by email asynchronously
            export_contracts.delay(
                int(form.cleaned_data['file_format']),
                queryset_pks,
                str(request.user.email),
                file_name,
                subject,
                body,
            )

            # show success message
            success_message = 'O relatório será encaminhado por e-mail.'
            success_message += ' %d contratos encontrados.' % len(queryset)
            messages.success(
                request,
                success_message,
            )
            return HttpResponseRedirect(request.get_full_path())

        context = self.get_export_context_data()

        context.update(self.admin_site.each_context(request))

        context['title'] = _('Export')
        context['form'] = form
        context['opts'] = self.model._meta
        request.current_app = self.admin_site.name
        return TemplateResponse(request, [self.export_template_name], context)

    def get_context_data(self, **kwargs):
        # Ordenando a tupla STATUS_NAME pelo nome do status (segundo elemento de cada tupla)
        STATUS_NAME_SORTED_BY_NAME = sorted(STATUS_NAME, key=lambda status: status[1])

        status_list = [
            {'status': status, 'status_name': status_name}
            for status, status_name in STATUS_NAME_SORTED_BY_NAME
        ]
        return {'status_list': status_list}

    def get_export_queryset(self, request: Request) -> QuerySet:
        """Define export queryset."""
        # extract parameters from request
        export_type = request.POST.get('tipo_exportacao')
        product_types = extract_request_options_int_list(request, 'tipo_produto')
        init_date = self.convert_init_date(request.POST.get('data_inicio'))
        end_date = self.convert_end_date(request.POST.get('data_fim'))
        status = request.POST.get('status')
        if status is not None:
            status = int(request.POST.get('status'))

        # filter product type and data range
        queryset = Contrato.objects.filter(
            tipo_produto__in=product_types, criado_em__range=(init_date, end_date)
        )

        # include all status if status option is 0 (All Status)
        if status != 0:
            status_filters = (
                Q(contrato_cartao_beneficio__status=status)
                | Q(contrato_saque_complementar__status=status)
                | Q(contrato_portabilidade__status=status)
                | Q(contrato_refinanciamento__status=status)
                | Q(contrato_margem_livre__status=status)
            )

            queryset = queryset.filter(status_filters).distinct()

        # filter product
        product_query_generator = ProductQueryGenerator(
            queryset=queryset,
            export_type=export_type,
            init_date=init_date,
            end_date=end_date,
            status=status,
            product_types=product_types,
        )
        for args in (
            (ExportBenefitCardReport, BENEFIT_CARD),
            (ExportPortabilityReport, PORTABILITY),
            (ExportFreeMarginReport, FREE_MARGIN),
            (ExporPortabilityRefinancingReport, PORTABILITY_REFINANCING),
        ):
            product_query_generator.add_querysets_for_products(*args)

        queryset = unify_querysets(
            model=Contrato, querysets=product_query_generator.generated_querysets
        )

        # order
        queryset = queryset.order_by('criado_em')

        return queryset

    # Metodo que restringe a visualizacao de certos contratos na listagem do django
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.groups.filter(name='Analise Mesa').exists():
            return qs.filter(
                Q(
                    contrato_portabilidade__status=ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value
                )
                | Q(
                    contrato_portabilidade__status=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                )
                | Q(
                    contrato_cartao_beneficio__status=ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value
                )
                | Q(
                    contrato_cartao_beneficio__status=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                )
                | Q(
                    contrato_margem_livre__status=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                )
                | Q(
                    contrato_margem_livre__status=ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value
                )
                | Q(
                    contrato_saque_complementar__status=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                )
                | Q(
                    contrato_saque_complementar__status=ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value
                )
            )
        elif request.user.groups.filter(name='Mesa Corban').exists():
            return qs.filter(
                Q(
                    contrato_portabilidade__status=ContractStatus.CHECAGEM_MESA_CORBAN.value
                )
                | Q(
                    contrato_cartao_beneficio__status=ContractStatus.CHECAGEM_MESA_CORBAN.value
                )
            )

        elif request.user.groups.filter(name='Analise manual de contratos').exists():
            return qs.filter(
                Q(
                    contrato_digitacao_manual=True,
                    contrato_cartao_beneficio__status=ContractStatus.AVERBACAO_MESA_DE_FORMALIZACAO.value,
                )
                | Q(
                    contrato_digitacao_manual=True,
                    contrato_digitacao_manual_validado=True,
                    contrato_cartao_beneficio__status=ContractStatus.REVISAO_MESA_DE_FORMALIZACAO.value,
                )
            )
        elif request.user.groups.filter(name='Mesa de Averbação').exists():
            return qs.filter(
                Q(
                    contrato_cartao_beneficio__status=ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value,
                )
                | Q(
                    contrato_cartao_beneficio__status=ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value,
                )
                | Q(
                    contrato_cartao_beneficio__status=ContractStatus.REGULARIZADA_MESA_AVERBACAO.value,
                )
            )

        elif (
            request.user.groups.filter(name='Backoffice').exists()
            or request.user.groups.filter(name='Master').exists()
            or request.user.groups.filter(
                name='Central de Atendimento - Cliente'
            ).exists()
        ):
            return qs.all()

        elif request.user.groups.filter(
            name='Revisao de analise manual contrato'
        ).exists():
            return qs.filter(
                contrato_digitacao_manual=True,
                contrato_digitacao_manual_validado=True,
                contrato_cartao_beneficio__status=ContractStatus.REVISAO_MESA_DE_FORMALIZACAO.value,
            )

        # If the user is not in any of the mentioned groups
        else:
            status_excluidos = [
                ContractStatus.REVISAO_MESA_DE_FORMALIZACAO.value,
                ContractStatus.AVERBACAO_MESA_DE_FORMALIZACAO.value,
                # ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value,
            ]

            # Contratos com contrato_digitacao_manual=True e status não na lista
            qs_digitacao_manual_true = qs.filter(
                contrato_digitacao_manual=True
            ).exclude(contrato_cartao_beneficio__status__in=status_excluidos)

            # Contratos com contrato_digitacao_manual=False
            qs_digitacao_manual_false = qs.filter(contrato_digitacao_manual=False)

            # Combina os dois QuerySets
            return qs_digitacao_manual_true | qs_digitacao_manual_false

        return qs

    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            # Exemplo de condição: se o atributo "tipo_produto" do contrato for "cartao_beneficio".
            if obj and obj.tipo_produto in [
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ]:
                # Condição para verificar se contrato_digitacao_manual está marcado e o inline é ReservadeMargemInline
                if (
                    isinstance(inline, ReservaDeMargemInline)
                    and obj.contrato_digitacao_manual
                ):
                    yield inline.get_formset(request, obj), inline
                elif isinstance(
                    inline,
                    (
                        ProdutoCartaoBeneficio,
                        AnexoContratoInline,
                        StatusContratoInline,
                        RegularizacaoContratoInline,
                        RetornoSaqueInline,
                        ValidacaoContratoInline,
                        PlanosContratoInline,
                    ),
                ):
                    yield inline.get_formset(request, obj), inline
            if obj and obj.tipo_produto in [
                EnumTipoProduto.MARGEM_LIVRE,
                EnumTipoProduto.INSS,
                EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
            ]:
                if isinstance(
                    inline,
                    (
                        ProdutoMargemLivre,
                        ParcelaInline,
                        StatusContratoInline,
                        ValidacaoContratoInline,
                        AnexoContratoInline,
                        DadosIN100Inline,
                        TestemunhaInline,
                        LogWebHookQiTechInline,
                    ),
                ):
                    yield inline.get_formset(request, obj), inline
            if obj and obj.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if isinstance(
                    inline,
                    (
                        ProdutoPortabilidade,
                        StatusContratoInline,
                        AnexoContratoInline,
                        AnexoAntifraudeInline,
                        ValidacaoContratoInline,
                        DadosIN100Inline,
                        TestemunhaInline,
                        ParcelaInline,
                    ),
                ):
                    yield inline.get_formset(request, obj), inline

            if (
                obj
                and obj.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
            ):
                if isinstance(
                    inline,
                    (
                        ProdutoPortabilidade,
                        ProdutoRefinanciamento,
                        StatusContratoInline,
                        AnexoContratoInline,
                        AnexoAntifraudeInline,
                        ValidacaoContratoInline,
                        DadosIN100Inline,
                        TestemunhaInline,
                        ParcelaInline,
                    ),
                ):
                    yield inline.get_formset(request, obj), inline

            if obj and obj.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                if isinstance(
                    inline,
                    (
                        ProdutoSaqueComplementar,
                        AnexoContratoInline,
                        StatusContratoInline,
                        RetornoSaqueInline,
                        ValidacaoContratoInline,
                        PlanosContratoInline,
                    ),
                ):
                    yield inline.get_formset(request, obj), inline
            elif not obj:
                yield inline.get_formset(request, obj), inline

    @staticmethod
    def __get_contract_status(contract: Contrato) -> Optional[str]:
        if refinancing := contract.contrato_refinanciamento.filter(
            contrato_id=contract.id
        ).first():
            portability = contract.contrato_portabilidade.filter(
                contrato_id=contract.id
            ).first()
            if portability.status == ContractStatus.INT_FINALIZADO.value:
                return refinancing.status
            else:
                return portability.status
        elif portability := contract.contrato_portabilidade.filter(
            contrato_id=contract.id
        ).first():
            return portability.status
        elif free_margin := contract.contrato_margem_livre.filter(
            contrato_id=contract.id
        ).first():
            return free_margin.status
        return None

    @csrf_protect_m
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        obj = None
        if object_id:
            obj = self.get_object(request, object_id)
            if extra_context is None:
                extra_context = {}
        proposal_status = None
        if contrato := obj:
            proposal_status = self.__get_contract_status(contract=contrato)
            if contrato.tipo_produto in [
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ]:
                cartao_beneficio = CartaoBeneficio.objects.get(contrato=contrato)
                extra_context['status_contrato'] = cartao_beneficio.status
                extra_context['convenio_inss'] = cartao_beneficio.convenio.convenio_inss
                extra_context['tipo_produto'] = contrato.tipo_produto
                extra_context['adicional_enviado'] = contrato.adicional_enviado
                extra_context['contracheque_enviado'] = contrato.contracheque_enviado
                extra_context['selfie_enviada'] = contrato.selfie_enviada
                extra_context['enviado_comprovante_residencia'] = (
                    contrato.enviado_comprovante_residencia
                )
                extra_context['enviado_documento_pessoal'] = (
                    contrato.enviado_documento_pessoal
                )
                extra_context['contrato_digitacao_manual'] = (
                    contrato.contrato_digitacao_manual
                )
                if contrato.contrato_digitacao_manual:
                    extra_context['revisa_analise_manual'] = False
                    if request.user.groups.filter(
                        Q(name='Revisao de analise manual contrato')
                        | Q(name='Analise manual de contratos')
                    ).exists():
                        extra_context['revisa_analise_manual'] = True
                    if ReservaDeMargem.objects.filter(contrato=contrato).exists():
                        reserva = ReservaDeMargem.objects.filter(
                            contrato=contrato
                        ).last()
                        extra_context['anexo_inserido_protocolo'] = bool(
                            reserva.anexo_url and reserva.protocolo
                        )

                extra_context['habilitar_botao_aprovar'] = (
                    self.card_should_show_approve_button(
                        extra_context['status_contrato'], request.user.groups, contrato
                    )
                )
                extra_context['habilitar_botao_pendenciar'] = (
                    self.card_should_show_pendency_button(
                        extra_context['status_contrato'], request.user.groups
                    )
                )
                extra_context['habilitar_botao_reprovar'] = (
                    self.card_should_show_reprove_button(
                        extra_context['status_contrato'], request.user.groups
                    )
                )

            elif contrato.tipo_produto in [
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.MARGEM_LIVRE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ]:
                # Define se os botões irão aparecer no admin
                habilitar_botao_aprovar = True
                habilitar_botao_aprovar_proposta = True
                habilitar_botao_reprovar = True
                habilitar_botao_pendenciar = True
                if request.user.groups.filter(
                    name='SAC-Central de Atendimento'
                ).exists():
                    habilitar_botao_aprovar = False
                    habilitar_botao_aprovar_proposta = False
                    habilitar_botao_reprovar = False
                    habilitar_botao_pendenciar = False
                elif request.user.groups.filter(name='BACKOFFICE').exists():
                    habilitar_botao_aprovar = False
                    habilitar_botao_aprovar_proposta = False
                    habilitar_botao_pendenciar = False

                # !TODO Pegar os parâmetros de produto daquele produto específico.

                # Coloca o status_contrato no contexto do admin
                if contrato.tipo_produto in (
                    EnumTipoProduto.PORTABILIDADE,
                    EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                ):
                    parametro_produto = ParametrosProduto.objects.filter(
                        tipoProduto=contrato.tipo_produto
                    ).first()
                    if parametro_produto.aprovar_automatico:
                        habilitar_botao_aprovar_proposta = False
                    portabilidade = Portabilidade.objects.get(contrato=contrato)
                    extra_context['CPF_Receita'] = portabilidade.CPF_dados_divergentes
                    if (
                        portabilidade.status == 38
                        and contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        refinanciamento = Refinanciamento.objects.get(contrato=contrato)
                        extra_context['status_contrato'] = refinanciamento.status
                    else:
                        extra_context['status_contrato'] = portabilidade.status

                    if (
                        extra_context['status_contrato']
                        == ContractStatus.CHECAGEM_MESA_CORBAN.value
                    ):
                        habilitar_botao_aprovar = False
                        habilitar_botao_pendenciar = False

                    elif (
                        extra_context['status_contrato']
                        == ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value
                    ):
                        habilitar_botao_aprovar = False
                        habilitar_botao_pendenciar = False
                        habilitar_botao_reprovar = False
                elif contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                    margem_livre = MargemLivre.objects.get(contrato=contrato)
                    extra_context['status_contrato'] = margem_livre.status

                if extra_context['status_contrato'] in [
                    ContractStatus.AGUARDA_ENVIO_LINK.value,
                    ContractStatus.AGUARDANDO_RETORNO_IN100.value,
                    ContractStatus.FORMALIZACAO_CLIENTE.value,
                ]:
                    habilitar_botao_pendenciar = False

                chave_status = StatusContrato.objects.filter(contrato=contrato).last()
                extra_context['tipo_produto'] = contrato.tipo_produto
                extra_context['motivo'] = chave_status.descricao_mesa
                extra_context['created_by'] = chave_status.created_by
                extra_context['data_modificacao'] = chave_status.data_fase_final
                extra_context['habilitar_botao_aprovar'] = habilitar_botao_aprovar
                extra_context['habilitar_botao_aprovar_proposta'] = (
                    habilitar_botao_aprovar_proposta
                )
                extra_context['habilitar_botao_pendenciar'] = habilitar_botao_pendenciar
                extra_context['habilitar_botao_reprovar'] = habilitar_botao_reprovar
            elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                saque_complementar = SaqueComplementar.objects.get(contrato=contrato)
                extra_context['status_contrato'] = saque_complementar.status
                extra_context['tipo_produto'] = contrato.tipo_produto

        if proposal_status == ContractStatus.INT_AJUSTE_AVERBACAO.value:
            extra_context['brazilian_states'] = [
                state.uf for state in BrazilianStatesEnum
            ]
            extra_context['status_contrato'] = proposal_status
            extra_context['habilitar_botao_atualizar_dados_pendentes'] = True
            extra_context['habilitar_botao_aprovar'] = False
            extra_context['habilitar_botao_aprovar_proposta'] = False
            extra_context['habilitar_botao_pendenciar'] = False
            status_contrato: StatusContrato = StatusContrato.objects.filter(
                contrato=contrato
            ).last()
            extra_context['motivo'] = status_contrato.descricao_mesa

            dados_bancarios = get_client_bank_data(client=contrato.cliente)

            extra_context['agencia'] = dados_bancarios.conta_agencia
            extra_context['conta'] = dados_bancarios.conta_numero
            extra_context['uf'] = contrato.cliente.endereco_uf
            extra_context['nome_cliente'] = contrato.cliente.nome_cliente
            extra_context['numero_beneficio'] = contrato.numero_beneficio

        return admin.ModelAdmin.changeform_view(
            self,
            request,
            object_id=object_id,
            extra_context=extra_context,
        )

    def card_should_show_approve_button_for_endorsoment(
        self, user_groups: QuerySet, contrato: Contrato
    ) -> bool:
        if user_groups.filter(name='Mesa de Averbação').exists():
            if not contrato.contrato_digitacao_manual:
                return True

            if ReservaDeMargem.objects.filter(contrato=contrato).exists():
                reserva = ReservaDeMargem.objects.filter(contrato=contrato).last()
                if reserva.anexo_url and reserva.protocolo:
                    return True

        return False

    def card_should_show_approve_button(
        self, status: ContractStatus, user_groups: QuerySet, contrato: Contrato
    ) -> bool:
        approvable_statuses = [
            ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
            ContractStatus.PENDENTE_DADOS_DIVERGENTES.value,
        ]

        is_endorsement_status = (
            status == ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value
            or status == ContractStatus.REGULARIZADA_MESA_AVERBACAO.value
        )

        return status in approvable_statuses or (
            is_endorsement_status
            and self.card_should_show_approve_button_for_endorsoment(
                user_groups, contrato
            )
        )

    def card_should_show_pendency_button(
        self, status: ContractStatus, user_groups: QuerySet
    ) -> bool:
        is_endorsement_status = (
            status == ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value
            or status == ContractStatus.REGULARIZADA_MESA_AVERBACAO.value
        )

        if is_endorsement_status:
            return user_groups.filter(name='Mesa de Averbação').exists()

        restricted_statuses = [
            ContractStatus.CHECAGEM_MESA_CORBAN.value,
            ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value,
        ]

        return status not in restricted_statuses

    def card_should_show_reprove_button(
        self, status: ContractStatus, user_groups: QuerySet
    ) -> bool:
        reprovable_statuses = [
            ContractStatus.ANDAMENTO_FORMALIZACAO.value,
            ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
            ContractStatus.PENDENTE_DOCUMENTACAO.value,
            ContractStatus.PENDENTE_DADOS_DIVERGENTES.value,
            ContractStatus.CHECAGEM_MESA_CORBAN.value,
            ContractStatus.REVISAO_MESA_DE_FORMALIZACAO.value,
        ]

        is_endorsement_status = (
            status == ContractStatus.CHECAGEM_MESA_DE_AVERBECAO.value
            or status == ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value
            or status == ContractStatus.REGULARIZADA_MESA_AVERBACAO.value
        )

        return status in reprovable_statuses or (
            is_endorsement_status
            and user_groups.filter(name='Mesa de Averbação').exists()
        )

    def solicitar_saque(self, request, queryset):
        user = UserProfile.objects.get(identifier=request.user.identifier)
        # TODO: Transformar em assíncrono
        for contrato in queryset:
            benefit_card = CartaoBeneficio.objects.filter(contrato=contrato).first()
            saque_complementar = SaqueComplementar.objects.filter(
                contrato=contrato
            ).first()
            payment_manager = PaymentManager(
                contrato,
                user,
                benefit_card=benefit_card,
                contrato_saque=saque_complementar,
            )
            cliente = contrato.cliente
            if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                cliente_cartao = saque_complementar.id_cliente_cartao
                resposta = limites_disponibilidades(
                    cliente_cartao.id_cartao_dock, cliente, cliente_cartao.pk
                )
                if resposta['saldoDisponivelSaque'] < float(
                    saque_complementar.valor_saque
                ):
                    alterar_status(
                        contrato,
                        saque_complementar,
                        EnumContratoStatus.CANCELADO,
                        ContractStatus.SAQUE_CANCELADO_LIMITE_DISPONIVEL_INSUFICIENTE.value,
                        user,
                    )
                    messages.error(
                        request,
                        f'Saque Cancelado - Limite disponível Insuficiente -  CONTRATO {contrato.pk}.',
                    )

                    return HttpResponseRedirect('/admin/contract/contrato/')

            cliente = contrato.cliente
            payment_manager.process_payment(cliente)

            if benefit_card:
                contrato_seq = benefit_card
            elif saque_complementar:
                contrato_seq = saque_complementar

            if contrato_seq.status == ContractStatus.ERRO_SOLICITACAO_SAQUE.value:
                messages.error(request, 'Falha ao solicitar saque.')
            elif contrato_seq.status == ContractStatus.ANDAMENTO_LIBERACAO_SAQUE.value:
                messages.success(request, 'Solicitação de saque realizada com sucesso.')

    def solicitar_comissionamento(self, request, queryset):
        # TODO: Transformar em assíncrono
        for contrato in queryset:
            parametro_backoffice = ParametrosBackoffice.objects.get(
                tipoProduto=contrato.tipo_produto
            )
            if parametro_backoffice.enviar_comissionamento:
                comissionamento_banksoft(contrato)

        messages.success(request, 'Comissionamento realizado com sucesso.')

    def reprocessar_documentoscopia(self, request, queryset):
        for contrato in queryset:
            if contrato.is_main_proposal:
                if (
                    protocol := SerasaProtocol.objects.filter(contract=contrato)
                    .exclude(
                        result__in=[
                            '',
                            ' ',
                            'PROTOCOLO DUPLICADO',
                            'COM RISCO - ALTA REINCIDÊNCIA',
                        ]
                    )
                    .first()
                ):
                    process_serasa_protocol(protocol)

        messages.success(request, 'Reprocessados com sucesso.')

    def validar_regras(self, request, queryset):
        # TODO: Transformar em assíncrono
        for contrato in queryset:
            payload = {
                'token': str(contrato.token_envelope),
                'cpf': contrato.cliente.nu_cpf,
            }
            validar_contrato_assync.apply_async(
                args=[
                    payload,
                    contrato.token_envelope,
                    contrato.cliente.nu_cpf,
                    '00000000099',
                ]
            )

        messages.success(request, 'Regras Validadas com sucesso.')

    def criar_individuo_dock(self, request, queryset):
        # TODO: Transformar em assíncrono
        for contrato in queryset:
            contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
            cliente = Cliente.objects.get(pk=contrato.cliente.pk)
            criar_individuo_dock.apply_async(
                args=[
                    'self',
                    cliente.nu_cpf,
                    contrato.pk,
                    request.user.identifier,
                    contrato_cartao.convenio.nome,
                ]
            )
            messages.success(request, 'Solicitação enviada com sucesso.')

    def solicitar_ajuste_financeiros(self, request, queryset):
        for contrato in queryset:
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
                ajustes_financeiros(contrato.id, contrato_cartao.id)
            elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                contrato_saque = SaqueComplementar.objects.get(contrato=contrato)
                ajustes_financeiros(contrato.id, contrato_saque.id)

    def lancar_saque_parcelado_fatura(self, request, queryset):
        for contrato in queryset:
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
                lancamento_saque_parcelado_fatura(contrato.id, contrato_cartao.id)
            elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                contrato_saque = SaqueComplementar.objects.get(contrato=contrato)
                lancamento_saque_parcelado_fatura(contrato.id, contrato_saque.id)

            messages.success(
                request,
                'Lançamento do saque realizado, acompanhe o Log para mais informações.',
            )

    def cancelar_reserva(self, request, queryset):
        # TODO: Transformar em assíncrono
        for contrato in queryset:
            contrato_cartao = CartaoBeneficio.objects.get(contrato=contrato)
            convenio = Convenios.objects.get(pk=contrato_cartao.convenio.pk)
            cliente_contrato = contrato.cliente_cartao_contrato.get()
            if convenio.averbadora == NomeAverbadoras.FACIL.value:
                cancelamento = cancela_reserva(
                    contrato.cliente.nu_cpf,
                    cliente_contrato.numero_matricula,
                    convenio.averbadora,
                    convenio.pk,
                    contrato.pk,
                )

            elif convenio.averbadora == NomeAverbadoras.ZETRASOFT.value:
                zetra = Zetra(
                    averbadora_number=convenio.averbadora, convenio_code=convenio.pk
                )
                cancelamento = zetra.margin_reserve_cancel(cpf=contrato.cliente.nu_cpf)

            elif convenio.averbadora == NomeAverbadoras.QUANTUM.value:
                cancelamento = cancela_reserva_quantum(
                    contrato.cliente.nu_cpf, convenio.averbadora, convenio.pk
                )

            elif convenio.averbadora == NomeAverbadoras.SERPRO.value:
                serpro = Serpro(averbadora=convenio.averbadora)
                cancelamento = serpro.margin_reserve_cancel(
                    cpf=contrato.cliente.nu_cpf,
                    registration_number=contrato.cliente.numero_matricula,
                    contract_id=contrato.id,
                    codigo_convenio=convenio.pk,
                )
            elif convenio.averbadora == NomeAverbadoras.DATAPREV_PINE.value:
                cancelamento = cancela_reserva_dataprev_pine(
                    cpf_cliente=contrato.cliente.nu_cpf,
                    averbadora=NomeAverbadoras.DATAPREV_PINE.value,
                    contrato=contrato,
                )

            elif convenio.averbadora == NomeAverbadoras.NEOCONSIG.value:
                neoconsig = Neoconsig(averbadora=convenio.averbadora)
                cancelamento = neoconsig.cancel_margin_reserve(
                    cpf=contrato.cliente.nu_cpf,
                    codigo_convenio=convenio.pk,
                    averbadora=convenio.averbadora,
                    contrato=contrato.pk,
                )

            if cancelamento.descricao:
                messages.error(
                    request,
                    f'A reserva de {contrato.cliente.nome_cliente} não foi cancelada. {cancelamento.descricao}',
                )
            else:
                contrato.cancelada = True
                contrato.save()
                messages.success(
                    request,
                    f'A reserva de {contrato.cliente.nome_cliente} foi cancelada com sucesso.',
                )

    def cancelar_reserva_qitech(self, request, queryset):
        for contrato in queryset:
            portabilidade = Portabilidade.objects.get(contrato=contrato)
            usuario = UserProfile.objects.get(identifier=request.user.identifier)

            try:
                if portabilidade.status != ContractStatus.INT_CONFIRMA_PAGAMENTO.value:
                    RefuseProposalFinancialPortability(contrato=contrato).execute()
                    contrato.status = EnumContratoStatus.CANCELADO
                    contrato.save()
                    portabilidade.status = ContractStatus.REPROVADO.value
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.REPROVADO.value,
                        created_by=usuario,
                    )
                    portabilidade.status_ccb = EnumStatusCCB.CANCELED.value
                    portabilidade.save()
                    messages.success(request, 'Proposta recusada com sucesso')
                else:
                    messages.error(
                        request,
                        "Não é possível Reprovar um contrato no status de 'INT CONFIRMA PAGAMENTO'",
                    )

            except Exception as e:
                # Log the error and display a message to the user
                messages.error(request, f'Ocorreu um erro ao RECUSAR a proposta: {e}')

    def insere_proposta_qitech(self, request, queryset):
        from contract.products.portabilidade.tasks import (
            insert_proposal_port_refin_async,
        )

        for contrato in queryset:
            try:
                toast_message = ''
                if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                    insert_portability_proposal.apply_async(
                        args=[str(contrato.token_contrato)]
                    )
                    toast_message = 'Proposta de Portabilidade inserida com sucesso'

                elif (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    if settings.ENVIRONMENT != EnvironmentEnum.PROD.value:
                        user = request.user
                        retorno = insert_proposal_port_refin_async(contrato.id, user.id)
                        if retorno:
                            toast_message = (
                                'Proposta de Port+Refin inserida com sucesso'
                            )
                        else:
                            toast_message = 'Tentativa de inserção falhou, realizaremos uma nova tentativa em 5 minutos'
                    else:
                        link_formalizacao_envelope(
                            contrato.token_envelope, request.user
                        )
                        toast_message = 'Proposta de Port+Refin inserida com sucesso'
                elif contrato.tipo_produto in (
                    EnumTipoProduto.MARGEM_LIVRE,
                    EnumTipoProduto.INSS,
                    EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
                ):
                    insert_free_margin_proposal(contract=contrato)
                    toast_message = 'Proposta de Margem Livre inserida com sucesso'
                else:
                    toast_message = 'Action não válida para esse tipo de produto'

                messages.success(request, toast_message)
            except Exception as e:
                # Log the error and display a message to the user
                messages.error(request, f'Ocorreu um erro ao SUBMETER a proposta: {e}')

    def reativar_link_formalizacao(self, request, queryset):
        for contrato in queryset:
            try:
                contratos_link = Contrato.objects.filter(
                    token_envelope=contrato.token_envelope
                )
                for contract in contratos_link:
                    contract.link_formalizacao_criado_em = datetime.now()
                    contract.save()
                messages.success(request, 'Link reativado com Sucesso')
            except Exception as e:
                # Log the error and display a message to the user
                messages.error(request, f'Ocorreu um erro ao reativar o link {e}')

    def enviar_dossie(self, request, queryset):
        for contrato in queryset:
            try:
                if contrato.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    contrato_seq = CartaoBeneficio.objects.get(contrato=contrato)
                elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    contrato_seq = SaqueComplementar.objects.get(contrato=contrato)
                retorno_saque.apply_async(args=[contrato.pk, 0])
                envio_dossie.apply_async(
                    args=[
                        contrato.cliente.nu_cpf,
                        contrato.token_contrato,
                        contrato_seq.possui_saque,
                        contrato_seq.saque_parcelado,
                    ]
                )

                messages.success(request, 'Envio dossie com sucesso!')
            except Exception as e:
                # Log the error and display a message to the user
                messages.error(request, f'Ocorreu um erro ao enviar dossie {e}')

    def atualizacao_cadastral_brb(self, request, queryset):
        for contrato in queryset:
            try:
                atualizacao_cadastral.apply_async(args=[contrato.cliente.nu_cpf])
                messages.success(request, 'Envio atualização cadastrar com sucesso!')
            except Exception as e:
                # Log the error and display a message to the user
                messages.error(
                    request, f'Ocorreu um erro ao atualizar dados do cadastro {e}'
                )

    def solicitar_plano(self, request, queryset):
        for contrato in queryset:
            try:
                for plano in contrato.plano.all():
                    if plano.seguradora.nome == EnumSeguradoras.TEM_SAUDE:
                        token = gerar_token_zeus()
                        adesao(contrato.cliente, token, contrato, plano)
                    elif plano.seguradora.nome == EnumSeguradoras.GENERALI:
                        if contrato.tipo_produto in (
                            EnumTipoProduto.CARTAO_BENEFICIO,
                            EnumTipoProduto.CARTAO_CONSIGNADO,
                        ):
                            contrato_seq = CartaoBeneficio.objects.get(
                                contrato=contrato
                            )
                            escrever_arquivo_generali(
                                contrato,
                                plano,
                                contrato_seq,
                                contrato.cliente_cartao_contrato.get(),
                            )
                        else:
                            messages.error(
                                request,
                                f'Impossivel solicitar plano para esse tipo de contrato: {contrato.tipo_produto}',
                            )
            except Exception as e:
                # Log the error and display a message to the user
                messages.error(
                    request, f'Ocorreu um erro ao tentar solicitar plano: {e}'
                )

    def solicitar_cancelamento_plano(self, request, queryset):
        messages.info(request, 'Enviado com sucesso.')

    def solicitar_cobranca_plano(self, request, queryset):
        # Inject JavaScript into the response to show a pop-up

        for contrato in queryset:
            try:
                for plano in contrato.plano.all():
                    if plano.seguradora.nome == EnumSeguradoras.GENERALI:
                        if contrato.tipo_produto in (
                            EnumTipoProduto.CARTAO_BENEFICIO,
                            EnumTipoProduto.CARTAO_CONSIGNADO,
                        ):
                            contrato_seq = CartaoBeneficio.objects.get(
                                contrato=contrato
                            )
                            beneficio = BeneficiosContratado.objects.filter(
                                contrato_emprestimo=contrato, plano=plano
                            ).first()
                            if beneficio:
                                premio_bruto = beneficio.premio_bruto
                            if plano.tipo_plano == EnumTipoPlano.PRATA:
                                messages.error(
                                    request,
                                    'Não existem lançamento para o plano Prata',
                                )
                            else:
                                solicitar_cobranca(
                                    contrato,
                                    plano,
                                    contrato_seq,
                                    contrato.cliente_cartao_contrato.get(),
                                    request,
                                    premio_bruto=premio_bruto,
                                )
                        else:
                            messages.error(
                                request,
                                f'Impossivel solicitar a cobranca plano para esse tipo de contrato: {contrato.tipo_produto}',
                            )
            except Exception as e:
                # Log the error and display a message to the user
                messages.error(
                    request,
                    f'Ocorreu um erro ao tentar solicitar a cobranca do plano: {e}',
                )

    def atualizar_dados_bancarios_banksoft(self, request, queryset):
        for contrato in queryset:
            try:
                if contrato.tipo_produto in (
                    EnumTipoProduto.CARTAO_BENEFICIO,
                    EnumTipoProduto.CARTAO_CONSIGNADO,
                ):
                    contrato_saque = CartaoBeneficio.objects.filter(
                        contrato=contrato
                    ).first()
                elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    contrato_saque = SaqueComplementar.objects.filter(
                        contrato=contrato
                    ).first()

                cliente_cartao = contrato.cliente.cliente_dados_bancarios.order_by(
                    '-updated_at'
                ).first()

                retorno_banksoft = atualizar_dados_bancarios(
                    contrato_saque.numero_proposta_banksoft,
                    cliente_cartao,
                    str(contrato.pk),
                )
                if retorno_banksoft in {200, 201, 202}:
                    alterar_status(
                        contrato,
                        contrato_saque,
                        EnumContratoStatus.DIGITACAO,
                        ContractStatus.ANDAMENTO_REAPRESENTACAO_DO_PAGAMENTO_DE_SAQUE.value,
                    )
                else:
                    alterar_status(
                        contrato,
                        contrato_saque,
                        EnumContratoStatus.DIGITACAO,
                        ContractStatus.ERRO_SOLICITACAO_SAQUE.value,
                    )
            except Exception as e:
                # Log the error and display a message to the user
                messages.error(
                    request,
                    f'Ocorreu um erro ao tentar solicitar atualização dos dados bancários: {e}',
                )

    def inserir_contrato_cliente(self, request, queryset):
        for contrato in queryset:
            try:
                cliente_cartao = ClienteCartaoBeneficio.objects.filter(
                    cliente=contrato.cliente
                ).first()
                cliente_cartao.contrato = contrato
                cliente_cartao.save()
                messages.success(request, 'Contrato relacionado ao cartão com sucesso')
            except Exception as e:
                messages.error(
                    request, f'Ocorreu um erro ao relacionar contrato ao cartão: {e}'
                )

    def inserir_campos_autoria(self, request, queryset):
        try:
            for contrato in Contrato.objects.all():
                if contrato.corban:
                    contrato.corban_photo = str(contrato.corban.corban_name)
                if contrato.created_by:
                    contrato.created_by_photo = contrato.created_by.name
                contrato.save()
            messages.success(request, 'Campos relacionados com sucesso!')
        except Exception as e:
            messages.error(request, f'Ocorreu um erro ao relacionar campos: {e}')

    def reparar_arquivos_danificados(self, request, queryset):
        user = request.user
        for contract in queryset:
            logging.info(f'Iniciando reparo de arquivos do contrato {contract.pk}.')
            AttachmentRepairer(contract, user).repair()
            logging.info(f'Arquivos do contrato {contract.pk} reparados.')
        messages.success(request, 'Arquivos reparados com sucesso')

    def reprocessar_envio_inss(self, request, queryset):
        for contrato in queryset:
            envia_info_inss_pine(contrato.pk, request)

    def consulta_beneficio_100(self, request, queryset):
        for contrato in queryset:
            dados_in100 = DadosIn100.objects.filter(
                cliente=contrato.cliente, numero_beneficio=contrato.numero_beneficio
            ).last()
            try:
                consulta_beneficio_in100_portabilidade(
                    contrato.cliente, contrato.numero_beneficio, dados_in100
                )
                messages.success(
                    request, 'A Consulta da IN100 foi realizada com Sucesso'
                )
            except Exception as e:
                logging.error(f'Ocorreu um erro ao realizar a consulta da IN100: {e}')
                messages.error(
                    request, 'Ocorreu um erro ao realizar a consulta da IN100.'
                )

    reprocessar_envio_inss.short_description = 'Reprocessar Dossie INSS/Pine'

    def cliente_numero_cpf(self, instance: Contrato) -> Optional[str]:
        # TODO: Criar correção melhor para quando o cliente não existir.
        cliente = getattr(instance, 'cliente', None)
        return None if not cliente else cliente.nu_cpf

    def envio_doc_qitec(self, request, queryset):
        for contrato in queryset:
            API_qitech_documentos(contrato.token_contrato)

    def envio_assinatura_qitech(self, request, queryset):
        for contrato in queryset:
            API_qitech_envio_assinatura(contrato.token_contrato)

    def gerar_token_e_buscar_beneficio_cartao_inss(self, request, queryset):
        # TODO: Transformar em assíncrono
        for contrato in queryset:
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                contrato_cartao = contrato.contrato_cartao_beneficio.first()
                gerar_token_e_buscar_beneficio(
                    contrato.cliente.nu_cpf,
                    contrato_cartao.convenio.averbadora,
                    contrato.token_contrato,
                    contrato_cartao.convenio.pk,
                )

        messages.success(
            request,
            'Solicitação realizada com sucesso, acompanhe o status do contrato.',
        )

    def get_status_produto(self, obj):
        try:
            return obj.get_status_produto
        except Exception as e:
            print(e)
            return '########'

    def dt_atualizacao(self, obj):
        return format_html(
            obj.ultima_atualizacao.astimezone(timezone.get_current_timezone()).strftime(
                '%d/%m/%Y - %H:%M'
            )
        )

    def dt_criacao(self, obj):
        return format_html(
            obj.criado_em.astimezone(timezone.get_current_timezone()).strftime(
                '%d/%m/%Y - %H:%M'
            )
        )

    def cliente_info(self, obj):
        return format_html(
            f'{obj.cliente}&nbsp; <a class="related-widget-wrapper-link view-related" id="view_id_cliente" data-href-template="/admin/core/cliente/__fk__/change/?_to_field=id" title="View selected Cliente" href="/admin/core/cliente/{obj.cliente.pk}/change/?_to_field=id"><img src="/static/admin/img/icon-viewlink.svg" alt="Visualizar"></a>'
        )

    def cliente_dt_nascimento(self, obj):
        return obj.cliente.dt_nascimento.strftime('%d/%m/%Y')

    def cliente_sexo(self, obj):
        return obj.cliente.sexo

    def cliente_nome_mae(self, obj):
        return obj.cliente.nome_mae

    def cliente_nome_pai(self, obj):
        return obj.cliente.nome_pai or '-'

    @admin.display(description='Data de nascimento')
    def cliente_idade(self, obj):
        return calcular_idade(obj.cliente.dt_nascimento)

    @admin.display(description='Nome')
    def rogado_nome(self, obj):
        if hasattr(obj, 'rogado') and obj.rogado.nome:
            return obj.rogado.nome
        return ''

    @admin.display(description='Data de nascimento')
    def rogado_dt_nascimento(self, obj):
        if hasattr(obj, 'rogado') and obj.rogado.data_nascimento:
            return obj.rogado.data_nascimento.strftime('%d/%m/%Y')
        return ''

    @admin.display(description='CPF')
    def rogado_cpf(self, obj):
        if hasattr(obj, 'rogado') and (cpf := obj.rogado.cpf):
            return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'
        return ''

    @admin.display(description='Telefone')
    def rogado_telefone(self, obj):
        if hasattr(obj, 'rogado') and (telefone := obj.rogado.telefone):
            return f'({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}'
        return ''

    def novo_url_formalizacao(self, obj):
        if obj.tipo_produto in {
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        }:
            portabilidade_obj = Portabilidade.objects.filter(contrato=obj).first()
            if portabilidade_obj.status in {
                ContractStatus.AGUARDANDO_RETORNO_IN100.value,
                ContractStatus.AGUARDA_ENVIO_LINK.value,
                ContractStatus.REPROVADA_FINALIZADA.value,
                ContractStatus.REPROVADA_MESA_FORMALIZACAO.value,
                ContractStatus.RECUSADA_AVERBACAO.value,
                ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                ContractStatus.REPROVADA_MESA_CORBAN.value,
                ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value,
                ContractStatus.REPROVADA_PAGAMENTO_DEVOLVIDO.value,
                ContractStatus.REPROVADO.value,
                ContractStatus.REPROVADA_REVISAO_MESA_DE_FORMALIZACAO.value,
            }:
                return ' - '
            else:
                return obj.url_formalizacao
        elif obj.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            margem_livre_obj = MargemLivre.objects.filter(contrato=obj).first()
            if margem_livre_obj.status in {
                ContractStatus.REPROVADO.value,
                ContractStatus.AGUARDANDO_RETORNO_IN100.value,
                ContractStatus.AGUARDA_ENVIO_LINK.value,
            }:
                return ' - '
            else:
                return obj.url_formalizacao

        elif not obj.url_formalizacao:
            return ' - '

        else:
            return obj.url_formalizacao

    def contratos_relacionados(self, obj):
        if relacionados := Contrato.objects.filter(
            token_envelope=obj.token_envelope
        ).exclude(pk=obj.pk):
            return format_html(
                '<br> '.join([
                    str(
                        f"<a href='/admin/contract/contrato/{c.pk}/change/' "
                        f"target='_blank'>{c.cliente} - {c.token_contrato}</a>"
                    )
                    for c in relacionados
                ])
            )
        return '-'

    def aceitar_port_refin(self, request, queryset):
        from contract.products.portabilidade.tasks import approve_refinancing

        for contrato in queryset:
            try:
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    approve_refinancing.apply_async(
                        args=[Refinanciamento.objects.get(contrato=contrato).pk]
                    )
                    messages.success(request, 'Contrato de Refinanciamento APROVADO')
                else:
                    messages.error(
                        request, f'O contrato não é de PORT+REFIN({contrato.id})'
                    )
            except Exception as e:
                messages.error(
                    request,
                    f'Ocorreu um erro ao APROVAR o contrato({contrato.id}): {e}',
                )

    def reprovar_em_lote(self, request, queryset):
        """Action Temporário"""
        if ENVIRONMENT == 'PROD':
            ids_contrato = []
            for id_contrato in ids_contrato:
                try:
                    contrato = Contrato.objects.filter(id=id_contrato).first()
                    if (
                        contrato.tipo_produto
                        == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                    ):
                        portabilidade = Portabilidade.objects.get(contrato=contrato)
                        refinanciamento = Refinanciamento.objects.get(contrato=contrato)
                        if refuse_product_proposal_qitech(
                            contract=contrato,
                            product=portabilidade,
                        ):
                            contrato.status = EnumContratoStatus.CANCELADO
                            contrato.save()
                            StatusContrato.objects.create(
                                contrato=contrato,
                                nome=ContractStatus.REPROVADO.value,
                                descricao_mesa='Retido',
                                descricao_front='Retenção do Cliente',
                            )
                            portabilidade.status = ContractStatus.REPROVADO.value
                            portabilidade.save()
                            refinanciamento.status = ContractStatus.REPROVADO.value
                            refinanciamento.save()
                            if request:
                                messages.success(
                                    request, f'Contrato {contrato.id} - REPROVADO.'
                                )
                        else:
                            if request:
                                messages.error(
                                    request,
                                    'Ocorreu um erro na chamada da API \n Valide na aba Portabilidade(RESPOSTAS APIS QITECH)',
                                )
                    else:
                        messages.error(
                            request, f'O contrato não é de PORT+REFIN({contrato.id})'
                        )
                except Exception as e:
                    messages.error(
                        request,
                        f'Ocorreu um erro ao REPROVAR o contrato({id_contrato}): {e}',
                    )
                    logging.error(
                        f'Ocorreu um erro ao REPROVAR o contrato({id_contrato}): {e}'
                    )

    def recalcular_contrato(self, request, queryset):
        from contract.products.portabilidade.tasks import (
            retorno_saldo_portabilidade_assync,
        )

        # TODO: Transformar em assíncrono
        for contrato in queryset:
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                EnumTipoProduto.PORTABILIDADE,
            ):
                if StatusContrato.objects.filter(
                    contrato=contrato, nome=ContractStatus.SALDO_RETORNADO.value
                ).exists():
                    contrato.ultima_atualizacao = datetime.now()
                    contrato.save()
                    portabilidade = Portabilidade.objects.get(contrato=contrato)
                    retorno_saldo_portabilidade_assync.delay(
                        contrato.token_contrato,
                        float(portabilidade.saldo_devedor_atualizado),
                        request.user.identifier,
                        portabilidade.numero_parcela_atualizada,
                        float(portabilidade.valor_parcela_original),
                    )
                    messages.success(
                        request, f'Contrato {contrato.id} : RECALCULADO com sucesso.'
                    )
                else:
                    messages.error(
                        request,
                        f'Contrato {contrato.id} : SALDO DEVEDOR ainda não retornado.',
                    )
            else:
                messages.error(
                    request,
                    f'Contrato {contrato.id} : Recalculo permitido somente em PORTABILIDADE e PORT + REFIN.',
                )

    def reapresentar_contrato(self, request, queryset):
        from contract.services.payment.payment_resubmission import PaymentResubmission

        for contrato in queryset:
            try:
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refinancing = Refinanciamento.objects.get(contrato=contrato)
                    PaymentResubmission(
                        product=refinancing,
                    ).execute_today()
                    messages.success(
                        request,
                        f'Contrato {contrato.id} : Reapresentação realizada com sucesso.',
                    )
                else:
                    messages.error(
                        request,
                        f'Contrato {contrato.id} : Recalculo permitido somente em PORTABILIDADE e PORT + REFIN.',
                    )
            except Exception as e:
                logging.error(f'Ocorreu um erro na Reapresentação ({contrato.id}): {e}')
                messages.error(
                    request,
                    f'Ocorreu um erro na Reapresentação ({contrato.id}), "{contrato.contrato_refinanciamento.first().chave_proposta}": {e}',
                )
                print(f'Erro: {contrato.id} - {e}')

    def check_corban_photo(self, obj):
        return obj.corban_photo if obj.corban_photo else obj.corban

    def check_created_by_photo(self, obj):
        return obj.created_by_photo if obj.created_by_photo else obj.created_by

    def resimular_port_refin(self, request, queryset):
        """
        Resimula contrato de PORT + Refin
        """
        executer = ResimularPortRefinActionExecuter(request, queryset)
        executer.execute()

        # display message
        number_of_contracts = len(queryset)
        plural = 's' if number_of_contracts > 1 else ''
        msg = f'Resimulando Port+Refin para {number_of_contracts} contrato{plural}.'
        messages.success(request, msg)

    def convenio_list(self, obj):
        cliente_cartao = obj.cliente_cartao_contrato.get()
        if cliente_cartao and cliente_cartao.convenio:
            return cliente_cartao.convenio.nome

    check_corban_photo.short_description = 'Corban'
    check_created_by_photo.short_description = 'Criado por'
    cliente_numero_cpf.short_description = 'CPF'
    get_status_produto.short_description = 'Status'
    dt_atualizacao.short_description = 'Última atualização'
    dt_criacao.short_description = 'Criado em'
    cliente_info.short_description = 'Nome do cliente'
    cliente_dt_nascimento.short_description = 'Nascimento'
    cliente_sexo.short_description = 'Sexo'
    cliente_nome_pai.short_description = 'Nome do pai'
    cliente_nome_mae.short_description = 'Nome da mãe'
    cliente_idade.short_description = 'Idade'
    contratos_relacionados.short_description = 'Contratos relacionados'
    novo_url_formalizacao.short_description = 'URL de Formalização'
    resimular_port_refin.short_description = 'Resimular Port + Refin'
    convenio_list.short_description = 'Convênio'

    fieldsets = (
        (
            'CONTRATO',
            {
                'fields': (
                    ('tipo_produto', 'cd_contrato_tipo', 'get_status_produto'),
                    (
                        'dt_criacao',
                        'dt_atualizacao',
                    ),
                    ('check_corban_photo', 'check_created_by_photo', 'cd_parceiro'),
                    ('contrato_assinado', 'contrato_pago', 'dt_pagamento_contrato'),
                    (
                        'cancelada',
                        'novo_url_formalizacao',
                        'is_ccb_generated',
                        'is_main_proposal',
                    ),
                    (
                        'token_contrato',
                        'contrato_digitacao_manual',
                        'contrato_digitacao_manual_validado',
                    ),
                    ('contrato_cross_sell',),
                )
            },
        ),
        (
            'DADOS DO CLIENTE',
            {
                'fields': (
                    (
                        'cliente_info',
                        'cliente_numero_cpf',
                        'cliente_sexo',
                        'numero_beneficio',
                    ),
                    (
                        'cliente_dt_nascimento',
                        'cliente_idade',
                    ),
                    (
                        'cliente_nome_mae',
                        'cliente_nome_pai',
                    ),
                    (
                        'vr_liberado_cliente',
                        'limite_pre_aprovado',
                        'vencimento_fatura',
                    ),
                )
            },
        ),
        (
            'DOCUMENTAÇÃO',
            {
                'fields': (
                    (
                        'enviado_documento_pessoal',
                        'selfie_enviada',
                        'enviado_comprovante_residencia',
                    ),
                    (
                        'adicional_enviado',
                        'pendente_documento',
                        'pendente_endereco',
                    ),
                    (
                        'selfie_pendente',
                        'contracheque_enviado',
                        'contracheque_pendente',
                    ),
                    (
                        'adicional_pendente',
                        'campos_pendentes',
                    ),
                )
            },
        ),
        (
            'DADOS DO ROGADO',
            {
                'fields': (
                    (
                        'rogado_nome',
                        'rogado_cpf',
                        'rogado_dt_nascimento',
                        'rogado_telefone',
                    ),
                ),
                'classes': ('collapse', 'envelope'),
            },
        ),
        (
            'TAXAS',
            {
                'fields': (
                    ('taxa', 'vr_tac'),
                    ('taxa_efetiva_ano', 'taxa_efetiva_mes'),
                    ('vr_iof', 'vr_iof_adicional'),
                    ('vr_iof_seguro', 'vr_iof_total'),
                    ('cet_mes', 'cet_ano'),
                )
            },
        ),
        (
            'SEGURO',
            {
                'fields': (
                    (
                        'seguro',
                        'plano',
                    ),
                )
            },
        ),
        (
            'ENVELOPE',
            {
                'fields': (
                    'token_envelope',
                    'contratos_relacionados',
                ),
                'classes': ('collapse', 'envelope'),
            },
        ),
    )

    raw_id_fields = (
        'cliente',
        'created_by',
    )

    list_display = (
        'id',
        'cliente',
        'cliente_numero_cpf',
        'tipo_produto',
        'get_status_produto',
        'dt_atualizacao',
        'convenio_list',
        'corban',
        'contrato_assinado',
        'contrato_pago',
        'created_by',
    )

    search_fields = (
        'cancelada',
        'corban__corban_name',
        'created_by__name',
        'cliente__nu_cpf',
        'cliente__nome_cliente',
        'token_envelope',
    )

    def get_search_fields(self, request, obj=None):
        q = request.GET.get('q')
        if q is not None:
            if q.isdigit() and Contrato.objects.filter(id=int(q)):
                return ('id',)
            else:
                return (
                    'cancelada',
                    'corban__corban_name',
                    'created_by__name',
                    'cliente__nu_cpf',
                    'cliente__nome_cliente',
                    'token_envelope',
                )
        return self.search_fields

    list_filter = (
        (
            'criado_em',
            DateTimeRangeFilterBuilder(
                title='Criado em',
                default_start=datetime(2023, 1, 1),
                default_end=datetime(2040, 1, 1),
            ),
        ),
        (
            'ultima_atualizacao',
            DateTimeRangeFilterBuilder(
                title='Última Atualização',
                default_start=datetime(2023, 1, 1),
                default_end=datetime(2040, 1, 1),
            ),
        ),
        'tipo_produto',
        'corban',
        'contrato_assinado',
        'contrato_pago',
        StatusListFilter,
        ConvenioListFilter,
    )
    exclude = ('token_contrato', 'url_formalizacao')

    actions = [
        cancelar_reserva,
        solicitar_saque,
        solicitar_comissionamento,
        envio_doc_qitec,
        envio_assinatura_qitech,
        cancelar_reserva_qitech,
        criar_individuo_dock,
        solicitar_ajuste_financeiros,
        insere_proposta_qitech,
        # reativar_link_formalizacao,
        validar_regras,
        reprocessar_documentoscopia,
        lancar_saque_parcelado_fatura,
        enviar_dossie,
        atualizacao_cadastral_brb,
        solicitar_plano,
        atualizar_dados_bancarios_banksoft,
        inserir_contrato_cliente,
        reparar_arquivos_danificados,
        aceitar_port_refin,
        inserir_campos_autoria,
        recalcular_contrato,
        solicitar_cobranca_plano,
        resimular_port_refin,
        reprocessar_envio_inss,
        solicitar_cancelamento_plano,
        reapresentar_contrato,
        gerar_token_e_buscar_beneficio_cartao_inss,
        reprovar_em_lote,
        consulta_beneficio_100,
    ]

    # Os campos são editaveis apenas para os usuários que então presentes no seguinte array

    readonly_fields = (
        'corban',
        'created_by',
        'cliente_info',
        'cliente_numero_cpf',
        'dt_criacao',
        'cliente_idade',
        'cliente_nome_pai',
        'get_status_produto',
        'cliente_sexo',
        'dt_atualizacao',
        'novo_url_formalizacao',
        'cliente_nome_mae',
        'cliente_dt_nascimento',
        'contratos_relacionados',
        'token_contrato',
        'tipo_produto',
        'cd_contrato_tipo',
        'cd_parceiro',
        'contrato_assinado',
        'contrato_pago',
        'cancelada',
        'vr_liberado_cliente',
        'limite_pre_aprovado',
        'vencimento_fatura',
        'enviado_documento_pessoal',
        'pendente_documento',
        'campos_pendentes',
        'enviado_comprovante_residencia',
        'pendente_endereco',
        'selfie_enviada',
        'selfie_pendente',
        'contracheque_enviado',
        'contracheque_pendente',
        'adicional_enviado',
        'adicional_pendente',
        'taxa',
        'vr_tac',
        'taxa_efetiva_ano',
        'taxa_efetiva_mes',
        'vr_iof',
        'vr_iof_adicional',
        'vr_iof_seguro',
        'vr_iof_total',
        'cet_mes',
        'cet_ano',
        'seguro',
        'vr_seguro',
        'taxa_seguro',
        'plano',
        'token_envelope',
        'dt_pagamento_contrato',
        'contrato_digitacao_manual',
        'contrato_digitacao_manual_validado',
        'check_corban_photo',
        'check_created_by_photo',
        'numero_beneficio',
        'contrato_cross_sell',
        'is_main_proposal',
        'rogado_nome',
        'rogado_cpf',
        'rogado_dt_nascimento',
        'rogado_telefone',
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super(ContratoAdmin, self).get_readonly_fields(request, obj)
        """
        if request.user.identifier in ['admin', 'joyce.csb@gmail.com', 'admin@admin.com']:
            return ()"""
        if obj:
            if request.user.groups.filter(name='Analise Mesa').exists():
                return readonly_fields
            return readonly_fields + ('cliente_numero_cpf',)
        return readonly_fields

    def has_change_permission(self, request, obj=None):
        if (
            request.user.groups.filter(name='Analise Mesa').exists()
            and obj
            and isinstance(obj, AnexoAntifraude)
        ):
            return True
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.has_perm('contrato.change_contrato'))

    def has_import_permission(self, request):
        return False

    change_form_template = 'admin/contract/contrato/contrato_pendente.html'


class BooleanWidget(fields.Field):
    def clean(self, value, row=None, *args, **kwargs):
        return str(value).lower() == 'true'


class BancosBrasileirosResource(resources.ModelResource):
    produto = fields.Field(
        column_name='produto',
        attribute='produto',
        widget=ManyToManyWidget(model=BancosBrasileiros, separator=',', field='nome'),
    )
    aceita_liberacao = BooleanWidget(
        column_name='aceita_liberacao',
        attribute='aceita_liberacao',
    )

    def import_field(self, field, obj, data, is_m2m=False, **kwargs):
        if field.attribute == 'aceita_liberacao':
            value = data.get(field.column_name)
            if value.lower() == 'sim':
                return True
            elif value.lower() == 'não':
                return False
            else:
                return super().import_field(field, obj, data, is_m2m, **kwargs)
        elif field.attribute == 'produto':
            value = data.get(field.column_name)
            product_names = [name.strip() for name in value.split(',')]
            return [
                Produtos.objects.get_or_create(nome=name)[0] for name in product_names
            ]
        else:
            return super().import_field(field, obj, data, is_m2m, **kwargs)

    class Meta:
        model = BancosBrasileiros
        fields = ('id', 'codigo', 'nome', 'ispb', 'produto', 'aceita_liberacao')
        export_order = ('id', 'codigo', 'nome', 'ispb', 'produto', 'aceita_liberacao')


class BancosBrasileirosAdmin(ImportExportModelAdmin):
    resource_class = BancosBrasileirosResource
    list_display = ('nome', 'codigo', 'get_produto', 'ispb', 'aceita_liberacao_display')

    def get_produto(self, obj):
        if obj.produto is not None and obj.produto is not False:
            produtos = obj.produto.all()
            return ', '.join([produto.nome for produto in produtos if produto.nome])
        return None

    def aceita_liberacao_display(self, obj):
        return 'Sim' if obj.aceita_liberacao else 'Não'

    get_produto.short_description = 'Produto'
    aceita_liberacao_display.short_description = 'Aceita Liberação'


class ReportSettingsAdmin(admin.ModelAdmin):
    list_display = ('subject', 'msg_email')


class ParametrosBackofficeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipoProduto', 'ativo')


class FontePagadoraContratoInline(admin.TabularInline):
    model = FontePagadora
    extra = 0


class MaisOpcoesParcelamento(admin.TabularInline):
    model = OpcoesParcelamento
    extra = 0


class EspecieBeneficioINSSInline(admin.TabularInline):
    model = EspecieBeneficioINSS
    extra = 0


class PensaoAlimenticiaINSSInline(admin.TabularInline):
    model = PensaoAlimenticiaINSS
    extra = 0


class SituacaoBeneficioINSSInline(admin.TabularInline):
    model = SituacaoBeneficioINSS
    extra = 0


class SegurosInline(admin.TabularInline):  # ou admin.StackedInline se preferir
    model = Seguros
    extra = 1  # número de linhas vazias a serem exibidas


class TipoVinculoSiapeInline(admin.TabularInline):
    model = TipoVinculoSiape
    extra = 0


class ClassificacaoSiapeInline(admin.TabularInline):
    model = ClassificacaoSiape
    extra = 0


class ConvenioSiapeInline(admin.TabularInline):
    model = ConvenioSiape
    extra = 0


class ProdutoConvenioInline(admin.StackedInline):
    model = ProdutoConvenio
    extra = 0
    readonly_fields = ('saque_parc_val_total',)

    # METODO FAZ COM QUE MARGEM UNIFICADA NAO SEJA PERMITIDO SELECAO
    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'tipo_margem':
            kwargs['choices'] = [
                (choice, label)
                for choice, label in db_field.choices
                if choice != EnumTipoMargem.MARGEM_UNIFICADA
            ]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    fieldsets = (
        (
            'PRODUTO',
            {'fields': (('produto',),)},
        ),
        (
            'TIPO DE MARGEM',
            {'fields': (('tipo_margem', 'cod_servico_zetra'),)},
        ),
        (
            'LIMITES',
            {
                'fields': (
                    (
                        'margem_minima',
                        'margem_maxima',
                    ),
                )
            },
        ),
        (
            'TAXAS',
            {
                'fields': (
                    (
                        'taxa_produto',
                        'cet_am',
                        'cet_aa',
                    ),
                )
            },
        ),
        (
            'PARAMETROS DOCK',
            {
                'fields': (
                    (
                        'data_vencimento_fatura',
                        'corte',
                        'saque_parc_cod_dock',
                    ),
                    (
                        'id_produto_logo_dock',
                        'id_plastico_dock',
                        'id_imagem_dock',
                    ),
                    ('cartao_virtual',),
                )
            },
        ),
        (
            'PARAMETROS SAQUE',
            {
                'fields': (
                    ('percentual_saque',),
                    (
                        'permite_saque',
                        'vr_minimo_saque',
                    ),
                    (
                        'permite_saque_parcelado',
                        'saque_parc_val_min',
                        'saque_parc_qnt_min_parcelas',
                        'saque_parc_val_total',
                    ),
                )
            },
        ),
    )


class ConveniosAdmin(admin.ModelAdmin):
    list_display = ('nome', 'averbadora')

    inlines = [
        ProdutoConvenioInline,
        RegrasIdadeInline,
        FontePagadoraContratoInline,
        SubOrgaoInline,
        SituacaoBeneficioINSSInline,
        PensaoAlimenticiaINSSInline,
        EspecieBeneficioINSSInline,
        SegurosInline,
        TipoVinculoSiapeInline,
        ClassificacaoSiapeInline,
        ConvenioSiapeInline,
    ]
    fieldsets = (
        (
            'DADOS CONVÊNIO',
            {
                'fields': (
                    (
                        'nome',
                        'averbadora',
                        'cod_convenio',
                        'cod_convenio_zetra',
                    ),
                    (
                        'digitacao_manual',
                        'senha_servidor',
                        'necessita_assinatura_fisica',
                        'permite_unificar_margem',
                        'permite_saque_complementar',
                        'fixar_valor_maximo',
                    ),
                    (
                        'derivacao_mesa_averbacao',
                        'idade_minima_assinatura',
                    ),
                    ('ativo',),
                )
            },
        ),
        (
            'DADOS INSS',
            {
                'fields': (
                    (
                        'convenio_inss',
                        'horario_func_ativo',
                        'aviso_reducao_margem',
                    ),
                    ('horario_func_inicio', 'horario_func_fim'),
                    ('porcentagem_reducao_margem',),
                )
            },
        ),
        (
            'DADOS DE ACESSO AVERBADORA',
            {
                'fields': (
                    ('usuario_convenio', 'senha_convenio', 'url', 'cliente_zetra'),
                )
            },
        ),
    )


class INSSBeneficioTipoAdmin(admin.ModelAdmin):
    list_display = ('cdInssBeneficioTipo', 'dsINSSBeneficioTipo', 'flAtivo')


class EnvelopeContratosAdmin(admin.ModelAdmin):
    list_display = (
        'token_envelope',
        'criado_em',
        'mensagem_confia',
        'id_transacao_confia',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)

        if obj:
            if obj.inicio_digitacao is not None:
                obj.inicio_digitacao = datetime.fromtimestamp(
                    obj.inicio_digitacao
                ).strftime('%d/%m/%Y %H:%M:%S')
            if obj.fim_digitacao is not None:
                obj.fim_digitacao = datetime.fromtimestamp(obj.fim_digitacao).strftime(
                    '%d/%m/%Y %H:%M:%S'
                )
            if obj.duracao_digitacao is not None:
                obj.duracao_digitacao = timedelta(seconds=obj.duracao_digitacao)

        return fields


class ParametrosProdutoAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            'REGRAS TAXAS',
            {
                'fields': (
                    ('tipoProduto'),
                    (
                        'taxa_maxima',
                        'taxa_minima',
                        'taxa_minima_recalculo',
                        'teto_inss',
                    ),
                    ('cet_mes', 'cet_ano', 'valor_tac'),
                )
            },
        ),
        (
            'REGRAS PARCELAS',
            {
                'fields': (
                    (
                        'valor_minimo_parcela',
                        'valor_maximo_parcela',
                        'quantidade_minima_parcelas',
                        'quantidade_maxima_parcelas',
                    ),
                )
            },
        ),
        (
            'REGRAS CLIENTE',
            {
                'fields': (
                    (
                        'idade_minima',
                        'idade_maxima',
                    ),
                )
            },
        ),
        (
            'REGRAS CONTRATOS',
            {
                'fields': (
                    (
                        'valor_minimo_emprestimo',
                        'valor_maximo_emprestimo',
                        'valor_de_seguranca_proposta',
                        'data_inicio_vencimento',
                        'prazo_maximo',
                        'prazo_minimo',
                        'idade_especie_87',
                    ),
                )
            },
        ),
        (
            'PARAMETROS PROPOSTA MARGEM LIVRE',
            {
                'fields': (
                    (
                        'taxa_proposta_margem_livre',
                        'multa_contrato_margem_livre',
                        'valor_minimo_margem',
                    ),
                )
            },
        ),
        (
            'REGRAS SIMULAÇÃO',
            {
                'fields': (
                    (
                        'dias_limite_para_desembolso',
                        'valor_minimo_parcela_simulacao',
                        'quantidade_dias_uteis_base_simulacao',
                        'meses_para_adicionar_quando_dias_uteis_menor_igual_base',
                        'meses_para_adicionar_quando_dias_uteis_maior_base',
                        'dia_vencimento_padrao_simulacao',
                        'valor_liberado_cliente_operacao_min',
                        'valor_liberado_cliente_operacao_max',
                    ),
                )
            },
        ),
        (
            'REGRAS PORTABILIDADE_REFINANCIAMENTO',
            {
                'fields': (
                    (
                        'valor_troco_minimo',
                        'percentual_maximo_aprovacao',
                        'percentual_maximo_pendencia',
                        'percentual_variacao_troco_recalculo',
                    ),
                )
            },
        ),
        (
            'CROSS SELL',
            {'fields': (('permite_oferta_cartao_inss',),)},
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.tipoProduto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            fieldsets += (
                (
                    'APROVAÇÃO AUTOMÁTICA',
                    {
                        'fields': ('aprovar_automatico',),
                    },
                ),
            )
        return fieldsets


class TaxaAdmin(admin.ModelAdmin):
    list_display = ('tipo_produto', 'taxa', 'ativo')
    ordering = [
        'tipo_produto',
    ]


class TermosDeUsoAdmin(admin.ModelAdmin):
    list_display = ('termos_de_uso', 'politica_privacidade')


class FaixaIdadeAdmin(admin.ModelAdmin):
    list_display = (
        'nu_idade_minima',
        'nu_idade_maxima',
        'vr_minimo',
        'vr_maximo',
        'nu_prazo_minimo',
        'nu_prazo_maximo',
        'fl_possui_representante_legal',
    )
    ordering = ['nu_idade_minima', 'nu_idade_maxima']


class DataAdmin(admin.ModelAdmin):
    list_display = ('dt_data_', 'ds_feriado', 'fl_feriado', 'fl_dia_util')
    list_filter = [
        'fl_feriado',
        'fl_dia_util',
        (
            'dt_data',
            DateTimeRangeFilterBuilder(
                title='por Data',
                default_start=datetime.now() - relativedelta(years=1),
                default_end=datetime.now(),
            ),
        ),
    ]
    ordering = ['dt_data']

    @admin.display(description='Data')
    def dt_data_(self, obj):
        return obj.dt_data.strftime('%d/%m/%Y')


class ComissaoTaxaAdmin(admin.ModelAdmin):
    list_display = (
        'cd_contrato_tipo',
        'prazo',
        'tx_efetiva_contrato_min',
        'tx_efetiva_contrato_max',
        'dt_vigencia_inicio_',
        'dt_vigencia_fim_',
    )
    ordering = ['cd_contrato_tipo']
    list_filter = ['cd_contrato_tipo', 'prazo']

    @admin.display(description='Data Vigencia Inicio')
    def dt_vigencia_inicio_(self, obj):
        return obj.dt_vigencia_inicio.strftime('%d/%m/%Y')

    @admin.display(description='Data Vigencia Fim')
    def dt_vigencia_fim_(self, obj):
        return obj.dt_vigencia_fim.strftime('%d/%m/%Y')


class DocumentoAceiteIN100Inline(admin.TabularInline):
    model = DocumentoAceiteIN100
    extra = 0
    fields = (
        'aceite_in100',
        'nome_anexo',
        'anexo_url_',
        'criado_em',
    )

    readonly_fields = (
        'anexo_url_',
        'nome_anexo',
        'aceite_in100',
        'criado_em',
    )

    def anexo_url_(self, obj):
        """
        Retorna o link e thumbnail de visualização para acesso aos anexos dos contratos
        """
        if anexo_url := obj.get_attachment_url:
            if '.PDF' in obj.nome_anexo.upper():
                return format_html(
                    f'<a href="{anexo_url}" target="_blank"><img src="/static/admin/img/pdf.png" title="Acessar PDF" height="48"></a>'
                )
            elif (
                '.PNG' in obj.nome_anexo.upper()
                or 'JPG' in obj.anexo_extensao.upper()
                or 'JPEG' in obj.anexo_extensao.upper()
            ):
                return format_html(
                    f'<a href="{anexo_url}" target="_blank"><img src="{anexo_url}" height="80"  title="Acessar imagem" style="border-radius:5px;"></a>'
                )
            else:
                return format_html(
                    f'<a href="{anexo_url}" target="_blank"><img src="/static/admin/img/file.png" title="Acessar documento" height="48"></a>'
                )
        return '-'


class HistoricoAceiteIN100Inline(
    admin.TabularInline
):  # ou admin.StackedInline, dependendo da sua preferência de apresentação
    model = HistoricoAceiteIN100
    extra = 0

    readonly_fields = (
        'canal',
        'hash_assinatura',
        'data_aceite',
        'data_vencimento_aceite',
        'produto',
    )


class DadosBeneficioIN100Inline(admin.StackedInline):
    model = DadosBeneficioIN100
    extra = 0

    readonly_fields = [f.name for f in model._meta.fields]

    fieldsets = (
        (
            'DADOS BÁSICOS',
            {
                'fields': (
                    ('numero_beneficio', 'cpf'),
                    ('nome_beneficiario', 'concessao_judicial'),
                )
            },
        ),
        (
            'SITUAÇÃO DO BENEFÍCIO',
            {
                'fields': (
                    ('codigo_situacao_beneficio', 'descricao_situacao_beneficio'),
                )
            },
        ),
        (
            'ESPÉCIE DO BENEFÍCIO',
            {'fields': (('codigo_especie_beneficio', 'descricao_especie_beneficio'),)},
        ),
        (
            'INFORMAÇÕES DE PAGAMENTO',
            {
                'fields': (
                    ('uf_pagamento', 'cbc_if_pagadora'),
                    ('agencia_pagadora', 'conta_corrente'),
                )
            },
        ),
        (
            'TIPO DE CRÉDITO',
            {'fields': (('codigo_tipo_credito', 'descricao_tipo_credito'),)},
        ),
        (
            'INFORMAÇÕES ADICIONAIS',
            {
                'fields': (
                    ('possui_representante_legal', 'possui_procurador'),
                    ('possui_entidade_representacao', 'bloqueado_para_emprestimo'),
                    ('margem_disponivel', 'margem_disponivel_cartao'),
                    ('valor_limite_cartao', 'qtd_emprestimos_ativos_suspensos'),
                    ('qtd_emprestimos_ativos', 'qtd_emprestimos_suspensos'),
                    ('qtd_emprestimos_refin', 'qtd_emprestimos_porta'),
                    ('data_consulta', 'elegivel_emprestimo'),
                    ('margem_disponivel_rcc', 'valor_limite_rcc'),
                    (
                        'valor_liquido',
                        'valor_comprometido',
                        'valor_maximo_comprometimento',
                    ),
                )
            },
        ),
        (
            'PENSÃO ALIMENTÍCIA',
            {
                'fields': (
                    ('codigo_pensao_alimenticia', 'descricao_pensao_alimenticia'),
                )
            },
        ),
    )


class AceiteIN100Admin(admin.ModelAdmin):
    list_display = (
        'cpf_cliente',
        'data_aceite',
        'data_criacao_token',
        'display_produto',
    )
    search_fields = ('cpf_cliente',)

    inlines = [
        DocumentoAceiteIN100Inline,
        DadosBeneficioIN100Inline,
        HistoricoAceiteIN100Inline,
    ]

    fields = (
        'cpf_cliente',
        'canal',
        'hash_assinatura',
        'data_aceite',
        'data_vencimento_aceite',
        'token_in100',
        'data_criacao_token',
        'data_vencimento_token',
        'display_produto',
    )

    readonly_fields = (
        'cpf_cliente',
        'canal',
        'hash_assinatura',
        'data_aceite',
        'data_vencimento_aceite',
        'token_in100',
        'data_criacao_token',
        'data_vencimento_token',
        'display_produto',
    )

    def display_produto(self, obj):
        enum_dict = {
            value: name
            for name, value in EnumTipoProduto.__dict__.items()
            if not name.startswith('__')
        }
        try:
            id = enum_dict.get(int(obj.produto))
        except Exception as e:
            print(e)
            id = ' '
        return f'{id}'.replace('_', ' ')

    display_produto.short_description = 'Produto'


class FeatureToggleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name',)


class BackofficeConfigsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Desabilita o botão de adicionar se já existir uma instância
        if BackofficeConfigs.objects.exists():
            return False
        return super().has_add_permission(request)

    def save_model(self, request, obj, form, change):
        if not change:
            # Se estiver tentando adicionar uma nova instância, verifica se já existe uma.
            if BackofficeConfigs.objects.exists():
                form.add_error(
                    None, 'Não é possível criar mais de uma configuração de backoffice.'
                )
                return
        # Se estiver editando a instância existente, simplesmente salve.
        obj.save()

    list_display = (
        '__str__',
        'session_expiration_time',
        'email_password_expiration_days',
        'subsequent_password_expiration_days',
    )
    search_fields = ('session_expiration_time',)


class DossieINSSCodigoFilter(SimpleListFilter):
    title = 'Status da Requisição'
    parameter_name = 'status_requisicao'

    def lookups(self, request, model_admin):
        return (
            ('sucesso', 'Sucesso'),
            ('falha', 'Falha'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'sucesso':
            queryset = queryset.filter(codigo_retorno='BD')
        elif value == 'falha':
            queryset = queryset.exclude(codigo_retorno='BD')
        return queryset


class DossieINSSAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        'cpf',
        'data_envio',
        'link_numero_contrato',
        'requisicao_bem_sucedida',
    )
    search_fields = ('cpf', 'contrato__pk')
    list_filter = (DossieINSSCodigoFilter, 'data_envio')
    resource_class = DossieINSSResource

    def link_numero_contrato(self, obj):
        url = reverse('admin:contract_contrato_change', args=[obj.contrato.pk])
        return format_html('<a href="{}">{}</a>', url, obj.contrato.pk)

    link_numero_contrato.allow_tags = True
    link_numero_contrato.short_description = 'Número do Contrato'

    def requisicao_bem_sucedida(self, obj):
        return obj.codigo_retorno == 'BD'

    requisicao_bem_sucedida.short_description = 'Requisição bem sucedida?'
    requisicao_bem_sucedida.boolean = True

    def numero_contrato(self, obj):
        return obj.contrato.pk

    numero_contrato.short_description = 'Número do contrato'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class RegraTeimosinhaINSSAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'codigo',
        'descricao',
        'produto',
        'intervalo_reprocessamento',
        'quantidade_tentativas',
        'ativo',
        'criado_em',
        'modificado_em',
    )
    list_filter = ('ativo', 'produto', 'codigo')
    search_fields = (
        'codigo',
        'descricao',
    )


admin.site.register(BancosBrasileiros, BancosBrasileirosAdmin)
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(AceiteIN100, AceiteIN100Admin)
admin.site.register(Contrato, ContratoAdmin)
admin.site.register(ParametrosBackoffice, ParametrosBackofficeAdmin)
admin.site.register(Convenios, ConveniosAdmin)
admin.site.register(INSSBeneficioTipo, INSSBeneficioTipoAdmin)
admin.site.register(ParametrosProduto, ParametrosProdutoAdmin)
admin.site.register(Taxa, TaxaAdmin)
admin.site.register(EnvelopeContratos, EnvelopeContratosAdmin)
admin.site.register(TermosDeUso, TermosDeUsoAdmin)
admin.site.register(FaixaIdade, FaixaIdadeAdmin)
admin.site.register(ComissaoTaxa, ComissaoTaxaAdmin)
admin.site.register(Data, DataAdmin)
admin.site.register(EspecieIN100, EspecieIN100Admin)
admin.site.register(FeatureToggle, FeatureToggleAdmin)
admin.site.register(ReportSettings, ReportSettingsAdmin)
admin.site.register(BackofficeConfigs, BackofficeConfigsAdmin)
admin.site.register(DossieINSS, DossieINSSAdmin)

if settings.ENVIRONMENT != 'PROD':
    admin.site.register(RegraTeimosinhaINSS, RegraTeimosinhaINSSAdmin)
