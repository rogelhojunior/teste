# built in imports
import logging

from django.utils import timezone

# third party imports
from rest_framework import serializers

# local imports
from contract.constants import EnumTipoProduto, EnumTipoAnexo, EnumEscolaridade
from contract.models.contratos import Contrato
from contract.models.envelope_contratos import EnvelopeContratos
from contract.models.regularizacao_contrato import RegularizacaoContrato
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import Convenios
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.consignado_inss.models.especie import EspecieIN100
from core.api.serializers import RogadoSerializer, TestemunhaSerializer
from core.models import Cliente, Testemunha
from core.models.cliente import DadosBancarios
from contract.models.tentativa_teimosinha_inss import TentativaTeimosinhaINSS
from core.utils import calcular_idade_cliente
from custom_auth.models import Corban, Produtos, UserProfile

from .PaymentRefusedIncomingDataSerializer import PaymentRefusedIncomingDataSerializer
from ...models.anexo_contrato import AnexoContrato

# constants
STATUS_CCB_PTBR = {
    0: 'Pendente Submissão',
    1: 'Pendente Resposta',
    2: 'Pendente de Aceitação',
    3: 'Aprovado pelo Originador',
    4: 'Cancelado',
    5: 'Retido',
    6: 'Acordo Enviado',
    7: 'Confirmação Pendente de resolução',
    8: 'Pago',
    9: 'Rejeitado',
    10: 'Assinatura Recebida',
    11: 'Garantia',
}

# global code
logger = logging.getLogger('digitacao')


class DetalheEspecieIN100(serializers.ModelSerializer):
    class Meta:
        model = EspecieIN100
        fields = '__all__'


class DetalheDadosBancariosSerializer(serializers.ModelSerializer):
    class Meta:
        model = DadosBancarios
        fields = '__all__'


class DetalheClienteSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.CharField()
    dados_bancarios = serializers.SerializerMethodField()
    tipo_cliente = serializers.CharField(
        source='get_tipo_cliente_display', read_only=True
    )
    documento_uf = serializers.CharField(
        source='get_documento_uf_display', read_only=True
    )
    documento_tipo = serializers.CharField(
        source='get_documento_tipo_display', read_only=True
    )
    endereco_residencial_tipo = serializers.CharField(
        source='get_endereco_residencial_tipo_display', read_only=True
    )

    class Meta:
        model = Cliente
        fields = '__all__'

    def get_dados_bancarios(self, obj):
        try:
            if dados_bancarios := obj.cliente_dados_bancarios.order_by().last():
                return {
                    'id': dados_bancarios.pk or '',
                    'conta_tipo': dados_bancarios.get_conta_tipo_display() or '',
                    'conta_banco': dados_bancarios.conta_banco or '',
                    'conta_agencia': dados_bancarios.conta_agencia or '',
                    'conta_numero': dados_bancarios.conta_numero or '',
                    'conta_digito': dados_bancarios.conta_digito or '',
                }
            return {}
        except Exception as e:
            logger.error(f'Erro ao pegar os dados bancários (get_dados_bancarios): {e}')
            return {}


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['name']  # Ou o campo que contém o nome do usuário


class ContratoSerializer(serializers.ModelSerializer):
    cliente = DetalheClienteSerializer(many=False, read_only=True)
    status = serializers.CharField(source='get_status_display', read_only=True)
    cartao_beneficio = serializers.SerializerMethodField()
    portabilidade = serializers.SerializerMethodField()
    margem_livre = serializers.SerializerMethodField()
    saque_complementar = serializers.SerializerMethodField()
    portabilidade_refin = serializers.SerializerMethodField()
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Contrato
        fields = '__all__'

    def get_cartao_beneficio(self, obj):
        try:
            if cartao_beneficio := obj.contrato_cartao_beneficio.first():
                return {
                    'status': cartao_beneficio.status or '',
                    'folha': cartao_beneficio.folha or '',
                    'verba': cartao_beneficio.verba or '',
                    'numero_contrato_averbadora': cartao_beneficio.numero_contrato_averbadora
                    or '',
                    'possui_saque': cartao_beneficio.possui_saque or '',
                    'possui_saque_complementar': cartao_beneficio.possui_saque_complementar
                    or '',
                    'valor_disponivel_saque': cartao_beneficio.valor_disponivel_saque
                    or '',
                    'valor_saque': cartao_beneficio.valor_saque or '',
                    'valor_financiado': cartao_beneficio.valor_financiado or '',
                    'codigo_instituicao': cartao_beneficio.codigo_instituicao or '',
                    'carencia': cartao_beneficio.carencia or '',
                    'reserva': cartao_beneficio.reserva or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Cartão Benefício: {e}')  # Adicione esta linha
            return {}

    def get_portabilidade(self, obj):
        try:
            if portabilidade := obj.contrato_portabilidade.first():
                status_qi = portabilidade.status_ccb
                # Obter o status correspondente em português
                status_qi_ptbr = STATUS_CCB_PTBR.get(status_qi, status_qi)

                return {
                    'saldo_devedor': portabilidade.saldo_devedor or '',
                    'saldo_devedor_atualizado': portabilidade.saldo_devedor_atualizado
                    or '',
                    'parcela_digitada': portabilidade.parcela_digitada or '',
                    'nova_parcela': portabilidade.nova_parcela or '',
                    'numero_contrato': portabilidade.numero_contrato or '',
                    'banco': portabilidade.banco or '',
                    'quantidade_parcela': portabilidade.prazo or '',
                    'quantidade_parcela_atualizada': portabilidade.numero_parcela_atualizada
                    or '',
                    'taxa': portabilidade.taxa or '',
                    'status_qi': status_qi_ptbr,
                    'status': portabilidade.status or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Portabilidade: {e}')  # Adicione esta linha
            return {}

    def get_margem_livre(self, obj):
        try:
            if margem_livre := obj.contrato_margem_livre.first():
                return {
                    'status': margem_livre.status or '',
                    'vr_contrato': margem_livre.vr_contrato or '',
                    'qtd_parcelas': margem_livre.qtd_parcelas or '',
                    'vr_parcelas': margem_livre.vr_parcelas or '',
                    'vr_liberado_cliente': margem_livre.vr_liberado_cliente or '',
                    'taxa_contrato_recalculada': margem_livre.taxa_contrato_recalculada
                    or '',
                    'valor_parcela_recalculada': margem_livre.valor_parcela_recalculada
                    or '',
                    'ccb_gerada': margem_livre.ccb_gerada or '',
                    'sucesso_insercao_proposta': margem_livre.sucesso_insercao_proposta
                    or '',
                    'insercao_sem_sucesso': margem_livre.insercao_sem_sucesso or '',
                    'sucesso_envio_assinatura': margem_livre.sucesso_envio_assinatura
                    or '',
                    'motivo_envio_assinatura': margem_livre.motivo_envio_assinatura
                    or '',
                    'sucesso_envio_documento_frente_cnh': margem_livre.sucesso_envio_documento_frente_cnh
                    or '',
                    'motivo_envio_documento_frente_cnh': margem_livre.motivo_envio_documento_frente_cnh
                    or '',
                    'sucesso_envio_documento_verso': margem_livre.sucesso_envio_documento_verso
                    or '',
                    'motivo_envio_documento_verso': margem_livre.motivo_envio_documento_verso
                    or '',
                    'sucesso_envio_documento_selfie': margem_livre.sucesso_envio_documento_selfie
                    or '',
                    'motivo_envio_documento_selfie': margem_livre.motivo_envio_documento_selfie
                    or '',
                    'sucesso_documentos_linkados': margem_livre.sucesso_documentos_linkados
                    or '',
                    'motivo_documentos_linkados': margem_livre.motivo_documentos_linkados
                    or '',
                    'sucesso_submissao_proposta': margem_livre.sucesso_submissao_proposta
                    or '',
                    'motivo_submissao_proposta': margem_livre.motivo_submissao_proposta
                    or '',
                    'sucesso_aceite_proposta': margem_livre.sucesso_aceite_proposta
                    or '',
                    'motivo_aceite_proposta': margem_livre.motivo_aceite_proposta or '',
                    'sucesso_recusa_proposta': margem_livre.sucesso_recusa_proposta
                    or '',
                    'motivo_recusa_proposta': margem_livre.motivo_recusa_proposta or '',
                    'cd_retorno_averbacao': margem_livre.cd_retorno_averbacao or '',
                    'codigo_dataprev': margem_livre.codigo_dataprev or '',
                    'descricao_dataprev': margem_livre.descricao_dataprev or '',
                    'dt_retorno_dataprev': margem_livre.dt_retorno_dataprev or '',
                    'dt_vencimento_primeira_parcela': margem_livre.dt_vencimento_primeira_parcela
                    or '',
                    'dt_vencimento_ultima_parcela': margem_livre.dt_vencimento_ultima_parcela
                    or '',
                    'vr_tarifa_cadastro': margem_livre.vr_tarifa_cadastro or '',
                    'fl_seguro': margem_livre.fl_seguro or '',
                    'vr_seguro': margem_livre.vr_seguro or '',
                    'dt_liberado_cliente': margem_livre.dt_liberado_cliente or '',
                    'related_party_key': margem_livre.related_party_key or '',
                    'dt_envio_proposta_CIP': margem_livre.dt_envio_proposta_CIP or '',
                    'collateral_key': margem_livre.collateral_key or '',
                    'document_key_QiTech_CCB': margem_livre.document_key_QiTech_CCB
                    or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Margem Livre: {e}')  # Adicione esta linha
            return {}

    def get_saque_complementar(self, obj):
        try:
            if saque_complementar := obj.contrato_saque_complementar.first():
                return {
                    'status': saque_complementar.status or '',
                    'valor_disponivel_saque': saque_complementar.valor_disponivel_saque
                    or '',
                    'valor_lancado_fatura': saque_complementar.valor_lancado_fatura
                    or '',
                    'valor_total_a_pagar': saque_complementar.valor_total_a_pagar or '',
                    'saque_parcelado': saque_complementar.saque_parcelado or '',
                    'valor_parcela': saque_complementar.valor_parcela or '',
                    'qtd_parcela_saque_parcelado': saque_complementar.qtd_parcela_saque_parcelado
                    or '',
                    'numero_proposta_banksoft': saque_complementar.numero_proposta_banksoft
                    or '',
                    'valor_saque': saque_complementar.valor_saque or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar dados do Saque complementar: {e}')
            return {}

    def get_portabilidade_refin(self, instance: Contrato) -> dict[str, any]:
        try:
            port = instance.contrato_portabilidade.first()
            refin = instance.contrato_refinanciamento.first()
            if port and refin:
                if port.status != ContractStatus.INT_FINALIZADO.value:
                    return {
                        'banco': refin.banco or '',
                        'status': port.status or '',
                        'status_port': port.status or '',
                        'nova_parcela': refin.nova_parcela or 0,
                        'numero_contrato': refin.numero_contrato or 0,
                        'prazo': refin.prazo or 0,
                        'valor_total': refin.valor_total or 0,
                        'margem_liberada': refin.margem_liberada or 0,
                        'taxa': refin.taxa or 0,
                        'troco': refin.troco or 0,
                        'troco_recalculado': refin.troco_recalculado or 0,
                    }

                return {
                    'banco': refin.banco or '',
                    'status': refin.status or '',
                    'status_port': port.status or '',
                    'nova_parcela': refin.nova_parcela or 0,
                    'numero_contrato': refin.numero_contrato or 0,
                    'prazo': refin.prazo or 0,
                    'valor_total': refin.valor_total or 0,
                    'margem_liberada': refin.margem_liberada or 0,
                    'taxa': refin.taxa or 0,
                    'troco': refin.troco or 0,
                    'troco_recalculado': refin.troco_recalculado or 0,
                }

            return {}

        except Exception:
            logger.exception('Error when querying refinancing.')
            return {}


class DetalheCorbanSerializer(serializers.ModelSerializer):
    corban_pai = serializers.CharField(source='corban_pai_', read_only=True)

    class Meta:
        model = Corban
        fields = '__all__'


class DetalheContratoSerializer(serializers.ModelSerializer):
    cliente = DetalheClienteSerializer(many=False, read_only=True)
    corban = DetalheCorbanSerializer(many=False, read_only=True)
    cd_contrato_tipo = serializers.CharField(
        source='get_cd_contrato_tipo_display', read_only=True
    )
    cartao_beneficio = serializers.SerializerMethodField()
    portabilidade = serializers.SerializerMethodField()
    margem_livre = serializers.SerializerMethodField()
    saque_complementar = serializers.SerializerMethodField()
    usuario_info = serializers.SerializerMethodField()
    url_formalizacao = serializers.SerializerMethodField()
    id_pending_account = serializers.SerializerMethodField()
    portabilidade_refin = serializers.SerializerMethodField()
    pendencia_averbacao = serializers.SerializerMethodField()
    rogado = serializers.SerializerMethodField()
    testemunhas = serializers.SerializerMethodField()
    teimosinha_inss = serializers.SerializerMethodField()

    class Meta:
        model = Contrato
        fields = '__all__'

    def get_url_formalizacao(self, obj):
        if obj.tipo_produto not in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            EnumTipoProduto.MARGEM_LIVRE,
        ):
            return obj.url_formalizacao
        try:
            dados_in100_exist = DadosIn100.objects.filter(
                numero_beneficio=obj.numero_beneficio
            ).exists()
            status = StatusContrato.objects.filter(contrato=obj).last()
            if dados_in100_exist:
                dados_in100 = DadosIn100.objects.filter(
                    numero_beneficio=obj.numero_beneficio
                ).first()
                especie = EspecieIN100.objects.filter(
                    numero_especie=dados_in100.cd_beneficio_tipo
                ).exists()
                if dados_in100.retornou_IN100:
                    if not especie:
                        return None
                    if dados_in100.situacao_beneficio in [
                        'INELEGÍVEL',
                        'BLOQUEADA',
                        'BLOQUEADO',
                    ]:
                        return None
                    if status.nome in {
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
                        return None
                    else:
                        return obj.url_formalizacao
            return None
        except Exception as e:
            print(f'Erro ao buscar o link: {e}')
            return {}

    def get_usuario_info(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            groups = [group.name for group in request.user.groups.all()]
            return {
                'nome': request.user.name,
                'grupo': groups,
            }
        return None

    def get_cartao_beneficio(self, obj):
        try:
            if cartao_beneficio := obj.contrato_cartao_beneficio.first():
                necessita_assinatura_fisica = bool(
                    (
                        cartao_beneficio.convenio.necessita_assinatura_fisica
                        and calcular_idade_cliente(obj.cliente)
                        >= cartao_beneficio.convenio.idade_minima_assinatura
                    )
                )
                return {
                    'status': cartao_beneficio.status or '',
                    'folha': cartao_beneficio.folha or '',
                    'verba': cartao_beneficio.verba or '',
                    'numero_contrato_averbadora': cartao_beneficio.numero_contrato_averbadora
                    or '',
                    'possui_saque': cartao_beneficio.possui_saque or '',
                    'possui_saque_complementar': cartao_beneficio.possui_saque_complementar
                    or '',
                    'saque_parcelado': cartao_beneficio.saque_parcelado or '',
                    'valor_parcela': cartao_beneficio.valor_parcela or '',
                    'qtd_parcela_saque_parcelado': cartao_beneficio.qtd_parcela_saque_parcelado
                    or '',
                    'valor_total_a_pagar': cartao_beneficio.valor_total_a_pagar or '',
                    'valor_disponivel_saque': cartao_beneficio.valor_disponivel_saque
                    or '',
                    'valor_saque': cartao_beneficio.valor_saque or '',
                    'valor_financiado': cartao_beneficio.valor_financiado or '',
                    'codigo_instituicao': cartao_beneficio.codigo_instituicao or '',
                    'carencia': cartao_beneficio.carencia or '',
                    'reserva': cartao_beneficio.reserva or '',
                    'numero_proposta_banksoft': cartao_beneficio.numero_proposta_banksoft
                    or '',
                    'necessita_assinatura_fisica': necessita_assinatura_fisica or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Cartão Benefício: {e}')  # Adicione esta linha
            return {}

    def get_portabilidade(self, obj):
        try:
            if portabilidade := obj.contrato_portabilidade.first():
                status_qi = portabilidade.status_ccb
                # Obter o status correspondente em português
                status_qi_ptbr = STATUS_CCB_PTBR.get(status_qi, status_qi)

                return {
                    'saldo_devedor': portabilidade.saldo_devedor or '',
                    'saldo_devedor_atualizado': portabilidade.saldo_devedor_atualizado
                    or '',
                    'parcela_digitada': portabilidade.parcela_digitada or '',
                    'nova_parcela': portabilidade.nova_parcela or '',
                    'numero_contrato': portabilidade.numero_contrato or '',
                    'valor_parcela_recalculada': portabilidade.valor_parcela_recalculada
                    or '',
                    'banco': portabilidade.banco or '',
                    'quantidade_parcela': portabilidade.prazo or '',
                    'quantidade_parcela_atualizada': portabilidade.numero_parcela_atualizada
                    or '',
                    'taxa': portabilidade.taxa or '',
                    'taxa_recalculada': portabilidade.taxa_contrato_recalculada or '',
                    'status_qi': status_qi_ptbr,
                    'status_qi_num': portabilidade.status_ccb,
                    'status': portabilidade.status or '',
                    'cpf_irregular_na_receita': portabilidade.CPF_dados_divergentes,
                    'motivo_recusa_cip': portabilidade.motivo_recusa,
                    'codigo_dataprev': portabilidade.codigo_dataprev or '',
                    'descricao_dataprev': portabilidade.descricao_dataprev or '',
                    'dt_retorno_dataprev': portabilidade.dt_retorno_dataprev or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Portabilidade: {e}')  # Adicione esta linha
            return {}

    def get_margem_livre(self, obj):
        try:
            if margem_livre := obj.contrato_margem_livre.first():
                return {
                    'status': margem_livre.status or '',
                    'vr_contrato': margem_livre.vr_contrato or '',
                    'qtd_parcelas': margem_livre.qtd_parcelas or '',
                    'vr_parcelas': margem_livre.vr_parcelas or '',
                    'vr_liberado_cliente': margem_livre.vr_liberado_cliente or '',
                    'cpf_irregular_na_receita': margem_livre.CPF_dados_divergentes,
                    'taxa_contrato_recalculada': margem_livre.taxa_contrato_recalculada
                    or '',
                    'valor_parcela_recalculada': margem_livre.valor_parcela_recalculada
                    or '',
                    'ccb_gerada': margem_livre.ccb_gerada or '',
                    'sucesso_insercao_proposta': margem_livre.sucesso_insercao_proposta
                    or '',
                    'insercao_sem_sucesso': margem_livre.insercao_sem_sucesso or '',
                    'sucesso_envio_assinatura': margem_livre.sucesso_envio_assinatura
                    or '',
                    'motivo_envio_assinatura': margem_livre.motivo_envio_assinatura
                    or '',
                    'sucesso_envio_documento_frente_cnh': margem_livre.sucesso_envio_documento_frente_cnh
                    or '',
                    'motivo_envio_documento_frente_cnh': margem_livre.motivo_envio_documento_frente_cnh
                    or '',
                    'sucesso_envio_documento_verso': margem_livre.sucesso_envio_documento_verso
                    or '',
                    'motivo_envio_documento_verso': margem_livre.motivo_envio_documento_verso
                    or '',
                    'sucesso_envio_documento_selfie': margem_livre.sucesso_envio_documento_selfie
                    or '',
                    'motivo_envio_documento_selfie': margem_livre.motivo_envio_documento_selfie
                    or '',
                    'sucesso_documentos_linkados': margem_livre.sucesso_documentos_linkados
                    or '',
                    'motivo_documentos_linkados': margem_livre.motivo_documentos_linkados
                    or '',
                    'sucesso_submissao_proposta': margem_livre.sucesso_submissao_proposta
                    or '',
                    'motivo_submissao_proposta': margem_livre.motivo_submissao_proposta
                    or '',
                    'sucesso_aceite_proposta': margem_livre.sucesso_aceite_proposta
                    or '',
                    'motivo_aceite_proposta': margem_livre.motivo_aceite_proposta or '',
                    'sucesso_recusa_proposta': margem_livre.sucesso_recusa_proposta
                    or '',
                    'motivo_recusa_proposta': margem_livre.motivo_recusa_proposta or '',
                    'cd_retorno_averbacao': margem_livre.cd_retorno_averbacao or '',
                    'codigo_dataprev': margem_livre.codigo_dataprev or '',
                    'descricao_dataprev': margem_livre.descricao_dataprev or '',
                    'dt_retorno_dataprev': margem_livre.dt_retorno_dataprev or '',
                    'dt_vencimento_primeira_parcela': margem_livre.dt_vencimento_primeira_parcela
                    or '',
                    'dt_vencimento_ultima_parcela': margem_livre.dt_vencimento_ultima_parcela
                    or '',
                    'vr_tarifa_cadastro': margem_livre.vr_tarifa_cadastro or '',
                    'fl_seguro': margem_livre.fl_seguro or '',
                    'vr_seguro': margem_livre.vr_seguro or '',
                    'dt_liberado_cliente': margem_livre.dt_liberado_cliente or '',
                    'related_party_key': margem_livre.related_party_key or '',
                    'dt_envio_proposta_CIP': margem_livre.dt_envio_proposta_CIP or '',
                    'collateral_key': margem_livre.collateral_key or '',
                    'document_key_QiTech_CCB': margem_livre.document_key_QiTech_CCB
                    or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar INSS: {e}')  # Adicione esta linha
            return {}

    def get_saque_complementar(self, obj):
        try:
            if saque_complementar := obj.contrato_saque_complementar.first():
                return {
                    'status': saque_complementar.status or '',
                    'valor_disponivel_saque': saque_complementar.valor_disponivel_saque
                    or '',
                    'valor_lancado_fatura': saque_complementar.valor_lancado_fatura
                    or '',
                    'valor_total_a_pagar': saque_complementar.valor_total_a_pagar or '',
                    'saque_parcelado': saque_complementar.saque_parcelado or '',
                    'valor_parcela': saque_complementar.valor_parcela or '',
                    'qtd_parcela_saque_parcelado': saque_complementar.qtd_parcela_saque_parcelado
                    or '',
                    'numero_proposta_banksoft': saque_complementar.numero_proposta_banksoft
                    or '',
                    'valor_saque': saque_complementar.valor_saque or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar dados do Saque complementar: {e}')
            return {}

    def get_id_pending_account(self, obj):
        return obj.get_pending_account().pk if obj.is_there_a_pending_account() else ''

    def get_portabilidade_refin(self, instance: Contrato) -> dict[str, any]:
        try:
            port = instance.contrato_portabilidade.first()
            refin = instance.contrato_refinanciamento.first()
            recalculado = False
            if StatusContrato.objects.filter(
                contrato=instance,
                nome=ContractStatus.RETORNO_IN100_RECALCULO_RECEBIDO.value,
            ).exists():
                recalculado = True
            if port and refin:
                if refin.troco_recalculado:
                    recalculado = True
                return {
                    'banco': refin.banco or '',
                    'status': refin.status or '',
                    'status_port': port.status or '',
                    'nova_parcela': refin.nova_parcela or 0,
                    'parcela': refin.parcela_digitada or 0,
                    'numero_contrato': refin.numero_contrato or 0,
                    'prazo': refin.prazo or 0,
                    'valor_total': refin.valor_total or 0,
                    'margem_liberada': refin.margem_liberada or 0,
                    'taxa': refin.taxa or 0,
                    'taxa_recalculada': refin.taxa_contrato_recalculada or 0,
                    'troco': refin.troco or 0,
                    'troco_recalculado': refin.troco_recalculado or 0,
                    'cpf_irregular_na_receita': refin.CPF_dados_divergentes,
                    'saldo_devedor': port.saldo_devedor,
                    'saldo_devedor_atualizado': port.saldo_devedor_atualizado,
                    'recalculado': recalculado,
                }
            return {}

        except Exception:
            logger.exception('Error when querying refinancing.')
            return {}

    def get_pendencia_averbacao(self, instance: Contrato) -> dict[str, any]:
        try:
            if regularizacao_contrato := RegularizacaoContrato.objects.filter(
                contrato=instance,
                active=True,
            ).last():
                return {
                    'tipo_pendencia': regularizacao_contrato.tipo_pendencia or None,
                    'mensagem_pendencia': regularizacao_contrato.mensagem_pendencia
                    or None,
                    'anexo_url_pendencia': regularizacao_contrato.get_attachment_url_pendencia
                    or None,
                }
            return None
        except Exception as e:
            print(f'Erro ao buscar pendência de averbação: {e}')
            return None

    def get_teimosinha_inss(self, instance: Contrato) -> bool:
        try:
            return TentativaTeimosinhaINSS.objects.filter(contrato=instance).exists()
        except Exception as e:
            print(f'Erro ao buscar Teimosinha INSS: {e}')
            return None

    def get_rogado(self, instance: Contrato):
        client = instance.cliente
        if (
            client
            and client.escolaridade == EnumEscolaridade.ANALFABETO
            and hasattr(instance, 'rogado')
        ):
            return RogadoSerializer(instance.rogado).data
        return None

    def get_testemunhas(self, instance: Contrato):
        client = instance.cliente
        if (
            client
            and client.escolaridade == EnumEscolaridade.ANALFABETO
            and (
                testemunhas := Testemunha.objects.filter(
                    cliente=client, contratos=instance
                )
            )
        ):
            return TestemunhaSerializer(testemunhas, many=True).data
        return None


class ClienteCallCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = (
            'nu_cpf',
            'nome_cliente',
        )


class StatusContratoSerializer(serializers.ModelSerializer):
    data_fase_inicial = serializers.SerializerMethodField()
    data_fase_final = serializers.SerializerMethodField()

    class Meta:
        model = StatusContrato
        fields = (
            'id',
            'nome',
            'descricao_mesa',
            'descricao_front',
            'data_fase_inicial',
            'data_fase_final',
            'contrato',
        )

    def get_data_fase_inicial(self, obj):
        if obj.data_fase_inicial:
            return obj.data_fase_inicial.astimezone(
                timezone.get_current_timezone()
            ).strftime('%d/%m/%Y - %H:%M:%S')
        else:
            return None

    def get_data_fase_final(self, obj):
        if obj.data_fase_final:
            return obj.data_fase_final.astimezone(
                timezone.get_current_timezone()
            ).strftime('%d/%m/%Y - %H:%M:%S')
        else:
            return None


class ConveniosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Convenios
        fields = ('nome',)


class CallCenterContratoSerializer(serializers.ModelSerializer):
    cliente = ClienteCallCenterSerializer(many=False, read_only=True)
    tipo_produto = serializers.CharField(
        source='get_tipo_produto_display', read_only=True
    )
    cd_contrato_tipo = serializers.CharField(
        source='get_cd_contrato_tipo_display', read_only=True
    )
    cartao_beneficio = serializers.SerializerMethodField()
    saque_complementar = serializers.SerializerMethodField()
    corban = DetalheCorbanSerializer(many=False, read_only=True)

    def get_cartao_beneficio(self, obj):
        try:
            cartao_beneficio = obj.contrato_cartao_beneficio.first()
            convenio = cartao_beneficio.convenio
            convenio_serializer = ConveniosSerializer(convenio)
            if cartao_beneficio:
                return {
                    'possui_saque': cartao_beneficio.possui_saque,
                    'valor_saque': cartao_beneficio.valor_saque,
                    'valor_financiado': cartao_beneficio.valor_financiado,
                    'status': cartao_beneficio.get_status_display() or '',
                    'convenio': convenio_serializer.data,
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Cartão Benefício: {e}')  # Adicione esta linha
            return {}

    def get_saque_complementar(self, obj):
        try:
            if saque_complementar := obj.contrato_saque_complementar.first():
                return {
                    'status': saque_complementar.get_status_display() or '',
                    'valor_saque': saque_complementar.valor_saque or '',
                    'valor_disponivel_saque': saque_complementar.valor_disponivel_saque
                    or '',
                    'valor_total_a_pagar': saque_complementar.valor_total_a_pagar or '',
                    'valor_lancado_fatura': saque_complementar.valor_lancado_fatura
                    or '',
                    'saque_parcelado': saque_complementar.saque_parcelado or '',
                    'valor_parcela': saque_complementar.valor_parcela or '',
                    'qtd_parcela_saque_parcelado': saque_complementar.qtd_parcela_saque_parcelado
                    or '',
                }
            return {}
        except Exception as e:
            logger.error(
                f'Erro ao consultar saque complementar (get_saque_complementar): {e}'
            )
            return {}

    class Meta:
        model = Contrato
        fields = (
            'id',
            'cliente',
            'tipo_produto',
            'cd_contrato_tipo',
            'corban',
            'cartao_beneficio',
            'saque_complementar',
            'limite_pre_aprovado',
            'criado_em',
            'ultima_atualizacao',
            'contrato_assinado',
            'contrato_pago',
            'enviado_documento_pessoal',
            'pendente_documento',
            'enviado_comprovante_residencia',
            'pendente_endereco',
            'selfie_enviada',
            'selfie_pendente',
            'contracheque_enviado',
            'contracheque_pendente',
            'taxa',
            'taxa_efetiva_ano',
            'adicional_enviado',
            'adicional_pendente',
            'vr_iof_total',
            'cet_mes',
            'cet_ano',
            'seguro',
            'vr_seguro',
        )


class CallCenterClienteSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.CharField()
    documento_tipo = serializers.CharField(
        source='get_documento_tipo_display', read_only=True
    )
    endereco_residencial_tipo = serializers.CharField(
        source='get_endereco_residencial_tipo_display', read_only=True
    )
    cliente_cartao = serializers.SerializerMethodField()

    def get_cliente_cartao(self, obj):
        try:
            cliente_cartao = obj.cliente_dados_cartao_beneficio.first()
            convenio = cliente_cartao.convenio
            convenio_serializer = ConveniosSerializer(convenio)

            return (
                {
                    'convenio': convenio_serializer.data,
                }
                if cliente_cartao
                else {}
            )
        except Exception as e:
            print(f'Erro ao buscar Cartão Benefício: {e}')  # Adicione esta linha
            return {}

    class Meta:
        model = Cliente
        fields = (
            'id',
            'nu_cpf',
            'nome_cliente',
            'dt_nascimento',
            'sexo',
            'estado_civil',
            'nome_mae',
            'nome_pai',
            'documento_tipo',
            'documento_numero',
            'documento_data_emissao',
            'documento_orgao_emissor',
            'documento_uf',
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
            'tempo_residencia',
            'email',
            'telefone_celular',
            'conjuge_nome',
            'conjuge_cpf',
            'conjuge_data_nascimento',
            'cliente_cartao',
        )


class DocumentoProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produtos
        fields = '__all__'


class LimitesDisponibilidadesSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    limite_total_saque = serializers.FloatField()
    limite_disponivel_saque = serializers.FloatField()
    limite_utilizado_saque = serializers.FloatField()
    limite_pre_aprovado = serializers.FloatField()
    valor_minimo_saque = serializers.FloatField()
    valor_maximo_saque = serializers.FloatField()
    apto_saque = serializers.BooleanField()


class UnicoCallbackDataSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.IntegerField()
    score = serializers.FloatField()


class UnicoCallbackSerializer(serializers.Serializer):
    data = UnicoCallbackDataSerializer()


class PendingRegistrationRegularizationRequestSerializer(serializers.Serializer):
    token_contrato = serializers.CharField()
    mensagem_regularizacao = serializers.CharField(required=False, allow_blank=True)
    arquivo_regularizacao = serializers.FileField(required=False)

    def validate(self, attrs):
        if not attrs.get('mensagem_regularizacao') and not attrs.get(
            'arquivo_regularizacao'
        ):
            raise serializers.ValidationError(
                'É obrigatório ter pelo menos a "mensagem_regularizacao" ou o "arquivo_regularizacao".'
            )
        return attrs


class LinkFormalizacaoAnalfabetoSerializer(serializers.ModelSerializer):
    url_formalizacao_curta = serializers.CharField(
        source='url_formalizacao', read_only=True
    )

    class Meta:
        model = Contrato
        fields = (
            'url_formalizacao_curta',
            'url_formalizacao_rogado',
        )


class StubbornINSSHistoryRequestSerializer(serializers.Serializer):
    token_contrato = serializers.CharField()
    page = serializers.IntegerField(required=False)
    items_per_page = serializers.IntegerField(required=False)


class TentativaTeimosinhaINSSSerializer(serializers.ModelSerializer):
    class Meta:
        model = TentativaTeimosinhaINSS
        fields = (
            'id',
            'solicitada_em',
            'respondida_em',
            'proxima_tentativa_em',
            'sucesso',
        )
