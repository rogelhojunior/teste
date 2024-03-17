from django.contrib.auth.models import Group
from rest_framework import serializers

from custom_auth.models import Produtos, UserProfile


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']


class ProductsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produtos
        fields = ['id', 'nome']


class ListSupervisorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('unique_id', 'name')


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = (
            'name',
            'corban',
            'produtos',
            'email',
            'birth_date',
            'phone',
            'cpf',
            'supervisor',
            'nivel_hierarquia',
            'identifier',
            'numero_febraban',
            'dt_emissao_certificado',
            'dt_validade_certificado',
            'uf_atuacao',
            'municipio',
            'created_by',
            'endereco',
            'cep_endereco',
            'numero_endereco',
            'bairro_endereco',
            'cidade_endereco',
            'uf_estado_endereco',
            'complemento_endereco',
            'is_active',
            'groups',
        )


class ListUserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'unique_id',
            'name',
            'identifier',
            'email',
            'nivel_hierarquia',
            'is_active',
        ]


class UserProfileDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = (
            'name',
            'corban',
            'produtos',
            'email',
            'birth_date',
            'phone',
            'cpf',
            'supervisor',
            'nivel_hierarquia',
            'identifier',
            'numero_febraban',
            'dt_emissao_certificado',
            'dt_validade_certificado',
            'uf_atuacao',
            'municipio',
            'created_by',
            'endereco',
            'cep_endereco',
            'numero_endereco',
            'bairro_endereco',
            'cidade_endereco',
            'uf_estado_endereco',
            'complemento_endereco',
        )
