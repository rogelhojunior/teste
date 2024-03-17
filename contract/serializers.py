import logging

from rest_framework import serializers
from rest_framework.parsers import MultiPartParser

from contract.constants import EnumEscolaridade
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    MargemLivre,
    Portabilidade,
)
from contract.products.cartao_beneficio.models.planos import BOOL_CHOICES, Planos
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.api.serializers import RogadoSerializer
from core.models.cliente import Cliente

logger = logging.getLogger('digitacao')


class DetalheClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ('id', 'nu_cpf', 'nome_cliente', 'dt_nascimento')


class ContratoSerializer(serializers.ModelSerializer):
    cliente = DetalheClienteSerializer(many=False, read_only=True)

    class Meta:
        model = Contrato
        fields = ('nuContratoFacta', 'dtDigitacao', 'status', 'cliente', 'vrContrato')


class DetalheContratoSerializer(serializers.ModelSerializer):
    cliente = DetalheClienteSerializer(many=False, read_only=True)

    class Meta:
        model = Contrato
        fields = (
            'cliente',
            'nuContratoFacta',
            'tipoProduto',
            'qtParcelasTotal',
            'status',
            'vrLiberadoCliente',
            'dtPrimeiroVencimento',
            'txEfetivaMes',
            'txEfetivaAno',
            'txCETMes',
            'txCETAno',
        )


class EnvioLinkFormalizacaoSerializer(serializers.ModelSerializer):
    urlFormalizacaoCurta = serializers.URLField()
    dtDigitacao = serializers.CharField()

    class Meta:
        model = Contrato
        fields = 'token_contrato', 'urlFormalizacaoCurta', 'dtDigitacao'


class AtualizarProcessoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrato
        fields = ('id_processo_unico',)


class DocumentosContratoSerializer(serializers.ModelSerializer):
    parser_classes = [MultiPartParser]

    class Meta:
        model = AnexoContrato
        fields = (
            'contrato',
            'arquivo',
            'nome_anexo',
            'tipo_anexo',
            'anexo_extensao',
            'anexo_url',
            'anexado_em',
        )


class DocumentosContratoPortabilidadeSerializer(serializers.ModelSerializer):
    parser_classes = [MultiPartParser]
    token_envelope = serializers.CharField(required=True)

    class Meta:
        model = AnexoContrato
        fields = (
            'token_envelope',
            'arquivo',
            'nome_anexo',
            'tipo_anexo',
            'anexo_extensao',
            'anexo_url',
            'anexado_em',
        )


class ClienteConsultaSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.CharField()
    rogado = serializers.SerializerMethodField()

    class Meta:
        model = Cliente
        fields = '__all__'

    def get_rogado(self, instance: Cliente):
        if instance.escolaridade == EnumEscolaridade.ANALFABETO and hasattr(
            instance, 'rogado'
        ):
            return RogadoSerializer(instance.rogado).data
        return None


class PortabilidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portabilidade
        fields = '__all__'


class MargemLivreSerializer(serializers.ModelSerializer):
    class Meta:
        model = MargemLivre
        fields = '__all__'


class CartaoBeneficioSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartaoBeneficio
        fields = '__all__'


class ConsultaAutorizacaoIN100Serializer(serializers.ModelSerializer):
    class Meta:
        model = DadosIn100
        fields = '__all__'


class PlanoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Planos
        fields = ['nome', 'valor_pago_cliente', 'carencia']


class ContratoFormalizacaoSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    portabilidade = serializers.SerializerMethodField()
    margem_livre = serializers.SerializerMethodField()
    cartao_beneficio = serializers.SerializerMethodField()
    saque_complementar = serializers.SerializerMethodField()
    plano = serializers.SerializerMethodField()
    portabilidade_refin = serializers.SerializerMethodField()

    class Meta:
        model = Contrato
        fields = '__all__'

    def get_plano(self, obj):
        try:
            # Pegando todos os planos associados ao contrato
            planos_associados = obj.contrato_planos_contratados.filter()
            resultados = []
            for plano in planos_associados:
                valor_premio = plano.plano.valor_segurado.replace('.', '').replace(
                    ',', '.'
                )
                plano_data = {
                    'nome': plano.plano.tipo_plano,
                    'valor_plano': plano.valor_plano,
                    'valor_premio': float(valor_premio),
                    'carencia': plano.plano.carencia,
                    'descricao': plano.plano.descricao_plano,
                    'gratuito': BOOL_CHOICES[plano.plano.gratuito][0] == 0,
                }
                resultados.append(plano_data)
            return resultados
        except Exception as e:
            logger.error(f'Erro ao consultar planos: {e}')
            return []

    def get_portabilidade(self, obj):
        try:
            if portabilidade := obj.contrato_portabilidade.first():
                return {
                    'banco': portabilidade.banco or '',
                    'numero_contrato': portabilidade.numero_contrato or '',
                    'saldo_devedor': portabilidade.saldo_devedor or '',
                    'prazo': portabilidade.prazo or '',
                    'taxa': portabilidade.taxa or '',
                    'nova_parcela': portabilidade.nova_parcela or '',
                    'ccb_gerada': portabilidade.ccb_gerada or '',
                }
            return {}
        except Exception as e:
            logger.error(f'Erro ao consultar portabilidade (get_portabilidade): {e}')
            return {}

    def get_saque_complementar(self, obj):
        try:
            if saque_complementar := obj.contrato_saque_complementar.first():
                return {
                    'status': saque_complementar.status or '',
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
                    'valor_total_a_pagar': cartao_beneficio.valor_total_a_pagar or '',
                    'valor_saque': cartao_beneficio.valor_saque or '',
                    'valor_financiado': cartao_beneficio.valor_financiado or '',
                    'codigo_instituicao': cartao_beneficio.codigo_instituicao or '',
                    'carencia': cartao_beneficio.carencia or '',
                    'reserva': cartao_beneficio.reserva or '',
                    'saque_parcelado': cartao_beneficio.saque_parcelado or '',
                    'valor_parcela': cartao_beneficio.valor_parcela or '',
                    'qtd_parcela_saque_parcelado': cartao_beneficio.qtd_parcela_saque_parcelado
                    or '',
                    'convenio_inss': cartao_beneficio.convenio.convenio_inss or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Cartão Benefício: {e}')  # Adicione esta linha
            return {}

    def get_portabilidade_refin(self, instance: Contrato) -> dict[str, any]:
        try:
            port = instance.contrato_portabilidade.first()
            refin = instance.contrato_refinanciamento.first()
            if port and refin:
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


class ContratoFormalizacaoSerializerPendente(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)

    class Meta:
        model = Contrato
        fields = '__all__'


class CriarContratoSerializer(serializers.ModelSerializer):
    cliente = DetalheClienteSerializer(many=False, read_only=True)

    class Meta:
        model = Contrato
        fields = ('cliente', 'token_contrato', 'id', 'chave_proposta')


class AtualizarContratoSerializer(serializers.Serializer):
    # ...
    class Meta:
        model = Contrato
        fields = '__all__'

    def update(self, instance, validated_data):
        instance.anexo_base64 = validated_data.get(
            'anexo_base64', serializers.CharField(max_length=10000)
        )
        instance.nome_anexo = validated_data.get('nome_anexo', serializers.CharField())
        instance.tipo_anexo = validated_data.get(
            'tipo_anexo', serializers.IntegerField()
        )
        instance.anexo_extensao = validated_data.get(
            'anexo_extensao', serializers.CharField()
        )
        instance.anexo_url = validated_data.get('anexo_url', serializers.CharField())
        instance.save()
        return instance

    #
    # token = serializers.CharField()
    # anexo_base64 = serializers.CharField(max_length=10000)
    # nome_anexo = serializers.CharField()
    # tipo_anexo = serializers.IntegerField()
    # anexo_extensao = serializers.CharField()
    # anexo_url = serializers.CharField()


class AtualizarCartaoBeneficioSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartaoBeneficio
        fields = '__all__'


class ContratoKPISerializer(serializers.Serializer):
    tipo_produto = serializers.IntegerField()
    count = serializers.IntegerField()


class SimulacaoPortabilidadeSerializer(serializers.Serializer):
    taxa_de_juros_mensal = serializers.FloatField()
    numero_de_parcelas = serializers.IntegerField()
    ultimo_devido_saldo = serializers.FloatField()


class CriarContratoCCBPortabilidadeSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)


class CriarContratoPortabilidadeSerializer(serializers.Serializer):
    id_cliente = serializers.IntegerField()
    tipo_produto = serializers.IntegerField()
    banco = serializers.CharField(max_length=100)
    numero_contrato = serializers.CharField(max_length=100)
    saldo_devedor = serializers.FloatField()
    prazo = serializers.IntegerField()
    taxa = serializers.CharField(max_length=100)
    nova_parcela = serializers.FloatField()
    token_envelope = serializers.CharField(max_length=100)


class StatusContratoPortabilidadeSerializer(serializers.Serializer):
    token_contrato = serializers.CharField(required=True)
    status = serializers.IntegerField(required=True)


class DadosIN100Serializer(serializers.ModelSerializer):
    class Meta:
        model = DadosIn100
        fields = (
            'cliente_id',
            'sucesso_envio_termo_in100',
            'sucesso_chamada_in100',
            'balance_request_key',
        )
