from django.conf import settings
from django.contrib import admin

from api_log.models import (
    Averbacao,
    Banksoft,
    CancelaReserva,
    ConsultaAverbadora,
    ConsultaBureau,
    ConsultaConsignacoes,
    ConsultaConvenio,
    ConsultaMargem,
    ConsultaMatricula,
    LogAtualizacaoCadastral,
    LogCliente,
    LogComercial,
    LogEnvioDossie,
    LogIn100,
    LogLoja,
    LogTransferenciaSaque,
    LogWebhook,
    QitechRetornos,
    RealizaReserva,
    RealizaSimulacao,
    RetornoCallbackUnico,
    RetornosDock,
    TemSaudeAdesao,
)


class ConsultaAverbadoraInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = ConsultaAverbadora
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class ConsultaMatriculaInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = ConsultaMatricula
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class ConsultaConsignacoesInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = ConsultaConsignacoes
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class ConsultaMargemInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = ConsultaMargem
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class ConsultaBureauInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = ConsultaBureau
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class ConsultaConvenioInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = ConsultaConvenio
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class RealizaReservaInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = RealizaReserva
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class CancelaReservaInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = CancelaReserva
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class RealizaSimulacaoInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = RealizaSimulacao
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class AverbacaoInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = Averbacao
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class RetornosDockInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = RetornosDock
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class RetornoCallbackUnicoInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = RetornoCallbackUnico
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class RetornoTemSaudeInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = TemSaudeAdesao
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class BanksoftInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = Banksoft
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class QitechRetornostInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = QitechRetornos
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class LogIn100Inline(admin.StackedInline):
    model = LogIn100
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'

    readonly_fields = ('criado_em_display',)


class LogAtualizacaoCadastralInline(admin.StackedInline):
    model = LogAtualizacaoCadastral
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'

    readonly_fields = ('criado_em_display',)


class LogEnvioDossieInline(admin.StackedInline):
    model = LogEnvioDossie
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'

    readonly_fields = ('criado_em_display',)


class LogTransferenciaSaqueInline(admin.StackedInline):
    model = LogTransferenciaSaque
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'

    readonly_fields = ('criado_em_display',)


class LogClienteAdmin(admin.ModelAdmin):
    search_fields = (
        'cliente__nome_cliente',
        'cliente__nu_cpf',
    )
    inlines = [
        ConsultaAverbadoraInline,
        RetornosDockInline,
        RetornoTemSaudeInline,
        BanksoftInline,
        QitechRetornostInline,
        LogIn100Inline,
        LogAtualizacaoCadastralInline,
        LogEnvioDossieInline,
        LogTransferenciaSaqueInline,
    ]


class LogRepresentanteComercialAdmin(admin.ModelAdmin):
    search_fields = (
        'representante_comercial',
        'usuario',
        'criado_em',
    )

    def nome_representante(self, obj):
        return obj.representante_comercial

    fieldsets = (
        (
            'DADOS CADASTRAIS',
            {
                'fields': (
                    ('usuario',),
                    ('operacao', 'representante_comercial'),
                    ('cpf_cnpj', 'cargo'),
                ),
            },
        ),
    )
    readonly_fields = ('criado_em',)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        fieldsets += (
            (
                'DATA DE CRIAÇÃO DO LOG',
                {
                    'fields': ('criado_em',),
                },
            ),
        )
        return fieldsets

    list_display = (
        'usuario',
        'operacao',
        'representante_comercial',
        'criado_em',
    )


class LogLojaAdmin(admin.ModelAdmin):
    search_fields = ('nome', 'representante_comercial')

    def nome_loja(self, obj):
        return obj.nome

    fieldsets = (
        (
            'DADOS CADASTRAIS',
            {
                'fields': (
                    ('usuario',),
                    ('operacao', 'loja'),
                    ('cpf_cnpj',),
                    ('representante_comercial',),
                    ('tipo_cadastro',),
                ),
            },
        ),
    )
    readonly_fields = ('criado_em',)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        fieldsets += (
            (
                'DATA DE CRIAÇÃO DO LOG',
                {
                    'fields': ('criado_em',),
                },
            ),
        )
        return fieldsets

    list_display = (
        'usuario',
        'operacao',
        'loja',
        'criado_em',
    )


class LogWebhookAdmin(admin.ModelAdmin):
    readonly_fields = ('criado_em',)
    model = LogWebhook
    extra = 0


if settings.ENVIRONMENT != 'PROD':
    admin.site.register(LogCliente, LogClienteAdmin)

admin.site.register(LogWebhook, LogWebhookAdmin)
admin.site.register(LogComercial, LogRepresentanteComercialAdmin)
admin.site.register(LogLoja, LogLojaAdmin)
