from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser

from core.constants import EnumNivelHierarquia
from .anexo_usuario import AnexoUsuario
from .models import Corban, Produtos, UserAddress, UserProfile


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = (
            'user',
            'name',
            'postal_code',
            'address',
            'address_neighborhood',
            'address_number',
            'address_complement',
            'city',
            'state',
            'is_principal',
            'id',
        )


class DocumentosUsuarioSerializer(serializers.ModelSerializer):
    parser_classes = [MultiPartParser]

    class Meta:
        model = AnexoUsuario
        fields = (
            'usuario',
            'arquivo',
            'tipo_anexo',
            'anexo_url',
            'selfie_url',
            'anexado_em',
        )


class ProdutosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produtos
        fields = ('nome', 'cd_produto', 'ativo')


class CorbanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Corban
        fields = ('corban_name', 'is_active')


class UserProfileSerializer(serializers.ModelSerializer):
    produtos = ProdutosSerializer(many=True, read_only=True)
    corban = CorbanSerializer(many=False, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            'unique_id',
            'name',
            'identifier',
            'groups',
            'produtos',
            'corban',
            'is_superuser',
            'is_staff',
            'is_active',
            'is_checked',
            'last_login',
            'date_joined',
            'device_id',
            'permissions',
            'possui_chat_suporte',
        )

    def manage_user_permission(self, obj):
        # Obtém a permissão 'add_contrato'
        add_contrato_permission = Permission.objects.get(codename='add_contrato')
        happy_generate_permission = Permission.objects.get(
            codename='happy_generate_contracts_report'
        )

        if obj.nivel_hierarquia in (
            EnumNivelHierarquia.DONO_LOJA,
            EnumNivelHierarquia.SUPERVISOR,
        ):
            obj.user_permissions.add(happy_generate_permission)

        # Verifica se o usuário está nos grupos 'Corban Master' ou 'Mesa Corban'
        is_in_special_group = obj.groups.filter(
            name__in=['Corban Master', 'Mesa Corban']
        ).exists()

        # Se o usuário estiver em um dos grupos especiais
        if is_in_special_group:
            # Remove a permissão do usuário
            obj.user_permissions.remove(add_contrato_permission)
            # Remove a permissão de cada grupo ao qual o usuário pertence
            for group in obj.groups.all():
                group.permissions.remove(add_contrato_permission)

        # Se o usuário não estiver em nenhum grupo, adiciona a permissão diretamente a ele
        elif not obj.groups.exists() or not is_in_special_group:
            obj.user_permissions.add(add_contrato_permission)

        # Salva as alterações no usuário
        obj.save()

    def get_permissions(self, obj):
        try:
            all_permissions = obj.user_permissions.all() | Permission.objects.filter(
                group__user=obj
            )
            self.manage_user_permission(obj)
            happy_permissions = all_permissions.filter(
                Q(codename__startswith='happy_') | Q(codename='add_contrato')
            ).distinct()
            return happy_permissions.values_list('codename', flat=True)
        except Exception:
            return {}


class RegistrationSerializer(serializers.ModelSerializer):
    birth_date = serializers.DateField(format='%d/%m/%Y', input_formats=['%d/%m/%Y'])

    class Meta:
        model = UserProfile
        fields = [
            'name',
            'cpf',
            'email',
            'phone',
            'birth_date',
            'password',
            'device_id',
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def save(self):
        user = UserProfile(
            name=self.validated_data['name'],
            cpf=self.validated_data['cpf'],
            email=self.validated_data['email'],
            identifier=self.validated_data['email'],
            phone=self.validated_data['phone'],
            birth_date=self.validated_data['birth_date'],
        )
        with transaction.atomic():
            password = self.validated_data['password']
            user.set_password(password)
            user.save()
            print(user)

        return user
