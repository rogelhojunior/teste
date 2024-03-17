from datetime import date

from rest_framework import serializers

from api_log.models import (
    CancelaReserva,
    ConsultaConsignacoes,
    ConsultaMargem,
    ConsultaMatricula,
    RealizaReserva,
)
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.api.serializers import RogadoSerializer
from core.models import Cliente
from core.models.aceite_in100 import AceiteIN100
from core.models.cliente import DadosBancarios


class ClienteConsultaSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.CharField()

    class Meta:
        model = Cliente
        fields = (
            'id',
            'nome_cliente',
            'dt_nascimento',
        )


class DetalheIN100Serializer(serializers.ModelSerializer):
    in100_autorizada = serializers.SerializerMethodField()
    rogado = serializers.SerializerMethodField()

    def get_rogado(self, instance):
        rogado = instance.rogados.order_by('id').last()
        if rogado:
            return RogadoSerializer(rogado).data
        return None

    def get_in100_autorizada(self, obj):
        aceite_in100 = None
        try:
            aceite_in100 = AceiteIN100.objects.get(cpf_cliente=obj.nu_cpf)
        except AceiteIN100.DoesNotExist:
            return False

        if aceite_in100:
            data_hoje = date.today()
            return data_hoje <= aceite_in100.data_vencimento_aceite
        try:
            if in100_autorizada := obj.cliente_in100.first():
                return in100_autorizada.in100_data_autorizacao_
            return False
        except Exception as e:
            print(f'Erro ao buscar IN100: {e}')
            return {}

    class Meta:
        model = Cliente
        fields = (
            'id',
            'nu_cpf',
            'nome_cliente',
            'escolaridade',
            'rogado',
            'in100_autorizada',
        )


class AutorizacaoDadosBancariosSerializer(serializers.ModelSerializer):
    class Meta:
        model = DadosBancarios
        fields = [
            'conta_tipo',
            'conta_banco',
            'conta_agencia',
            'conta_numero',
            'conta_digito',
        ]


class IN100Serializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    in100_autorizada = serializers.SerializerMethodField()
    dados_bancarios = AutorizacaoDadosBancariosSerializer(
        source='cliente__dados_bancarios', read_only=True
    )

    def get_in100_autorizada(self, obj):
        try:
            return obj.in100_data_autorizacao_ if obj.in100_data_autorizacao_ else False
        except Exception as e:
            print(f'Erro ao buscar IN100: {e}')
            return {}

    class Meta:
        model = DadosIn100
        fields = '__all__'


class ConsultaMatriculaSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    margem_atual = serializers.DecimalField(10, 2)

    class Meta:
        model = ConsultaMatricula
        fields = (
            'cliente',
            'matricula',
            'folha',
            'verba',
            'tipo_margem',
            'margem_atual',
            'estavel',
            'criado_em',
        )


class ConsultaMatriculaFacilSerializer(serializers.Serializer):
    idProduto = serializers.CharField()
    tipoProduto = serializers.CharField()
    tipoMargem = serializers.IntegerField()
    numeroMatricula = serializers.CharField()
    folha = serializers.CharField()
    verba = serializers.CharField()
    nome = serializers.CharField()
    margem_atual = serializers.DecimalField(10, 2)
    cargo = serializers.CharField()
    estavel_bool = serializers.BooleanField()
    nascimento = serializers.DateField(input_formats=['%d/%m/%Y'])


class ClienteQuantumConsultaSerializer(serializers.ModelSerializer):
    dt_nascimento = ''

    class Meta:
        model = Cliente
        fields = ('id',)


class ConsultaMatriculaQuantumSerializer(serializers.ModelSerializer):
    cliente = ClienteQuantumConsultaSerializer(many=False, read_only=True)
    margem_atual = serializers.DecimalField(10, 2)

    class Meta:
        model = ConsultaMatricula
        fields = (
            'cliente',
            'matricula',
            'folha',
            'verba',
            'tipo_margem',
            'margem_atual',
            'estavel',
            'criado_em',
        )


class ConsultaConsignacaoSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    valor = serializers.DecimalField(10, 2)
    valor_liberado = serializers.DecimalField(10, 2)

    class Meta:
        model = ConsultaConsignacoes
        fields = (
            'cliente',
            'codigo_operacao',
            'prazo',
            'valor',
            'valor_liberado',
            'codigo_operacao_instituicao',
            'verba',
            'prazo_restante',
            'criado_em',
            'codigo_retorno',
            'descricao',
        )


class ConsultaMargemQuantumSerializer(serializers.ModelSerializer):
    cliente = ClienteQuantumConsultaSerializer(many=False, read_only=True)
    margem_atual = serializers.DecimalField(10, 2)

    class Meta:
        model = ConsultaMargem
        fields = (
            'cliente',
            'matricula',
            'folha',
            'margem_atual',
            'estavel',
            'codigo_retorno',
            'descricao',
            'criado_em',
        )


class ConsultaMargemSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    margem_atual = serializers.DecimalField(10, 2)
    numeroMatricula = serializers.CharField(source='matricula')

    class Meta:
        model = ConsultaMargem
        fields = (
            'cliente',
            'numeroMatricula',
            'folha',
            'margem_atual',
            'estavel',
            'codigo_retorno',
            'descricao',
            'criado_em',
        )


class ConsultaMargemSerproSerializer(serializers.Serializer):
    margem_atual = serializers.DecimalField(10, 2)
    numeroMatricula = serializers.CharField(source='matricula')
    folha = serializers.CharField()
    verba = serializers.CharField()
    convenio_SIAPE = serializers.CharField()
    tipoVinc_SIAPE = serializers.CharField()
    classifica_SIAPE = serializers.CharField()
    cargo = serializers.CharField()
    estavel_bool = serializers.CharField()
    nascimento = serializers.CharField()

    idProduto = serializers.CharField()
    tipoProduto = serializers.CharField()
    tipoMargem = serializers.IntegerField()
    nome_cliente = serializers.CharField()
    instituidor = serializers.CharField()


class ConsultaMargemZetraSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    margem_atual = serializers.DecimalField(10, 2)
    numeroMatricula = serializers.CharField(source='matricula')
    idProduto = serializers.CharField()
    tipoProduto = serializers.CharField()
    tipoMargem = serializers.IntegerField()
    verba = serializers.CharField()
    orgao = serializers.CharField()

    class Meta:
        model = ConsultaMargem
        fields = (
            'cliente',
            'numeroMatricula',
            'folha',
            'orgao',
            'margem_atual',
            'estavel',
            'codigo_retorno',
            'descricao',
            'criado_em',
            'idProduto',
            'tipoProduto',
            'tipoMargem',
            'verba',
        )


class RealizaReservaQuantumSerializer(serializers.ModelSerializer):
    cliente = ClienteQuantumConsultaSerializer(many=False, read_only=True)
    valor = serializers.DecimalField(10, 2)

    class Meta:
        model = RealizaReserva
        fields = (
            'cliente',
            'matricula',
            'folha',
            'verba',
            'valor',
            'reserva',
            'codigo_retorno',
            'descricao',
            'criado_em',
        )


class RealizaReservaDataprevSerializer(serializers.ModelSerializer):
    cliente = ClienteQuantumConsultaSerializer(many=False, read_only=True)
    valor = serializers.DecimalField(10, 2)

    class Meta:
        model = RealizaReserva
        fields = (
            'cliente',
            'valor',
            'reserva',
            'codigo_retorno',
            'descricao',
            'criado_em',
        )


class RealizaReservaSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    valor = serializers.DecimalField(10, 2)

    class Meta:
        model = RealizaReserva
        fields = (
            'cliente',
            'matricula',
            'folha',
            'verba',
            'valor',
            'reserva',
            'codigo_retorno',
            'descricao',
            'criado_em',
        )


class CancelaReservaQuantumSerializer(serializers.ModelSerializer):
    cliente = ClienteQuantumConsultaSerializer(many=False, read_only=True)

    class Meta:
        model = CancelaReserva
        fields = (
            'cliente',
            'matricula',
            'reserva',
            'cancelada',
            'codigo_retorno',
            'descricao',
            'criado_em',
        )


class CancelaReservaSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)

    class Meta:
        model = CancelaReserva
        fields = (
            'cliente',
            'matricula',
            'reserva',
            'cancelada',
            'codigo_retorno',
            'descricao',
            'criado_em',
        )
