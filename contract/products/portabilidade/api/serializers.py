from rest_framework import serializers

from core.models.parametro_produto import ParametrosProduto


class DetalheParametrosProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametrosProduto
        fields = (
            'taxa_minima',
            'taxa_maxima',
            'valor_minimo_parcela',
            'valor_maximo_parcela',
            'valor_minimo_emprestimo',
            'valor_maximo_emprestimo',
            'valor_minimo_margem',
            'quantidade_minima_parcelas',
            'quantidade_maxima_parcelas',
            'idade_minima',
            'idade_maxima',
            'prazo_maximo',
            'prazo_minimo',
        )
