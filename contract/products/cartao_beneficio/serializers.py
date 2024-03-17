from rest_framework import serializers

from api_log.models import RealizaSimulacao
from contract.models.contratos import Contrato
from contract.products.cartao_beneficio.models.convenio import Convenios
from contract.products.cartao_beneficio.models.planos import Planos
from core.serializers import ClienteConsultaSerializer


class ConsultaConveniosSerializer(serializers.ModelSerializer):
    especie_in100 = serializers.SerializerMethodField()
    produtos = serializers.SerializerMethodField()
    sub_orgao = serializers.SerializerMethodField()
    convenio_siape = serializers.SerializerMethodField()
    classificacao_siape = serializers.SerializerMethodField()

    class Meta:
        model = Convenios
        fields = (
            'id',
            'nome',
            'averbadora',
            'digitacao_manual',
            'senha_servidor',
            'necessita_assinatura_fisica',
            'idade_minima_assinatura',
            'convenio_inss',
            'especie_in100',
            'produtos',
            'sub_orgao',
            'convenio_siape',
            'classificacao_siape',
            'permite_unificar_margem',
            'fixar_valor_maximo',
        )

    def get_especie_in100(self, obj):
        try:
            especies_in100 = obj.convenio_especie.all()
            return [
                {
                    'codigo': especie_in100.codigo or '',
                    'descricao': especie_in100.descricao or '',
                    'permite_contratacao': especie_in100.permite_contratacao,
                }
                for especie_in100 in especies_in100
            ]
        except Exception as e:
            print(f'Erro ao buscar especie in100: {e}')
            return {}

    def get_sub_orgao(self, obj):
        try:
            sub_orgaos = obj.suborgao_convenio.filter(ativo=True)

            return [
                {
                    'nome_orgao': sub_orgao.nome_orgao or '',
                    'codigo_folha': sub_orgao.codigo_folha or '',
                }
                for sub_orgao in sub_orgaos
            ]
        except Exception as e:
            print(f'Erro ao buscar sub orgãos: {e}')
            return {}

    def get_convenio_siape(self, obj):
        try:
            convenios_siape = obj.convenio_convenio_siape.filter(
                permite_contratacao=True
            )

            return [
                {
                    'codigo': convenio_siape.codigo or '',
                    'descricao': convenio_siape.descricao or '',
                }
                for convenio_siape in convenios_siape
            ]
        except Exception as e:
            print(f'Erro ao buscar dados do convenio - siape: {e}')
            return {}

    def get_classificacao_siape(self, obj):
        try:
            classificacoes_siape = obj.convenio_classificacao_siape.filter(
                permite_contratacao=True
            )

            return [
                {
                    'codigo': classificacoe_siape.codigo or '',
                    'descricao': classificacoe_siape.descricao or '',
                }
                for classificacoe_siape in classificacoes_siape
            ]
        except Exception as e:
            print(f'Erro ao buscar classificação siape: {e}')
            return {}

    def get_produtos(self, obj):
        try:
            produtos = obj.produto_convenio.all()
            return [
                {
                    'codigo_produto': produto.produto or '',
                    'produto': produto.get_tipo_produto_display() or '',
                    'tipo_margem': produto.tipo_margem,
                }
                for produto in produtos
            ]
        except Exception as e:
            print(f'Erro ao buscar produtos: {e}')
            return {}


class SimulacaoSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    limite_pre_aprovado = serializers.DecimalField(10, 2)

    class Meta:
        model = RealizaSimulacao
        fields = (
            'cliente',
            'matricula',
            'limite_pre_aprovado',
            'convenio',
            'valor_saque',
        )


class SimulacaoSaqueSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    limite_pre_aprovado = serializers.DecimalField(10, 2)

    class Meta:
        model = RealizaSimulacao
        fields = (
            'cliente',
            'matricula',
            'valor_saque',
            'limite_pre_aprovado',
            'cet_aa',
            'cet_am',
            'valor_iof',
        )


class EnvioLinkFormalizacaoSerializer(serializers.ModelSerializer):
    cliente = ClienteConsultaSerializer(many=False, read_only=True)
    url_formalizacao_curta = serializers.URLField()

    class Meta:
        model = Contrato
        fields = (
            'id',
            'cliente',
            'token_contrato',
            'url_formalizacao_curta',
            'criado_em',
        )


class PlanosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Planos
        fields = ('nome', 'valor_plano', 'descricao_plano', 'valor_plano_brl', 'ativo')


class PlanosSerializerSeguradora(serializers.ModelSerializer):
    nome_seguradora = serializers.CharField(source='seguradora.nome')
    valor_plano = serializers.FloatField()
    premio = serializers.CharField(source='valor_segurado')
    validade = serializers.IntegerField(source='quantidade_parcelas')
    obrigatorio = serializers.BooleanField(source='get_obrigatorio')
    renovacao_automatica = serializers.BooleanField(source='get_renovacao_automatica')

    class Meta:
        model = Planos
        fields = [
            'id',
            'nome',
            'nome_seguradora',
            'tipo_plano',
            'obrigatorio',
            'valor_plano',
            'premio',
            'validade',
            'renovacao_automatica',
            'carencia',
            'descricao_plano',
        ]
