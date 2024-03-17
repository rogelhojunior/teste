import json
import logging
from datetime import datetime
from django.conf import settings

import newrelic.agent
import requests
from rest_framework.exceptions import ValidationError

from api_log.models import (
    CancelaReserva,
    ConsultaAverbadora,
    ConsultaConsignacoes,
    ConsultaMargem,
    ConsultaMatricula,
    LogCliente,
    RealizaReserva,
)
from contract.constants import EnumTipoMargem, EnumTipoProduto
from contract.products.cartao_beneficio.models.convenio import Convenios, SubOrgao
from core.models.cliente import ClienteCartaoBeneficio
from core.utils import consulta_cliente, get_dados_convenio

logger = logging.getLogger('digitacao')
url = settings.HUB_AVERBADORA_URL


class Zetra:
    """
    Class for integration with the Zetra API.
    """

    url = settings.HUB_AVERBADORA_URL

    def __init__(self, averbadora_number: int, convenio_code: int) -> None:
        """
        Initializes a new instance of the class.

        Parameters:
            averbadora_number (int): The averbadora number.
            convenio_code (int): The convenio code.

        Returns:
            None
        """

        self.averbadora_number = averbadora_number
        self.convenio = Convenios.objects.filter(
            id=convenio_code, averbadora=averbadora_number, ativo=True
        ).first()

        if not self.convenio:
            raise ValidationError({'Erro': 'Convênio não encontrado.'})

    def _get_headers(self) -> dict:
        """
        Returns the headers for an HTTP request.

        :return: A dictionary containing the headers.
        :rtype: dict
        """

        return {'Content-Type': 'application/json'}

    def _request(self, method: str, payload: dict = None) -> requests.Response:
        """
        Sends a request to the specified URL using the specified HTTP method and payload.

        Parameters:
            method (str): The HTTP method to use for the request.
            payload (dict): The payload to send with the request. Defaults to an empty dictionary.

        Returns:
            requests.Response: The response object containing the server's response to the request.
        """

        if payload is None:
            payload = {}
        headers = self._get_headers()
        data = json.dumps(payload)
        return requests.request(method=method, url=self.url, data=data, headers=headers)

    def _consignment_consult_request(
        self, cpf: str, registration_number: str
    ) -> requests.Response:
        """
        Sends a POST request to the consignment service to consult a consignment with the given CPF and registration number.

        Args:
            cpf (str): The CPF of the customer.
            registration_number (str): The registration number of the customer.

        Returns:
            requests.Response: The response object containing the result of the request.
        """
        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora_number,
                'operacao': 'consultarConsignacao',
            },
            'parametrosBackoffice': {
                'senhaAdmin': self.convenio.senha_convenio,
                'usuario': self.convenio.usuario_convenio,
                'convenio': self.convenio.cod_convenio_zetra,
                'cliente': self.convenio.cliente_zetra,
            },
            'cliente': {'nuCpf': cpf, 'nuMatricula': registration_number},
        }

        return self._request(method=method, payload=payload)

    def _registration_consult_request(
        self, cpf: str, registration_number: str, server_password: str
    ) -> requests.Response:
        """
        Sends a registration consult request to the server.

        Args:
            cpf (str): The CPF (Brazilian ID) of the customer.
            registration_number (str): The registration number of the customer.
            server_password (str): The password for the server.

        Returns:
            requests.Response: The response from the server.
        """

        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora_number,
                'operacao': 'consultarMargem',
            },
            'parametrosBackoffice': {
                'senhaAdmin': self.convenio.senha_convenio,
                'usuario': self.convenio.usuario_convenio,
                'convenio': self.convenio.cod_convenio_zetra,
                'cliente': self.convenio.cliente_zetra,
            },
            'cliente': {
                'nuCpf': cpf,
                'nuMatricula': registration_number,
                'senha_servidor': server_password,
            },
        }

        return self._request(method=method, payload=payload)

    def _margins_consult_request(
        self,
        cpf: str,
        registration_number: str,
        server_password: str,
        service_code: str,
        codigo_orgao: str = None,
    ) -> requests.Response:
        """
        Sends a POST request to the margins consultation endpoint of the API.

        Args:
            cpf (str): The CPF of the customer.
            registration_number (str): The registration number of the customer.
            server_password (str): The server password of the customer.
            service_code (str): The code of the service.

        Returns:
            requests.Response: The response object containing the result of the request.
        """

        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora_number,
                'operacao': 'consultarMargem',
            },
            'parametrosBackoffice': {
                'senhaAdmin': self.convenio.senha_convenio,
                'usuario': self.convenio.usuario_convenio,
                'convenio': self.convenio.cod_convenio_zetra,
                'cliente': self.convenio.cliente_zetra,
                'codigo_servico': service_code,
                'codigo_orgao': codigo_orgao,
            },
            'cliente': {
                'nuCpf': cpf,
                'nuMatricula': registration_number,
                'senha_servidor': server_password,
            },
        }

        print(json.dumps(payload))

        return self._request(method=method, payload=payload)

    def _margin_reserve_request(self, **kwargs) -> requests.Response:
        """
        Sends a margin reserve request to the server.

        Args:
            cpf (str): The CPF of the customer.
            server_password (str): The password for the server.
            service_code (str): The code of the service.
            installment_amount (float): The amount of the installment.
            free_value (float): The amount of the free value.

        Returns:
            requests.Response: The response from the server.
        """
        cpf = kwargs.get('cpf')
        server_password = kwargs.get('server_password')
        service_code = kwargs.get('service_code')
        installment_amount = kwargs.get('installment_amount')
        free_value = kwargs.get('free_value')
        registration_number = kwargs.get('registration_number')
        qta_parcela = kwargs.get('qta_parcela')
        codigo_orgao = kwargs.get('codigo_orgao')

        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora_number,
                'operacao': 'reservarMargem',
            },
            'parametrosBackoffice': {
                'senhaAdmin': self.convenio.senha_convenio,
                'usuario': self.convenio.usuario_convenio,
                'convenio': self.convenio.cod_convenio_zetra,
                'cliente': self.convenio.cliente_zetra,
                'codigo_servico': service_code,
                'codigo_orgao': codigo_orgao,
            },
            'cliente': {
                'nuCpf': cpf,
                'valParcela': float(free_value or 0),
                'valLiberado': float(installment_amount or 0),
                'senha_servidor': server_password,
                'nuMatricula': registration_number,
            },
        }

        if settings.ORIGIN_CLIENT == 'DIGIMAIS':
            payload['cliente']['qtaParcela'] = int(qta_parcela)

        print(json.dumps(payload))

        return self._request(method=method, payload=payload)

    def _margin_reserve_cancel_request(
        self,
        cpf: str,
        reserve_number: str,
    ) -> requests.Response:
        """
        Sends a cancel request for a margin reserve.

        Args:
            cpf (str): The CPF of the customer.
            reserve_number (str): The reserve number.

        Returns:
            requests.Response: The response from the cancel request.
        """

        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora_number,
                'operacao': 'reservarMargem',
            },
            'parametrosBackoffice': {
                'senhaAdmin': self.convenio.senha_convenio,
                'usuario': self.convenio.usuario_convenio,
                'convenio': self.convenio.cod_convenio_zetra,
                'cliente': self.convenio.cliente_zetra,
            },
            'cliente': {'nuCpf': cpf, 'nuReserva': reserve_number},
        }

        return self._request(method=method, payload=payload)

    def consignment_consult(
        self, cpf: str, registration_number: str
    ) -> ConsultaConsignacoes:
        """
        Consults the consignment information for a given CPF and registration number.

        Args:
            cpf (str): The CPF of the customer.
            registration_number (str): The registration number of the consignment.

        Returns:
            ConsultaConsignacoes: The consignment information object.

        Raises:
            Exception: If there is an error while consulting the consignment information.
        """

        response = self._consignment_consult_request(
            cpf=cpf,
            registration_number=registration_number,
        )

        response_text = json.loads(response.text)

        customer = consulta_cliente(numero_cpf=cpf)
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=customer)

        try:
            consignacao_obj, _ = ConsultaConsignacoes.objects.get_or_create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                descricao=response_text.get('descricao'),
                codigo_retorno=response_text.get('codigoRetorno'),
            )

            logger.info(
                f'{customer.id_unico} - Margem do cliente consultada na averbadora {self.averbadora_number}'
            )

        except Exception as e:
            logger.error(
                f'{customer.id_unico} - Erro ao consultar margem do cliente na averbadora {self.averbadora_number}: {e}'
            )

            consignacao_obj, _ = ConsultaConsignacoes.objects.get_or_create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                descricao=response_text.get('descricao'),
                codigo_retorno=response_text.get('codigoRetorno'),
            )

        return consignacao_obj

    def registration_consult(
        self, cpf: str, registration_number: str, server_password: str
    ) -> list:
        """
        Retrieves registration information for a customer based on their CPF and registration number.

        Args:
            cpf (str): The CPF of the customer.
            registration_number (str): The registration number of the customer.
            server_password (str): The password for accessing the server.

        Returns:
            list: A list containing the registration information of the customer.
        """

        response = self._registration_consult_request(
            cpf=cpf,
            registration_number=registration_number,
            server_password=server_password,
        )

        matricula_obj = None

        try:
            response_text = json.loads(response.text)
            nascimento = response_text.get('nascimento')
            cliente = consulta_cliente(cpf)

            if nascimento:
                nascimento = datetime.strptime(nascimento, '%d/%m/%Y').strftime(
                    '%Y-%m-%d'
                )
                cliente.dt_nascimento = nascimento
                cliente.nome_cliente = response_text.get('nome')
                cliente.save()

            if cliente_cartao := ClienteCartaoBeneficio.objects.filter(
                cliente=cliente
            ).first():
                cliente_cartao.convenio = self.convenio
                cliente_cartao.numero_matricula = response_text.get('numeroMatricula')
                cliente_cartao.folha = response_text.get('folha')
                cliente_cartao.margem_atual = response_text.get('margemAtual')
                cliente_cartao.save()

            else:
                cliente_cartao = ClienteCartaoBeneficio.objects.create(
                    cliente=cliente,
                    convenio=self.convenio,
                    numero_matricula=response_text.get('numeroMatricula'),
                    folha=response_text.get('folha'),
                    margem_atual=response_text.get('margemAtual'),
                )

            log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

            matricula_obj, _ = ConsultaMatricula.objects.update_or_create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                matricula=response_text.get('numeroMatricula'),
                folha=response_text.get('folha'),
                margem_atual=response_text.get('margemAtual'),
                cargo=response_text.get('cargo'),
                estavel=response_text.get('estavel'),
            )

        except Exception:
            newrelic.agent.notice_error()

        ConsultaAverbadora.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            payload_envio=response.request.body,
            payload=response_text,
            tipo_chamada='Consulta Matricula',
        )

        return [matricula_obj]

    def margins_consult(
        self, cpf: str, registration_number: str, server_password: str
    ) -> list:
        """
        Consults the margins for a customer based on their CPF, registration number, and server password.

        Parameters:
            cpf (str): The customer's CPF.
            registration_number (str): The customer's registration number.
            server_password (str): The password for the server.

        Returns:
            list: A list of margins for the customer. Each margin is represented as a dictionary.
        """

        margins = []

        customer = consulta_cliente(
            cpf
        )  # Certifique-se de que essa função esteja definida
        products = self.convenio.produto_convenio.all()
        suborgaos = SubOrgao.objects.filter(convenio=self.convenio, ativo=True).first()

        for product in products:
            response = self._margins_consult_request(
                cpf=cpf,
                registration_number=registration_number,
                server_password=server_password,
                service_code=product.cod_servico_zetra,
                codigo_orgao=suborgaos.codigo_folha,
            )

            response_text = json.loads(response.text)
            log_api_id, _ = LogCliente.objects.get_or_create(cliente=customer)

            if 'servidores' in response_text:
                for servidor in response_text['servidores']:
                    try:
                        response = self._margins_consult_request(
                            cpf=cpf,
                            registration_number=registration_number,
                            server_password=server_password,
                            service_code=product.cod_servico_zetra,
                            codigo_orgao=servidor['codigo_folha']['#text'],
                        )
                        response_text = json.loads(response.text)
                        margem_atual = response_text.get('margemAtual', '0.00')
                        tipo_margem = self.determine_tipo_margem(
                            product, response_text['verba']
                        )
                        if isinstance(margem_atual, dict) and '#text' in margem_atual:
                            margem_atual = margem_atual['#text']
                        else:
                            margem_atual = '0.00'

                        margins.append({
                            'margem_atual': margem_atual,
                            'verba': response_text['verba'],
                            'folha': response_text['codigo_folha']['#text'],
                            'orgao': response_text['folha']['#text'],
                            'matricula': response_text['numeroMatricula']['#text'],
                            'idProduto': product.produto,
                            'tipoMargem': tipo_margem,
                            'descricao': response_text.get('descricao', ''),
                            'codigo_retorno': response_text.get('codigoRetorno', ''),
                        })

                    except Exception as e:
                        logger.error(
                            f'Erro ao processar múltiplos servidores: {e}',
                            exc_info=True,
                        )

            elif 'descricao' in response_text:
                margins.append({
                    'descricao': response_text['descricao'],
                    'codigo_retorno': response_text['codigoRetorno'],
                })

            else:
                try:
                    margem_atual = response_text.get('margemAtual', '0.00')
                    tipo_margem = self.determine_tipo_margem(
                        product, response_text['verba']
                    )
                    if isinstance(margem_atual, dict) and '#text' in margem_atual:
                        margem_atual = margem_atual['#text']
                    else:
                        margem_atual = '0.00'

                    margins.append({
                        'margem_atual': margem_atual,
                        'verba': response_text['verba'],
                        'folha': response_text['codigo_folha']['#text'],
                        'orgao': response_text['folha']['#text'],
                        'matricula': response_text['numeroMatricula']['#text'],
                        'idProduto': product.produto,
                        'tipoMargem': tipo_margem,
                        'descricao': response_text.get('descricao', ''),
                        'codigo_retorno': response_text.get('codigoRetorno', ''),
                    })

                except Exception as e:
                    logger.error(
                        f'Erro ao processar um único servidor: {e}', exc_info=True
                    )

            ConsultaAverbadora.objects.create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                payload_envio=response.request.body,
                payload=response_text,
                tipo_chamada='Consulta Margem',
            )

        suborgaos_ativos = SubOrgao.objects.filter(convenio=self.convenio, ativo=True)
        if not suborgaos_ativos.exists():
            logger.error(
                f'{cpf} - Não existem orgãos cadastrados, contate o administrador. Numero Averbadora: {self.averbadora_number}',
                exc_info=True,
            )
            return {
                'descricao': 'A matrícula informada não possui orgão cadastrado, contate o administrador.',
                'codigo_retorno': 400,
            }

        elif suborgaos_ativos.count() == 1:
            suborgao = suborgaos_ativos.first()
            margin = next(
                (
                    margin
                    for margin in margins
                    if margin.get('folha') == suborgao.codigo_folha
                ),
                None,
            )

            if margin:
                return [margin]
            else:
                logger.error(
                    f'{cpf} - Nenhum subórgão com código de folha correspondente encontrado na lista. Contate o administrador.'
                )
                return {
                    'descricao': 'A matrícula informada não possui orgão cadastrado, contate o administrador.',
                    'codigo_retorno': 400,
                }
        else:
            codigos_folha_suborgaos = [
                suborgao.codigo_folha for suborgao in suborgaos_ativos
            ]
            margens_correspondentes = [
                margin
                for margin in margins
                if margin.get('folha') in codigos_folha_suborgaos
                and float(margin.get('margem_atual'))
            ]
            if margens_correspondentes:
                return margens_correspondentes
            else:
                logger.error(
                    f'{cpf} - Nenhum subórgão com código de folha correspondente encontrado na lista. Contate o administrador.'
                )
                return {
                    'descricao': 'A matrícula informada não possui margem para os orgãos cadastrados.',
                    'codigo_retorno': 400,
                }

    def determine_tipo_margem(self, product, verba):
        """
        Determina o tipo de margem com base no produto e na verba.
        """
        tipo_margem = ''
        if product.produto == EnumTipoProduto.CARTAO_BENEFICIO and verba == '010':
            tipo_margem = 'Cartão Benefício - Saque'
        elif product.produto == EnumTipoProduto.CARTAO_BENEFICIO and verba == '009':
            tipo_margem = 'Cartão Benefício - Compra'
        elif product.produto == EnumTipoProduto.CARTAO_CONSIGNADO and verba == '010':
            tipo_margem = 'Cartão Consignado - Saque'
        elif product.produto == EnumTipoProduto.CARTAO_CONSIGNADO and verba == '009':
            tipo_margem = 'Cartão Consignado - Compra'
        return tipo_margem

    def margin_reserve(
        self,
        cpf: str,
        server_password: str,
        verba: str,
        folha: str,
        registration_number: str,
        qta_parcela: int,
        valor_parcela: float,
        customer_benefit_card: ClienteCartaoBeneficio,
    ) -> RealizaReserva:
        """
        Generates a margin reserve based on the given CPF, server password, and verba.

        Args:
            cpf (str): The CPF of the customer.
            server_password (str): The password used to access the server.
            verba (str): The verba used to generate the margin reserve.

        Returns:
            RealizaReserva: An object representing the margin reserve.
        """

        customer = consulta_cliente(numero_cpf=cpf)

        if not customer:
            logger.error('Cliente não encontrado', exc_info=True)
            raise ValueError('Cliente não encontrado.')

        if not customer_benefit_card:
            logger.error('Cartão benefício do cliente não encontrado', exc_info=True)
            raise ValueError('Cartão benefício do cliente não encontrado.')

        if customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA:
            return self._margin_reserve_unified(
                cpf=cpf,
                server_password=server_password,
                customer=customer,
                customer_benefit_card=customer_benefit_card,
                registration_number=registration_number,
                qta_parcela=qta_parcela,
                valor_parcela=valor_parcela,
            )

        else:
            return self._margin_reserve_unique(
                cpf=cpf,
                server_password=server_password,
                verba=verba,
                folha=folha,
                customer=customer,
                customer_benefit_card=customer_benefit_card,
                registration_number=registration_number,
                qta_parcela=qta_parcela,
                valor_parcela=valor_parcela,
            )

    def _margin_reserve_unified(
        self,
        cpf: str,
        server_password: str,
        customer: dict,
        customer_benefit_card: ClienteCartaoBeneficio,
        registration_number: str,
        qta_parcela: int,
        valor_parcela: float,
    ) -> RealizaReserva:
        """
        Reserves margins for a customer in a unified way.

        Args:
            cpf (str): The customer's CPF.
            server_password (str): The server password.
            customer (dict): A dictionary containing customer information.
            customer_benefit_card (ClienteCartaoBeneficio): An instance of the ClienteCartaoBeneficio class.

        Returns:
            RealizaReserva: An instance of the RealizaReserva class.

        Raises:
            Exception: If an error occurs during the reservation process.

        """

        margins_to_reserve = {
            'compra': {
                'amount': customer_benefit_card.margem_compra,
                'verba': customer_benefit_card.verba_compra,
            },
            'saque': {
                'amount': customer_benefit_card.margem_saque,
                'verba': customer_benefit_card.verba_saque,
            },
        }

        reserved_margins = []

        for margin_type, margin_data in margins_to_reserve.items():
            amount = margin_data.get('amount')
            verba = margin_data.get('verba')

            response = self._margin_reserve_request(
                cpf=cpf,
                server_password=server_password,
                service_code=verba,
                installment_amount=amount,
                free_value=amount,
                registration_number=registration_number,
                qta_parcela=qta_parcela,
            )

            response_text = json.loads(response.text)

            log_api_id, _ = LogCliente.objects.get_or_create(cliente=customer)

            try:
                numero_matricula = response_text.get('numeroMatricula')
                verba = response_text.get('verba')
                folha = response_text.get('folha')
                valor = response_text.get('valor')
                reserva = response_text.get('reserva')

                customer_benefit_card.numero_matricula = numero_matricula

                if margin_type == 'compra':
                    customer_benefit_card.reserva_compra = reserva
                    customer_benefit_card.folha_compra = folha
                    customer_benefit_card.verba_compra = verba

                elif margin_type == 'saque':
                    customer_benefit_card.reserva_saque = reserva
                    customer_benefit_card.folha_saque = folha
                    customer_benefit_card.verba_saque = verba

                customer_benefit_card.save()

                realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
                    log_api_id=log_api_id.pk,
                    cliente=customer,
                    matricula=numero_matricula,
                    folha=folha,
                    verba=verba,
                    valor=valor,
                    reserva=reserva,
                )

                reserved_margins.append(margin_type)

            except Exception:
                newrelic.agent.notice_error()

                realiza_reserva_obj = RealizaReserva.objects.create(
                    log_api_id=log_api_id.pk,
                    cliente=customer,
                    descricao=response_text.get('descricao'),
                    codigo_retorno=response_text.get('codigoRetorno'),
                )

                for margem_reservada in reserved_margins:
                    self.margin_reserve_cancel(
                        cpf=cpf,
                        margin_reserved_type=margem_reservada,
                    )

            ConsultaAverbadora.objects.create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                payload_envio=response.request.body,
                payload=response_text,
                tipo_chamada='Reserva Margem',
            )

        return realiza_reserva_obj

    def _margin_reserve_unique(
        self,
        cpf: str,
        server_password: str,
        verba: str,
        folha: str,
        customer: dict,
        customer_benefit_card: ClienteCartaoBeneficio,
        registration_number: str,
        qta_parcela: int,
        valor_parcela: float,
    ) -> RealizaReserva:
        """
        Performs a margin reserve for a unique customer.

        Args:
            cpf (str): The customer's CPF.
            server_password (str): The server password.
            verba (str): The service code.
            customer (dict): A dictionary containing customer details.
            customer_benefit_card (ClienteCartaoBeneficio): The customer's benefit card.

        Returns:
            RealizaReserva: The object representing the margin reserve.
        """
        params = {
            'cpf': cpf,
            'server_password': server_password,
            'service_code': verba,
            'installment_amount': float(
                customer_benefit_card.margem_compra
                or customer_benefit_card.margem_saque
                or customer_benefit_card.margem_atual
            ),
            'free_value': valor_parcela,
            'registration_number': registration_number,
            'qta_parcela': qta_parcela,
            'codigo_orgao': folha,
        }
        response = self._margin_reserve_request(**params)
        try:
            response_text = json.loads(response.text)
            numero_matricula = response_text.get('numeroMatricula')
            verba = response_text.get('verba')
            folha = response_text.get('folha')
            valor = response_text.get('valor')
            reserva = response_text.get('reserva')
            log_api_id, _ = LogCliente.objects.get_or_create(cliente=customer)
            customer_benefit_card.numero_matricula = numero_matricula
            customer_benefit_card.verba = verba
            customer_benefit_card.folha = folha
            customer_benefit_card.reserva = reserva
            customer_benefit_card.save()

            realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                matricula=numero_matricula,
                folha=folha,
                verba=verba,
                valor=valor,
                reserva=reserva,
            )

        except Exception:
            newrelic.agent.notice_error()

            realiza_reserva_obj = RealizaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                descricao='descricao',
                codigo_retorno='codigoRetorno',
            )

        ConsultaAverbadora.objects.create(
            log_api_id=log_api_id.pk,
            cliente=customer,
            payload_envio=str(params),
            payload=str(response_text),
            tipo_chamada='Reserva Margem',
        )

        return realiza_reserva_obj

    def margin_reserve_cancel(
        self, cpf: str, margin_reserved_type: str = ''
    ) -> CancelaReserva:
        customer = consulta_cliente(numero_cpf=cpf)
        customer_benefit_card = ClienteCartaoBeneficio.objects.get(cliente=customer)
        reserve_number = customer_benefit_card.reserva

        if margin_reserved_type == 'compra':
            reserve_number = customer_benefit_card.reserva_compra

        elif margin_reserved_type == 'saque':
            reserve_number = customer_benefit_card.reserva_saque

        response = self._margin_reserve_cancel_request(
            cpf=cpf,
            reserve_number=reserve_number,
        )
        response_text = json.loads(response.text)

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=customer)

        cancela_reserva_obj = None

        try:
            numero_matricula = response_text.get('numeroMatricula')
            reserva = response_text.get('reserva')
            cancelada = response_text.get('cancelada')

            cancela_reserva_obj, _ = CancelaReserva.objects.update_or_create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                matricula=numero_matricula,
                reserva=reserva,
                cancelada=cancelada,
            )

        except Exception:
            newrelic.agent.notice_error()

            cancela_reserva_obj = CancelaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=customer,
                descricao=response_text.get('descricao'),
                codigo_retorno=response_text.get('codigoRetorno'),
            )

        ConsultaAverbadora.objects.create(
            log_api_id=log_api_id.pk,
            cliente=customer,
            payload_envio=response.request.body,
            payload=response_text,
            tipo_chamada='Cancela Reserva',
        )

        return cancela_reserva_obj


def consulta_consignacoes_zetra(
    numero_cpf, averbadora, codigo_convenio, numero_matricula
):
    logger = logging.getLogger('digitacao')
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        convenios,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)

    payload = json.dumps(
        {
            'averbadora': {
                'nomeAverbadora': averbadora,
                'operacao': 'consultarConsignacao',
            },
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': convenios.cod_convenio_zetra,
                'cliente': convenios.cliente_zetra,
            },
            'cliente': {'nuCpf': f'{numero_cpf}', 'nuMatricula': numero_matricula},
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = json.loads(response.text)
    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

    try:
        consignacao_obj, _ = ConsultaConsignacoes.objects.get_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )

        logger.info(
            f'{cliente.id_unico} - Margem do cliente consultada na averbadora {averbadora}'
        )
    except Exception as e:
        logger.error(
            f'{cliente.id_unico} - Erro ao consultar margem do cliente na averbadora {averbadora}: {e}'
        )
        consignacao_obj, _ = ConsultaConsignacoes.objects.get_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )
    return consignacao_obj


# API de consultar a matricula na zetra
def consulta_matricula_zetra(
    numero_cpf, averbadora, codigo_convenio, numero_matricula, senha_servidor
):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        convenios,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    matricula_obj = None

    payload = json.dumps(
        {
            'averbadora': {'nomeAverbadora': averbadora, 'operacao': 'consultarMargem'},
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': convenios.cod_convenio_zetra,
                'cliente': convenios.cliente_zetra,
            },
            'cliente': {
                'nuCpf': f'{numero_cpf}',
                'nuMatricula': numero_matricula,
                'senha_servidor': senha_servidor,
            },
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)

    try:
        response_text = json.loads(response.text)
        nascimento = response_text['nascimento']
        cliente = consulta_cliente(numero_cpf)
        if nascimento:
            nascimento = datetime.strptime(nascimento, '%d/%m/%Y').strftime('%Y-%m-%d')
            cliente.dt_nascimento = nascimento
            cliente.nome_cliente = response_text['nome']
            cliente.save()

        if cliente_cartao := ClienteCartaoBeneficio.objects.filter(
            cliente=cliente
        ).first():
            cliente_cartao.convenio = convenios
            cliente_cartao.numero_matricula = response_text.get('numeroMatricula')
            cliente_cartao.folha = response_text.get('folha')
            cliente_cartao.margem_atual = response_text.get('margemAtual')
            cliente_cartao.save()

        else:
            cliente_cartao = ClienteCartaoBeneficio.objects.create(
                cliente=cliente,
                convenio=convenios,
                numero_matricula=response_text.get('numeroMatricula'),
                folha=response_text.get('folha'),
                margem_atual=response_text.get('margemAtual'),
            )

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        matricula_obj, _ = ConsultaMatricula.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=response_text['numeroMatricula'],
            folha=response_text['folha'],
            margem_atual=response_text['margemAtual'],
            cargo=response_text['cargo'],
            estavel=response_text['estavel'],
        )
    except Exception as e:
        print(e)
        print('Erro ao consultar matrícula:', e)

    ConsultaAverbadora.objects.create(
        log_api_id=log_api_id.pk,
        cliente=cliente,
        payload_envio=payload,
        payload=response_text,
        tipo_chamada='Consulta Matricula',
    )
    return [matricula_obj]


# API de consulta de margem na zetra
def consulta_margem_zetra(
    numero_cpf, averbadora, codigo_convenio, numero_matricula, senha_servidor
):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        convenios,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)

    margins = []

    products = convenios.produto_convenio.all()

    for product in products:
        payload = json.dumps(
            {
                'averbadora': {
                    'nomeAverbadora': averbadora,
                    'operacao': 'consultarMargem',
                },
                'parametrosBackoffice': {
                    'senhaAdmin': f'{senha_admin}',
                    'usuario': f'{usuario_convenio}',
                    'convenio': convenios.cod_convenio_zetra,
                    'codigo_servico': product.cod_servico_zetra,
                    'cliente': convenios.cliente_zetra,
                },
                'cliente': {
                    'nuCpf': f'{numero_cpf}',
                    'nuMatricula': numero_matricula,
                    'senha_servidor': senha_servidor,
                },
            },
            indent=4,
            ensure_ascii=False,
        )

        headers = {
            'Content-Type': 'application/json',
        }
        response = requests.request('POST', url, headers=headers, data=payload)
        response_text = json.loads(response.text)
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        if response_text.get('descricao'):
            margins = {
                'descricao': response_text.get('descricao'),
                'codigo_retorno': response_text.get('codigoRetorno'),
            }

        else:
            try:
                # nascimento = response_text.get('nascimento')

                # if nascimento:
                #     nascimento = datetime.strptime(nascimento, '%d/%m/%Y').strftime(
                #         '%Y-%m-%d'
                #     )
                #     cliente.dt_nascimento = nascimento
                #     cliente.nome_cliente = response_text.get('nome')
                #     cliente.save()

                # cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.filter(
                #     cliente=cliente
                # ).first()

                # if cliente_cartao_beneficio:
                #     cliente_cartao_beneficio.convenio = convenios
                #     cliente_cartao_beneficio.numero_matricula = response_text.get(
                #         'numeroMatricula'
                #     )
                #     cliente_cartao_beneficio.folha = response_text.get('folha')
                #     cliente_cartao_beneficio.margem_atual = response_text.get(
                #         'margemAtual'
                #     )
                #     cliente_cartao_beneficio.verba = response_text.get('verba')
                #     cliente_cartao_beneficio.save()

                # else:
                #     cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.create(
                #         cliente=cliente,
                #         convenio=convenios,
                #         numero_matricula=response_text.get('numeroMatricula'),
                #         folha=response_text.get('folha'),
                #         margem_atual=response_text.get('margemAtual'),
                #         verba=response_text.get('verba'),
                #     )

                margem_obj, _ = ConsultaMargem.objects.update_or_create(
                    log_api_id=log_api_id.pk,
                    cliente=cliente,
                    matricula=response_text.get('numeroMatricula'),
                    folha=response_text.get('folha'),
                    margem_atual=response_text.get('margemAtual'),
                    cargo=response_text.get('cargo'),
                    estavel=response_text.get('estavel'),
                    verba=response_text.get('verba'),
                )

                tipo_margem = 0

                if product.produto == EnumTipoProduto.CARTAO_BENEFICIO:
                    tipo_margem = 'Cartão Benefício'

                elif product.produto == EnumTipoProduto.CARTAO_CONSIGNADO:
                    tipo_margem = 'Cartão Consignado'

                margins.append({
                    'margem_atual': margem_obj.margem_atual or '0.00',
                    'verba': margem_obj.verba,
                    'folha': margem_obj.folha,
                    'matricula': margem_obj.matricula,
                    'idProduto': product.produto,
                    'tipoMargem': tipo_margem,
                })

            except Exception as e:
                logger.error(
                    f'Não foi possível consultar a margem - {averbadora} - {e}',
                    exc_info=True,
                )

                margem_obj = ConsultaMargem.objects.update_or_create(
                    log_api_id=log_api_id.pk,
                    cliente=cliente,
                    descricao=response_text['descricao'],
                    codigo_retorno=response_text['codigoRetorno'],
                )

                margins = {
                    'descricao': margem_obj.descricao,
                    'codigo_retorno': margem_obj.codigo_retorno,
                }

        ConsultaAverbadora.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            payload_envio=payload,
            payload=response_text,
            tipo_chamada='Consulta Margem',
        )

    return margins


# API QUE REALIZA RESERVA DA MARGEM NA ZETRASOFT
def reservar_margem_zetra(
    numero_cpf,
    averbadora,
    valor,
    codigo_convenio,
    senha_servidor,
    verba,
):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        convenios,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)
    cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.get(cliente=cliente)

    payload = json.dumps(
        {
            'averbadora': {
                'nomeAverbadora': averbadora,
                'operacao': 'reservarMargem',
            },
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': f'{convenios.cod_convenio_zetra}',
                'codigo_servico': f'{verba}',
                'cliente': f'{convenios.cliente_zetra}',
            },
            'cliente': {
                'nuCpf': f'{numero_cpf}',
                'valParcela': f'{cliente_cartao_beneficio.margem_atual}',
                'valLiberado': f'{cliente_cartao_beneficio.margem_atual}',
                'senha_servidor': f'{senha_servidor}',
            },
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = json.loads(response.text)

    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

    try:
        numero_matricula = response_text['numeroMatricula']
        verba = response_text['verba']
        folha = response_text['folha']
        valor = response_text['valor']
        reserva = response_text['reserva']

        cliente_cartao_beneficio.numero_matricula = numero_matricula
        cliente_cartao_beneficio.verba = verba
        cliente_cartao_beneficio.folha = folha
        cliente_cartao_beneficio.valor = valor
        cliente_cartao_beneficio.reserva = reserva
        cliente_cartao_beneficio.save()

        realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=numero_matricula,
            folha=folha,
            verba=verba,
            valor=valor,
            reserva=reserva,
        )

    except Exception as e:
        print(e)
        realiza_reserva_obj = RealizaReserva.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )

    ConsultaAverbadora.objects.create(
        log_api_id=log_api_id.pk,
        cliente=cliente,
        payload_envio=payload,
        payload=response_text,
        tipo_chamada='Reserva Margem',
    )

    return realiza_reserva_obj


def cancela_reserva_zetra(numero_cpf, averbadora, codigo_convenio):
    (
        senha_admin,
        usuario_convenio,
        _,
        _,
        convenios,
    ) = get_dados_convenio(averbadora, codigo_convenio)

    cliente = consulta_cliente(numero_cpf)
    cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.get(cliente=cliente)
    reserva = cliente_cartao_beneficio.reserva

    payload = json.dumps(
        {
            'averbadora': {'nomeAverbadora': 2, 'operacao': 'cancelarConsignacao'},
            'parametrosBackoffice': {
                'senhaAdmin': f'{senha_admin}',
                'usuario': f'{usuario_convenio}',
                'convenio': convenios.cod_convenio_zetra,
                'cliente': convenios.cliente_zetra,
            },
            'cliente': {'nuCpf': f'{numero_cpf}', 'nuReserva': f'{reserva}'},
        },
        indent=4,
        ensure_ascii=False,
    )

    headers = {
        'Content-Type': 'application/json',
    }

    response = requests.request('POST', url, headers=headers, data=payload)
    response_text = json.loads(response.text)
    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

    try:
        numero_matricula = response_text['numeroMatricula']
        reserva = response_text['reserva']
        cancelada = response_text['cancelada']

        cancela_reserva_obj, _ = CancelaReserva.objects.update_or_create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            matricula=numero_matricula,
            reserva=reserva,
            cancelada=cancelada,
        )

    except Exception as e:
        print(e)
        cancela_reserva_obj = CancelaReserva.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            descricao=response_text['descricao'],
            codigo_retorno=response_text['codigoRetorno'],
        )

    ConsultaAverbadora.objects.create(
        log_api_id=log_api_id.pk,
        cliente=cliente,
        payload_envio=payload,
        payload=response_text,
        tipo_chamada='Cancela Reserva',
    )

    return cancela_reserva_obj
