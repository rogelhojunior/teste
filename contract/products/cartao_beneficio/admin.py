from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from contract.products.cartao_beneficio.models.averbacao_inss import LogAverbacaoINSS
from contract.products.cartao_beneficio.models.convenio import (
    FontePagadora,
    RegrasIdade,
    SubOrgao,
)
from contract.products.cartao_beneficio.models.planos import Planos
from contract.products.cartao_beneficio.models.seguradoras import Seguradoras


class FontePagadoraContratoInline(admin.TabularInline):
    model = FontePagadora
    extra = 0


class RegrasIdadeInline(admin.StackedInline):
    model = RegrasIdade
    extra = 0

    # def get_formset(
    #     self, request, obj=None, **kwargs
    # ):  # filtra para exibir apenas os suborgaos relacionados ao convenio
    #     formset = super().get_formset(request, obj=None, **kwargs)
    #     self.convenio_id = obj.id if obj else None
    #     formset.form.base_fields['suborgao'].queryset = SubOrgao.objects.filter(
    #         convenio=self.convenio_id
    #     )
    #     return formset

    fieldsets = (
        (
            'REGRA IDADE',
            {
                'fields': (
                    (
                        'idade_minima',
                        'idade_maxima',
                        'produto',
                        'tipo_vinculo_siape',
                        'ativo',
                    ),
                ),
            },
        ),
        (
            'LIMITES',
            {
                'fields': (
                    (
                        'fator',
                        'fator_saque',
                        'fator_compra',
                    ),
                    (
                        'limite_minimo_credito',
                        'limite_maximo_credito',
                    ),
                ),
            },
        ),
        (
            'GRUPO DE PARCELAS',
            {
                'fields': (
                    (
                        'grupo_parcelas',
                        'grupo_parcelas_2',
                        'grupo_parcelas_3',
                        'grupo_parcelas_4',
                    ),
                ),
            },
        ),
    )

    def limite_maximo_credito_formatted(self, instance):
        return '{:.2f}'.format(instance.limite_maximo_credito)

    limite_maximo_credito_formatted.short_description = 'Limite máximo de crédito'


class SubOrgaoInline(admin.TabularInline):
    model = SubOrgao
    extra = 0


class ParametrosConvenioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'taxa_produto', 'ativo')
    inlines = [RegrasIdadeInline, FontePagadoraContratoInline, SubOrgaoInline]


class PlanosAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo_plano')

    def delete_selected(self, request, queryset):
        # Verificar se algum dos planos selecionados está relacionado a um contrato
        for obj in queryset:
            if obj.contrato_planos.exists():
                # Mostrar uma mensagem amigável
                self.message_user(
                    request,
                    'Um ou mais planos estão relacionados a contratos e não podem ser deletados.',
                    level=messages.ERROR,
                )
                # Redirecionar para a página de alteração do primeiro plano que causa o erro
                return HttpResponseRedirect(
                    reverse('admin:cartao_beneficio_planos_changelist')
                )

        # Se não houver problemas, continue com a ação de deletar padrão
        super().delete_selected(request, queryset)

    # Modificando o nome da ação na lista dropdown
    delete_selected.short_description = 'Remover Planos selecionados'

    # Sobrescrevendo o método actions para incluir o nosso método personalizado delete_selected
    actions = [delete_selected]

    class Media:
        js = ('js/masks.js',)


class SeguradorasAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'tipo_comunicacao')


class LogAverbacaoINSSAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'timestamp',
    )
    change_list_template = 'admin/averbacao_inss/registroinss_change_list.html'


admin.site.register(Planos, PlanosAdmin)
admin.site.register(Seguradoras, SeguradorasAdmin)
admin.site.register(LogAverbacaoINSS, LogAverbacaoINSSAdmin)
