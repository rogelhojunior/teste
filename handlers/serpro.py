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
from contract.products.cartao_beneficio.models.convenio import (
    ClassificacaoSiape,
    ConvenioSiape,
    SubOrgao,
    TipoVinculoSiape,
)
from core.models.cliente import ClienteCartaoBeneficio
from core.utils import consulta_cliente, get_dados_convenio

logger = logging.getLogger('digitacao')


class Serpro:
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

    def _registrations_and_margins_consult_request(self, cpf: str) -> requests.Response:
        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora,
                'operacao': 'consultarMatriculaMargem',
            },
            'cliente': {
                'nuCpf': cpf,
            },
        }

        return self._request(method=method, payload=payload)

    def _margin_reserve_request(
        self,
        cpf: str,
        registration_number: str,
        contract_id: int,
        card_limit_value: float,
    ) -> requests.Response:
        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora,
                'operacao': 'reservarMargem',
            },
            'cliente': {
                'nuCpf': cpf,
                'nuMatricula': registration_number,
            },
            'contrato': {
                'idContrato': contract_id,
                'valorLimiteCartao': card_limit_value,
            },
        }

        return self._request(method=method, payload=payload)

    def _margin_reserve_cancel_request(
        self,
        cpf: str,
        registration_number: str,
        contract_id: int,
    ) -> requests.Response:
        method = 'POST'
        payload = {
            'averbadora': {
                'nomeAverbadora': self.averbadora,
                'operacao': 'cancelarMargem',
            },
            'cliente': {
                'nuCpf': cpf,
                'nuMatricula': registration_number,
            },
            'contrato': {
                'idContrato': contract_id,
            },
        }

        return self._request(method=method, payload=payload)

    def registrations_consult(self, cpf: str, codigo_convenio: str) -> dict:
        response = self._registrations_and_margins_consult_request(cpf=cpf)

        if response.status_code != 200:
            logger.error(
                f'Não foi possível consultar a matrícula para o servidor {cpf}',
                exc_info=True,
            )
            return [], 'Erro_Consulta'

        _, _, _, _, convenios = get_dados_convenio(self.averbadora, codigo_convenio)

        response_json = response.json()

        valid_matriculas_data = []

        try:
            suborgaos = SubOrgao.objects.filter(convenio=convenios, ativo=True)

            if not suborgaos.exists():
                raise Exception(
                    'Não foi possível consultar a matrícula - Nenhum Sub-Orgão cadastrado nesse Convênio para essa averbadora'
                )

            # Liste os códigos de folha ativos
            active_folha_codes = [suborgao.codigo_folha for suborgao in suborgaos]
            registrations_and_margins = response_json.get(
                'registrations_and_margins', []
            )
            valid_matriculas_data.extend(
                registration_and_margin
                for registration_and_margin in registrations_and_margins
                if int(registration_and_margin['folha']) in active_folha_codes
            )
            if not valid_matriculas_data:
                raise Exception(
                    'Não foi possível consultar a matrícula - Nenhum Sub-Orgão cadastrado nesse Convênio para essa averbadora'
                )

        except Exception as e:
            logger.error(str(e), exc_info=True)
            return [], 'SubOrgao_Vazio'

        try:
            cliente = consulta_cliente(cpf)

            log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

            ConsultaAverbadora.objects.create(
                log_api_id=log_api_id.pk,
                tipo_chamada='Consulta Matricula',
                cliente=cliente,
                payload_envio=response.request.body,
                payload=response_json,
            )

            cliente.nome_cliente = response_json.get('nome')
            cliente.save()

            for valid_matricula in valid_matriculas_data:
                valid_matricula['cliente'] = {
                    'id': cliente.pk,
                    'nome_cliente': cliente.nome_cliente,
                }

            logger.info(f'{cliente.id_unico} - Matrícula consultada com sucesso.')

        except Exception as e:
            logger.error(f'Erro ao consultar matrícula. {e}', exc_info=True)

        return valid_matriculas_data, 'Erro_Consulta'

    def margins_consult(
        self, cpf: str, codigo_convenio: str, numero_matricula: str
    ) -> list:
        response = self._registrations_and_margins_consult_request(cpf=cpf)
        response_json = response.json()

        _, _, _, _, convenios = get_dados_convenio(self.averbadora, codigo_convenio)

        # Trate erros primeiro
        if 'descricao' in response_json:
            return {
                'descricao': response_json['descricao'],
                'codigo_retorno': response_json['codigoRetorno'],
            }
        # Tratar caso bem-sucedido
        try:
            registrations_and_margins = response_json.get(
                'registrations_and_margins', []
            )

            margens_obj = []

            for registration_and_margin in registrations_and_margins:
                margem_atual = registration_and_margin.get('margem_atual')
                verba = registration_and_margin.get('verba')
                folha = registration_and_margin.get('folha')
                matricula = registration_and_margin.get('numeroMatricula')

                codClassificacao = registration_and_margin.get('codClassificacao')
                codTipoVinc = registration_and_margin.get('codTipoVinc')
                cdConvenio = registration_and_margin.get('cdConvenio')
                orgMatInst = registration_and_margin.get('orgMatInst')

                if numero_matricula and (numero_matricula != matricula):
                    continue

                # Verificar SubOrgao
                suborgaos = SubOrgao.objects.filter(convenio=convenios, ativo=True)
                if not suborgaos.exists():
                    logger.error(
                        f'{cpf} - Não foi possível consultar a margem - Nenhum Sub-Orgão cadastrado nesse Convênio para a averbadora {self.averbadora}',
                        exc_info=True,
                    )
                    continue

                # Liste os códigos de folha ativos
                active_folha_codes = [suborgao.codigo_folha for suborgao in suborgaos]

                if folha not in active_folha_codes:
                    continue

                # Verificar Tipo Vinculo - SIAPE
                listTipoVinc = TipoVinculoSiape.objects.filter(
                    convenio=convenios, permite_contratacao=True
                )
                if not listTipoVinc.exists():
                    logger.error(
                        f'{cpf} - Não foi possível consultar a margem - Nenhum Tipo Vinculo - SIAPE cadastrado nesse Convênio para a averbadora {self.averbadora}',
                        exc_info=True,
                    )
                    continue

                active_tipoVinc_codes = [
                    tipoVincSiape.codigo for tipoVincSiape in listTipoVinc
                ]

                if codTipoVinc not in active_tipoVinc_codes:
                    continue

                # Verificar Classificacao - SIAPE
                listCodClassificacao = ClassificacaoSiape.objects.filter(
                    convenio=convenios, permite_contratacao=True
                )
                if not listCodClassificacao.exists():
                    logger.error(
                        f'{cpf} - Não foi possível consultar a margem - Nenhum Classificação - SIAPE cadastrado nesse Convênio para a averbadora {self.averbadora}',
                        exc_info=True,
                    )
                    continue

                active_classificacao_codes = [
                    classificacaoSiape.codigo
                    for classificacaoSiape in listCodClassificacao
                ]

                if int(codClassificacao) not in active_classificacao_codes:
                    continue

                # Verificar Classificacao - SIAPE
                listCdConvenio = ConvenioSiape.objects.filter(
                    convenio=convenios, permite_contratacao=True
                )
                if not listCodClassificacao.exists():
                    logger.error(
                        f'{cpf} - Não foi possível consultar a margem - Nenhum Convênnio - SIAPE cadastrado nesse Convênio para a averbadora {self.averbadora}',
                        exc_info=True,
                    )
                    continue

                active_convenio_siape_codes = [
                    convenioSiape.codigo for convenioSiape in listCdConvenio
                ]

                if int(cdConvenio) not in active_convenio_siape_codes:
                    continue

                if codTipoVinc == 'S':
                    codTipoVinc = 'Servidor'
                elif codTipoVinc == 'P':
                    codTipoVinc = 'Pensionista'

                margem_obj = {
                    'nome_cliente': response_json.get('nome'),
                    'margem_atual': margem_atual or '0.00',
                    'verba': verba,
                    'tipoMargem': verba,
                    'folha': folha,
                    'matricula': matricula,
                    'convenio_SIAPE': cdConvenio,
                    'tipoVinc_SIAPE': codTipoVinc,
                    'classifica_SIAPE': codClassificacao,
                    'instituidor': orgMatInst,
                    'cargo': None,
                    'estavel_bool': None,
                    'nascimento': None,
                }

                margens_obj.append(margem_obj)

            logger.info(f'{cpf} - Margem consultada na averbadora {self.averbadora}')

        except Exception as e:
            logger.error(
                f'{cpf} - Erro ao consultar margem na averbadora {self.averbadora}, {e}',
                exc_info=True,
            )

        return margens_obj

    def margin_reserve(
        self,
        cpf: str,
        registration_number: str,
        contract_id: int,
        card_limit_value: float,
        codigo_convenio: str,
    ) -> dict:
        response = self._margin_reserve_request(
            cpf=cpf,
            registration_number=registration_number,
            contract_id=contract_id,
            card_limit_value=card_limit_value,
        )

        response_json = response.json()

        cliente = consulta_cliente(cpf)
        cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.filter(
            cliente=cliente
        ).first()

        verba = cliente_cartao_beneficio.verba

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        try:
            matricula = response_json.get(
                'numeroMatricula', cliente_cartao_beneficio.numero_matricula
            )
            verba = response_json.get('verba', cliente_cartao_beneficio.verba)
            folha = response_json.get('folha', cliente_cartao_beneficio.folha)

            cliente_cartao_beneficio.numero_matricula = matricula
            cliente_cartao_beneficio.verba = verba
            cliente_cartao_beneficio.folha = folha
            # cliente_cartao_beneficio.valor = response_json['valor'] Variável não existe em ClienteCartaoBeneficio
            # cliente_cartao_beneficio.reserva = response_json['reserva']
            cliente_cartao_beneficio.save()

            realiza_reserva_obj, _ = RealizaReserva.objects.update_or_create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                matricula=matricula,
                folha=folha,
                verba=verba,
                # valor=response_json['valor'],
                # reserva=response_json['reserva'],
            )
        except Exception as e:
            print(e)
            realiza_reserva_obj = RealizaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                descricao=response_json['dsRetCode'],
                codigo_retorno=response_json['cdRetCode'],
            )
        ConsultaAverbadora.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            payload_envio=response.request.body,
            payload=response_json,
            tipo_chamada='Realiza Reserva',
        )

        return realiza_reserva_obj

    def margin_reserve_cancel(
        self, cpf: str, registration_number: str, contract_id: int, codigo_convenio: str
    ) -> dict:
        response = self._margin_reserve_cancel_request(
            cpf=cpf,
            registration_number=registration_number,
            contract_id=contract_id,
        )
        response_json = response.json()

        cliente = consulta_cliente(cpf)

        cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.filter(
            cliente=cliente
        ).first()

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)

        try:
            cancelada = response_json.get('cd_ret_code') == '0000'

            cancela_reserva_obj, _ = CancelaReserva.objects.update_or_create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                matricula=cliente.numero_matricula,
                reserva=cliente_cartao_beneficio.reserva,
                cancelada=cancelada,
            )

        except Exception as e:
            print(e)
            cancela_reserva_obj = CancelaReserva.objects.create(
                log_api_id=log_api_id.pk,
                cliente=cliente,
                descricao=response_json.get('ds_ret_code'),
                codigo_retorno=response_json.get('cd_ret_code'),
            )

        ConsultaAverbadora.objects.create(
            log_api_id=log_api_id.pk,
            cliente=cliente,
            payload_envio=response.request.body,
            payload=response_json,
            tipo_chamada='Cancela Reserva',
        )

        return cancela_reserva_obj
