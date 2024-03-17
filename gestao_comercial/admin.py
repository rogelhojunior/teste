from django.contrib import admin, messages
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin

from api_log.models import LogComercial
from core.constants import EnumCargo
from gestao_comercial.forms import (
    AgenteInlineForm,
    GerenteInlineForm,
    SuperintendenteInlineForm,
)
from gestao_comercial.models.representante_comercial import (
    Agente,
    Gerente,
    LocalAtuacao,
    RepresentanteComercial,
    Superintendente,
)


class CustomInline(admin.TabularInline):
    def has_delete_permission(self, request, obj=None):
        return False


class AgenteInline(admin.TabularInline):
    model = Agente
    form = AgenteInlineForm
    extra = 0
    min_num = 1
    max_num = 10


class GerenteInline(admin.TabularInline):
    model = Gerente
    form = GerenteInlineForm
    extra = 0
    min_num = 1
    max_num = 10


class SuperintendenteInline(CustomInline):
    model = Superintendente
    form = SuperintendenteInlineForm
    extra = 0
    min_num = 1
    max_num = 10


class LocalAtuacaoInline(admin.TabularInline):
    model = LocalAtuacao
    extra = 0
    min_num = 1
    max_num = 10


class RepresentanteComercialAdmin(ImportExportModelAdmin):
    list_display = ('nome', 'tipo_atuacao', 'get_supervisor_direto')
    inlines = [
        LocalAtuacaoInline,
    ]

    def change_view(self, request, object_id, form_url='', extra_context=None):
        obj = self.get_object(request, object_id)
        if obj:
            self.inlines = self.get_inlines_for_cargo(obj.cargo)
        else:
            self.inlines = [LocalAtuacaoInline]
        response = super().change_view(request, object_id, form_url, extra_context)
        self.inlines.clear()
        self.inlines = [LocalAtuacaoInline]

        # Verificar se a alteração foi bem-sucedida e se houve uma alteração no objeto
        if response.status_code == 200 and obj and 'POST' in request.method:
            # Salvar log de edição
            log = LogComercial.objects.create(
                usuario=request.user,
                representante_comercial=obj.nome,
                cpf_cnpj=obj.nu_cpf_cnpj,
                cargo=obj.cargo,
                operacao='Edição',
            )
            log.save()

        return response

    def get_inlines_for_cargo(self, cargo):
        self.inlines.clear()
        inlines = [LocalAtuacaoInline]
        if not cargo or not self:
            return inlines
        if cargo == EnumCargo.AGENTE:
            inlines.append(AgenteInline)
        elif cargo == EnumCargo.GERENTE:
            inlines.append(GerenteInline)
        elif cargo == EnumCargo.SUPERINTENDENTE:
            inlines.append(SuperintendenteInline)
        return inlines

    def get_supervisor_direto(self, obj):
        supervisor_direto = ''
        if isinstance(obj, RepresentanteComercial):
            if obj.agente_set.exists():
                supervisor_direto = obj.agente_set.first().supervisor_direto
            elif obj.gerente_set.exists():
                supervisor_direto = obj.gerente_set.first().supervisor_direto
            elif obj.superintendente_set.exists():
                supervisor_direto = obj.superintendente_set.first().supervisor_direto
        return supervisor_direto or ''

    get_supervisor_direto.short_description = 'Supervisor Direto'

    def save_model(self, request, obj, form, change):
        if representante := RepresentanteComercial.objects.filter(
            nu_cpf_cnpj=obj.nu_cpf_cnpj
        ):
            if representante.get().cargo is not None:
                # Se o que foi salvo é igual ao que vai ser salvo agora
                if obj.cargo == representante.get().cargo:
                    super().save_model(request, obj, form, change)
                    operacao = 'Criação' if not change else 'Edição'
                    log = LogComercial.objects.create(
                        usuario=request.user,
                        representante_comercial=obj.nome,
                        cpf_cnpj=obj.nu_cpf_cnpj,
                        cargo=obj.cargo if obj.cargo is not None else 'N/A',
                        operacao=operacao,
                    )
                    log.save()
                    return
                else:
                    if obj.cargo is EnumCargo.AGENTE:  # Cargo atual
                        if (
                            representante.get().cargo is EnumCargo.GERENTE
                        ):  # Cargo anterior
                            gerente = Gerente.objects.filter(
                                representante_comercial_id=representante.get().id
                            )
                            gerente.delete()
                        elif (
                            representante.get().cargo is EnumCargo.SUPERINTENDENTE
                        ):  # Cargo anterior
                            superintendente = Superintendente.objects.filter(
                                representante_comercial_id=representante.get().id
                            )
                            superintendente.delete()
                    elif obj.cargo is EnumCargo.GERENTE:  # Cargo atual
                        if (
                            representante.get().cargo is EnumCargo.AGENTE
                        ):  # Cargo anterior
                            agente = Agente.objects.filter(
                                representante_comercial_id=representante.get().id
                            )
                            agente.delete()
                        elif (
                            representante.get().cargo is EnumCargo.SUPERINTENDENTE
                        ):  # Cargo anterior
                            superintendente = Superintendente.objects.filter(
                                representante_comercial_id=representante.get().id
                            )
                            superintendente.delete()
                    elif obj.cargo is EnumCargo.SUPERINTENDENTE:  # Cargo atual
                        if (
                            representante.get().cargo is EnumCargo.AGENTE
                        ):  # Cargo anterior
                            agente = Agente.objects.filter(
                                representante_comercial_id=representante.get().id
                            )
                            agente.delete()
                        elif (
                            representante.get().cargo is EnumCargo.GERENTE
                        ):  # Cargo anterior
                            gerente = Gerente.objects.filter(
                                representante_comercial_id=representante.get().id
                            )
                            gerente.delete()
        # Salva e gera o log
        super().save_model(request, obj, form, change)
        operacao = 'Criação' if not change else 'Edição'
        log = LogComercial.objects.create(
            usuario=request.user,
            representante_comercial=obj.nome,
            cpf_cnpj=obj.nu_cpf_cnpj,
            cargo=obj.cargo if obj.cargo is not None else 'N/A',
            operacao=operacao,
        )
        log.save()

    def add_view(self, request, form_url='', extra_context=None):
        messages.warning(
            request,
            format_html(
                '<strong>Atenção:</strong> '
                ' Após preencher as abas'
                '<strong>"Dados Cadastrais"</strong> e <strong>"Local de Atuação"</strong>'
                ', clique no botão '
                '<strong>"Salvar e continuar editando"</strong>'
                'para desbloquear a aba '
                '<strong>"Responsável Direto"</strong>.'
                ' No caso de não possuir Responsável Direto, apenas escreva "Não Possui".'
            ),
        )
        return super().add_view(request, form_url, extra_context)

    fieldsets = (
        (
            'DADOS CADASTRAIS',
            {
                'fields': (
                    ('nome',),
                    ('nu_cpf_cnpj',),
                    ('telefone',),
                    ('email',),
                    ('cargo',),
                ),
            },
        ),
        (
            'ÁREA DE COBERTURA',
            {
                'fields': (('tipo_atuacao',),),
            },
        ),
    )

    def delete_queryset(self, request, queryset):
        # Salvar logs de exclusão para cada objeto do queryset
        for obj in queryset:
            log = LogComercial.objects.create(
                usuario=request.user,
                representante_comercial=obj.nome,
                cpf_cnpj=obj.nu_cpf_cnpj,
                cargo=obj.cargo,
                operacao='Exclusão',
            )
            log.save()

        super().delete_queryset(request, queryset)


admin.site.register(RepresentanteComercial, RepresentanteComercialAdmin)
