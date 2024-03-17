import datetime
import uuid

from botocore.exceptions import ValidationError
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError as ValidationUserError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from contract.choices import TIPOS_PRODUTO
from contract.constants import EnumContratoStatus, EnumTipoProduto
from core.choices import (
    GRAU_CORBAN,
    NIVEIS_HIERARQUIA,
    TIPOS_CADASTRO,
    TIPOS_ESTABELECIMENTO,
    TIPOS_RELACIONAMENTO,
    TIPOS_VENDA,
    UFS,
)
from core.constants import EnumGrauCorban, EnumNivelHierarquia


class UserProfileManager(BaseUserManager):
    """Helps Django work with our custom user model."""

    def create_user(self, identifier, name, password=None):
        """Creates a new user profile."""

        if not identifier:
            raise ValueError('Usuários precisam de um identificador')

        # email = self.normalize_email(email)
        user = self.model(
            identifier=identifier,
            name=name,
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, identifier, name, password):
        """Creates and saves a new superuser with given details."""

        user = self.create_user(identifier, name, password)

        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)

        return user


class Produtos(models.Model):
    nome = models.CharField(
        max_length=200,
        verbose_name='Nome do produto',
        null=True,
        blank=True,
    )
    cd_produto = models.CharField(
        max_length=50,
        verbose_name='Código do produto',
        null=True,
        blank=True,
    )
    tipo_produto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO,
        default=EnumTipoProduto.FGTS,
    )  # tipo de produto
    documento_pessoal = models.BooleanField(
        default=True,
        verbose_name='Envio documento pessoal?',
        help_text='É necessário enviar esse documento para esse produto?',
    )
    comprovante_residencia = models.BooleanField(
        default=True,
        verbose_name='Envio comprovante residência?',
        help_text='É necessário enviar esse documento para esse produto?',
    )
    contracheque = models.BooleanField(
        default=False,
        verbose_name='Envio contracheque?',
        help_text='É necessário enviar esse documento para esse produto?',
    )
    ativo = models.BooleanField(verbose_name='Ativo?', default=True)
    confia = models.BooleanField(verbose_name='Confia?', default=False)

    def __str__(self):
        return self.nome or ''

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = '2. Produtos'


class Corban(models.Model):
    corban_name = models.CharField(
        max_length=250, verbose_name='Nome', null=True, blank=False
    )
    corban_CNPJ = models.CharField(
        max_length=250,
        verbose_name='Número de CPF/CNPJ',
        unique=True,
        null=True,
        blank=False,
    )
    corban_endereco = models.CharField(
        max_length=250, verbose_name='Endereço Completo', null=True, blank=False
    )
    corban_email = models.CharField(
        max_length=250, verbose_name='E-mail Coorporativo', null=True, blank=False
    )
    mesa_corban = models.BooleanField(
        verbose_name='Mesa Corban', default=False, null=True, blank=True
    )
    is_active = models.BooleanField(
        verbose_name='Ativo?', default=False, null=True, blank=True
    )
    telefone_validator = RegexValidator(
        regex=r'^\d{11}$',
        message='Número de telefone inválido. O formato deve ser: 00123456789',
    )
    telefone = models.CharField(
        max_length=11,
        verbose_name='Telefone da Loja',
        null=True,
        blank=True,
        validators=[telefone_validator],
    )
    banco = models.CharField(
        verbose_name='Número do banco', null=True, blank=True, max_length=255
    )
    agencia = models.CharField(
        verbose_name='Número da agência', null=True, blank=True, max_length=255
    )
    conta = models.CharField(
        verbose_name='Número da conta', null=True, blank=True, max_length=255
    )
    tipo_estabelecimento = models.SmallIntegerField(
        verbose_name='Tipo de Estabelecimento',
        choices=TIPOS_ESTABELECIMENTO,
        null=True,
        blank=True,
    )
    tipo_venda = models.SmallIntegerField(
        verbose_name='Tipo de Venda', choices=TIPOS_VENDA, null=True, blank=True
    )
    tipo_cadastro = models.SmallIntegerField(
        verbose_name='Tipo de Cadastro', choices=TIPOS_CADASTRO, null=True, blank=True
    )
    representante_comercial = models.ForeignKey(
        'gestao_comercial.RepresentanteComercial',
        verbose_name='Representante Comercial',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tipo_relacionamento = models.SmallIntegerField(
        verbose_name='Tipo de Relacionamento',
        choices=TIPOS_RELACIONAMENTO,
        null=True,
        blank=True,
    )
    loja_matriz = models.CharField(
        verbose_name='Número da Loja Matriz', null=True, blank=True, max_length=255
    )
    nome_representante = models.CharField(
        verbose_name='Nome Completo', max_length=200, null=True, blank=False
    )
    nu_cpf_cnpj_representante = models.CharField(
        verbose_name='Número de CPF/CNPJ',
        max_length=14,
        unique=True,
        null=True,
        blank=False,
    )
    telefone_representante = models.CharField(
        max_length=11,
        verbose_name='Telefone de Contato',
        validators=[telefone_validator],
        null=True,
        blank=False,
    )
    produtos = models.ManyToManyField(
        Produtos,
        verbose_name='Produtos',
    )
    # Novo campo para estabelecer a relação hierárquica
    parent_corban = models.ForeignKey(
        'self',  # Referência para o próprio modelo Corban
        verbose_name='Corban Superior',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sub_corbans',  # Nome para a relação reversa
    )

    corban_type = models.SmallIntegerField(
        verbose_name='Grau do Corban',
        choices=GRAU_CORBAN,
        null=True,
        blank=True,
    )

    # Método para recuperar a hierarquia
    def get_hierarchy(self):
        hierarchy = []
        current_corban = self
        while current_corban:
            hierarchy.append(current_corban)
            current_corban = current_corban.parent_corban
        return hierarchy

    def get_subordinate_hierarchy(self):
        # Função recursiva para buscar todos os subordinados
        def get_subordinates(corban):
            # Verifica se o corban é o mesmo que o parent_corban para evitar auto-referência
            if corban.id == corban.parent_corban_id:
                return []

            subordinates = [corban]
            for sub_corban in Corban.objects.filter(parent_corban=corban):
                subordinates.extend(get_subordinates(sub_corban))
            return subordinates

        return get_subordinates(self)

    def get_corban_type_display(self):
        return dict(GRAU_CORBAN).get(self.corban_type)

    def clean(self):
        if self.corban_CNPJ:
            if (
                Corban.objects.filter(corban_CNPJ=self.corban_CNPJ)
                .exclude(pk=self.pk)
                .first()
            ):
                raise ValidationError('Já existe um corban com esse CPF.')

                # Verifica se o parent_corban é o mesmo que o corban atual
        if self.parent_corban_id and self.id == self.parent_corban_id:
            raise ValidationUserError({
                'parent_corban': 'Um Corban não pode ser um Corban superior de si mesmo.'
            })

        if (
            self.corban_type
            and self.corban_type > EnumGrauCorban.CORBAN_MASTER
            and not self.parent_corban
        ):
            raise ValidationUserError({
                'corban_type': 'Para o grau de Corban selecionado, é '
                'necessário selecionar um Corban Superior.'
            })

    def before_import_row(self, row, **kwargs):
        """
        Este método é chamado antes de cada linha ser importada.
        Se um Corban for especificado, associaremos todos os seus produtos ao usuário.
        """
        # Verifica se o Corban está presente na linha
        if 'Corban' in row:
            try:
                # Busca o Corban pela sua identificação única (presumivelmente 'corban_name')
                corban = Corban.objects.get(corban_name=row['Corban'])

                # Cria uma lista dos nomes dos produtos associados a este Corban
                produtos_corban = [produto.nome for produto in corban.produtos.all()]

                # Atualiza a linha com os nomes dos produtos
                row['Produtos'] = ','.join(produtos_corban)
            except Corban.DoesNotExist:
                # Caso o Corban especificado não exista, você pode decidir como lidar
                # Por exemplo, registrar um erro ou simplesmente ignorar
                pass

    def __str__(self):
        return f'{self.pk} - {self.corban_name.upper()}' or ''

    class Meta:
        verbose_name = 'Corban'
        verbose_name_plural = '3. Corbans'
        ordering = ('corban_name',)


@receiver(post_save, sender=Corban)
def update_user_profile_on_corban_save(sender, instance, **kwargs):
    # Verifica se existe um representante comercial associado ao Corban
    if instance.representante_comercial:
        if user_profile := UserProfile.objects.filter(
            identifier=instance.representante_comercial.nu_cpf_cnpj.replace(
                '.', ''
            ).replace('-', '')
        ).first():
            # Atualiza o campo corban no UserProfile
            user_profile.corban = instance
            user_profile.save()


class UserProfile(AbstractBaseUser, PermissionsMixin):
    """
    Represents a "user profile" inside out system. Stores all user account
    related data, such as 'email address' and 'name'.
    """

    unique_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        null=True,
        blank=True,
    )
    identifier = models.CharField(
        max_length=80,
        verbose_name='CPF do usuário',
        unique=True,
        blank=False,
        help_text='Login do usuário',
    )

    name = models.CharField(max_length=255)
    corban = models.ForeignKey(
        Corban,
        verbose_name='Corban/Loja',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    produtos = models.ManyToManyField(
        Produtos,
        verbose_name='Produtos',
    )
    email = models.EmailField(
        unique=True,
        max_length=255,
        blank=True,
        null=True,
    )
    birth_date = models.DateField(
        verbose_name='Data de nascimento',
        null=True,
        blank=True,
    )
    phone = models.CharField(
        max_length=30,
        verbose_name='Telefone',
        null=True,
        blank=True,
    )

    cpf = models.CharField(
        max_length=30,
        verbose_name='CPF',
        null=True,
        blank=True,
    )

    is_premium = models.BooleanField(verbose_name='Assinatura ativa?', default=False)
    device_id = models.CharField(
        max_length=50, verbose_name='Device ID', null=True, blank=True, default=None
    )

    info = models.TextField(
        verbose_name='Informações adicionais',
        help_text='Informações relevantes',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True, verbose_name='Usuário Ativo?')
    is_staff = models.BooleanField(
        default=False,
        verbose_name='Staff',
        help_text='Indica quem tem acesso ao Backoffice',
    )
    is_checked = models.BooleanField(verbose_name='Verificado?', default=False)
    last_checked = models.DateTimeField(
        verbose_name='Última verificação', null=True, blank=True
    )
    numero_febraban = models.CharField(
        max_length=50,
        verbose_name='Certificado Febraban',
        help_text='Número do certificado Febraban',
        null=True,
        blank=True,
    )
    dt_emissao_certificado = models.DateField(
        verbose_name='Data de emissão',
        help_text='Data de emissão do certificado Febraban',
        null=True,
        blank=True,
    )
    dt_validade_certificado = models.DateField(
        verbose_name='Data de validade',
        help_text='Data de validade do certificado Febraban',
        null=True,
        blank=True,
    )
    uf_atuacao = models.SmallIntegerField(
        verbose_name='UF de atuação', choices=UFS, null=True, blank=True
    )
    municipio = models.CharField(
        verbose_name='Município de atuação',
        max_length=200,
        blank=True,
        null=True,
    )
    funcionario_byx = models.BooleanField(
        default=False,
        verbose_name='Funcionário grupo BYX?',
    )
    departamento = models.CharField(
        verbose_name='Departamento',
        max_length=200,
        blank=True,
        null=True,
    )
    responsavel_direto = models.CharField(
        verbose_name='Responsável direto',
        max_length=200,
        blank=True,
        null=True,
    )
    representante_comercial = models.BooleanField(
        verbose_name='Representante Comercial?', default=False
    )
    objects = UserProfileManager()

    date_joined = models.DateTimeField(('date joined'), default=timezone.now)

    media_segundos_digitacao = models.IntegerField(
        verbose_name='Média segundos digitação', null=True, blank=True
    )
    possui_chat_suporte = models.BooleanField(
        verbose_name='Possui suporte por chat ?', default=False
    )
    supervisor = models.ForeignKey(
        'self',
        verbose_name='Gestor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinados',
    )
    nivel_hierarquia = models.SmallIntegerField(
        choices=NIVEIS_HIERARQUIA,
        null=True,
        blank=True,
        verbose_name='Nível Hierárquico',
    )
    created_by = models.ForeignKey(
        'self',
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users_created',
    )
    endereco = models.CharField(
        max_length=500,
        verbose_name='Endereço',
        null=True,
        blank=True,
    )
    cep_endereco = models.CharField(
        max_length=10,
        verbose_name='CEP',
        null=True,
        blank=True,
    )
    numero_endereco = models.CharField(
        max_length=10,
        verbose_name='Número',
        null=True,
        blank=True,
    )
    bairro_endereco = models.CharField(
        max_length=500,
        verbose_name='Bairro',
        null=True,
        blank=True,
    )
    cidade_endereco = models.CharField(
        max_length=500,
        verbose_name='Cidade',
        null=True,
        blank=True,
    )
    uf_estado_endereco = models.CharField(
        verbose_name='UF de residência do cliente',
        max_length=2,
        null=True,
        blank=True,
    )
    complemento_endereco = models.CharField(
        max_length=500,
        verbose_name='Bairro',
        null=True,
        blank=True,
    )

    password_created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Senha criada em'
    )
    password_changed_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Senha atualizada em'
    )
    is_initial_password = models.BooleanField(default=True)
    USERNAME_FIELD = 'identifier'
    REQUIRED_FIELDS = ['name']

    @classmethod
    def get_subordinates(cls, user):
        """
        Retorna uma QuerySet de usuários que são subordinados do usuário fornecido,
        diretamente ou indiretamente. Se o usuário for DONO_LOJA, retorna todos os usuários
        do mesmo Corban.

        :param user: O usuário supervisor ou dono da loja
        :return: QuerySet de UserProfile
        """
        if user.nivel_hierarquia == EnumNivelHierarquia.DONO_LOJA:
            return cls.objects.filter(corban=user.corban)

        return cls._get_subordinates_recursive(user)

    @classmethod
    def _get_subordinates_recursive(cls, supervisor, visited_users=None):
        """
        Método auxiliar recursivo para obter subordinados.
        :param supervisor: O usuário supervisor
        :param visited_users: Conjunto de IDs de usuários já visitados para evitar loops
        :return: Lista de UserProfile
        """
        if visited_users is None:
            visited_users = set()

        if supervisor.id in visited_users:
            # Se já visitamos este usuário, retornamos uma lista vazia para evitar loops
            return []

        visited_users.add(supervisor.id)

        subordinates = cls.objects.filter(
            supervisor=supervisor, corban=supervisor.corban
        )
        all_subordinates = list(subordinates)

        for subordinate in subordinates:
            sub_subordinates = cls._get_subordinates_recursive(
                subordinate, visited_users
            )
            all_subordinates.extend(sub_subordinates)

        return cls.objects.filter(id__in=[user.id for user in all_subordinates])

    def set_password(self, raw_password):
        super().set_password(raw_password)
        # Definir um atributo de instância para indicar que a senha foi alterada
        self._password_changed = True

    def is_password_expired(self):
        from core.models import BackofficeConfigs

        # Obter configurações atuais
        configs = BackofficeConfigs.objects.first()

        # Utiliza a data da última alteração da senha; se nunca alterada, usa a data de criação
        last_password_change = self.password_changed_at or self.password_created_at

        # Prazo de expiração apenas para senhas subsequentes
        expiration_days = configs.subsequent_password_expiration_days

        return (
            last_password_change + datetime.timedelta(days=expiration_days)
            < timezone.now()
        )

    def get_nivel_hierarquia_display(self):
        return dict(NIVEIS_HIERARQUIA).get(self.nivel_hierarquia)

    def get_uf_atuacao_display(self):
        return dict(UFS).get(self.uf_atuacao)

    def clean(self):
        """
        Método de validação personalizado para verificar o nível de hierarquia e a presença do supervisor.
        """
        if (
            self.nivel_hierarquia
            and self.nivel_hierarquia < EnumNivelHierarquia.DONO_LOJA
            and not self.supervisor
        ):
            raise ValidationUserError(
                f'Para o nível de hierarquia selecionado, {self.get_nivel_hierarquia_display()}, é necessário selecionar um gestor.'
            )

        # Sempre chame o método clean do super para garantir que outras validações padrão sejam executadas
        super(UserProfile, self).clean()

    @property
    def get_full_name(self):
        """Django uses this when it needs to get the user's full name."""

        return self.name

    def get_short_name(self):
        """Django uses this when it needs to get the users abbreviated name."""

        return self.name

    def get_contratos_digitados(self):
        from contract.models.contratos import Contrato

        return Contrato.objects.filter(created_by=self)

    def get_contratos_pagos(self):
        from contract.models.contratos import Contrato

        return Contrato.objects.filter(created_by=self, contrato_pago=True)

    def get_contratos_cancelados(self):
        from contract.models.contratos import Contrato

        return Contrato.objects.filter(
            created_by=self, status=EnumContratoStatus.CANCELADO
        )

    def get_groups_list(self):
        """
        Get a list of group names.

        :param self: The instance of the class.
        :return: A list of group names.
        """

        return self.groups.values_list('name', flat=True)

    def __str__(self):
        """Django uses this when it needs to convert the object to text."""

        return self.name

    permissions = [
        ('happy_can_create_user', '[HAPPY] Can Create User'),
    ]

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = '1. Usuários'
        ordering = ('name',)


class FeatureToggle(models.Model):
    FACE_MATCHING = 'face_matching'
    CONFIA_FEATURE = 'confia_feature'

    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    @classmethod
    def is_feature_active(cls, feature_name):
        try:
            feature = cls.objects.get(name=feature_name)
            return feature.is_active
        except cls.DoesNotExist:
            return False


class CorbanBase(models.Model):
    @staticmethod
    def get_related_name():
        return '%(app_label)s_%(class)s'

    corban = models.ForeignKey(
        Corban,
        verbose_name='Corban',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='corban_loja',
    )
    corban_photo = models.CharField(
        verbose_name='Corban',
        max_length=200,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        UserProfile,
        verbose_name='Digitado por',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )
    created_by_photo = models.CharField(
        verbose_name='Digitado por',
        max_length=200,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.corban or ''

    class Meta:
        abstract = True


class UserAddress(models.Model):
    user = models.ForeignKey(
        UserProfile,
        verbose_name='Usuário',
        on_delete=models.PROTECT,
        related_name='user_address',
    )
    name = models.CharField(
        max_length=200,
        verbose_name='Identificação do endereço',
        null=True,
        blank=True,
    )
    postal_code = models.CharField(
        max_length=12,
        verbose_name='CEP',
        null=True,
        blank=True,
    )
    address = models.CharField(
        max_length=200,
        verbose_name='Endereço',
        null=True,
        blank=True,
    )
    address_neighborhood = models.CharField(
        max_length=50,
        verbose_name='Bairro',
        null=True,
        blank=True,
    )
    address_number = models.CharField(
        max_length=50,
        verbose_name='Número',
        null=True,
        blank=True,
    )
    address_complement = models.CharField(
        max_length=50,
        verbose_name='Complemento',
        null=True,
        blank=True,
    )
    city = models.CharField(
        max_length=40,
        verbose_name='Cidade',
        null=True,
        blank=True,
    )
    state = models.CharField(
        max_length=2,
        verbose_name='Estado',
        null=True,
        blank=True,
    )
    is_principal = models.BooleanField(
        verbose_name='Endereço principal?', default=False
    )

    def str(self):
        return self.name or ''

    class Meta:
        verbose_name = 'Usuário - Endereço'
        verbose_name_plural = 'Usuários - Endereços'


class UserSession(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, blank=True, null=True)

    def __str__(self):
        return self.user.identifier


class TokenSession(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    token = models.TextField(blank=True, null=True)
    access = models.TextField(blank=True, null=True, default=None)

    def __str__(self):
        return self.user.identifier
