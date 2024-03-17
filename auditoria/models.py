from django.db import models

from core.models import Cliente


class LogAlteracaoCadastral(models.Model):
    cliente = models.ForeignKey(
        Cliente, verbose_name='Cliente', on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = 'Histórico de alteração'
        verbose_name_plural = 'Histórico de alterações'

    def __str__(self):
        return self.cliente.nome_cliente


class LogAlteracaoCadastralDock(models.Model):
    log_cadastral = models.ForeignKey(
        LogAlteracaoCadastral,
        verbose_name='Alteração Cadastral',
        on_delete=models.CASCADE,
    )

    tipo_registro = models.CharField(verbose_name='Tipo de Registro', max_length=20)

    registro_anterior = models.CharField(
        verbose_name='Registro Anterior', max_length=300, null=True, blank=True
    )

    novo_registro = models.CharField(
        verbose_name='Novo Registro', max_length=300, null=True, blank=True
    )

    usuario = models.CharField(
        verbose_name='Usuário', max_length=300, null=True, blank=True
    )

    canal = models.CharField(
        verbose_name='Canal', max_length=300, null=True, blank=True
    )

    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de alteração - DOCK'
        verbose_name_plural = 'Histórico de alterações - DOCK'

    def __str__(self):
        return f'{self.tipo_registro} - {self.canal}'


class LogAlteracaoCadastralDadosCliente(models.Model):
    log_cadastral = models.ForeignKey(
        LogAlteracaoCadastral,
        verbose_name='Alteração Cadastral',
        on_delete=models.CASCADE,
    )

    tipo_registro = models.CharField(
        verbose_name='Tipo de Registro', max_length=20, null=True, blank=True
    )

    registro_anterior = models.CharField(
        verbose_name='Registro Anterior', max_length=300, null=True, blank=True
    )

    novo_registro = models.CharField(
        verbose_name='Novo Registro', max_length=300, null=True, blank=True
    )

    usuario = models.CharField(
        verbose_name='Usuário', max_length=300, null=True, blank=True
    )

    canal = models.CharField(
        verbose_name='Canal', max_length=300, null=True, blank=True
    )

    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Histórico de alteração - Dados Bancários'
        verbose_name_plural = 'Histórico de alterações - Dados Bancários'

    def __str__(self):
        return f'{self.tipo_registro} - {self.canal}'
