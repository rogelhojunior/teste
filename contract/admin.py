from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from contract.constants import EnumTipoProduto
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    Portabilidade,
    SaqueComplementar,
)
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from core.models import Cliente
from core.utils import calcular_idade
import logging

logger = logging.getLogger('digitacao')


# Recebe uma variavel pasa saber se o relatorio é no front ou no backoffice
def contrato_resource_export(isFront):
    class ContratoResource(resources.ModelResource):
        numero_contrato = fields.Field(
            column_name='Nr Proposta', attribute='numero_contrato'
        )
        cliente = fields.Field(
            column_name='Nome Cliente',
            attribute='cliente',
            widget=ForeignKeyWidget(Cliente, 'nome_cliente'),
        )
        numero_cpf = fields.Field(
            column_name='CPF Cliente',
            attribute='numero_cpf',
        )
        idade = fields.Field(
            column_name='Idade Cliente',
            attribute='idade',
        )
        especie_beneficio = fields.Field(
            column_name='Espécie Cliente', attribute='especie_beneficio'
        )
        status = fields.Field(
            column_name='Status Proposta',
            attribute='status',
        )
        contrato_assinado = fields.Field(
            column_name='Contrato Assinado?',
            attribute='contrato_assinado',
        )
        contrato_pago = fields.Field(
            column_name='Contrato Pago?',
            attribute='contrato_pago',
        )
        tipo_produto = fields.Field(
            column_name='Produto',
            attribute='tipo_produto',
        )
        tipo_contrato = fields.Field(
            column_name='Convênio',
            attribute='tipo_contrato',
        )
        corban = fields.Field(
            column_name='Corban',
            attribute='corban',
            widget=ForeignKeyWidget('custom_auth.Corban', 'corban_name'),
        )
        login_usuario = fields.Field(
            column_name='Identificador do Usuário',
            widget=ForeignKeyWidget('custom_auth.UserProfile', 'identifier'),
        )
        digitado_por = fields.Field(
            column_name='Usuario Digitador',
            widget=ForeignKeyWidget('custom_auth.UserProfile', '__str__'),
        )
        vlr_proposta = fields.Field(
            column_name='Valor Proposta',
            attribute='vlr_proposta',
        )
        vlr_liberado_cliente = fields.Field(
            column_name='Valor Liberado Cliente',
            attribute='vlr_liberado_cliente',
        )
        data_cadastro = fields.Field(
            column_name='Data Cadastro',
            attribute='data_cadastro',
        )
        data_status = fields.Field(
            column_name='Data Status',
            attribute='data_status',
        )
        data_integracao = fields.Field(
            column_name='Data Integração',
            attribute='data_integracao',
        )
        qtd_parcelas = fields.Field(
            column_name='Qtd Parcelas',
            attribute='qtd_parcelas',
        )
        vlr_parcela = fields.Field(
            column_name='Valor Parcela',
            attribute='vlr_parcela',
        )
        taxa_operacao = fields.Field(
            column_name='Taxa da operação',
            attribute='taxa_operacao',
        )
        cet_ano = fields.Field(
            column_name='Taxa CET a.a.',
            attribute='cet_ano',
        )
        cet_mes = fields.Field(
            column_name='Taxa CET a.m.',
            attribute='cet_mes',
        )
        taxa_efetiva_ano = fields.Field(
            column_name='Taxa efetiva a.a.',
            attribute='taxa_efetiva_ano',
        )
        taxa_efetiva_mes = fields.Field(
            column_name='Taxa efetiva a.m.',
            attribute='taxa_efetiva_mes',
        )
        vlr_tac = fields.Field(
            column_name='Valor TAC',
            attribute='vlr_tac',
        )
        vlr_iof = fields.Field(
            column_name='Valor do IOF',
            attribute='vlr_iof',
        )
        vlr_iof_adicional = fields.Field(
            column_name='IOF Adicional',
            attribute='vlr_iof_adicional',
        )
        vlr_iof_seguro = fields.Field(
            column_name='Valor IOF Seguro',
            attribute='vlr_iof_seguro',
        )
        vlr_iof_total = fields.Field(
            column_name='Valor IOF total',
            attribute='vlr_iof_total',
        )
        limite_pre_aprovado = fields.Field(
            column_name='Limite pré aprovado',
            attribute='limite_pre_aprovado',
        )
        seguro = fields.Field(
            column_name='Seguro',
            attribute='seguro',
        )
        vr_seguro = fields.Field(
            column_name='Valor do seguro',
            attribute='vr_seguro',
        )
        taxa_seguro = fields.Field(
            column_name='Taxa do seguro',
            attribute='taxa_seguro',
        )
        plano = fields.Field(
            column_name='Plano',
            attribute='plano',
        )
        enviado_documento_pessoal = fields.Field(
            column_name='Documento pessoal enviado?',
            attribute='enviado_documento_pessoal',
        )
        pendente_documento_pessoal = fields.Field(
            column_name='Documento pessoal pendente?',
            attribute='pendente_documento_pessoal',
        )
        campos_pendentes = fields.Field(
            column_name='Campos Pendentes?',
            attribute='campos_pendentes',
        )
        enviado_comprovante_residencia = fields.Field(
            column_name='Comprovante de residência enviado?',
            attribute='enviado_comprovante_residencia',
        )
        pendente_comprovante_residencia = fields.Field(
            column_name='Comprovante de residência pendente?',
            attribute='pendente_comprovante_residencia',
        )
        selfie_enviada = fields.Field(
            column_name='Selfie enviada?',
            attribute='selfie_enviada',
        )
        selfie_pendente = fields.Field(
            column_name='Selfie pendente?',
            attribute='selfie_pendente',
        )
        contracheque_enviado = fields.Field(
            column_name='Contracheque enviado?',
            attribute='contracheque_enviado',
        )
        contracheque_pendente = fields.Field(
            column_name='Contracheque pendente?',
            attribute='contracheque_pendente',
        )
        adicional_enviado = fields.Field(
            column_name='Adicional enviado?',
            attribute='adicional_enviado',
        )
        adicional_pendente = fields.Field(
            column_name='Adicional pendente?',
            attribute='adicional_pendente',
        )
        observacoes = fields.Field(
            column_name='Observações',
            attribute='observacoes',
        )
        restricoes = fields.Field(
            column_name='Restricoes',
            attribute='restricoes',
        )
        regras_validadas = fields.Field(
            column_name='Regras validadas',
            attribute='regras_validadas',
        )
        token_contrato = fields.Field(
            column_name='Token Contrato',
            attribute='token_contrato',
        )
        token_envelope = fields.Field(
            column_name='Token Envelope',
            attribute='token_envelope',
        )
        numero_contrato_original = fields.Field(
            column_name='Contrato Original Portabilidade',
            attribute='numero_contrato_original',
        )
        banco_atacado = fields.Field(
            column_name='Banco Atacado',
            attribute='banco_atacado',
        )
        quantidade_de_parcelas_digitadas = fields.Field(
            column_name='Quantidade Parcelas Digitadas',
            attribute='quantidade_de_parcelas_digitadas',
        )
        quantidade_de_parcelas_cip = fields.Field(
            column_name='Quantidade Parcelas Retornadas',
            attribute='quantidade_de_parcelas_cip',
        )
        valor_parcela = fields.Field(
            column_name='Valor Parcela Digitada',
            attribute='valor_parcela',
        )
        valor_parcela_cip = fields.Field(
            column_name='Valor Parcela Retornada',
            attribute='valor_parcela_cip',
        )
        valor_parcela_recalculada = fields.Field(
            column_name='Valor Parcela Recalculada',
            attribute='valor_parcela_recalculada',
        )
        valor_proposta_digitada = fields.Field(
            column_name='Saldo Devedor Digitado',
            attribute='valor_proposta_digitada',
        )
        valor_proposta_cip = fields.Field(
            column_name='Saldo Devedor Retornado',
            attribute='valor_proposta_cip',
        )
        taxa_digitada = fields.Field(
            column_name='Taxa Digitada',
            attribute='taxa_digitada',
        )
        taxa_cip = fields.Field(
            column_name='Taxa Retornada',
            attribute='taxa_cip',
        )
        taxa_recalculada = fields.Field(
            column_name='Taxa Recalculada',
            attribute='taxa_recalculada',
        )
        recusa_portabilidade = fields.Field(
            column_name='Recusa de Portabilidade CIP',
            attribute='recusa_portabilidade',
        )
        data_envio_CIP = fields.Field(
            column_name='Data Envio CIP',
            attribute='data_envio_CIP',
        )
        data_retorno_saldo_CIP = fields.Field(
            column_name='Data Retorno Saldo CIP',
            attribute='data_retorno_saldo_CIP',
        )
        troco = fields.Field(
            column_name='Valor do Troco',
            attribute='troco',
        )
        troco_recalculado = fields.Field(
            column_name='Valor do Troco Recalculado',
            attribute='troco_recalculado',
        )
        saldo_devedor = fields.Field(
            column_name='Saldo Devedor',
            attribute='saldo_devedor',
        )
        wanted_fields = []

        def __init__(self, *args, **kwargs):
            self.queryset_pks = None
            super(ContratoResource, self).__init__(*args, **kwargs)

            if isFront:
                self.wanted_fields = [
                    'numero_cpf',
                    'numero_contrato',
                    'digitado_por',
                    'cliente',
                    'idade',
                    'status',
                    'tipo_produto',
                    'tipo_contrato',
                    'corban',
                    'login_usuario',
                    'vlr_proposta',
                    'vlr_liberado_cliente',
                    'data_cadastro',
                    'data_status',
                    'data_integracao',
                    'qtd_parcelas',
                    'vlr_parcela',
                    'taxa_operacao',
                    'troco',
                    'troco_recalculado',
                    'limite_pre_aprovado',
                    'seguro',
                    'vr_seguro',
                    'taxa_seguro',
                    'plano',
                    'enviado_documento_pessoal',
                    'pendente_documento_pessoal',
                    'campos_pendentes',
                    'enviado_comprovante_residencia',
                    'pendente_comprovante_residencia',
                    'selfie_enviada',
                    'selfie_pendente',
                    'contracheque_enviado',
                    'contracheque_pendente',
                    'adicional_enviado',
                    'adicional_pendente',
                    'recusa_portabilidade',
                    'data_envio_CIP',
                    'data_retorno_saldo_CIP',
                    'valor_proposta_cip',
                    'taxa_recalculada',
                ]
            else:
                self.wanted_fields = [
                    'numero_contrato',
                    'cliente',
                    'numero_cpf',
                    'idade',
                    'especie_beneficio',
                    'status',
                    'contrato_assinado',
                    'contrato_pago',
                    'tipo_produto',
                    'tipo_contrato',
                    'corban',
                    'login_usuario',
                    'digitado_por',
                    'vlr_proposta',
                    'vlr_liberado_cliente',
                    'data_cadastro',
                    'data_status',
                    'data_integracao',
                    'qtd_parcelas',
                    'vlr_parcela',
                    'taxa_operacao',
                    'cet_ano',
                    'cet_mes',
                    'taxa_efetiva_ano',
                    'taxa_efetiva_mes',
                    'vlr_tac',
                    'vlr_iof',
                    'vlr_iof_adicional',
                    'vlr_iof_seguro',
                    'vlr_iof_total',
                    'limite_pre_aprovado',
                    'seguro',
                    'vr_seguro',
                    'taxa_seguro',
                    'plano',
                    'enviado_documento_pessoal',
                    'pendente_documento_pessoal',
                    'campos_pendentes',
                    'enviado_comprovante_residencia',
                    'pendente_comprovante_residencia',
                    'selfie_enviada',
                    'selfie_pendente',
                    'contracheque_enviado',
                    'contracheque_pendente',
                    'adicional_enviado',
                    'adicional_pendente',
                    'observacoes',
                    'restricoes',
                    'regras_validadas',
                    'token_contrato',
                    'token_envelope',
                    'numero_contrato_original',
                    'banco_atacado',
                    'quantidade_de_parcelas_digitadas',
                    'quantidade_de_parcelas_cip',
                    'valor_parcela',
                    'valor_parcela_cip',
                    'valor_parcela_recalculada',
                    'valor_proposta_digitada',
                    'valor_proposta_cip',
                    'taxa_digitada',
                    'taxa_cip',
                    'taxa_recalculada',
                    'recusa_portabilidade',
                    'data_envio_CIP',
                    'data_retorno_saldo_CIP',
                    'troco',
                    'troco_recalculado',
                ]
            for field_name in list(self.fields.keys()):
                if field_name not in self.wanted_fields:
                    self.fields.pop(field_name)

        def set_queryset_pks(self, queryset_pks):
            self.queryset_pks = queryset_pks

        def get_queryset(self):
            return Contrato.objects.filter(pk__in=self.queryset_pks)

        def get_export_headers(self):
            headers = super(ContratoResource, self).get_export_headers()
            return [
                header
                for header, field_name in zip(headers, self.fields.keys(), strict=False)
                if field_name in self.wanted_fields
            ]

        class Meta:
            model = Contrato

        def dehydrate_cliente(self, contrato):
            if contrato.cliente and contrato.cliente.nome_cliente:
                return contrato.cliente.nome_cliente

            else:
                return ''

        def dehydrate_numero_contrato(self, contrato):
            if contrato.id:
                return contrato.id
            return ''

        def dehydrate_numero_cpf(self, contrato):
            if contrato.cliente:
                return contrato.cliente.nu_cpf
            return ''

        def dehydrate_idade(self, contrato):
            if contrato.cliente:
                return calcular_idade(contrato.cliente.dt_nascimento)
            return ''

        def dehydrate_especie_beneficio(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                EnumTipoProduto.MARGEM_LIVRE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if contrato.cliente and contrato.cliente.cliente_in100.exists():
                    return contrato.cliente.cliente_in100.first().cd_beneficio_tipo
            return ''

        def dehydrate_status(self, contrato):
            try:
                return contrato.get_status_produto
            except Exception as e:
                logger.error(f'Contrato {contrato.pk} não possui objeto: {e}')
                return ''

        def dehydrate_contrato_assinado(self, contrato):
            if contrato.contrato_assinado:
                return 'SIM'
            return 'NÃO'

        def dehydrate_contrato_pago(self, contrato):
            if contrato.contrato_pago:
                return 'SIM'
            return 'NÃO'

        def dehydrate_tipo_produto(self, contrato):
            return contrato.get_tipo_produto_display()

        def dehydrate_tipo_contrato(self, contrato):
            if contrato.tipo_produto in {
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
                EnumTipoProduto.SAQUE_COMPLEMENTAR,
            }:
                if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    saque_complementar = SaqueComplementar.objects.filter(
                        contrato=contrato
                    )

                    if saque_complementar.exists():
                        if (
                            cliente_cartao
                            := saque_complementar.first().id_cliente_cartao
                        ):
                            convenio = getattr(cliente_cartao, 'convenio', None)
                            if convenio is not None:
                                return convenio
                        return 'Convênio não encontrado'
                    else:
                        return 'Saque Complementar não encontrado'
                else:
                    if cartao_beneficio := CartaoBeneficio.objects.filter(
                        contrato=contrato
                    ).last():
                        if cartao_beneficio.convenio:
                            return cartao_beneficio.convenio
                        else:
                            return 'Contrato sem CONVÊNIO'
                    else:
                        return 'Cartão Benefício não encontrado'
            if contrato.tipo_produto in {
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                EnumTipoProduto.MARGEM_LIVRE,
            }:
                return 'INSS'
            return contrato.get_cd_contrato_tipo_display()

        def dehydrate_login_usuario(self, contrato):
            if contrato.created_by:
                return str(contrato.created_by.identifier)
            return ''

        def dehydrate_digitado_por(self, contrato):
            if contrato.created_by:
                return str(contrato.created_by)
            return ''

        def dehydrate_saldo_devedor(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().saldo_devedor_atualizado:
                    return (
                        contrato.contrato_portabilidade.last().saldo_devedor_atualizado
                    )
                else:
                    return contrato.contrato_portabilidade.last().saldo_devedor
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().saldo_devedor_atualizado:
                    return (
                        contrato.contrato_portabilidade.last().saldo_devedor_atualizado
                    )
                else:
                    return contrato.contrato_portabilidade.last().saldo_devedor

        def dehydrate_vlr_proposta(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().saldo_devedor_atualizado:
                    return (
                        contrato.contrato_portabilidade.last().saldo_devedor_atualizado
                    )
                else:
                    return contrato.contrato_portabilidade.last().saldo_devedor
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                if contrato.contrato_refinanciamento.last().valor_total_recalculado:
                    return (
                        contrato.contrato_refinanciamento.last().valor_total_recalculado
                    )
                else:
                    return contrato.contrato_refinanciamento.last().valor_total
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                if contrato.contrato_margem_livre.last().vr_contrato:
                    return contrato.contrato_margem_livre.last().vr_contrato
                else:
                    return ''
            if contrato.tipo_produto in {
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
                EnumTipoProduto.SAQUE_COMPLEMENTAR,
            }:
                if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    if (
                        saque_complementar
                        := contrato.contrato_saque_complementar.last()
                    ):
                        if not saque_complementar:
                            return 'N/A'
                        return saque_complementar.valor_saque
                else:
                    contrato_cartao_beneficio = (
                        contrato.contrato_cartao_beneficio.last()
                    )
                    if not contrato_cartao_beneficio:
                        return 'N/A'
                    if (
                        contrato_cartao_beneficio
                        and contrato_cartao_beneficio.valor_saque
                    ):
                        return contrato_cartao_beneficio.valor_saque
                    elif not (
                        contrato_cartao_beneficio.possui_saque
                        or contrato_cartao_beneficio.saque_parcelado
                    ):
                        return 'sem saque'
            return ''

        def dehydrate_vlr_liberado_cliente(self, contrato):
            if contrato.tipo_produto in (EnumTipoProduto.PORTABILIDADE,):
                return '0'
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                if contrato.contrato_refinanciamento.last().troco:
                    return contrato.contrato_refinanciamento.last().troco
                else:
                    return ''
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                if contrato.contrato_margem_livre.last().vr_liberado_cliente:
                    return contrato.contrato_margem_livre.last().vr_liberado_cliente
                else:
                    return ''
            if contrato.tipo_produto in {
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            }:
                contrato_cartao_beneficio = contrato.contrato_cartao_beneficio.last()
                if not contrato_cartao_beneficio:
                    return 'N/A'
                if contrato_cartao_beneficio and contrato_cartao_beneficio.valor_saque:
                    return contrato_cartao_beneficio.valor_saque
            return ''

        def dehydrate_data_cadastro(self, contrato):
            if contrato.criado_em:
                return str(contrato.criado_em.strftime('%Y-%m-%d'))
            return ''

        def dehydrate_data_status(self, contrato):
            if contrato.ultima_atualizacao:
                return str(contrato.ultima_atualizacao.strftime('%Y-%m-%d'))
            return ''

        def dehydrate_data_integracao(self, contrato):
            if contrato.dt_pagamento_contrato:
                return str(contrato.dt_pagamento_contrato.strftime('%Y-%m-%d'))
            return ''

        def dehydrate_qtd_parcelas(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().numero_parcela_atualizada:
                    return (
                        contrato.contrato_portabilidade.last().numero_parcela_atualizada
                    )
                else:
                    return contrato.contrato_portabilidade.last().prazo
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                if contrato.contrato_margem_livre.last().qtd_parcelas:
                    return contrato.contrato_margem_livre.last().qtd_parcelas
                else:
                    return ''
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                if contrato.contrato_refinanciamento.last().prazo:
                    return contrato.contrato_refinanciamento.last().prazo
                else:
                    return ''
            if contrato.tipo_produto in [
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
                EnumTipoProduto.SAQUE_COMPLEMENTAR,
            ]:
                if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                    contrato_saque_complementar = (
                        contrato.contrato_saque_complementar.last()
                    )
                    if not contrato_saque_complementar:
                        return 'N/A'
                    if (
                        contrato_saque_complementar.possui_saque
                        or contrato_saque_complementar.saque_parcelado
                    ):
                        if contrato_saque_complementar.possui_saque:
                            return 'saque a vista'
                        elif (
                            contrato_saque_complementar
                            and contrato_saque_complementar.qtd_parcela_saque_parcelado
                        ):
                            return (
                                contrato_saque_complementar.qtd_parcela_saque_parcelado
                            )
                    else:
                        return 'sem saque'
                else:
                    contrato_cartao_beneficio_last = (
                        contrato.contrato_cartao_beneficio.last()
                    )
                    if not contrato_cartao_beneficio_last:
                        return 'N/A'
                    if (
                        contrato_cartao_beneficio_last.possui_saque
                        or contrato_cartao_beneficio_last.saque_parcelado
                        or contrato_cartao_beneficio_last.possui_saque_complementar
                    ):
                        if contrato_cartao_beneficio_last.possui_saque:
                            return 'saque a vista'
                        if (
                            contrato_cartao_beneficio_last
                            and contrato_cartao_beneficio_last.qtd_parcela_saque_parcelado
                        ):
                            return contrato_cartao_beneficio_last.qtd_parcela_saque_parcelado
                    else:
                        return 'sem saque'
                return ''

        def dehydrate_vlr_parcela(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().valor_parcela_recalculada:
                    return (
                        contrato.contrato_portabilidade.last().valor_parcela_recalculada
                    )
                if contrato.contrato_portabilidade.last().valor_parcela_original:
                    return contrato.contrato_portabilidade.last().valor_parcela_original
                else:
                    return contrato.contrato_portabilidade.last().parcela_digitada
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                if contrato.contrato_margem_livre.last().vr_parcelas:
                    return contrato.contrato_margem_livre.last().vr_parcelas
                else:
                    return ''
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                if contrato.contrato_refinanciamento.last().valor_parcela_recalculada:
                    return contrato.contrato_refinanciamento.last().valor_parcela_recalculada
                if contrato.contrato_refinanciamento.last().valor_parcela_original:
                    return (
                        contrato.contrato_refinanciamento.last().valor_parcela_original
                    )
                else:
                    return contrato.contrato_refinanciamento.last().parcela_digitada
            if contrato.tipo_produto in {
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            }:
                contrato_cartao_beneficio = contrato.contrato_cartao_beneficio.last()
                if not contrato_cartao_beneficio:
                    return 'N/A'
                if (
                    contrato_cartao_beneficio
                    and contrato_cartao_beneficio.valor_parcela
                ):
                    return contrato_cartao_beneficio.valor_parcela
            return ''

        def dehydrate_taxa_operacao(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().taxa_contrato_recalculada:
                    return (
                        contrato.contrato_portabilidade.last().taxa_contrato_recalculada
                    )
                if contrato.contrato_portabilidade.last().taxa_contrato_original:
                    return contrato.contrato_portabilidade.last().taxa_contrato_original
                else:
                    return contrato.contrato_portabilidade.last().taxa
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                if contrato.contrato_margem_livre.last().taxa_contrato_recalculada:
                    return (
                        contrato.contrato_margem_livre.last().taxa_contrato_recalculada
                    )
                else:
                    return ''
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                if contrato.contrato_refinanciamento.last().taxa_contrato_recalculada:
                    return contrato.contrato_refinanciamento.last().taxa_contrato_recalculada
                if contrato.contrato_refinanciamento.last().taxa_contrato_original:
                    return (
                        contrato.contrato_refinanciamento.last().taxa_contrato_original
                    )
                else:
                    return contrato.contrato_refinanciamento.last().taxa

            if contrato.taxa:
                return contrato.taxa
            return ''

        def dehydrate_cet_ano(self, contrato):
            if contrato.cet_ano:
                return contrato.cet_ano
            return ''

        def dehydrate_cet_mes(self, contrato):
            if contrato.cet_mes:
                return contrato.cet_mes
            return ''

        def dehydrate_taxa_efetiva_ano(self, contrato):
            if contrato.taxa_efetiva_ano:
                return contrato.taxa_efetiva_ano
            return ''

        def dehydrate_taxa_efetiva_mes(self, contrato):
            if contrato.taxa_efetiva_mes:
                return contrato.taxa_efetiva_mes
            return ''

        def dehydrate_vlr_tac(self, contrato):
            if contrato.vr_tac:
                return contrato.vr_tac
            return ''

        def dehydrate_vlr_iof(self, contrato):
            if contrato.vr_iof:
                return contrato.vr_iof
            return ''

        def dehydrate_vlr_iof_adicional(self, contrato):
            if contrato.vr_iof_adicional:
                return contrato.vr_iof_adicional
            return ''

        def dehydrate_vlr_iof_seguro(self, contrato):
            if contrato.vr_iof_seguro:
                return contrato.vr_iof_seguro
            return ''

        def dehydrate_vlr_iof_total(self, contrato):
            if contrato.vr_iof_total:
                return contrato.vr_iof_total
            return ''

        def dehydrate_limite_pre_aprovado(self, contrato):
            if contrato.tipo_produto in {
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            }:
                return contrato.limite_pre_aprovado
            return ''

        def dehydrate_seguro(self, contrato):
            if contrato.seguro:
                return contrato.seguro
            return ''

        def dehydrate_vr_seguro(self, contrato):
            if contrato.vr_seguro:
                return contrato.vr_seguro
            return ''

        def dehydrate_taxa_seguro(self, contrato):
            if contrato.taxa_seguro:
                return contrato.taxa_seguro
            return ''

        def dehydrate_plano(self, contrato):
            if contrato.plano.exists():
                return contrato.plano.first().nome
            return ''

        def dehydrate_enviado_documento_pessoal(self, contrato):
            if contrato.enviado_documento_pessoal:
                return 'SIM'
            return 'NÃO'

        def dehydrate_pendente_documento_pessoal(self, contrato):
            if contrato.pendente_documento:
                return 'SIM'
            return 'NÃO'

        def dehydrate_campos_pendentes(self, contrato):
            if contrato.campos_pendentes:
                return 'SIM'
            return 'NÃO'

        def dehydrate_enviado_comprovante_residencia(self, contrato):
            if contrato.enviado_comprovante_residencia:
                return 'SIM'
            return 'NÃO'

        def dehydrate_pendente_comprovante_residencia(self, contrato):
            if contrato.pendente_endereco:
                return 'SIM'
            return 'NÃO'

        def dehydrate_selfie_enviada(self, contrato):
            if contrato.selfie_enviada:
                return 'SIM'
            return 'NÃO'

        def dehydrate_selfie_pendente(self, contrato):
            if contrato.selfie_pendente:
                return 'SIM'
            return 'NÃO'

        def dehydrate_contracheque_enviado(self, contrato):
            if contrato.contracheque_enviado:
                return 'SIM'
            return 'NÃO'

        def dehydrate_contracheque_pendente(self, contrato):
            if contrato.contracheque_pendente:
                return 'SIM'
            return 'NÃO'

        def deydrate_adicional_enviado(self, contrato):
            if contrato.adicional_enviado:
                return 'SIM'
            return 'NÃO'

        def dehydrate_adicional_pendente(self, contrato):
            if contrato.adicional_pendente:
                return 'SIM'
            return 'NÃO'

        def dehydrate_observacoes(self, contrato):
            status_contrato = StatusContrato.objects.filter(contrato=contrato)
            if status_contrato.exists():
                for i in status_contrato:
                    if i.nome == ContractStatus.REPROVADA_MESA_DE_FORMALIZACAO.value:
                        return i.descricao_mesa
                    elif i.nome == ContractStatus.REPROVADA_MESA_FORMALIZACAO.value:
                        return i.descricao_mesa
                    elif i.nome == ContractStatus.REPROVADA_POLITICA_INTERNA.value:
                        return i.descricao_mesa
                    elif i.nome == ContractStatus.REPROVADA_FINALIZADA.value:
                        return i.descricao_mesa
                    elif i.nome == ContractStatus.SALDO_REPROVADO.value:
                        return i.descricao_mesa
                if status_contrato.last().descricao_mesa:
                    return status_contrato.last().descricao_mesa
            return ''

        def dehydrate_restricoes(self, contrato):
            restricoes = contrato.contrato_validacoes.all().filter(checked=False)
            restricoes_list = []
            for restricao in restricoes:
                restricoes_list.append(restricao.mensagem_observacao)
            return ''.join(restricoes_list)

        def dehydrate_regras_validadas(self, contrato):
            validacao_contrato = ValidacaoContrato.objects.filter(contrato=contrato)
            for validacao in validacao_contrato:
                if not validacao.checked:
                    return 'NAO'
            return 'SIM'

        def dehydrate_token_contrato(self, contrato):
            if contrato.token_contrato:
                return str(contrato.token_contrato)
            return ''

        def dehydrate_token_envelope(self, contrato):
            if contrato.token_envelope:
                return str(contrato.token_envelope)
            return ''

        def dehydrate_numero_contrato_original(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return ''
                return (
                    contrato.contrato_portabilidade.last().numero_portabilidade_CTC_CIP
                )
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_portabilidade.last():
                    return ''
                return (
                    contrato.contrato_portabilidade.last().numero_portabilidade_CTC_CIP
                )
            return ''

        def dehydrate_banco_atacado(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return ''
                return contrato.contrato_portabilidade.last().banco
            return ''

        def dehydrate_quantidade_de_parcelas_digitadas(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return ''
                return contrato.contrato_portabilidade.last().prazo
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return ''
                return contrato.contrato_refinanciamento.last().prazo
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return ''
                return contrato.contrato_margem_livre.last().qtd_parcelas
            return ''

        def dehydrate_quantidade_de_parcelas_cip(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return ''
                return contrato.contrato_portabilidade.last().numero_parcela_atualizada
            return ''

        def dehydrate_valor_parcela(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().parcela_digitada
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                return contrato.contrato_refinanciamento.last().parcela_digitada
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                return contrato.contrato_margem_livre.last().vr_parcelas
            return ''

        def dehydrate_valor_parcela_cip(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().valor_parcela_original
            return ''

        def dehydrate_valor_parcela_recalculada(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().valor_parcela_recalculada
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().valor_parcela_recalculada
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                return contrato.contrato_margem_livre.last().valor_parcela_recalculada
            return ''

        def dehydrate_valor_proposta_digitada(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().saldo_devedor
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                return contrato.contrato_refinanciamento.last().saldo_devedor
            return ''

        def dehydrate_valor_proposta_cip(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().saldo_devedor_atualizado
            return ''

        def dehydrate_taxa_digitada(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().taxa
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                return contrato.contrato_refinanciamento.last().taxa
            return ''

        def dehydrate_taxa_cip(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().taxa_contrato_original:
                    taxa = (
                        1
                        + float(
                            contrato.contrato_portabilidade.last().taxa_contrato_original
                            / 100
                        )
                    ) ** (1 / 12) - 1
                    return taxa * 100
            return ''

        def dehydrate_taxa_recalculada(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().taxa_contrato_recalculada
            if contrato.tipo_produto in (EnumTipoProduto.MARGEM_LIVRE,):
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                return contrato.contrato_margem_livre.last().taxa_contrato_recalculada
            return ''

        def dehydrate_valor_motivo_recusa(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                return contrato.contrato_portabilidade.last().motivo_recusa
            return ''

        def dehydrate_recusa_portabilidade(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                portabilidade = Portabilidade.objects.filter(contrato=contrato).last()
                if not portabilidade:
                    return ''
                if portabilidade.motivo_recusa:
                    return f'Recusa na CIP: {portabilidade.motivo_recusa}'
            return ''

        def dehydrate_data_envio_CIP(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().dt_envio_proposta_CIP:
                    return str(
                        contrato.contrato_portabilidade.last().dt_envio_proposta_CIP.strftime(
                            '%Y-%m-%d'
                        )
                    )
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                if not contrato.contrato_margem_livre.last():
                    return 'N/A'
                if contrato.contrato_margem_livre.last().dt_envio_proposta_CIP:
                    return str(
                        contrato.contrato_margem_livre.last().dt_envio_proposta_CIP.strftime(
                            '%Y-%m-%d'
                        )
                    )
            return ''

        def dehydrate_data_retorno_saldo_CIP(self, contrato):
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                if not contrato.contrato_portabilidade.last():
                    return 'N/A'
                if contrato.contrato_portabilidade.last().dt_recebimento_saldo_devedor:
                    return str(
                        contrato.contrato_portabilidade.last().dt_recebimento_saldo_devedor.strftime(
                            '%Y-%m-%d'
                        )
                    )
                elif contrato.contrato_portabilidade.last().dt_recusa_retido:
                    return str(
                        contrato.contrato_portabilidade.last().dt_recusa_retido.strftime(
                            '%Y-%m-%d'
                        )
                    )
            return ''

        def dehydrate_troco(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                return contrato.contrato_refinanciamento.last().troco

        def dehydrate_troco_recalculado(self, contrato):
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                if not contrato.contrato_refinanciamento.last():
                    return 'N/A'
                return contrato.contrato_refinanciamento.last().troco_recalculado

    return ContratoResource
