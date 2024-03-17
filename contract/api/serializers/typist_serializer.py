from rest_framework import serializers

from custom_auth.models import UserProfile


class TypistSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='name')
    user_id = serializers.IntegerField(source='id')

    class Meta:
        model = UserProfile
        fields = ['user_name', 'user_id']
