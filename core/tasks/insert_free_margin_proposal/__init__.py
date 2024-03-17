"""Implements insert_free_margin_proposal task."""

from contract.constants import EnumContratoStatus
from contract.models.contratos import Contrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.utils import atualizar_status_contratos
from core.models.parametro_produto import ParametrosProduto
from core.tasks import insere_proposta_margem_livre_financeira_hub


def insert_free_margin_proposal(contract: Contrato) -> None:
    in100 = DadosIn100.objects.filter(
        numero_beneficio=contract.numero_beneficio
    ).first()
    if in100.retornou_IN100:
        parametros_produto = ParametrosProduto.objects.filter(
            tipoProduto=contract.tipo_produto
        ).first()
        insere_proposta_margem_livre_financeira_hub(
            contract,
            float(contract.taxa_efetiva_mes) / 100,
            'calendar_days',
            float(parametros_produto.multa_contrato_margem_livre) / 100,
        )
    else:
        atualizar_status_contratos(
            contract,
            EnumContratoStatus.DIGITACAO,
            ContractStatus.AGUARDANDO_RETORNO_IN100.value,
            '-',
            user=None,
        )
