from django.db import models

from contract.choices import TIPOS_STATUS
from contract.models.contratos import Contrato

# from core.models import Cliente


class BeneficiosContratado(models.Model):
    id_conta_dock = models.CharField(
        max_length=50,
        verbose_name='Conta Dock atrelada ao cartão',
        null=True,
        blank=True,
    )
    id_cartao_dock = models.CharField(
        max_length=50,
        verbose_name='Cartão Dock atrelada ao cartão',
        null=True,
        blank=True,
    )
    contrato_emprestimo = models.ForeignKey(
        Contrato,
        on_delete=models.SET_NULL,
        verbose_name='contrato vinculado',
        null=True,
        blank=True,
    )
    plano = models.ForeignKey(
        'cartao_beneficio.Planos',
        verbose_name='Planos',
        on_delete=models.SET_NULL,
        related_name='beneficio_planos_contratados',
        blank=True,
        null=True,
    )
    nome_operadora = models.CharField(
        max_length=50, verbose_name='Nome do Operador', null=True, blank=True
    )
    tipo_plano = models.CharField(
        max_length=50, verbose_name='Tipo do plano', null=True, blank=True
    )
    obrigatorio = models.BooleanField(default=False, verbose_name='Obrigatório')
    identificacao_segurado = models.CharField(
        max_length=50, verbose_name='identificação do segurado', blank=True, null=True
    )
    nome_plano = models.CharField(
        max_length=150, verbose_name='Nome do Plano', blank=True, null=True
    )
    valor_plano = models.CharField(
        verbose_name='Valor do plano', max_length=25, null=True, blank=True
    )
    premio_bruto = models.CharField(
        max_length=50, verbose_name='Prêmio Bruto', blank=True, null=True
    )
    premio_liquido = models.CharField(
        max_length=50, verbose_name='Prêmio Líquido', blank=True, null=True
    )
    validade = models.CharField(
        max_length=50, verbose_name='validade', blank=True, null=True
    )
    renovacao_automatica = models.BooleanField(
        default=False, verbose_name='Renovacao automatica'
    )
    carencia = models.CharField(
        max_length=50, verbose_name='Carencia', null=True, blank=True
    )
    cliente = models.ForeignKey(
        'core.Cliente',
        on_delete=models.CASCADE,
        verbose_name='contrato de empréstimo',
        null=True,
        blank=True,
    )
    status = models.SmallIntegerField(
        verbose_name='Status', choices=TIPOS_STATUS, default=0
    )
    qtd_arrecadacao = models.CharField(
        max_length=50, verbose_name='Quantidade de arrecadação', null=True, blank=True
    )

    def __str__(self) -> str:
        return self.cliente.nome_cliente

    class Meta:
        verbose_name = 'Seguro / Benefício'
        verbose_name_plural = 'Seguro / Benefício'
