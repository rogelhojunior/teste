import uuid

from django.apps import apps
from django.db import models

from contract.constants import EnumTipoProduto


class EnvelopeContratos(models.Model):
    token_envelope = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        null=True,
        blank=True,
    )
    id_processo_unico = models.TextField(
        verbose_name='ID processo - Unico', null=True, blank=True
    )
    id_transacao_confia = models.TextField(
        verbose_name='Transaction id da Confia', null=True, blank=True
    )
    mensagem_confia = models.TextField(
        verbose_name='Mensagem de retorno da confia', null=True, blank=True
    )
    score_unico = models.CharField(
        verbose_name='Score Unico', null=True, blank=True, max_length=5
    )
    status_unico = models.SmallIntegerField(
        verbose_name='Status Unico', null=True, blank=True
    )
    criado_em = models.DateTimeField(
        verbose_name='Criado em',
        auto_now_add=True,
    )
    inicio_digitacao = models.IntegerField(
        verbose_name='Início da digitação', null=True, blank=True
    )
    fim_digitacao = models.IntegerField(
        verbose_name='Fim da digitação', null=True, blank=True
    )
    duracao_digitacao = models.IntegerField(
        verbose_name='Duração da digitação', null=True, blank=True
    )
    erro_unico = models.BooleanField(default=True, verbose_name='Erro Unico?')
    erro_restritivo_unico = models.BooleanField(
        default=False, verbose_name='Erro Restritivo Unico?'
    )

    @property
    def contracts(self):
        Contrato = apps.get_model('contract', 'Contrato')
        return Contrato.objects.filter(token_envelope=self.token_envelope)

    @property
    def is_ccb_generated_for_all_contracts(self) -> bool:
        """
        This method checks if all contracts in this envelope
        have a CCB generated.
        """
        return all(
            contract.is_ccb_generated
            for contract in self.contracts.filter(
                tipo_produto__in=[
                    EnumTipoProduto.PORTABILIDADE,
                    EnumTipoProduto.MARGEM_LIVRE,
                    EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                ]
            )
        )

    @property
    def first_contract(self):
        Contrato = apps.get_model('contract', 'Contrato')
        return (
            Contrato.objects.filter(token_envelope=self.token_envelope)
            .order_by('id')
            .first()
        )

    class Meta:
        verbose_name = 'Envelope'
        verbose_name_plural = '2. Envelopes'

    def is_any_proposal_being_inserted(self) -> bool:
        """
        This method checks if there is any contract in this envelope
        with flag is_proposal_being_inserted, this  means that
        the async function executed in the
        moment to insert the proposal from Qi Tech is still running."""

        return any(
            contract.is_still_inserting_proposal() for contract in self.contracts
        )
