from django.db import models


class INSSBeneficioTipo(models.Model):
    cdInssBeneficioTipo = models.IntegerField(
        verbose_name='Código do tipo do benefício no INSS', null=True
    )
    dsINSSBeneficioTipo = models.CharField(
        verbose_name='Descrição do tipo do beneficio', max_length=300, null=True
    )
    inssBeneficioTipo = models.TextField(
        verbose_name='Descrição do tipo do beneficio do INSS', max_length=300, null=True
    )
    dsINSSBeneficioTipoIngles = models.CharField(
        verbose_name='Nome do tipo do beneficio em ingles, utilizado pela financeira qi tech',
        max_length=200,
        null=True,
    )
    flConsignavel = models.BooleanField(
        verbose_name='Indica se o beneficio é consignável', null=True
    )
    flAtivo = models.BooleanField(
        verbose_name='Indica se o benefício está ativo', null=True
    )

    def __str__(self):
        return self.cdInssBeneficioTipo or ''

    @property
    def nome_(self):
        return f'{self.cdInssBeneficioTipo}'

    class Meta:
        verbose_name = '3. INSS Beneficio'
        verbose_name_plural = '3. INSS Beneficios'
