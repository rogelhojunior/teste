import json
import logging

import requests
from django.conf import settings

from api_log.models import (
    CancelaReserva,
    ConsultaAverbadora,
    LogCliente,
    RealizaReserva,
)
from contract.constants import EnumTipoMargem
from contract.models.contratos import Contrato
from core.utils import consulta_cliente, get_dados_convenio

logger = logging.getLogger('digitacao')


class Neoconsig:
    url = settings.HUB_AVERBADORA_URL

    def __init__(self, averbadora: int) -> None:
        self.averbadora = averbadora

        return

    def _get_headers(self) -> dict:
        return {
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, payload: dict = None) -> requests.Response:
        if payload is None:
            payload = {}
        headers = self._get_headers()

        return requests.request(
            method=method, url=self.url, data=json.dumps(payload), headers=headers
        )

    def _margins_consult_request(
        self, cpf: str, matricula: str, cod_convenio: int
    ) -> requests.Response:
        method = 'POST'
        payload = {
            'parametrosBackoffice': {'codConvenio': f'{cod_convenio}'},
            'averbadora': {
                'nomeAverbadora': self.averbadora,
                'operacao': 'consultarMargem',
            },
            'cliente': {'nuCpf': cpf, 'nuMatricula': matricula},
        }

        return self._request(method=method, payload=payload)

    def _margin_reserve_request(
        self,
        cpf: str,
        matricula: str,
        cod_convenio: int,
        valor: str,
        verba: str,
        margem: str,
        senha: str,
    ) -> requests.Response:
        method = 'POST'
        payload = {
            'parametrosBackoffice': {'codConvenio': f'{cod_convenio}'},
            'averbadora': {
                'nomeAverbadora': self.averbadora,
                'operacao': 'reservarMargem',
            },
            'cliente': {
                'nuCpf': f'{cpf}',
                'nuMatricula': f'{matricula}',
                'valLiberado': f'{margem}',
                'valParcela': f'{valor}',
                'verba': f'{verba}',
                'senha': f'{senha}',
            },
        }

        return self._request(method=method, payload=payload)

    def _margin_reserve_confirm_request(
        self, id_contrato: str, cod_convenio: [int, str], numero_contrato: str
    ) -> tuple[requests.Response, dict]:
        method = 'POST'
        payload = {
            'parametrosBackoffice': {'codConvenio': f'{cod_convenio}'},
            'averbadora': {
                'nomeAverbadora': self.averbadora,
                'operacao': 'confirmarReservaMargem',
            },
            'cliente': {
                'idContrato': f'{id_contrato}',
                'numeroContrato': f'{numero_contrato}',
            },
        }

        response = self._request(method=method, payload=payload)

        return response, payload

    def _cancel_margin_reserve_request(
        self,
        id_contrato: str,
        cod_convenio: int,
        cpf: str,
        matricula: str,
        numero_contrato: str,
    ) -> tuple[requests.Response, dict]:
        method = 'POST'
        payload = {
            'parametrosBackoffice': {'codConvenio': f'{cod_convenio}'},
            'averbadora': {
                'nomeAverbadora': self.averbadora,
                'operacao': 'cancelarReserva',
            },
            'cliente': {
                'idContrato': f'{id_contrato}',
                'nuCpf': f'{cpf}',
                'nuMatricula': f'{matricula}',
                'numeroContrato': f'{numero_contrato}',
            },
        }

        response = self._request(method=method, payload=payload)

        return response, payload

    def margins_consult(
        self, cpf: str, codigo_convenio: str, numero_matricula: str
    ) -> any:
        _, _, _, _, convenios = get_dados_convenio(self.averbadora, codigo_convenio)

        response = self._margins_consult_request(
            cpf=cpf, matricula=numero_matricula, cod_convenio=convenios.cod_convenio
        )
        response_json = response.json()

        # Trate erros primeiro
        if 'descricao' in response_json:
            logger.error(
                f'{cpf} - Erro ao consultar margem na averbadora {self.averbadora}, {response_json}',
                exc_info=True,
            )

            return {
                'descricao': response_json['descricao'],
                'codigo_retorno': response_json['codigoRetorno'],
            }
        # Tratar caso bem-sucedido
        try:
            margens_obj = [
                {
                    **margin,
                    'nome': '',
                    'cargo': '',
                    'nascimento': '',
                    'estavel_bool': '',
                    'cliente': '',
                    'idProduto': '',
                }
                for margin in response_json
            ]
            logger.info(f'{cpf} - Margem consultada na averbadora {self.averbadora}')

            return margens_obj
        except Exception as e:
            logger.error(
                f'{cpf} - Erro ao consultar margem na averbadora {self.averbadora}, {e}',
                exc_info=True,
            )

            return {
                'descricao': f'{cpf} - Erro ao consultar margem na averbadora {self.averbadora}, {e}',
                'codigo_retorno': '500',
            }

    def margin_reserve(
        self, cpf: str, codigo_convenio, customer_benefit_card, margin_to_reserve
    ):
        cliente = consulta_cliente(cpf)
        margem = margin_to_reserve['valor']
        verba = margin_to_reserve['verba']
        matricula = customer_benefit_card.numero_matricula
        senha = customer_benefit_card.senha_portal

        # Realizar Reserva de Margem
        response = self._margin_reserve_request(
            cpf=cpf,
            matricula=matricula,
            margem=margem,
            cod_convenio=codigo_convenio,
            verba=verba,
            valor=margem,
            senha=senha,
        )

        response_text = json.loads(response.text)
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        if 'descricao' in response_text:
            logger.error(
                f'Erro ao reservar margem Neoconsig / Status code: {response_text["codigoRetorno"]} - Response Averbadora: {response_text["descricao"]}'
            )
            return RealizaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                descricao=response_text['descricao'],
                codigo_retorno=response_text['codigoRetorno'],
            )
        if 'idContrato' not in response_text:
            logger.error(
                f'Erro ao reservar margem Neoconsig - Id de contrato não identificado ao realizar reserva de margem. CPF: {cpf} /// Response Text: {response.text} /// Response: {response} ///  Response Content: {response.content} /// Response Json: {response.json()} /// Status code: {response.status_code}',
            )

            return RealizaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                descricao='Id de contrato não identificado ao realizar reserva de margem.',
                codigo_retorno='500',
            )
        if margin_to_reserve['tipo_margem'] == EnumTipoMargem.MARGEM_COMPRA:
            customer_benefit_card.reserva_compra = response_text.get('idContrato')
            margin_to_reserve['reserva'] = response_text.get('idContrato')

        if margin_to_reserve['tipo_margem'] == EnumTipoMargem.MARGEM_SAQUE:
            customer_benefit_card.reserva_saque = response_text.get('idContrato')
            margin_to_reserve['reserva'] = response_text.get('idContrato')

        if margin_to_reserve['tipo_margem'] == EnumTipoMargem.MARGEM_UNICA:
            customer_benefit_card.reserva = response_text.get('idContrato')
            margin_to_reserve['reserva'] = response_text.get('idContrato')

        customer_benefit_card.save()

        return response_text

    def margin_reserve_confirm(
        self, cpf: str, cod_convenio: str, customer_benefit_card, margin_to_reserve
    ):
        cliente = consulta_cliente(cpf)

        margem = margin_to_reserve['valor']
        verba = margin_to_reserve['verba']
        id_contrato = margin_to_reserve['reserva']
        matricula = customer_benefit_card.numero_matricula
        numero_contrato = customer_benefit_card.contrato_id

        response, payload = self._margin_reserve_confirm_request(
            id_contrato=id_contrato,
            cod_convenio=cod_convenio,
            numero_contrato=numero_contrato,
        )

        response_text = json.loads(response.text)

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        if 'descricao' in response_text:
            logger.error(
                f'Erro ao confirmar reserva margem Neoconsig / Status code: {response_text["codigoRetorno"]} - Response Averbadora: {response_text["descricao"]}'
            )
            return RealizaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                descricao=response_text['descricao'],
                codigo_retorno=response_text['codigoRetorno'],
            )
        try:
            numero_matricula = matricula
            verba = verba
            folha = cod_convenio
            valor = margem
            reserva = response_text['idContrato']

            if margin_to_reserve['tipo_margem'] == EnumTipoMargem.MARGEM_COMPRA:
                customer_benefit_card.verba_compra = verba
                customer_benefit_card.folha_compra = folha
                customer_benefit_card.margem_compra = valor
                customer_benefit_card.reserva_compra = reserva

            if margin_to_reserve['tipo_margem'] == EnumTipoMargem.MARGEM_SAQUE:
                customer_benefit_card.verba_saque = verba
                customer_benefit_card.folha_saque = folha
                customer_benefit_card.margem_saque = valor
                customer_benefit_card.reserva_saque = reserva

            if margin_to_reserve['tipo_margem'] == EnumTipoMargem.MARGEM_UNICA:
                customer_benefit_card.verba = verba
                customer_benefit_card.folha = folha
                customer_benefit_card.margem_atual = valor
                customer_benefit_card.reserva = reserva

            customer_benefit_card.numero_matricula = matricula
            customer_benefit_card.save()

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
            logger.error(
                f'Erro ao confirmar reserva margem Neoconsig / Except - Erro codigo: {e}'
            )
            logger.error(
                f'Erro ao confirmar reserva margem Neoconsig / Except / Status code: {response_text["codigoRetorno"]} - Response Averbadora: {response_text["descricao"]}'
            )
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

    def margin_reserve_and_confirmation(
        self, cpf: str, averbadora, codigo_convenio, contrato
    ):
        customer_benefit_card = contrato.cliente_cartao_contrato.get()
        _, _, _, _, convenios = get_dados_convenio(averbadora, codigo_convenio)
        cod_convenio = convenios.cod_convenio

        margins_to_reserve = []
        reserved_margins = []
        margin_reserve_confirmation_response = None

        if customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA:
            margins_to_reserve.extend((
                {
                    'valor': customer_benefit_card.margem_compra,
                    'verba': customer_benefit_card.verba_compra,
                    'folha': customer_benefit_card.folha_compra,
                    'reserva': customer_benefit_card.reserva_compra,
                    'tipo_margem': EnumTipoMargem.MARGEM_COMPRA,
                },
                {
                    'valor': customer_benefit_card.margem_saque,
                    'verba': customer_benefit_card.verba_saque,
                    'folha': customer_benefit_card.folha_saque,
                    'reserva': customer_benefit_card.reserva_saque,
                    'tipo_margem': EnumTipoMargem.MARGEM_SAQUE,
                },
            ))
        elif customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_SAQUE:
            # Margem Saque
            margins_to_reserve.append({
                'valor': customer_benefit_card.margem_saque,
                'verba': customer_benefit_card.verba_saque,
                'folha': customer_benefit_card.folha_saque,
                'reserva': customer_benefit_card.reserva_saque,
                'tipo_margem': EnumTipoMargem.MARGEM_SAQUE,
            })
        elif customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_COMPRA:
            # Margem Compra
            margins_to_reserve.append({
                'valor': customer_benefit_card.margem_compra,
                'verba': customer_benefit_card.verba_compra,
                'folha': customer_benefit_card.folha_compra,
                'reserva': customer_benefit_card.reserva_compra,
                'tipo_margem': EnumTipoMargem.MARGEM_COMPRA,
            })
        elif customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_UNICA:
            # Margem Unica
            margins_to_reserve.append({
                'valor': customer_benefit_card.margem_atual,
                'verba': customer_benefit_card.verba,
                'folha': customer_benefit_card.folha,
                'reserva': customer_benefit_card.reserva,
                'tipo_margem': EnumTipoMargem.MARGEM_UNICA,
            })

        for selected_margin_to_reserve in margins_to_reserve:
            margin_reserve_response = self.margin_reserve(
                cpf=cpf,
                codigo_convenio=cod_convenio,
                customer_benefit_card=customer_benefit_card,
                margin_to_reserve=selected_margin_to_reserve,
            )

            if (
                isinstance(margin_reserve_response, RealizaReserva)
                and margin_reserve_response.descricao
            ):
                return margin_reserve_response

            margin_reserve_confirmation_response = self.margin_reserve_confirm(
                cpf=cpf,
                cod_convenio=cod_convenio,
                customer_benefit_card=customer_benefit_card,
                margin_to_reserve=selected_margin_to_reserve,
            )

            if (
                isinstance(margin_reserve_response, RealizaReserva)
                and margin_reserve_response.descricao
            ):
                self.cancel_margin_reserve(
                    cpf=cpf,
                    codigo_convenio=codigo_convenio,
                    averbadora=averbadora,
                    contrato=contrato.pk,
                )
                return margin_reserve_response

            reserved_margins.append(margin_reserve_confirmation_response)

        return margin_reserve_confirmation_response

    def cancel_margin_reserve(self, cpf: str, averbadora, codigo_convenio, contrato):
        cliente = consulta_cliente(cpf)
        contrato = Contrato.objects.get(pk=contrato)
        customer_benefit_card = contrato.cliente_cartao_contrato.get()
        _, _, _, _, convenios = get_dados_convenio(averbadora, codigo_convenio)
        cod_convenio = convenios.cod_convenio

        margins_to_cancel = []
        canceled_margins = []
        cancela_reserva_obj = None

        if customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA:
            margins_to_cancel.extend((
                {
                    'matricula': customer_benefit_card.numero_matricula,
                    'reserva': customer_benefit_card.reserva_compra,
                },
                {
                    'matricula': customer_benefit_card.numero_matricula,
                    'reserva': customer_benefit_card.reserva_saque,
                },
            ))
        elif customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_SAQUE:
            # Margem Saque
            margins_to_cancel.append({
                'matricula': customer_benefit_card.numero_matricula,
                'reserva': customer_benefit_card.reserva_saque,
            })
        elif customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_COMPRA:
            # Margem Compra
            margins_to_cancel.append({
                'matricula': customer_benefit_card.numero_matricula,
                'reserva': customer_benefit_card.reserva_compra,
            })
        elif customer_benefit_card.tipo_margem == EnumTipoMargem.MARGEM_UNICA:
            # Margem Unica
            margins_to_cancel.append({
                'matricula': customer_benefit_card.numero_matricula,
                'reserva': customer_benefit_card.reserva,
            })

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        for margin_to_cancel in margins_to_cancel:
            response, payload = self._cancel_margin_reserve_request(
                cpf=cpf,
                matricula=margin_to_cancel['matricula'],
                cod_convenio=cod_convenio,
                numero_contrato=contrato,
                id_contrato=margin_to_cancel['reserva'],
            )
            response_text = json.loads(response.text)

            try:
                cancelada = response_text['cancelada']

                cancela_reserva_obj, _ = CancelaReserva.objects.update_or_create(
                    log_api_id=log_api_id.pk,
                    cliente=cliente,
                    matricula=margin_to_cancel['matricula'],
                    reserva=margin_to_cancel['reserva'],
                    cancelada=cancelada,
                )

                canceled_margins.append(cancela_reserva_obj)
            except Exception as e:
                print(e)
                cancela_reserva_obj = CancelaReserva.objects.create(
                    log_api_id=log_api_id.pk,
                    cliente=cliente,
                    descricao=response_text['descricao'],
                    codigo_retorno=response_text['codigoRetorno'],
                )

                canceled_margins.append(cancela_reserva_obj)

            ConsultaAverbadora.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                payload_envio=payload,
                payload=response_text,
                tipo_chamada='Cancela Reserva',
            )

        return cancela_reserva_obj
