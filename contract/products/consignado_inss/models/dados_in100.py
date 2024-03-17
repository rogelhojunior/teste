"""This module implements the class DadosIn100."""

# imports
from datetime import datetime, timedelta

# django imports
from django.db import models

# local imports
from contract.products.consignado_inss.models.especie import EspecieIN100


class DadosIn100(models.Model):
    cliente = models.ForeignKey(
        'core.Cliente',
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        related_name='cliente_in100',
    )
    balance_request_key = models.CharField(
        verbose_name='Key do cliente IN100',
        max_length=50,
        null=True,
        blank=True,
    )
    sucesso_chamada_in100 = models.BooleanField(
        verbose_name='Sucesso chamada IN100',
        null=True,
        blank=True,
        default=None,
        help_text='Mostra se houve sucesso na chamada da in100',
    )
    chamada_sem_sucesso = models.CharField(
        verbose_name='Motivo de erro QITECH',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso a chamada não foi bem sucedida aqui aparece o motivo do erro',
    )
    sucesso_envio_termo_in100 = models.BooleanField(
        verbose_name='Envio do termo IN100',
        null=True,
        blank=True,
        default=None,
        help_text='Mostra se houve sucesso no envio do termo IN100',
    )
    envio_termo_sem_sucesso = models.CharField(
        verbose_name='Motivo envio do termo IN100',
        max_length=300,
        null=True,
        blank=True,
        help_text='Caso o envio do termo IN100 não foi bem sucedida aqui aparece o motivo do erro',
    )
    in100_data_autorizacao = models.DateTimeField(
        verbose_name='Data de autorização da IN100', null=True, blank=True, default=None
    )
    situacao_beneficio = models.CharField(
        verbose_name='Status do Benefício',
        max_length=50,
        null=True,
        blank=True,
    )
    cd_beneficio_tipo = models.IntegerField(
        verbose_name='Código do Tipo de Benefício',
        null=True,
        blank=True,
    )
    uf_beneficio = models.CharField(
        verbose_name='UF do Benefício',
        max_length=2,
        null=True,
        blank=True,
    )
    numero_beneficio = models.CharField(
        verbose_name='Número do benefício', null=True, blank=True, max_length=20
    )
    situacao_pensao = models.CharField(
        verbose_name='Situação da Pensão Alimetícia',
        null=True,
        blank=True,
        max_length=150,
    )
    valor_margem = models.DecimalField(
        verbose_name='Margem livre do credito consignado',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    limite_cartao_consignado = models.DecimalField(
        verbose_name='Limite do cartão consignado',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    margem_livre_cartao_consignado = models.DecimalField(
        verbose_name='Margem livre do cartão_consignado',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    limite_cartao_beneficio = models.DecimalField(
        verbose_name='Limite do cartão benefício',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    margem_livre_cartao_beneficio = models.DecimalField(
        verbose_name='Margem livre do cartão benefício',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    beneficio_ativo = models.CharField(
        verbose_name='Situação do benefício',
        null=True,
        blank=True,
        max_length=150,
    )
    valor_beneficio = models.DecimalField(
        verbose_name='Valor do benefício',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor Calculado',
    )
    valor_liquido = models.DecimalField(
        verbose_name='Valor Líquido do Benefício',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    qt_total_emprestimos = models.IntegerField(
        verbose_name='Quantidade Total de Empréstimos Reservados',
        null=True,
        blank=True,
    )

    qt_total_emprestimos_suspensos = models.IntegerField(
        verbose_name='Quantidade Total de Empréstimos Suspensos',
        null=True,
        blank=True,
    )
    concessao_judicial = models.BooleanField(
        verbose_name='Concessão Judicial',
        null=True,
        blank=True,
    )
    possui_representante_legal = models.BooleanField(
        verbose_name='Possui Representante Legal',
        null=True,
        blank=True,
    )
    possui_procurador = models.BooleanField(
        verbose_name='Possui Procuração',
        null=True,
        blank=True,
    )
    possui_entidade_representante = models.BooleanField(
        verbose_name='Possui Entidade Representante',
        null=True,
        blank=True,
    )
    descricao_recusa = models.TextField(
        verbose_name='Descrição da Recusa', null=True, blank=True
    )
    ultimo_exame_medico = models.DateField(
        verbose_name='Data da última Auditoria realizada pelo INSS',
        null=True,
        blank=True,
    )
    dt_expedicao_beneficio = models.DateField(
        verbose_name='Data de Expedição do Benefício', null=True, blank=True
    )
    retornou_IN100 = models.BooleanField(
        verbose_name='Retornou Dados IN100', null=True, blank=True, default=False
    )
    tipo_retorno = models.CharField(
        verbose_name='Tipo de recebimento do beneficio',
        max_length=150,
        null=True,
        blank=True,
    )
    validacao_in100_saldo_retornado = models.BooleanField(
        verbose_name='IN100 saldo retornado',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a proxima in100 que vai voltar é a do recalculo',
    )
    validacao_in100_recalculo = models.BooleanField(
        verbose_name='IN100 Recalculo',
        default=None,
        null=True,
        blank=True,
        help_text='Indica se a in100 ja retornou na fase do recalculo',
    )
    vr_disponivel_emprestimo = models.DecimalField(
        verbose_name='Valor total disponível para empréstimo',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    data_final_beneficio = models.CharField(
        verbose_name='Data final do benefício',
        max_length=150,
        null=True,
        blank=True,
    )
    data_expiracao_beneficio = models.DateField(
        verbose_name='Data de expiração do benefício',
        max_length=150,
        null=True,
        blank=True,
    )
    data_retorno_in100 = models.CharField(
        verbose_name='Data de retorno da in100',
        max_length=150,
        null=True,
        blank=True,
    )
    margem_total_beneficio = models.DecimalField(
        verbose_name='Margem total do benefício',
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    @property
    def in100_data_autorizacao_(self):
        if self.in100_data_autorizacao:
            today = datetime.now().date()
            end_date = self.in100_data_autorizacao.date() + timedelta(days=30)
            return today <= end_date
        return False

    class Meta:
        verbose_name = 'Dados de retorno da IN100'
        verbose_name_plural = 'Dados de retorno da IN100'

    def does_in100_specie_exists(self) -> bool:
        """Checks if a specie exists."""
        return EspecieIN100.objects.filter(
            numero_especie=self.cd_beneficio_tipo
        ).exists()

    def is_inelegible_or_blocked(self) -> bool:
        """Checks if the record is ineligible or blocked."""
        return self.situacao_beneficio in ['inelegible', 'blocked']
