import logging
import traceback
from datetime import date
from typing import Optional

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from contract.constants import (
    ContractTypeEnum,
    EnumTipoContrato,
    EnumTipoProduto,
    ProductTypeEnum,
)
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.products.portabilidade.views import validar_regra_especie
from contract.services.validators.in100 import is_contract_end_date_valid
from core.models import Cliente
from core.models.parametro_produto import ParametrosProduto
from handlers.validar_regras_beneficio_contrato import ValidadorRegrasBeneficioCliente
from simulacao.communication import qitech
from simulacao.communication.hub import (
    definir_data_primeiro_vencimento,
    get_parametro_sistema,
)
from simulacao.constants import EnumParametroSistema
from simulacao.exceptions.simulate import SimulateFreeMarginContractException
from simulacao.models import ComissaoTaxa, FaixaIdade
from simulacao.models.parametros_contrato import OpcoesContratoParametros
from simulacao.serializers import (
    OpcaoContrato,
    RestricaoOperacao,
    SimularContrato,
    SimulateContractSerializer,
)
from simulacao.utils import (
    calcular_idade_com_mes,
    convert_string_to_date_yyyymmdd,
    data_atual_sem_hora,
)

logger = logging.getLogger('digitacao')


class SimulateFreeMarginContract(APIView):
    serializer_class = SimulateContractSerializer

    def simular_contrato(
        self,
        dt_nascimento: date,
        cd_inss_beneficio_tipo: int,
        vr_margem_livre: float,
        vr_contrato: float,
        vr_parcela: float,
        vr_taxa: float,
        tipo_contrato: ContractTypeEnum,
        tipo_produto: ProductTypeEnum,
    ) -> tuple[Optional[SimularContrato], Optional[str]]:
        taxa_filtro_response = 0
        data_primeiro_vencimento = definir_data_primeiro_vencimento(tipo_produto)
        data_desembolso = None

        try:
            match tipo_contrato:
                case EnumTipoContrato.OPERACAO_NOVA:
                    dias_limite_desembolso = get_parametro_sistema(
                        EnumParametroSistema.DIAS_LIMITE_PARA_DESEMBOLSO, tipo_produto
                    )
                    data_desembolso = convert_string_to_date_yyyymmdd(
                        data_atual_sem_hora()
                    )
                case _:
                    dias_limite_desembolso = 0

            if opcoes_contrato := obter_opcoes_contrato(
                dt_primeiro_vencimento=data_primeiro_vencimento,
                dt_nascimento=dt_nascimento,
                cd_inss_beneficio_tipo=cd_inss_beneficio_tipo,
                vr_margem_livre=vr_margem_livre,
                vr_contrato=vr_contrato,
                vr_parcela=vr_parcela,
                tipo_contrato=tipo_contrato,
                tipo_produto=tipo_produto,
            ):
                prazos = []
                taxas = []
                body = []

                for param in opcoes_contrato:
                    prazos.append(param.prazo)

                    if param.prazo > 0:
                        if vr_taxa == 0 or vr_taxa is None:
                            taxa_opcao_prazo = obter_taxa(param.prazo, tipo_contrato)
                        else:
                            taxa_opcao_prazo = 0 if vr_taxa is None else vr_taxa

                        if taxa_opcao_prazo:
                            taxas.append(taxa_opcao_prazo)
                            taxa_filtro_response = max(
                                taxa_opcao_prazo, taxa_filtro_response
                            )
                            body_opcao_prazo = definir_body_request_simulacao(
                                param.prazo,
                                vr_parcela,
                                data_primeiro_vencimento,
                                taxa_opcao_prazo,
                                dias_limite_desembolso,
                                data_desembolso,
                            )
                            body.append(body_opcao_prazo)
                        else:
                            error_message = (
                                'Não foi possível as taxas para realizar a simulação.'
                            )
                            return None, error_message

                if body:
                    corpo_requisicao = {
                        'complex_operation': True,
                        'operation_batch': body,
                    }

                    integracao_financeira = qitech.QitechApiIntegration()
                    json_retorno, status_code = integracao_financeira.execute(
                        settings.QITECH_BASE_ENDPOINT_URL,
                        settings.QITECH_ENDPOINT_DEBT_SIMULATION,
                        corpo_requisicao,
                        'POST',
                    )

                    if status_code in [
                        status.HTTP_200_OK,
                        status.HTTP_201_CREATED,
                        status.HTTP_202_ACCEPTED,
                    ]:
                        simular_contrato = transpor_dados_financeira(
                            json_retorno=json_retorno,
                            prazos=prazos,
                            vr_parcela=vr_parcela,
                            dt_vencimento_primeira_parcela=data_primeiro_vencimento,
                            opcoes_contrato=opcoes_contrato,
                            taxas=taxas,
                            tipo_produto=tipo_produto,
                        )
                        return simular_contrato, ''

                    else:
                        error_message = f'Falha na comunicação com a financeira. Mensagens: {json_retorno}'
                        return None, error_message
                else:
                    error_message = 'Não foi possível montar o corpo da requisição para comunicação com a financeira.'
                    return None, error_message
            else:
                error_message = 'Não foi possível opções de contrato.'
                return None, error_message
        except Exception as e:
            traceback.print_exc()
            error_message = f'Ocorreu um erro ao realização simulação. ERRO: {e}'
            return None, error_message

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        birth_date: date = validated_data['dt_nascimento']
        benefit_code: int = validated_data['codigo_beneficio']
        contract_type: ContractTypeEnum = validated_data['tipo_contrato']
        contract_value: float = validated_data['valor_contrato']
        free_margin: float = validated_data['margem_livre']
        installment_value: float = validated_data['valor_parcela']
        vr_taxa: float = float(self._get_taxa() / 100)
        cpf_number: str = validated_data['numero_cpf']
        numero_beneficio: str = validated_data['numero_beneficio']

        cliente = Cliente.objects.filter(
            nu_cpf=cpf_number,
        ).first()
        dados_in100 = DadosIn100.objects.filter(
            numero_beneficio=numero_beneficio
        ).first()

        valida_regras_beneficio_cliente(cliente, dados_in100, free_margin)

        try:
            # TODO: Refactor with a service or a controller class
            resultado_simulacao, _ = self.simular_contrato(
                dt_nascimento=birth_date,
                cd_inss_beneficio_tipo=benefit_code,
                vr_margem_livre=free_margin,
                vr_contrato=contract_value,
                vr_parcela=installment_value,
                vr_taxa=vr_taxa,
                tipo_contrato=contract_type,
                tipo_produto=EnumTipoProduto.MARGEM_LIVRE,
            )

        except Exception as e:
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

        if resultado_simulacao:
            resultado_simulacao.lista_taxas = [
                taxa * 100 for taxa in resultado_simulacao.lista_taxas
            ]

            resultado_simulacao.opcoes_contrato = verifica_opcoes_contrato_cliente(
                cliente,
                dados_in100,
                resultado_simulacao.opcoes_contrato,
            )
            return Response(resultado_simulacao.as_dict(), status=status.HTTP_200_OK)
        else:
            raise SimulateFreeMarginContractException

    def _get_taxa(self):
        parametro = ParametrosProduto.objects.filter(
            tipoProduto=EnumTipoProduto.MARGEM_LIVRE
        ).first()
        return parametro.taxa_proposta_margem_livre


def valida_regras_beneficio_cliente(
    cliente: Cliente,
    dados_in100: DadosIn100,
    margem_livre: float,
):
    """
    Verifica se retornou os dados in100 e caso não passe na regra, dá um erro
    :param cliente: Cliente a ser validado
    :param dados_in100: DadosIn100 para buscar os dados necessários.
    :param margem_livre: valor livre para o contrato.
    :return:
    """
    if dados_in100 and dados_in100.retornou_IN100:
        resposta_regra_especie = validar_regra_especie(
            dados_in100.cd_beneficio_tipo, cliente, dados_in100.numero_beneficio
        )
        if not resposta_regra_especie['regra_aprovada']:
            raise ValidationError({
                'Erro': 'Este cliente não passou na validação das regras de espécie.'
            })


def verifica_opcoes_contrato_cliente(
    cliente: Cliente,
    dados_in100: DadosIn100,
    opcoes_contrato: list,
) -> list:
    """
    Verifica se as opções de contrato retornada estão de acordo com as condições do cliente
    :param cliente: Cliente a ser validado
    :param dados_in100: DadosIn100 para buscar os dados necessários.
    :param opcoes_contrato: Lista das opções de contrato
    :return: Opções de contrato atualizada. Traz apenas as opções de contrato que se encaixam nas regras.
    :raise: ValidationError caso o cliente não possua nem uma parcela válida.
    """

    novas_opcoes_contrato = opcoes_contrato
    if dados_in100 and dados_in100.retornou_IN100:
        validador_beneficio_cliente = ValidadorRegrasBeneficioCliente(
            cliente,
            dados_in100,
        )
        novas_opcoes_contrato = []
        for opcao_contrato in opcoes_contrato:
            validador_beneficio_cliente.set_parcelas(opcao_contrato.qt_parcelas)
            resposta_regra_morte = validador_beneficio_cliente.validar_regra_morte()
            is_end_date_valid = is_contract_end_date_valid(
                benefit_end_date=dados_in100.data_expiracao_beneficio,
                months=opcao_contrato.qt_parcelas,
            )
            if resposta_regra_morte['regra_aprovada'] and is_end_date_valid:
                novas_opcoes_contrato.append(opcao_contrato)

            # validate MARGEM LIVRE min contract value
            product_parameters = ParametrosProduto.objects.filter(
                tipoProduto__in=[
                    EnumTipoProduto.MARGEM_LIVRE,
                    EnumTipoProduto.INSS,
                ]
            ).first()
            min_value = product_parameters.valor_minimo_emprestimo
            if opcao_contrato.vr_liberado_cliente < min_value:
                msg = 'Valor minimo para esse tipo de contrato é %0.2f' % min_value
                raise ValidationError({'Erro': msg})

        # verifica quais opções de contrato estão dentro do intervalo
        if not novas_opcoes_contrato:
            # Caso não tenha nem uma opcao de contrato após validar, retorna um erro.
            raise ValidationError({
                'Erro': 'Este cliente não passou na validação das regras benefício por invalidez ou pelo fim do benefício.'
            })

    return novas_opcoes_contrato


def obter_opcoes_contrato(
    dt_primeiro_vencimento: date,
    dt_nascimento: date,
    cd_inss_beneficio_tipo: int,  # noqa: F401
    vr_margem_livre: float,
    vr_contrato: float,  # noqa: F401
    vr_parcela: float,  # noqa: F401
    tipo_contrato: EnumTipoContrato,
    tipo_produto: EnumTipoProduto,
) -> list[OpcoesContratoParametros]:
    try:
        vr_parcela_minima = get_parametro_sistema(
            EnumParametroSistema.VALOR_MINIMO_PARCELA, tipo_produto
        )

        idade = calcular_idade_com_mes(
            dt_nascimento, convert_string_to_date_yyyymmdd(data_atual_sem_hora())
        )

        product_params: ParametrosProduto = ParametrosProduto.objects.get(
            tipoProduto=tipo_produto
        )
        # contrato_tipo_taxa = ContratoTipoTaxa.objects.filter(cd_contrato_tipo=tipo_contrato).first()
        try:
            age_range: FaixaIdade = FaixaIdade.objects.get(
                nu_idade_minima__lte=idade, nu_idade_maxima__gte=idade
            )
        except FaixaIdade.DoesNotExist as e:
            raise ValidationError({
                'Erro': 'O cliente não de encaixa em nenhuma faixa de idade.',
            }) from e
        # Pega apenas as taxas de comissão com o prazo menor ou igual ao máximo da faixa de idade
        commission_rates: ComissaoTaxa = ComissaoTaxa.objects.filter(
            cd_contrato_tipo=tipo_contrato,
            prazo__lte=age_range.nu_prazo_maximo,
        )
        # Define o Parametro do produto
        commission_rates: ComissaoTaxa = commission_rates.filter(
            prazo__lte=product_params.prazo_maximo,
            prazo__gte=product_params.prazo_minimo,
        )

        contract_options = []
        for commission_rate in commission_rates:
            contract_option = OpcoesContratoParametros(
                vr_parcela_min=vr_parcela_minima,
                vr_parcela_max=vr_margem_livre,
                prazo=commission_rate.prazo,
                tx_juros=commission_rate.tx_efetiva_contrato_max,
                vr_contrato_min=age_range.vr_minimo,
                vr_contrato_max=age_range.vr_maximo,
            )
            contract_options.append(contract_option)

        return contract_options

    except Exception as e:
        traceback.print_exc()
        logger.exception(f'Erro ao listar opções (obter_opcoes_contrato): {e}')
        raise


def obter_taxa(prazo, tipo_contrato):
    try:
        prazo_arredondado = 0
        resto_divisao_prazo = prazo % 12

        if resto_divisao_prazo == 0:
            prazo_arredondado = prazo
        else:
            prazo_arredondado = prazo - resto_divisao_prazo + 12

        if comissao_taxa := (
            ComissaoTaxa.objects.filter(
                Q(cd_contrato_tipo=tipo_contrato)
                | Q(prazo=prazo_arredondado, cd_contrato_tipo=1),
                fl_ativa=True,
                dt_vigencia_inicio__lte=timezone.now().date(),
                dt_vigencia_fim__gte=timezone.now().date(),
            )
            .order_by('-tx_efetiva_contrato_max')
            .first()
        ):
            return comissao_taxa.tx_efetiva_contrato_max
        else:
            return None
    except Exception as e:
        logger.error(f'Erro ao obter taxa (obter_taxa): {e}')
        print(e)
        raise


def definir_body_request_simulacao(
    qt_parcelas,
    vr_parcela,
    data_primeiro_vencimento,
    taxa_opcao_prazo,
    dias_limite_desembolso,
    data_desembolso,
):
    try:
        return {
            'borrower': {'person_type': 'natural'},
            'financial': {
                'first_due_date': data_primeiro_vencimento.strftime('%Y-%m-%d'),
                'number_of_installments': qt_parcelas,
                'installment_face_value': vr_parcela,
                'limit_days_to_disburse': dias_limite_desembolso,
                'interest_type': 'pre_price_days',
                'fine_configuration': {
                    'monthly_rate': 0,
                    'interest_base': 'calendar_days',
                    'contract_fine_rate': 0,
                },
                'credit_operation_type': 'ccb',
                'interest_grace_period': 0,
                'principal_grace_period': 0,
                'monthly_interest_rate': taxa_opcao_prazo,
                'disbursement_date': data_desembolso.strftime('%Y-%m-%d'),
            },
            'collaterals': [{'collateral_type': 'social_security'}],
        }
    except Exception:
        return None


def transpor_dados_financeira(
    json_retorno,
    prazos,
    vr_parcela,
    dt_vencimento_primeira_parcela,
    opcoes_contrato,
    taxas,
    tipo_produto,
):
    try:
        simular_contrato = SimularContrato()
        restricao_operacao = RestricaoOperacao()
        restricao_operacao.vr_op_min = get_parametro_sistema(
            EnumParametroSistema.VALOR_LIBERADO_CLIENTE_OPERACAO_MIN, tipo_produto
        )
        restricao_operacao.vr_op_max = get_parametro_sistema(
            EnumParametroSistema.VALOR_LIBERADO_CLIENTE_OPERACAO_MAX, tipo_produto
        )

        data_list = list(json_retorno['data'])
        data = data_list[0]['data']
        data_filtro_prazo = list(
            filter(
                lambda p: (prazos.__contains__(data['number_of_installments'])),
                data_list,
            )
        )
        for sf in data_filtro_prazo:
            opcao_contrato = OpcaoContrato()
            opcao_contrato.qt_parcelas = int(sf['data']['number_of_installments'])
            opcao_contrato.tx_efetiva_mes = sf['data']['prefixed_interest_rate'][
                'monthly_rate'
            ]
            opcao_contrato.tx_efetiva_ano = sf['data']['prefixed_interest_rate'][
                'annual_rate'
            ]
            if disbursement_options := list(sf['data']['disbursement_options']):
                opcao_contrato.tx_cet_mes = disbursement_options[0]['cet']
                opcao_contrato.tx_cet_ano = disbursement_options[0]['annual_cet']
                opcao_contrato.dt_desembolso = disbursement_options[0][
                    'disbursement_date'
                ]
                opcao_contrato.vr_contrato = disbursement_options[0]['issue_amount']
                opcao_contrato.vr_liberado_cliente = disbursement_options[0][
                    'disbursed_issue_amount'
                ]
                opcao_contrato.vr_iof = disbursement_options[0]['iof_amount']
                opcao_contrato.dt_liberado_cliente = disbursement_options[0][
                    'disbursement_date'
                ]
            opcao_contrato.vr_parcela_calculada = vr_parcela
            opcao_contrato.dt_vencimento_primeira_parcela = (
                dt_vencimento_primeira_parcela
            )
            opcao_contrato.dt_vencimento_ultima_parcela = (
                opcao_contrato.dt_vencimento_primeira_parcela
                + relativedelta(months=int(sf['data']['number_of_installments']) - 1)
            )
            opcao_contrato.vr_tarifa_cadastro = 0
            opcao_contrato.fl_seguro = False
            opcao_contrato.vr_seguro = 0
            opcao_contrato.vr_iof_adicional = 0
            if opcoes_contrato:
                if opcao_contrato_por_prazo := list(
                    filter(
                        lambda p: p.prazo == int(sf['data']['number_of_installments']),
                        opcoes_contrato,
                    )
                ):
                    opcao_contrato.vr_contrato_max = opcao_contrato_por_prazo[
                        0
                    ].vr_contrato_max
                    opcao_contrato.vr_contrato_min = opcao_contrato_por_prazo[
                        0
                    ].vr_contrato_min
                    opcao_contrato.vr_parcela_max = opcao_contrato_por_prazo[
                        0
                    ].vr_parcela_max
                    opcao_contrato.vr_parcela_min = opcao_contrato_por_prazo[
                        0
                    ].vr_parcela_min

                    opcao_contrato.valor_simulacao_dentro_faixa_idade = (
                        opcao_contrato.vr_contrato <= opcao_contrato.vr_contrato_max
                    )
            simular_contrato.opcoes_contrato.append(opcao_contrato)

        simular_contrato.restricao_operacao = restricao_operacao
        simular_contrato.lista_taxas = list(set(taxas))

        return simular_contrato
    except Exception as e:
        print(e)
        logger.error(
            f'Erro ao transpor dados financeira (transpor_dados_financeira): {e}'
        )
        raise
