from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.choices import CARGO, TIPOS_ATUACAO, TIPOS_REGIAO, UFS
from custom_auth.models import UserProfile


class RepresentanteComercial(models.Model):
    nome = models.CharField(
        verbose_name='Nome Completo', max_length=200, null=True, blank=False
    )
    nu_cpf_cnpj = models.CharField(
        verbose_name='Número de CPF/CNPJ',
        max_length=14,
        unique=True,
        null=True,
        blank=False,
    )
    telefone_validator = RegexValidator(
        regex=r'^\d{11}$',
        message='Número de telefone inválido. O formato deve ser: 00123456789',
    )
    telefone = models.CharField(
        max_length=11,
        verbose_name='DDD + número com 9 dígitos',
        null=True,
        blank=False,
        validators=[telefone_validator],
    )
    email = models.CharField(
        verbose_name='E-mail Corporativo',
        max_length=200,
        null=True,
        blank=False,
    )
    cargo = models.SmallIntegerField(
        verbose_name='Cargo',
        choices=CARGO,
        null=True,
        blank=False,
    )
    tipo_atuacao = models.SmallIntegerField(
        verbose_name='Tipo de Atuação',
        choices=TIPOS_ATUACAO,
        null=True,
        blank=True,
    )

    def clean(self):
        if self.nu_cpf_cnpj:
            if (
                RepresentanteComercial.objects.filter(nu_cpf_cnpj=self.nu_cpf_cnpj)
                .exclude(pk=self.pk)
                .first()
            ):
                raise ValidationError(
                    'Já existe um representante comercial com esse CPF.'
                )

    @property
    def telefone_ddd(self):
        prefixo, numero = '', ''
        if self.telefone_celular:
            telefone = (
                self.telefone_celular.replace('(', '').replace(')', '').replace('-', '')
            )
            prefixo, numero = telefone.split(' ', 1)

        return prefixo, numero

    def __str__(self):
        return self.nome if self.nome else ''

    class Meta:
        verbose_name = 'Representante Comercial'
        verbose_name_plural = '1. Representantes Comerciais'


@receiver(post_save, sender=RepresentanteComercial)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    identifier = instance.nu_cpf_cnpj.replace('.', '').replace('-', '')

    _, created = UserProfile.objects.get_or_create(
        identifier=identifier,
        defaults={
            'name': instance.nome,
            'email': instance.email,
            'phone': instance.telefone,
            'cpf': instance.nu_cpf_cnpj,
            'representante_comercial': True,
        },
    )

    if not created:
        # O UserProfile já existe, então atualize os detalhes e marque como representante comercial
        UserProfile.objects.filter(identifier=identifier).update(
            name=instance.nome,
            email=instance.email,
            phone=instance.telefone,
            representante_comercial=True,
        )


class Superintendente(models.Model):
    supervisor_direto = models.CharField(
        verbose_name='Supervisor Direto',
        max_length=200,
    )
    representante_comercial = models.ForeignKey(
        RepresentanteComercial,
        verbose_name='Representante Comercial',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )

    def __str__(self):
        if self.representante_comercial_id:
            return self.representante_comercial.nome
        return 'N/A'

    class Meta:
        verbose_name = 'Responsável Direto'
        verbose_name_plural = 'Responsável Direto'


class LocalAtuacao(models.Model):
    representante_comercial = models.ForeignKey(
        RepresentanteComercial,
        verbose_name='Representante Comercial',
        on_delete=models.CASCADE,
        blank=True,
    )
    regiao = models.SmallIntegerField(
        verbose_name='Região', choices=TIPOS_REGIAO, null=True, blank=True
    )
    estado = models.SmallIntegerField(
        verbose_name='Estado', choices=UFS, null=True, blank=True
    )
    municipio = models.CharField(
        verbose_name='Município',
        max_length=200,
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.representante_comercial.nome or ''

    class Meta:
        verbose_name = 'Locais de Atuação'
        verbose_name_plural = 'Locais de Atuação'


class Gerente(models.Model):
    supervisor_direto = models.ForeignKey(
        Superintendente,
        verbose_name='Supervisor Direto',
        on_delete=models.CASCADE,
    )
    representante_comercial = models.ForeignKey(
        RepresentanteComercial,
        verbose_name='Representante Comercial',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )

    def __str__(self):
        return self.representante_comercial.nome or ''

    class Meta:
        verbose_name = 'Responsável Direto'
        verbose_name_plural = 'Responsável Direto'


class Agente(models.Model):
    supervisor_direto = models.ForeignKey(
        Gerente,
        verbose_name='Supervisor Direto',
        on_delete=models.CASCADE,
    )
    representante_comercial = models.ForeignKey(
        RepresentanteComercial,
        verbose_name='Representante Comercial',
        on_delete=models.CASCADE,
        null=False,
        blank=False,
    )

    def __str__(self):
        return self.representante_comercial.nome or ''

    class Meta:
        verbose_name = 'Responsável Direto'
        verbose_name_plural = 'Responsável Direto'
