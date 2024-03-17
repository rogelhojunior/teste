from django.contrib import admin

from auditoria.models import (
    LogAlteracaoCadastral,
    LogAlteracaoCadastralDadosCliente,
    LogAlteracaoCadastralDock,
)


# Register your models here.
class LogAlteracaoCadastralDockInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = LogAlteracaoCadastralDock
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class LogAlteracaoCadastralDadosClienteInline(admin.StackedInline):
    readonly_fields = ('criado_em_display',)
    model = LogAlteracaoCadastralDadosCliente
    extra = 0

    def criado_em_display(self, obj):
        return obj.criado_em

    criado_em_display.short_description = 'Criado em'


class LogAlteracaoCadastralAdmin(admin.ModelAdmin):
    list_display = ('cliente',)
    inlines = [LogAlteracaoCadastralDockInline, LogAlteracaoCadastralDadosClienteInline]


admin.site.register(LogAlteracaoCadastral, LogAlteracaoCadastralAdmin)
