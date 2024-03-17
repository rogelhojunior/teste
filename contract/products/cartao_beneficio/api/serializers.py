from rest_framework import serializers

from contract.api.serializers import DetalheClienteSerializer
from contract.models.contratos import CartaoBeneficio, Contrato
from core.models import Cliente
from core.models.aceite_in100 import AceiteIN100
from core.validators import checar_cep


class AtualizarClienteSerializer(serializers.ModelSerializer):
    endereco_cep = serializers.CharField(validators=[checar_cep], required=False)

    data_nascimento = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )
    documento_data_emissao = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )

    class Meta:
        model = Cliente
        fields = '__all__'


class ContratoSaqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrato
        fields = [
            'token_contrato',
            'limite_pre_aprovado',
            'vr_iof_total',
            'taxa',
            'taxa_efetiva_ano',
            'cet_mes',
            'cet_ano',
            'vr_iof_adicional',
            'vr_iof',
            'vencimento_fatura',
        ]


class CartaoBeneficioSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartaoBeneficio
        fields = [
            'possui_saque',
            'valor_saque',
            'valor_disponivel_saque',
            'valor_financiado',
            'folha',
            'verba',
            'convenio',
            'saque_parcelado',
            'valor_parcela',
            'qtd_parcela_saque_parcelado',
            'valor_total_a_pagar',
        ]


class RetornaCartaoExistente(serializers.Serializer):
    cartao_criado = serializers.BooleanField()
    id_registro_dock = serializers.CharField()
    id_conta_dock = serializers.CharField()
    id_cartao_dock = serializers.CharField()
    id_endereco_dock = serializers.CharField()
    id_telefone_dock = serializers.CharField()
    id_processo_unico = serializers.CharField()
    token_envelope = serializers.CharField()
    codigo_convenio = serializers.CharField()
    nome_convenio = serializers.CharField()
    bandeira_cartao = serializers.CharField()
    numero_cartao = serializers.CharField()
    produto_codigo = serializers.IntegerField()
    tipo_margem = serializers.IntegerField()
    tipo_cartao = serializers.CharField()
    id_cliente_cartao = serializers.IntegerField()
    possui_seguro_prata = serializers.BooleanField()
    possui_seguro_ouro = serializers.BooleanField()
    possui_seguro_diamante = serializers.BooleanField()


class ClienteCartoesSerializer(serializers.Serializer):
    cartoes = RetornaCartaoExistente(many=True)
    apto_saque = serializers.BooleanField()

    def __init__(self, *args, **kwargs):
        apto_saque = kwargs.pop('apto_saque', None)
        super(ClienteCartoesSerializer, self).__init__(*args, **kwargs)
        if apto_saque is not None:
            self.fields['apto_saque'].default = apto_saque


class ConsultaAceiteIN100Cartao(serializers.ModelSerializer):
    in100_aceita = serializers.SerializerMethodField()
    url_formalizacao_curta = serializers.SerializerMethodField()
    id_cliente = serializers.SerializerMethodField()

    class Meta:
        model = AceiteIN100
        fields = '__all__'  # Add your field name here

    def get_in100_aceita(self, obj):
        return self.context.get('in100_aceita')

    def get_url_formalizacao_curta(self, obj):
        return self.context.get('url_formalizacao_curta')

    def get_id_cliente(self, obj):
        return self.context.get('id_cliente')


class CriarContratoSaqueComplementarSerializer(serializers.ModelSerializer):
    cliente = DetalheClienteSerializer(many=False, read_only=True)
    saque_complementar = serializers.SerializerMethodField()

    class Meta:
        model = Contrato
        fields = (
            'id',
            'cliente',
            'token_contrato',
            'token_envelope',
            'saque_complementar',
        )

    def get_saque_complementar(self, obj):
        try:
            if saque_complementar := obj.contrato_saque_complementar.first():
                return {
                    'id': saque_complementar.pk or '',
                    'status': saque_complementar.status or '',
                    'valor_disponivel_saque': saque_complementar.valor_disponivel_saque
                    or '',
                    'valor_lancado_fatura': saque_complementar.valor_lancado_fatura
                    or '',
                }
            return {}
        except Exception as e:
            print(f'Erro ao buscar Saque Complementar: {e}')  # Adicione esta linha
            return {}
