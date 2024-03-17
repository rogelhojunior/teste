from django.db import models


class ContractDisbursementAccount(models.Model):
    """
    Model for contract disbursement registry
    """

    free_margin = models.OneToOneField(
        'contract.MargemLivre',
        related_name='disbursement_account',
        on_delete=models.PROTECT,
    )

    url = models.URLField(max_length=500, null=True, blank=True)

    # Aqui mesmo
    amount = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=5,
        max_digits=12,
    )

    description = models.TextField(null=True, blank=True)

    transaction_key = models.CharField(max_length=255, null=True, blank=True)

    origin_transaction_key = models.CharField(max_length=255, null=True, blank=True)

    destination_name = models.CharField(max_length=255, null=True, blank=True)
    destination_type = models.CharField(max_length=255, null=True, blank=True)
    destination_branch = models.CharField(max_length=255, null=True, blank=True)
    destination_purpose = models.CharField(max_length=255, null=True, blank=True)
    destination_document = models.CharField(max_length=255, null=True, blank=True)
    destination_bank_ispb = models.CharField(max_length=255, null=True, blank=True)
    destination_branch_digit = models.CharField(max_length=255, null=True, blank=True)
    destination_account_digit = models.CharField(max_length=255, null=True, blank=True)
    destination_account_number = models.CharField(max_length=255, null=True, blank=True)

    payment_date = models.DateTimeField()
