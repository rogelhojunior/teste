from datetime import datetime

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from contract.products.cartao_beneficio.choices import STATUS_NAME
from contract.products.cartao_beneficio.constants import ContractStatus
from custom_auth.models import UserProfile


class StatusContrato(models.Model):
    created_by = models.ForeignKey(
        UserProfile,
        verbose_name='Criado por',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
    )

    contrato = models.ForeignKey(
        'contract.Contrato', verbose_name='Contrato', on_delete=models.CASCADE
    )

    nome = models.SmallIntegerField(
        verbose_name='Nome do status',
        choices=STATUS_NAME,
        null=True,
        blank=True,
        default=ContractStatus.ANDAMENTO_SIMULACAO.value,
    )

    descricao_inicial = models.CharField(
        verbose_name='Descrição Inicial', max_length=50, blank=True, null=True
    )
    descricao_originacao = models.CharField(
        verbose_name='Descrição Originação', max_length=50, blank=True, null=True
    )
    descricao_mesa = models.CharField(
        verbose_name='Observação', max_length=255, blank=True, null=True
    )
    descricao_front = models.CharField(
        verbose_name='Descrição Front', max_length=255, blank=True, null=True
    )
    original_proposals_status = models.JSONField(
        verbose_name='Status originais das propostas', blank=True, null=True
    )

    data_fase_inicial = models.DateTimeField(
        verbose_name='Data da fase inicial', auto_now_add=True
    )
    data_fase_final = models.DateTimeField(
        verbose_name='Data da fase final', auto_now_add=True
    )

    def __str__(self):
        return str(self.get_nome_display()) or ''

    class Meta:
        verbose_name = 'Status dos contratos'
        verbose_name_plural = 'Status dos contratos'


@receiver(post_save, sender=StatusContrato)
def check_dataprev_status(sender, instance, **kwargs):
    from core.tasks import agendar_consulta, gerar_token_e_buscar_beneficio

    if instance.nome == ContractStatus.ANDAMENTO_CHECAGEM_DATAPREV.value:
        contrato = instance.contrato
        contrato_cartao = contrato.contrato_cartao_beneficio.first()

        current_time = datetime.now().time()
        convenio = contrato_cartao.convenio

        cpf_cliente = contrato.cliente.nu_cpf
        averbadora = convenio.averbadora
        token_contrato = contrato.token_contrato
        if convenio.horario_func_ativo:
            if (
                convenio.horario_func_inicio
                <= current_time
                <= convenio.horario_func_fim
            ):
                gerar_token_e_buscar_beneficio(
                    cpf_cliente, averbadora, token_contrato, convenio.pk
                )
            else:
                agendar_consulta(contrato, convenio)
        else:
            gerar_token_e_buscar_beneficio(
                cpf_cliente, averbadora, token_contrato, convenio.pk
            )


post_save.connect(check_dataprev_status, sender=StatusContrato)
