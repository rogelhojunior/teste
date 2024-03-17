import logging
from datetime import date, datetime, timedelta

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from api_log.constants import EnumStatusCCB
from api_log.models import LogCliente, QitechRetornos
from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.contratos import Contrato, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.portabilidade.utils import calcular_diferenca_datas
from contract.products.portabilidade_refin.calcs import (
    calc_free_margin,
    calc_percentage_interest,
    calc_refin_change,
)
from contract.products.portabilidade_refin.handlers import (
    CancelRefinancing,
    PortRefinSimulationValidation,
)
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from core.models.bancos_brasileiros import BancosBrasileiros
from core.models.cliente import DadosBancarios
from custom_auth.models import UserProfile
from handlers.qitech import QiTech
from handlers.webhook_qitech import validar_in100_recalculo
from simulacao.utils import convert_string_to_date_yyyymmdd, data_atual_sem_hora

logger = logging.getLogger('digitacao')


class PortRefinViewSet(viewsets.ViewSet):
    @action(methods=['POST'], detail=False, url_path='simulacao')
    def simulation(self, request):
        """
        Calculates the simulation for a refinancing operation.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: The HTTP response object containing the simulation results.
        """

        cpf = request.data.get('cpf')
        due_amount = request.data.get('due_amount')
        original_installment_amount = request.data.get('original_installment_amount')
        due_installments_quantity = request.data.get('due_installments_quantity')
        refin_installment_amount = request.data.get('refin_installment_amount')
        refin_installments_quantity = request.data.get('refin_installments_quantity')
        refin_interest = request.data.get('refin_interest')

        port_refin_validations = PortRefinSimulationValidation(cpf=cpf)
        port_refin_validations.pre_simulation(
            refin_installment_amount=refin_installment_amount,
            original_installment_amount=original_installment_amount,
            refin_installments_quantity=refin_installments_quantity,
            due_amount=due_amount,
        )

        percentage_interest = calc_percentage_interest(interest=refin_interest)

        qi_tech = QiTech()

        response = qi_tech.simulation_port_refin(
            original_installment_amount=original_installment_amount,
            due_installments_quantity=due_installments_quantity,
            monthly_interest=percentage_interest,
            refin_installment_amount=refin_installment_amount,
            refin_installments_quantity=refin_installments_quantity,
            due_amount=due_amount,
        )

        decoded_response_body = qi_tech.decode_body(response_json=response.json())

        if response.status_code != 201:
            return Response(
                {'Erro': decoded_response_body.get('translation', '')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refin_data_list = decoded_response_body.get(
            'refinancing_credit_operation', {}
        ).get('disbursement_options', [])

        if not refin_data_list:
            return Response(
                {'Erro': 'Sem dados de refinanciamento.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refin_data = refin_data_list[0]
        annual_cet = refin_data.get('annual_cet')
        portability_monthly_interest_rate = (
            decoded_response_body['portability_credit_operation'][
                'disbursement_options'
            ][0]['prefixed_interest_rate']['monthly_rate']
            * 100
        )

        refin_total_amount = refin_data.get('disbursed_issue_amount')

        refin_change = calc_refin_change(
            due_amount=due_amount,
            refin_total_amount=refin_total_amount,
        )

        free_margin = calc_free_margin(
            original_installment_amount=original_installment_amount,
            refin_installment_amount=refin_installment_amount,
        )

        response_data = {
            'refin_total_amount': refin_total_amount,
            'refin_change': refin_change,
            'free_margin': free_margin,
            'annual_cet': annual_cet,
        }

        if error_pos_simulation := port_refin_validations.post_simulation(
            refin_change=refin_change,
            refin_installments_quantity=refin_installments_quantity,
            refin_total_amount=refin_total_amount,
            portability_monthly_interest_rate=portability_monthly_interest_rate,
        ):
            response_data['Erro'] = error_pos_simulation

        return Response(data=response_data, status=status.HTTP_200_OK)

    @action(methods=['POST'], detail=False, url_path='aprovar')
    def approve_contract(self, request):
        """
        Approves a contract for portability and refinancing.

        Args:
            request (Request): The HTTP request object.

        Returns:
            Response: The HTTP response object.
        """

        contract, _ = self._validate_approve_refuse_request(request=request)

        validar_in100_recalculo(contrato=contract)

        logger.info(
            f'Corban({request.user.email}) - Contrato({contract.id}): Aprovação manual de portabilidade + refinanciamento.'
        )

        return Response(
            data={
                'detail': 'Contrato de Portabilidade + Refinanciamento aprovado com sucesso.'
            },
            status=status.HTTP_200_OK,
        )

    @action(methods=['POST'], detail=False, url_path='cancelar')
    def cancel_contract(self, request):
        """
        Cancels a contract.

        Args:
            self: The contract instance.
            request: The HTTP request object.

        Returns:
            A Response object with the result of the contract cancellation.
        """

        contract, portability = self._validate_approve_refuse_request(request=request)

        portability.status_ccb = EnumStatusCCB.CANCELED.value
        portability.status = ContractStatus.REPROVADO.value
        portability.save()

        contract.status = EnumContratoStatus.CANCELADO
        contract.save()

        # TODO: Ver se deve ser feito o cancelamento da proposta, já que a portabilidade já foi averbada, então não pode ser cancelada
        RefuseProposalFinancialPortability(contrato=contract).execute()

        refuse_reason = 'Recusa manual de portabilidade + refinanciamento.'

        logger.info(
            f'Corban({request.user.email}) - Contrato({contract.id}): {refuse_reason}'
        )

        user = UserProfile.objects.get(identifier=request.user.identifier)
        StatusContrato.objects.create(
            contrato=contract,
            nome=ContractStatus.REPROVADO.value,
            descricao_mesa=refuse_reason,
            created_by=user,
        )

        CancelRefinancing(
            refinancing=Refinanciamento.objects.get(contrato=contract),
            reason=refuse_reason,
        ).execute()

        return Response(
            data={
                'detail': 'Contrato de Portabilidade + Refinanciamento recusado com sucesso.'
            },
            status=status.HTTP_200_OK,
        )

    @action(methods=['POST'], detail=False, url_path='reapresentar-pagamento')
    def payment_resubmission(self, request):
        """
        Resubmits a payment request.

        Parameters:
            request (HttpRequest): The HTTP request object.

        Returns:
            HttpResponse: The response object.

        Raises:
            Exception: If an error occurs during the resubmission process.
        """

        contract = self._get_contract(contract_token=request.data.get('token_contrato'))
        user = request.user
        try:
            refinancing = self._get_refinancing(contract=contract)
            bank_account = self._get_bank_account(
                contract=contract,
                bank_account_id=request.data.get('id_pending_account'),
            )
            bank = self._get_bank(bank_account=bank_account)
            response = self._request_payment_resubmission(
                refinancing=refinancing,
                contract=contract,
                bank_account=bank_account,
                bank=bank,
            )

            return self._process_response(
                contract=contract, response=response, user=user
            )

        except Exception as e:
            return self._get_response_error(contract=contract, error=e)

    def _get_contract(self, contract_token):
        """
        Retrieves a contract object based on the provided contract token.

        Parameters:
            contract_token (str): The token of the contract to retrieve.

        Returns:
            Contrato: The contract object corresponding to the provided token.

        Raises:
            ValidationError: If no contract is found with the provided token.
        """

        if contract := Contrato.objects.filter(token_contrato=contract_token).first():
            return contract
        else:
            raise ValidationError({'Erro': 'Contrato não encontrado.'})

    def _get_refinancing(self, contract):
        """
        Retrieves the refinancing information for a given contract.

        :param contract: The contract object.
        :type contract: Contract

        :return: The refinancing object.
        :rtype: Refinancing

        :raises ValidationError: If the refinancing is not found or if it is not yet averbado.
        """

        refinancing = contract.contrato_refinanciamento.filter(
            status=ContractStatus.PENDENTE_CORRECAO_DADOS_BANCARIOS.value
        ).first()

        if not refinancing or not refinancing.dt_averbacao:
            raise ValidationError({
                'Erro': 'Não foi possível realizar a reapresentação do pagamento pois ele ainda não foi averbado.'
            })
        self._validate_date_limit(
            endorsement_date=refinancing.dt_averbacao, refinancing=refinancing
        )

        return refinancing

    def _validate_date_limit(self, endorsement_date, refinancing):
        """
        Validates the date limit for a given endorsement date and refinancing.
        Parameters:
            endorsement_date (datetime): The endorsement date to be validated.
            refinancing (Refinancing): The refinancing object to be validated.
        Raises:
            ValidationError: If the date limit is exceeded.
        """

        anos, _, _ = calcular_diferenca_datas(
            data_inicial=endorsement_date, data_final=date.today()
        )

        if anos >= 1:
            reason = 'Não foi possível realizar a reapresentação do pagamento pois ja se passaram os 1 ano de reapresentação.'
            CancelRefinancing(refinancing=refinancing, reason=reason).execute()
            raise ValidationError({'Erro': reason})

    def _get_bank_account(self, contract, bank_account_id):
        """
        Get a bank account from the given contract and bank account ID.

        Args:
            contract (Contract): The contract object.
            bank_account_id (int): The ID of the bank account.

        Returns:
            BankAccount: The bank account object.

        Raises:
            ValidationError: If the bank account is not found.
        """

        if bank_account := DadosBancarios.objects.filter(
            cliente=contract.cliente, id=bank_account_id
        ).first():
            return bank_account
        else:
            raise ValidationError({
                'Erro': 'Não foi possível realizar a reapresentação do pagamento pois os dados bancários do cliente não foram encontrados.'
            })

    def _get_bank(self, bank_account):
        """
        Retrieves the bank information based on the given bank account.

        Parameters:
            bank_account (BankAccount): The bank account for which to retrieve the bank information.

        Returns:
            BancosBrasileiros: The bank information associated with the bank account.

        Raises:
            ValidationError: If the bank information for the given bank account is not found.
        """

        if bank := BancosBrasileiros.objects.filter(
            codigo=bank_account.conta_banco
        ).first():
            return bank
        else:
            raise ValidationError({
                'Erro': 'Não foi possível realizar a reapresentação do pagamento pois Banco do cliente não encontrado.'
            })

    def _request_payment_resubmission(self, refinancing, contract, bank_account, bank):
        """
        Request payment resubmission.

        :param refinancing: The refinancing object.
        :type refinancing: Refinancing

        :param contract: The contract object.
        :type contract: Contract

        :param bank_account: The bank account.
        :type bank_account: str

        :param bank: The bank.
        :type bank: str

        :return: The response from the payment resubmission request.
        :rtype: dict
        """

        disbursement_date: date = convert_string_to_date_yyyymmdd(
            date_string=data_atual_sem_hora()
        )
        if timezone.localtime().hour < 17:
            new_disbursement_date = disbursement_date.isoformat()
        else:
            new_disbursement_date = self._adicionar_dia_na_data(
                date_str=str(disbursement_date)
            )

        refinancing.dt_desembolso = new_disbursement_date
        refinancing.save()

        qi_tech = QiTech()

        return qi_tech.payment_resubmission(
            proposal_key=refinancing.chave_proposta,
            disbursement_date=new_disbursement_date,
            bank_account=bank_account,
            bank=bank,
            cpf=contract.cliente.nu_cpf_,
            customer_name=contract.cliente.nome_cliente,
            product_type=contract.tipo_produto,
        )

    def _process_response(self, contract, response, user):
        """
        Process the response from the API.

        Args:
            contract (str): The contract associated with the response.
            response (Response): The response object from the API.

        Returns:
            Response: The response object containing the processed data.
        """

        qi_tech = QiTech()

        log_type = 'REAPRESENTAÇAO'
        response_json = qi_tech.decode_body(response_json=response.json())

        if response.status_code in {200, 201, 202}:
            success = True
            return_data = {'msg': 'Reapresentação do pagamento realizada.'}
            return_status = status.HTTP_200_OK
            refin = self._get_refinancing(contract=contract)
            refin.status = ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value
            refin.sucesso_reapresentacao_pagamento = True
            refin.save()
            StatusContrato.objects.create(
                contrato=contract,
                nome=ContractStatus.AGUARDANDO_DESEMBOLSO_REFIN.value,
                descricao_mesa='Reapresentada, AGUARDANDO DESEMBOLSO (REFIN)',
                created_by=user,
            )

        else:
            from contract.constants import QI_TECH_ENDPOINTS
            from contract.api.views.get_qi_tech_data import execute_qi_tech_get

            success = False
            return_data = {
                'Erro': 'Não foi possível realizar a reapresentação do pagamento. Contate o Suporte.'
            }
            return_status = status.HTTP_400_BAD_REQUEST
            refin = self._get_refinancing(contract=contract)
            message = response_json['description']
            endpoint = QI_TECH_ENDPOINTS['credit_transfer'] + refin.chave_proposta
            consulta = execute_qi_tech_get(endpoint).data
            if 'refinancing_credit_operation' in consulta:
                message = (
                    message
                    + 'status_qitech'
                    + consulta['refinancing_credit_operation'][
                        'credit_operation_status'
                    ]
                )
                if (
                    consulta['refinancing_credit_operation']['credit_operation_status']
                    == 'opened'
                ):
                    refin.status = ContractStatus.INT_FINALIZADO_DO_REFIN.value
                    refin.save()
                    StatusContrato.objects.create(
                        contrato=contract,
                        nome=ContractStatus.INT_FINALIZADO_DO_REFIN.value,
                        descricao_mesa='REFIN ja foi finalizado',
                        created_by=user,
                    )

            refin.sucesso_reapresentacao_pagamento = False
            refin.motivo_reapresentacao_pagamento = message
            refin.save()

        self._register_log(
            contract=contract,
            response_json=response_json,
            log_type=log_type,
            success=success,
        )

        return Response(data=return_data, status=return_status)

    def _register_log(self, contract, response_json, log_type, success=True):
        """
        Registers a log entry for a given contract, response JSON, log type, and success status.

        Parameters:
            contract (Contract): The contract object.
            response_json (dict): The JSON response received.
            log_type (str): The type of log entry.
            success (bool, optional): Indicates if the operation was successful. Defaults to True.

        Returns:
            None
        """

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contract.cliente)

        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contract.cliente,
            retorno=response_json,
            tipo=log_type,
        )

        if success:
            logger.info(
                f'{contract.cliente.id_unico} - Contrato({contract.pk}) (Portabilidade + Refinanciamento) Reapresentado com sucesso.\n Payload {response_json}'
            )

        else:
            logger.error(
                f'{contract.cliente.id_unico} - Contrato({contract.pk}) (Portabilidade + Refinanciamento) Erro na reapresentação do Pagamento.\n Payload {response_json}'
            )

    def _get_response_error(self, contract, error):
        """
        Generates the response error for a given contract and error.

        Args:
            contract (Contract): The contract object.
            error (Exception): The error object.

        Returns:
            Response: The response object with the error message.
        """

        if isinstance(error, ValidationError):
            raise error

        msg = 'Não foi possível realizar a reapresentação do pagamento, contacte o Suporte.'

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=contract.cliente)

        QitechRetornos.objects.create(
            log_api_id=log_api_id.pk,
            cliente=contract.cliente,
            retorno=str(error),
            tipo='REAPRESENTAÇAO',
        )

        logger.error(
            f'{contract.cliente.id_unico} - Contrato({contract.pk}):'
            f' (Portabilidade + Refinanciamento) Erro ao realizar o cancelamento da proposta na QiTech.\n Payload {error}'
        )

        return Response({'Erro': msg}, status=status.HTTP_400_BAD_REQUEST)

    def _adicionar_dia_na_data(self, date_str, format_str='%Y-%m-%d'):
        """
        Parses a date string and adds one day to it.

        Parameters:
            date_str (str): The input date string to be parsed.
            format_str (str): The format string specifying the format of the date_str. Defaults to '%Y-%m-%d'.

        Returns:
            str: The modified date string with one day added.

        """

        date_obj = datetime.strptime(date_str, format_str)

        # Adicionando um dia
        nova_data = date_obj + timedelta(days=1)

        # Convertendo de volta para string
        nova_data = nova_data.strftime(format_str)

        return nova_data

    def _validate_approve_refuse_request(self, request):
        """
        Validates and approves or refuses a request.

        Args:
            request (object): The request object.

        Raises:
            ValidationError: If the user is not authorized or if the contract or portability is not available.

        Returns:
            tuple: A tuple containing the contract and portability objects.
        """

        if request.user and 'Corban Master' not in request.user.get_groups_list():
            raise ValidationError({'Erro': 'Acesso não autorizado.'})

        contract_token = request.data.get('contract_token')

        contract = Contrato.objects.filter(
            token_contrato=contract_token,
            tipo_produto=EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ).first()

        if not contract:
            raise ValidationError({
                'Erro': 'Contrato não disponível para cancelamento.'
            })

        if portability := contract.contrato_portabilidade.filter(
            status=ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value
        ).first():
            return contract, portability
        else:
            raise ValidationError({
                'Erro': 'Portabilidade não disponível para cancelamento.'
            })
