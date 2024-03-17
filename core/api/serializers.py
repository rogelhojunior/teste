from rest_framework import serializers
from rest_framework.parsers import MultiPartParser

from auditoria.models import LogAlteracaoCadastral, LogAlteracaoCadastralDock
from contract.constants import ProductTypeEnum
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Contrato, RetornoSaque
from contract.models.envelope_contratos import EnvelopeContratos
from contract.products.portabilidade.models.taxa import Taxa
from core.models import BancosBrasileiros, ParametrosBackoffice, Rogado, Testemunha
from core.models.cliente import Cliente
from core.models.parametro_produto import ParametrosProduto
from core.models.termos_de_uso import TermosDeUso


class BancosBrasileirosSerializer(serializers.ModelSerializer):
    class Meta:
        model = BancosBrasileiros
        fields = ('nome_', 'codigo', 'id')


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


class EnvioLinkFormalizacaoFormalizacaoSerializer(serializers.Serializer):
    token_envelope = serializers.CharField()


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


class ClienteConsultaSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.CharField()

    class Meta:
        model = Cliente
        fields = '__all__'


class ContratoFormalizacaoSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    url_frame = serializers.URLField()

    class Meta:
        model = Contrato
        fields = '__all__'


class ContratoFormalizacaoSerializerPendente(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)

    class Meta:
        model = Contrato
        fields = '__all__'


class RogadoSerializer(serializers.ModelSerializer):
    cliente_id = serializers.CharField(
        write_only=True,
    )
    data_nascimento = serializers.DateField(
        input_formats=[
            '%d/%m/%Y',
            '%Y-%m-%d',
        ]
    )

    class Meta:
        model = Rogado
        fields = (
            'id',
            'cliente_id',
            'nome',
            'telefone',
            'cpf',
            'grau_parentesco',
            'data_nascimento',
        )


class TestemunhaSerializer(serializers.ModelSerializer):
    cliente_id = serializers.CharField(
        write_only=True,
    )
    data_nascimento = serializers.DateField(
        input_formats=[
            '%d/%m/%Y',
            '%Y-%m-%d',
        ]
    )

    class Meta:
        model = Testemunha
        fields = (
            'id',
            'cliente_id',
            'contratos',
            'nome',
            'telefone',
            'cpf',
            'data_nascimento',
        )


class ClienteSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )

    class Meta:
        model = Cliente
        fields = ('id', 'nu_cpf', 'dt_nascimento')


class ClienteSerializerCartao(serializers.ModelSerializer):
    dt_nascimento = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )
    cliente_cartao_beneficio_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cliente
        fields = ('id', 'nu_cpf', 'dt_nascimento', 'cliente_cartao_beneficio_id')


class AtualizarClienteIN100Serializer(serializers.ModelSerializer):
    documento_data_emissao = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )

    class Meta:
        model = Cliente
        fields = (
            'tipo_cliente',
            'id_unico',
            'nu_cpf',
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
            'endereco_cep',
            'tempo_residencia',
            'email',
            'telefone_celular',
            'telefone_residencial',
            'conjuge_nome',
            'conjuge_cpf',
            'conjuge_data_nascimento',
            'cd_familiar_unico',
            'form_ed_financeira',
            'IP_Cliente',
        )


class AtualizarClienteOriginacaoSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )
    documento_data_emissao = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )

    class Meta:
        model = Cliente
        fields = '__all__'


class AtualizarClienteSerializer(serializers.ModelSerializer):
    dt_nascimento = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )
    documento_data_emissao = serializers.DateField(
        format='%d/%m/%Y', input_formats=['%d/%m/%Y'], required=False
    )

    class Meta:
        model = Cliente
        fields = '__all__'

    def validate(self, data):
        endereco_fields = [
            'endereco_cep',
            'endereco_logradouro',
            'endereco_numero',
            'endereco_bairro',
            'endereco_uf',
            'endereco_cidade',
        ]
        if any(field in data for field in endereco_fields):
            if missing_fields := [
                field for field in endereco_fields if field not in data
            ]:
                raise serializers.ValidationError(
                    f'Os seguintes campos de endereço são obrigatórios: {", ".join(missing_fields)}'
                )
        return data

    def update(self, instance, validated_data):
        user = self.context['request'].user
        for field_name, new_value in validated_data.items():
            old_value = getattr(instance, field_name)
            if old_value != new_value:
                log_cadastral, _ = LogAlteracaoCadastral.objects.get_or_create(
                    cliente=instance
                )
                LogAlteracaoCadastralDock.objects.create(
                    log_cadastral=log_cadastral,
                    tipo_registro=field_name,
                    registro_anterior=str(old_value),
                    novo_registro=str(new_value),
                    usuario=user,
                    canal='API',
                )
        return super().update(instance, validated_data)


class CriarContratoSerializer(serializers.ModelSerializer):
    cliente = DetalheClienteSerializer(many=False, read_only=True)

    class Meta:
        model = Contrato
        fields = ('cliente', 'token_contrato')


class ParametrosSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametrosBackoffice
        fields = '__all__'


class ParametrosProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametrosProduto
        fields = '__all__'


class TaxaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Taxa
        fields = '__all__'


class UnicoJWTSerializer(serializers.Serializer):
    access_token = serializers.CharField(max_length=500)


class FacetecBlobResultSerializer(serializers.Serializer):
    auditTrailImage = serializers.CharField(required=False)
    faceScan = serializers.CharField(required=True)
    lowQualityAuditTrailImage = serializers.CharField(required=False)
    sessionId = serializers.CharField(required=True)
    transactionId = serializers.CharField(required=True)


class UnicoProcessesRequestDataSerializer(serializers.Serializer):
    nu_cpf = serializers.CharField(max_length=11)
    nome_cliente = serializers.CharField(max_length=150)
    sexo = serializers.CharField(required=False)
    dt_nascimento = serializers.CharField(max_length=10, required=False)
    email = serializers.CharField(max_length=50, required=False)
    telefone_celular = serializers.CharField(max_length=13, required=False)
    selfie_encrypted = serializers.CharField()


class CriarEnvelopeContratosSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvelopeContratos
        fields = ('token_envelope',)


class CriarClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = (
            'id',
            'nu_cpf',
        )


class RetornoSaqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetornoSaque
        exclude = ('contrato',)


class TermosDeUsoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermosDeUso
        fields = ['termos_de_uso', 'politica_privacidade']


class AvailableOffersRequestGetSerializer(serializers.Serializer):
    tipo_produto = serializers.ChoiceField(
        choices=[str(e.value) for e in ProductTypeEnum]
    )
    id_cliente = serializers.IntegerField()
