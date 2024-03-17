from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import (
    CharWidget,
    ForeignKeyWidget,
    IntegerWidget,
    ManyToManyWidget,
)

from api_log.models import LogLoja
from contract.constants import EnumTipoProduto
from core.choices import NIVEIS_HIERARQUIA, UFS
from core.constants import EnumCadastro
from custom_auth.anexo_usuario import AnexoUsuario
from custom_auth.forms import CorbanForm, UserCreationForm, UserForm
from custom_auth.models import Corban, Produtos, UserProfile


# Aqui que fala quais campos seram importados/exportados
class UserResource(resources.ModelResource):
    corban = fields.Field(
        column_name='Corban',
        attribute='corban',
        widget=ForeignKeyWidget(
            Corban,
            'corban_name',
        ),
    )
    name = fields.Field(
        column_name='Nome',
        attribute='name',
    )
    identifier = fields.Field(
        column_name='Login',
        attribute='identifier',
        widget=CharWidget(),
    )
    phone = fields.Field(
        column_name='Telefone',
        attribute='phone',
    )
    birth_date = fields.Field(
        column_name='Nascimento',
        attribute='birth_date',
    )
    cpf = fields.Field(
        column_name='CPF',
        attribute='cpf',
        widget=CharWidget(),
    )
    date_joined = fields.Field(
        column_name='Criado em',
        attribute='date_joined',
    )
    is_active = fields.Field(
        column_name='Ativo?',
        attribute='is_active',
    )

    is_staff = fields.Field(
        column_name='Staff?',
        attribute='is_staff',
    )
    groups = fields.Field(
        column_name='Perfil de acesso',
        attribute='groups',
        widget=ManyToManyWidget(Group, field='name'),
    )
    representante_comercial = fields.Field(
        column_name='Representante Comercial',
        attribute='representante_comercial',
    )
    produtos = fields.Field(
        column_name='Produtos',
        attribute='produtos',
        widget=ManyToManyWidget(Produtos, field='nome'),
    )
    uf = fields.Field(column_name='UF', attribute='uf_atuacao')
    email = fields.Field(column_name='Email', attribute='email')
    nivel_hierarquia = fields.Field(
        column_name='Nivel Hierarquia',
        attribute='nivel_hierarquia',
        widget=IntegerWidget(),
    )

    def get_nivel_hierarquia_value(self, nome_nivel):
        hierarquia_choices = dict(
            NIVEIS_HIERARQUIA
        )  # Converte a tupla para um dicionário
        hierarquia_para_valor = {
            v: k for k, v in hierarquia_choices.items()
        }  # Inverte o dicionário
        return hierarquia_para_valor.get(nome_nivel)

    def get_uf_value(self, nome_uf):
        uf_choices = dict(UFS)  # Converte a tupla para um dicionário
        uf_para_valor = {v: k for k, v in uf_choices.items()}  # Inverte o dicionário
        return uf_para_valor.get(nome_uf)

    def before_import_row(self, row, **kwargs):
        nivel_nome = row.get('Nivel Hierarquia', None)
        nome_uf = row.get('UF', None)
        if nivel_nome:
            row['Nivel Hierarquia'] = self.get_nivel_hierarquia_value(nivel_nome)
        if nome_uf:
            row['UF'] = self.get_uf_value(nome_uf)

        # Método para manipular dados antes da exportação

    def dehydrate_nivel_hierarquia(self, user_profile):
        # Use o método get_nivel_hierarquia_display do modelo, se disponível
        if hasattr(user_profile, 'get_nivel_hierarquia_display'):
            return user_profile.get_nivel_hierarquia_display()

    def dehydrate_uf(self, user_profile):
        # Use o método get_nivel_hierarquia_display do modelo, se disponível
        if hasattr(user_profile, 'get_uf_atuacao_display'):
            return user_profile.get_uf_atuacao_display()

        # Método para importar apenas supervisores

    def import_supervisors(self, dataset, dry_run=False):
        for row in dataset.dict:
            user_identifier = row['Login']
            supervisor_identifier = row['Supervisor']
            try:
                user = UserProfile.objects.get(identifier=user_identifier)
                supervisor = UserProfile.objects.get(identifier=supervisor_identifier)
                if supervisor.corban == user.corban:
                    user.supervisor = supervisor
                    if not dry_run:
                        user.save()
            except UserProfile.DoesNotExist:
                # Tratar exceções, como usuário ou supervisor não encontrado
                pass

    def dehydrate_is_active(self, obj):
        return 'True' if obj.is_active else 'False'

    def dehydrate_is_staff(self, obj):
        return 'True' if obj.is_staff else 'False'

    def dehydrate_representante_comercial(self, obj):
        return 'True' if obj.representante_comercial else 'False'

    class Meta:
        model = UserProfile
        fields = (
            'corban',
            'name',
            'login',
            'phone',
            'nascimento',
            'cpf',
            'representante_comercial',
            'created_at',
            'is_active',
            'is_staff',
            'groups',
            'email',
            'produtos',
            'uf',
            'nivel_hierarquia',
        )
        skip_unchanged = True
        report_skipped = True
        import_id_fields = ['identifier']


class AnexoUsuarioInline(admin.StackedInline):
    model = AnexoUsuario
    extra = 0


class CustomUserAdmin(UserAdmin, ImportExportModelAdmin):
    resource_class = UserResource
    inlines = [
        AnexoUsuarioInline,
    ]
    form = UserForm
    add_form = UserCreationForm
    ordering = ('name',)
    list_display = (
        'name',
        'identifier',
        'email',
        'corban',
        'grupos',
        'is_active',
        'is_staff',
        'is_superuser',
        'created_by',
    )
    search_fields = ('name', 'identifier', 'email')
    list_filter = (
        'corban',
        'groups',
        'is_active',
        'is_staff',
        'is_superuser',
        'is_checked',
        'last_checked',
    )
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (
            _('INFORMAÇÕES DE ACESSO'),
            {
                'fields': (
                    ('name', 'identifier'),
                    (
                        'email',
                        'phone',
                    ),
                    (
                        'password_created_at',
                        'password_changed_at',
                        'is_initial_password',
                    ),
                )
            },
        ),
        (
            _('VINCULO COBAN/LOJA'),
            {
                'fields': (
                    ('corban',),
                    (
                        'nivel_hierarquia',
                        'supervisor',
                    ),
                )
            },
        ),
        (
            _('PERMISSÕES'),
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'representante_comercial',
                    (
                        'is_checked',
                        'last_checked',
                    ),
                    'produtos',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        (_('DATAS IMPORTANTES'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'identifier',
                    'name',
                    'email',
                    'phone',
                    'corban',
                    'nivel_hierarquia',
                    'supervisor',
                    'produtos',
                    'groups',
                ),
                'description': (
                    'Preencha os dados de identificação e configurações de contas'
                ),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if (
            request.user.is_superuser
            or request.user.groups.filter(name='Master').exists()
        ):
            return qs
        if request.user.corban.tipo_cadastro is EnumCadastro.MATRIZ:
            return qs.filter(
                Q(corban__tipo_cadastro=EnumCadastro.SUBSIDIARIA)
                | Q(corban__tipo_cadastro=EnumCadastro.SUBESTABELECIMENTO)
            )
        return qs.filter(corban=request.user.corban)

    def media_tempo_digitacao(self, obj):
        if obj.media_segundos_digitacao is not None:
            return timedelta(seconds=obj.media_segundos_digitacao)
        return '-'

    def adicionar_produto(
        self,
        usuario,
        request,
        produto,
        mensagem_sucesso,
        mensagem_erro_corban,
        mensagem_erro_produto,
    ):
        """
        Adiciona um produto a um usuário. Essa função é reutilizada nas funções abaixo, que são actions.

        Args:
            usuario: O usuário ao qual o produto será adicionado.
            request: O objeto de requisição.
            produto: O produto a ser adicionado.
            mensagem_sucesso: Mensagem de sucesso para exibição.
            mensagem_erro_corban: Mensagem de erro para falta do produto no corban.
            mensagem_erro_produto: Mensagem de erro para produto já existente no usuário.
        """
        if usuario.corban:
            if produto in usuario.corban.produtos.all():
                if produto in usuario.produtos.all():
                    messages.error(request, f'{usuario.name} - {mensagem_erro_produto}')
                else:
                    usuario.produtos.add(produto)
                    messages.success(request, f'{usuario.name} - {mensagem_sucesso}')
            else:
                messages.error(
                    request,
                    f'{usuario.name} - O corban {usuario.corban.corban_name} {mensagem_erro_corban}',
                )
        else:
            messages.error(request, f'{usuario.name} não possui corban')

    def adicionar_produto_margem_livre(self, request, queryset):
        """
        Adiciona o produto de margem livre aos usuários selecionados.

        Args:
            request: O objeto de requisição.
            queryset: O conjunto de usuários selecionados.
        """
        produto_margem_livre = Produtos.objects.filter(
            tipo_produto=EnumTipoProduto.MARGEM_LIVRE
        ).first()
        mensagem_sucesso = 'Produto Margem Livre adicionado com sucesso!'
        mensagem_erro_corban = 'não possui o produto Margem Livre'
        mensagem_erro_produto = 'Usuário já possui o produto Margem Livre'

        for usuario in queryset:
            self.adicionar_produto(
                usuario,
                request,
                produto_margem_livre,
                mensagem_sucesso,
                mensagem_erro_corban,
                mensagem_erro_produto,
            )

    def adicionar_produto_cartao(self, request, queryset):
        """
        Adiciona o produto de cartão benefício aos usuários selecionados.

        Args:
            request (tipo): Descrição do objeto de requisição.
            queryset (tipo): Descrição do conjunto de usuários selecionados.
        """
        produto_cartao_beneficio = Produtos.objects.filter(
            tipo_produto__in=[
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.SAQUE_COMPLEMENTAR,
            ]
        )
        mensagem_sucesso = 'Produto Cartão Benefício adicionado com sucesso!'
        mensagem_erro_corban = 'não possui o produto Cartão Benefício'
        mensagem_erro_produto = 'Usuário já possui o produto Cartão Benefício'

        for usuario in queryset:
            for produto in produto_cartao_beneficio:
                self.adicionar_produto(
                    usuario,
                    request,
                    produto,
                    mensagem_sucesso,
                    mensagem_erro_corban,
                    mensagem_erro_produto,
                )

    def adicionar_produto_port_refin(self, request, queryset):
        """
        Adiciona o produto de portabilidade refinanciamento aos usuários selecionados.

        Args:
            request: O objeto de requisição.
            queryset: O conjunto de usuários selecionados.
        """
        produto_port_refin = Produtos.objects.filter(
            tipo_produto__in=[
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ]
        )
        mensagem_sucesso = (
            'Produto Portabilidade Refinanciamento adicionado com sucesso!'
        )
        mensagem_erro_corban = 'não possui o produto Portabilidade Refinanciamento'
        mensagem_erro_produto = (
            'Usuário já possui o produto Portabilidade Refinanciamento'
        )

        for usuario in queryset:
            for produto in produto_port_refin:
                self.adicionar_produto(
                    usuario,
                    request,
                    produto,
                    mensagem_sucesso,
                    mensagem_erro_corban,
                    mensagem_erro_produto,
                )

    adicionar_produto_port_refin.short_description = (
        'Adicionar Portabilidade Refinanciamento'
    )
    adicionar_produto_cartao.short_description = (
        'Adicionar Cartão Benefício, Saque Complementar'
    )
    adicionar_produto_margem_livre.short_description = 'Adicionar Margem Livre'

    def get_readonly_fields(self, request, obj=None):
        """
        Defines the fields that cannot be changed in the user record
        """

        has_permission = request.user.groups.filter(
            Q(name='Master') | Q(name='Corban Master') | Q(name='Backoffice')
        ).exists()

        readonly_fields = [
            'date_joined',
            'last_login',
            'password_created_at',
            'password_changed_at',
            'representante_comercial',
        ]
        restricted_fields = ['identifier', 'corban', 'name', 'email', 'phone']

        if not has_permission:
            readonly_fields += restricted_fields

        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.groups.filter(name='Master').exists():
            fieldsets += (
                (
                    'INFORMAÇÕES PESSOAIS',
                    {
                        'fields': (
                            'numero_febraban',
                            ('dt_emissao_certificado', 'dt_validade_certificado'),
                            (
                                'uf_atuacao',
                                'municipio',
                            ),
                            'funcionario_byx',
                            'possui_chat_suporte',
                        )
                    },
                ),
                (
                    'PERMISSÕES MASTER',
                    {
                        'fields': (
                            ('is_staff',),
                            ('is_superuser',),
                        )
                    },
                ),
                ('DADOS IMPORTANTES', {'fields': ('info',)}),
            )
            if obj and obj.funcionario_byx:
                fieldsets += (
                    (
                        'DADOS GRUPO BYX',
                        {'fields': (('departamento',), ('responsavel_direto',))},
                    ),
                )
        return fieldsets

    def grupos(self, obj):
        return format_html('<br /> '.join([str(p) for p in obj.groups.all()]))

    media_tempo_digitacao.short_description = 'Média de tempo por digitação'
    grupos.short_description = 'Perfil de acesso'

    def upload_csv_action(self, request, queryset):
        return HttpResponseRedirect('/custom_auth/upload-csv/')

    upload_csv_action.short_description = 'Importar Supervisores via CSV'

    class Media:
        js = ('js/custom_user_admin.js',)

    actions = [
        adicionar_produto_margem_livre,
        adicionar_produto_cartao,
        adicionar_produto_port_refin,
        upload_csv_action,
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class CorbanAdmin(admin.ModelAdmin):
    list_display = ('id', 'corban_name', 'representante_comercial')
    search_fields = ('id', 'corban_name', 'representante_comercial__nome')
    # filter_horizontal = ('produtos',)
    form = CorbanForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.is_active:
            usuarios = UserProfile.objects.filter(corban=obj)
            for usuario in usuarios:
                usuario.is_active = False
                usuario.save()

        # Salvar log de criação ou edição
        log = LogLoja.objects.create(
            usuario=request.user,
            loja=obj.corban_name,
            cpf_cnpj=obj.corban_CNPJ,
            representante_comercial=obj.representante_comercial,
            tipo_cadastro=obj.tipo_cadastro,
            operacao='Edição' if change else 'Criação',
        )
        log.save()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # Obter o objeto antes de realizar a alteração
        obj = self.get_object(request, object_id)

        # Chamada ao método change_view original
        response = super().change_view(request, object_id, form_url, extra_context)

        # Verificar se a alteração foi bem-sucedida e se houve uma alteração no objeto
        if response.status_code == 200 and obj and 'POST' in request.method:
            # Salvar log de edição
            log = LogLoja.objects.create(
                usuario=request.user,
                loja=obj.corban_name,
                cpf_cnpj=obj.corban_CNPJ,
                representante_comercial=obj.representante_comercial,
                tipo_cadastro=obj.tipo_cadastro,
                operacao='Edição',
            )
            log.save()

        return response

    def add_view(self, request, form_url='', extra_context=None):
        messages.warning(
            request,
            format_html(
                '<strong>Atenção:</strong> '
                ' Após preencher o campo <strong>"Tipo de Cadastro (Subsidiária/Subestabelecimento)"</strong>, clique no botão <strong>"Salvar e continuar editando"</strong> para que seja exibido o campo <strong>"Número da Loja Matriz"</strong>'
            ),
        )
        return super().add_view(request, form_url, extra_context)

    fieldsets = (
        (
            'DADOS CADASTRAIS',
            {
                'fields': (
                    'corban_name',
                    'corban_CNPJ',
                    'corban_endereco',
                    'telefone',
                    'representante_comercial',
                    'mesa_corban',
                    'parent_corban',
                    'corban_type',
                    'is_active',
                ),
            },
        ),
        (
            'DADOS BANCÁRIOS',
            {
                'fields': (
                    'banco',
                    ('agencia', 'conta'),
                ),
            },
        ),
        (
            'REPRESENTANTE DA LOJA',
            {
                'fields': (
                    'nome_representante',
                    'telefone_representante',
                    ('nu_cpf_cnpj_representante', 'corban_email'),
                    'tipo_relacionamento',
                ),
            },
        ),
        (
            'OUTRAS INFORMAÇÕES',
            {
                'fields': (
                    ('tipo_estabelecimento', 'tipo_venda'),
                    ('tipo_cadastro',),
                ),
            },
        ),
        (
            'VINCULO DE PRODUTOS',
            {
                'fields': (('produtos',),),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.tipo_cadastro in (
            EnumCadastro.SUBSIDIARIA,
            EnumCadastro.SUBESTABELECIMENTO,
        ):
            fieldsets += (
                (
                    'CAMPO ADICIONAL',
                    {
                        'fields': ('loja_matriz',),
                    },
                ),
            )
        return fieldsets

    def delete_queryset(self, request, queryset):
        # Salvar logs de exclusão para cada objeto do queryset
        for obj in queryset:
            log = LogLoja.objects.create(
                usuario=request.user,
                loja=obj.corban_name,
                cpf_cnpj=obj.corban_CNPJ,
                representante_comercial=obj.representante_comercial,
                tipo_cadastro=obj.tipo_cadastro,
                operacao='Exclusão',
            )
            log.save()

        super().delete_queryset(request, queryset)

    class Media:
        js = ('js/custom_corban_admin.js',)


class ProdutoAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'ativo',
    )

    # def has_change_permission(self, request, obj=None):
    #     return False
    #
    # def has_add_permission(self, request, obj=None):
    #     return False
    #
    # def has_delete_permission(self, request, obj=None):
    #     return False


admin.site.register(UserProfile, CustomUserAdmin)
admin.site.register(Corban, CorbanAdmin)
admin.site.register(Produtos, ProdutoAdmin)
