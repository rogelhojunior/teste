import locale

from django.db import models

from core.choices import CARGO, TIPOS_CADASTRO
from core.models import cliente
from custom_auth.models import UserProfile
from gestao_comercial.models.representante_comercial import RepresentanteComercial

# Formatting settings using locale
locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')


class LogLoja(models.Model):
    usuario = models.ForeignKey(
        UserProfile, verbose_name='Usuário', on_delete=models.CASCADE
    )
    loja = models.CharField(verbose_name='Nome do Corban/Loja', max_length=200)
    cpf_cnpj = models.CharField(verbose_name='CPF/CNPJ do Corban/Loja', max_length=200)
    representante_comercial = models.ForeignKey(
        RepresentanteComercial,
        verbose_name='Representante Comercial',
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
    )
    tipo_cadastro = models.SmallIntegerField(
        verbose_name='Tipo de Cadastro', choices=TIPOS_CADASTRO, null=True, blank=True
    )
    operacao = models.CharField(verbose_name='Operação', max_length=20)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return f'{self.loja} - {self.operacao}'

    class Meta:
        verbose_name = 'Log - Corban/Loja'
        verbose_name_plural = 'Logs - Corban/Loja'


class LogComercial(models.Model):
    usuario = models.ForeignKey(
        UserProfile, verbose_name='Usuário', on_delete=models.CASCADE
    )
    representante_comercial = models.CharField(
        verbose_name='Nome do Representante Comercial', max_length=200
    )
    cpf_cnpj = models.CharField(
        verbose_name='CPF/CNPJ do Representante Comercial', max_length=200
    )
    cargo = models.SmallIntegerField(
        verbose_name='Cargo', choices=CARGO, null=True, blank=True
    )
    operacao = models.CharField(verbose_name='Operação', max_length=20)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return f'{self.representante_comercial} - {self.operacao}'

    class Meta:
        verbose_name = 'Log - Representante Comercial'
        verbose_name_plural = 'Logs - Representantes Comerciais'


class LogCliente(models.Model):
    cliente = models.ForeignKey(
        cliente.Cliente, verbose_name='Cliente', on_delete=models.CASCADE
    )

    def __str__(self):
        return self.cliente.nome_cliente

    class Meta:
        verbose_name = 'Log - Cliente'
        verbose_name_plural = 'Log - Clientes'


class ConsultaAverbadora(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tipo_chamada = models.CharField(
        verbose_name='Tipo chamada', null=True, blank=True, max_length=50
    )
    payload_envio = models.TextField(
        verbose_name='Payload de envio', null=True, blank=True
    )
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return self.log_api.cliente.nome_cliente

    class Meta:
        verbose_name = 'Consulta Averbadora'
        verbose_name_plural = 'Consulta Averbadora'


class ConsultaMatricula(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    matricula = models.CharField(
        verbose_name='Matrícula', null=True, blank=True, max_length=45
    )
    folha = models.CharField(verbose_name='Folha', null=True, blank=True, max_length=10)
    verba = models.CharField(verbose_name='Verba', null=True, blank=True, max_length=15)
    tipo_margem = models.CharField(
        verbose_name='Tipo Margem', null=True, blank=True, max_length=40
    )
    margem_atual = models.DecimalField(
        verbose_name='Margem atual',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    cargo = models.CharField(
        verbose_name='Cargo', null=True, blank=True, max_length=200
    )
    estavel = models.BooleanField(verbose_name='Estável', default=False)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return self.log_api.cliente.nome_cliente

    class Meta:
        verbose_name = 'Consulta Matrícula'
        verbose_name_plural = 'Consulta Matrícula'


class ConsultaConvenio(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    codigo_folha = models.CharField(
        verbose_name='Código folha', null=True, blank=True, max_length=25
    )
    descricao_folha = models.CharField(
        verbose_name='Descricao folha', null=True, blank=True, max_length=300
    )
    periodo_atual = models.IntegerField(
        verbose_name='Período atual', null=True, blank=True
    )
    verba = models.IntegerField(verbose_name='Verba', null=True, blank=True)
    autorizacao = models.BooleanField(verbose_name='Requer autorização?', default=False)
    cet_maximo = models.DecimalField(
        verbose_name='CET máximo',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    descricao_margem = models.CharField(
        verbose_name='Descrição da margem', null=True, blank=True, max_length=500
    )
    descricao_modalidade = models.CharField(
        verbose_name='Descrição da modalidade', null=True, blank=True, max_length=500
    )
    validade_reserva = models.IntegerField(
        verbose_name='Validade da reserva', null=True, blank=True
    )
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )
    descricao = models.CharField(
        verbose_name='Descrição', null=True, blank=True, max_length=500
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em',
        auto_now_add=True,
        blank=True,
    )

    def __str__(self):
        return self.descricao_margem

    class Meta:
        verbose_name = 'Consulta Convênio'
        verbose_name_plural = 'Consulta Convênios'


class ConsultaConsignacoes(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    codigo_operacao = models.CharField(
        verbose_name='Código da operação', null=True, blank=True, max_length=25
    )
    prazo = models.IntegerField(verbose_name='Prazo', null=True, blank=True)
    valor = models.DecimalField(
        verbose_name='Valor', decimal_places=7, max_digits=12, null=True, blank=True
    )
    valor_liberado = models.DecimalField(
        verbose_name='Valor liberado',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    codigo_operacao_instituicao = models.CharField(
        verbose_name='Código da operação na instituição',
        null=True,
        blank=True,
        max_length=25,
    )
    verba = models.CharField(verbose_name='Verba', null=True, blank=True, max_length=15)
    prazo_restante = models.CharField(
        verbose_name='Verba', null=True, blank=True, max_length=15
    )
    data_consignacao = models.DateTimeField(
        verbose_name='Data da Consignação', null=True, blank=True
    )
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )
    descricao = models.CharField(
        verbose_name='Descrição', null=True, blank=True, max_length=500
    )

    def __str__(self):
        return self.log_api.cliente.nome_cliente

    class Meta:
        verbose_name = 'Consulta Consignação'
        verbose_name_plural = 'Consulta Consignações'


class ConsultaMargem(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    matricula = models.CharField(
        verbose_name='Matrícula', null=True, blank=True, max_length=15
    )
    folha = models.CharField(verbose_name='Folha', null=True, blank=True, max_length=10)
    verba = models.CharField(verbose_name='Verba', null=True, blank=True, max_length=15)
    margem_atual = models.DecimalField(
        verbose_name='Margem atual',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    cargo = models.CharField(
        verbose_name='Cargo', null=True, blank=True, max_length=200
    )
    estavel = models.BooleanField(verbose_name='Estável', default=False)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )
    descricao = models.CharField(
        verbose_name='Descrição', null=True, blank=True, max_length=500
    )

    def __str__(self):
        return self.log_api.cliente.nome_cliente

    class Meta:
        verbose_name = 'Consulta Margem'
        verbose_name_plural = 'Consulta Margens'


class RealizaReserva(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='realiza_reserva_cliente',
    )
    matricula = models.CharField(
        verbose_name='Matrícula', null=True, blank=True, max_length=15
    )
    folha = models.CharField(verbose_name='Folha', null=True, blank=True, max_length=10)
    verba = models.CharField(verbose_name='Verba', null=True, blank=True, max_length=15)
    valor = models.DecimalField(
        verbose_name='Valor', decimal_places=7, max_digits=12, null=True, blank=True
    )
    reserva = models.CharField(
        verbose_name='Número da Reserva', null=True, blank=True, max_length=15
    )
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )
    descricao = models.CharField(
        verbose_name='Descrição', null=True, blank=True, max_length=500
    )

    def __str__(self):
        return self.log_api.cliente.nome_cliente

    class Meta:
        verbose_name = 'Realizar reserva'
        verbose_name_plural = 'Realiza reservas '


class CancelaReserva(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    matricula = models.CharField(
        verbose_name='Matrícula', null=True, blank=True, max_length=15
    )
    cancelada = models.BooleanField(verbose_name='Reserva cancelada?', default=False)
    reserva = models.CharField(
        verbose_name='Número da Reserva', null=True, blank=True, max_length=15
    )
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )
    descricao = models.CharField(
        verbose_name='Descrição', null=True, blank=True, max_length=500
    )

    def __str__(self):
        return str(self.cancelada)

    @property
    def descricao_(self):
        return f'{self.codigo_retorno} - {self.descricao}'

    class Meta:
        verbose_name = 'Cancelar reserva'
        verbose_name_plural = 'Cancelar reservas '


class RealizaSimulacao(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    matricula = models.CharField(
        verbose_name='Matrícula', null=True, blank=True, max_length=15
    )
    convenio = models.IntegerField(
        verbose_name='Código do convênio', null=True, blank=True
    )
    taxa = models.DecimalField(
        verbose_name='Taxa', decimal_places=7, max_digits=12, null=True, blank=True
    )
    cet_am = models.DecimalField(
        verbose_name='Taxa CET a.m',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    cet_aa = models.DecimalField(
        verbose_name='Taxa CET a.a',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_iof = models.DecimalField(
        verbose_name='Valor IOF', decimal_places=7, max_digits=12, null=True, blank=True
    )
    valor_disponivel_saque = models.DecimalField(
        verbose_name='Valor disponível para saque',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_parcela = models.DecimalField(
        verbose_name='Valor da parcela',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    valor_saque = models.DecimalField(
        verbose_name='Valor do saque',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    valor_financiado = models.DecimalField(
        verbose_name='Valor Financiado',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    limite_pre_aprovado = models.DecimalField(
        verbose_name='Valor do limite pré-aprovado',
        decimal_places=2,
        max_digits=20,
        null=True,
        blank=True,
    )
    saque = models.BooleanField(verbose_name='Possui saque?', default=True)
    seguro = models.BooleanField(verbose_name='Possui seguro?', default=True)
    taxa_seguro = models.DecimalField(
        verbose_name='Taxa do seguro prestamista',
        decimal_places=7,
        max_digits=12,
        null=True,
        blank=True,
    )
    reservado = models.BooleanField(verbose_name='Reservado?', default=False)
    averbado = models.BooleanField(verbose_name='Averbado?', default=False)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    @property
    def taxa_(self):
        return float(self.taxa * 100)

    @property
    def valor_parcela_brl(self):
        valor_parcela = locale.currency(self.valor_parcela)
        return valor_parcela

    @property
    def valor_disponivel_saque_brl(self):
        valor_disponivel_saque = locale.currency(self.valor_disponivel_saque)
        return valor_disponivel_saque

    @property
    def limite_pre_aprovado_brl(self):
        limite_pre_aprovado = locale.currency(self.limite_pre_aprovado)
        return limite_pre_aprovado

    class Meta:
        verbose_name = 'Realizar simulaçao'
        verbose_name_plural = 'Realiza simulações'


class Averbacao(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    matricula = models.CharField(
        verbose_name='Matrícula', null=True, blank=True, max_length=15
    )
    folha = models.CharField(verbose_name='Folha', null=True, blank=True, max_length=10)
    verba = models.CharField(verbose_name='Verba', null=True, blank=True, max_length=15)
    cancelada = models.BooleanField(verbose_name='Reserva cancelada?', default=False)
    valor = models.DecimalField(
        verbose_name='Valor', decimal_places=7, max_digits=12, null=True, blank=True
    )
    contrato = models.CharField(
        verbose_name='Número do Contrato', null=True, blank=True, max_length=15
    )
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )
    descricao = models.CharField(
        verbose_name='Descrição', null=True, blank=True, max_length=500
    )

    def __str__(self):
        return str(self.contrato)

    class Meta:
        verbose_name = 'Averbação'
        verbose_name_plural = 'Averbação'


class ConsultaBureau(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )

    def __str__(self):
        return str(self.log_api.cliente.nome_cliente)

    class Meta:
        verbose_name = 'Consulta Bureau - DXON'
        verbose_name_plural = 'Consulta Bureau - DXON'


class RetornosDock(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    id_cliente = models.CharField(
        verbose_name='Id cliente - Dock', null=True, blank=True, max_length=15
    )
    nome_chamada = models.CharField(
        verbose_name='Nome da chamada', null=True, blank=True, max_length=50
    )
    payload_envio = models.TextField(
        verbose_name='Payload de envio', null=True, blank=True
    )
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    codigo_retorno = models.CharField(
        verbose_name='Código de retorno', null=True, blank=True, max_length=15
    )

    def __str__(self):
        return str(self.log_api.cliente.nome_cliente)

    class Meta:
        verbose_name = 'Resposta - Dock'
        verbose_name_plural = 'Respostas - Dock'


class RetornoCallbackUnico(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    nome = models.TextField(verbose_name='nome do retorno', null=True, blank=True)
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return str(self.nome)

    class Meta:
        verbose_name = 'Callback Unico'
        verbose_name_plural = 'Callback - Unico'


class TemSaudeAdesao(models.Model):
    log_api = models.ForeignKey(
        LogCliente, verbose_name='Log_Cliente', on_delete=models.CASCADE
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    nome = models.CharField(
        verbose_name='Nome do Cliente', null=True, blank=True, max_length=50
    )
    tipo_servico = models.CharField(
        verbose_name='Tipo de Servico', null=True, blank=True, max_length=50
    )
    payload = models.TextField(
        verbose_name='Payload de Resposta', null=True, blank=True
    )
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return str(self.nome)

    class Meta:
        verbose_name = 'Tem Saude'
        verbose_name_plural = 'Tem Saude'


class Banksoft(models.Model):
    log_api = models.ForeignKey(
        LogCliente,
        verbose_name='Log_Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    contrato = models.CharField(
        verbose_name='Contrato', null=True, blank=True, max_length=50
    )
    tipo_chamada = models.CharField(
        verbose_name='Tipo chamada', null=True, blank=True, max_length=50
    )
    payload_enviado = models.TextField(
        verbose_name='Payload enviado', null=True, blank=True, default=None
    )
    payload = models.TextField(
        verbose_name='Payload de resposta', null=True, blank=True
    )
    criado_em = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)

    def __str__(self):
        return str(self.cliente)

    class Meta:
        verbose_name = 'Log - Banksoft'
        verbose_name_plural = 'Logs - Banksoft'


class QitechRetornos(models.Model):
    log_api = models.ForeignKey(
        LogCliente,
        verbose_name='Log_Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em', auto_now_add=True, null=True, blank=True
    )
    tipo = models.CharField(
        verbose_name='Tipo de chamada', null=True, blank=True, max_length=50
    )
    retorno = models.JSONField(verbose_name='Retorno', null=True, blank=True)

    def __str__(self):
        return str(self.cliente)

    class Meta:
        verbose_name = 'Log - Retorno qitech'
        verbose_name_plural = 'Logs - Retornos qitech'


class LogWebhook(models.Model):
    chamada_webhook = models.CharField(
        verbose_name='Tipo da Chamada', null=True, blank=True, max_length=300
    )
    log_webhook = models.TextField(
        verbose_name='Payload de resposta', null=True, blank=True
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em', auto_now_add=True, null=True, blank=True
    )

    def __str__(self):
        return self.chamada_webhook

    class Meta:
        verbose_name = 'Log - Webhook'
        verbose_name_plural = 'Log - Webhook'


class LogIn100(models.Model):
    log_api = models.ForeignKey(
        LogCliente,
        verbose_name='Log_Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payload_envio = models.TextField(
        verbose_name='Payload de envio', null=True, blank=True
    )
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    tipo_chamada = models.CharField(
        verbose_name='Tipo Chamada', null=True, blank=True, max_length=255
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em', auto_now_add=True, null=True, blank=True
    )

    def __str__(self):
        return f'{self.log_api.pk}'

    class Meta:
        verbose_name = 'Log - In100'
        verbose_name_plural = 'Log - In100'


class LogAtualizacaoCadastral(models.Model):
    log_api = models.ForeignKey(
        LogCliente,
        verbose_name='Log Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payload_envio = models.TextField(
        verbose_name='Payload de envio', null=True, blank=True
    )
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    tipo_chamada = models.CharField(
        verbose_name='Tipo Chamada', null=True, blank=True, max_length=255
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em', auto_now_add=True, null=True, blank=True
    )

    def __str__(self):
        return f'{self.log_api.pk}'

    class Meta:
        verbose_name = 'Atualização Cadastral'
        verbose_name_plural = 'Atualização Cadastral'


class LogEnvioDossie(models.Model):
    log_api = models.ForeignKey(
        LogCliente,
        verbose_name='Log Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payload_envio = models.TextField(
        verbose_name='Payload de envio', null=True, blank=True
    )
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    tipo_chamada = models.CharField(
        verbose_name='Tipo Chamada', null=True, blank=True, max_length=255
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em', auto_now_add=True, null=True, blank=True
    )

    def __str__(self):
        return f'{self.log_api.pk}'

    class Meta:
        verbose_name = 'Envio Dossie'
        verbose_name_plural = 'Envio Dossie'


class LogTransferenciaSaque(models.Model):
    log_api = models.ForeignKey(
        LogCliente,
        verbose_name='Log Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    payload_envio = models.TextField(
        verbose_name='Payload de envio', null=True, blank=True
    )
    payload = models.TextField(verbose_name='Payload de retorno', null=True, blank=True)
    tipo_chamada = models.CharField(
        verbose_name='Tipo Chamada', null=True, blank=True, max_length=255
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em', auto_now_add=True, null=True, blank=True
    )

    def __str__(self):
        return f'{self.log_api.pk}'

    class Meta:
        verbose_name = 'Transferência Saque'
        verbose_name_plural = 'Transferência Saque'


class StatusCobrancaDock(models.Model):
    cliente = models.ForeignKey(
        cliente.Cliente,
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    status_cobranca = models.CharField(
        max_length=25, verbose_name='Status Cobrança', null=True, blank=True
    )

    class Meta:
        verbose_name = 'Status Cobrança'
        verbose_name_plural = 'Status Cobrança'
