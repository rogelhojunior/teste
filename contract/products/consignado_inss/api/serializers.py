from rest_framework import serializers

from contract.models.contratos import Contrato, MargemLivre
from core.models.parametros_backoffice import ParametrosBackoffice


class RetornaBeneficiosSerializer(serializers.Serializer):
    numero_beneficio = serializers.IntegerField()
    valor_receita = serializers.FloatField()
    numero_tipo_beneficio = serializers.IntegerField()
    nome_beneficio = serializers.CharField()


class ParametrosSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametrosBackoffice
        fields = '__all__'


class AtualizarMargemLivreSerializer(serializers.ModelSerializer):
    class Meta:
        model = MargemLivre
        fields = '__all__'


class AtualizarContratoMargemLivreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrato
        fields = '__all__'
