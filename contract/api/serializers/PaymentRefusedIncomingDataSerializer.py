# third party imports
from rest_framework import serializers

# local imports
from contract.models.PaymentRefusedIncomingData import PaymentRefusedIncomingData


class PaymentRefusedIncomingDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentRefusedIncomingData
        fields = '__all__'
