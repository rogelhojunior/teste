from contract.parsers.in100 import In100Benefit
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from handlers.dicionario_beneficios import procura_valor


def update_in100_with_benefit_values(in100: DadosIn100, benefit: In100Benefit) -> None:
    """
    Updates in100 instance with parsed benefit values
    Args:
        in100: DadosIn100 instance
        benefit: In100Benefit object with social security info.

    """
    in100.uf_beneficio = benefit.state
    in100.situacao_beneficio = benefit.benefit_status
    # TODO change procura_valor function to better one
    in100.cd_beneficio_tipo = procura_valor(benefit.benefit_type)
    in100.valor_margem = benefit.margin_value
    in100.valor_beneficio = benefit.value
    in100.valor_liquido = benefit.liquid_value
    in100.situacao_pensao = benefit.alimony_status
    in100.concessao_judicial = benefit.has_judicial_concession
    in100.possui_entidade_representante = benefit.has_entity_representation
    in100.dt_expedicao_beneficio = benefit.concession_date
    in100.possui_procurador = benefit.has_attorney
    in100.vr_disponivel_emprestimo = benefit.available_loan_amount
    in100.data_expiracao_beneficio = benefit.benefit_quota_expiration_date
    in100.retornou_IN100 = True
    if in100.validacao_in100_saldo_retornado:
        in100.validacao_in100_recalculo = in100.validacao_in100_saldo_retornado
    in100.save()
