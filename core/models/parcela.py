from django.db import models

from contract.models.contratos import Contrato


class Parcela(models.Model):
    contrato = models.ForeignKey(
        Contrato, verbose_name='Contrato', on_delete=models.CASCADE
    )
    nuParcela = models.IntegerField(verbose_name='Número da parcela', db_index=True)
    dtVencimento = models.DateField(
        verbose_name='Data de vencimento da parcela', db_index=True
    )
    vrParcela = models.DecimalField(
        verbose_name='Valor da parcela', decimal_places=2, max_digits=12
    )
    recebido_facta = models.BooleanField(
        verbose_name='Recebido parceiro?', default=False
    )
    paga = models.BooleanField(verbose_name='Paga?', default=False)
    dtPagamento = models.DateTimeField(
        verbose_name='Data do pagamento da parcela', null=True, blank=True
    )
    vrPago = models.DecimalField(
        verbose_name='Valor pago da parcela',
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
    )
    vrJuros = models.DecimalField(
        verbose_name='Valor de juros da parcela',
        null=True,
        blank=True,
        decimal_places=2,
        help_text='Se aplicável',
        max_digits=12,
    )
    vrMulta = models.DecimalField(
        verbose_name='Valor multa da parcela',
        null=True,
        blank=True,
        help_text='Se aplicável',
        decimal_places=2,
        max_digits=12,
    )
    cdOrigemBaixa = models.PositiveBigIntegerField(
        verbose_name='Código de origem da baixa', null=True, blank=True
    )

    dtCompra = models.DateField(verbose_name='Data de compra', null=True, blank=True)
    vrParcelaVencimento = models.DecimalField(
        verbose_name='Valor da parcela no vencimento',
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
    )
    vrCompra = models.DecimalField(
        verbose_name='Valor da compra',
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
    )

    vrPrincipalParcela = models.DecimalField(
        verbose_name='Valor principal da parcela',
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
    )
    saldoDevedorParcela = models.DecimalField(
        verbose_name='Saldo devedor da parcela',
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
    )
    txNegociacao = models.DecimalField(
        verbose_name='Taxa da negociação',
        null=True,
        blank=True,
        decimal_places=7,
        max_digits=12,
    )

    vrCessaoFIDC = models.DecimalField(
        verbose_name='Valor da Cessão FIDC',
        null=True,
        blank=True,
        default=None,
        decimal_places=2,
        max_digits=12,
    )

    dtUltimaAtualizacao = models.DateTimeField(
        verbose_name='Atualizado em', null=True, blank=True, default=None
    )
    nuCodParceiro = models.CharField(
        verbose_name='Cód. registrador', null=True, blank=True, max_length=50
    )

    @property
    def txNegociacao_(self):
        return self.txNegociacao or 0

    @property
    def vrPago_(self):
        return self.vrPago or ''

    def __str__(self):
        return str(self.nuParcela)

    class Meta:
        verbose_name = 'Contrato - Parcela'
        verbose_name_plural = 'Contrato - Parcelas'
        ordering = ('nuParcela',)
        indexes = [
            models.Index(fields=['nuParcela']),
            models.Index(fields=['dtVencimento']),
        ]
