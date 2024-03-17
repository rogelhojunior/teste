import json
import logging
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal

import boto3
import paramiko
import requests
from celery import shared_task
from django.conf import settings
from django.contrib import messages
from django.db.models import Max, Q
from django.utils import timezone

from api_log.models import LogWebhook, RealizaReserva
from contract.constants import (
    EnumArquivosSeguros,
    EnumContratoStatus,
    EnumTipoAnexo,
    EnumTipoProduto,
    NomeAverbadoras,
)
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import (
    CartaoBeneficio,
    Contrato,
    MargemLivre,
    Portabilidade,
    Refinanciamento,
)
from dateutil.relativedelta import relativedelta
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.api.views import create_dados_beneficio
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.cartao_beneficio.models.convenio import (
    EspecieBeneficioINSS,
    PensaoAlimenticiaINSS,
)
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from contract.serializers import AtualizarContratoSerializer
from contract.utils import atualizar_status_contratos
from core.common.enums import EnvironmentEnum
from core.constants import EnumCanalAutorizacaoDigital, EnumTipoConta
from core.models import DossieINSS, BeneficiosContratado, Cliente
from contract.models.contratos import Contrato
from core.models.aceite_in100 import AceiteIN100, DadosBeneficioIN100
from core.models.arquivos_generali import ArquivoGenerali
from core.models.cliente import DadosBancarios, ClienteCartaoBeneficio
from core.settings import ENVIRONMENT
from core.utils import alterar_status, exclude_all_check_rules
from custom_auth.models import Produtos, UserProfile, FeatureToggle
from handlers.consultas import consulta_regras_hub, url_to_base64, is_pdf
from handlers.converters import convert_pdf_base64_to_image
from handlers.in100_cartao import (
    autorizacao_consulta_digital,
    consulta_beneficio,
    consulta_margem_inss,
)
from handlers.insere_proposta_inss_financeira import (
    autenticacao_hub,
    formatar_cpf,
    separar_numero_ddd,
    traduzir_tipo_conta,
)
from handlers.insere_proposta_portabilidade_financeira import (
    traduzir_estado_civil,
    traduzir_sexo,
)
from handlers.valida_beneficio_in100 import ValidadorBeneficio
from handlers.validar_regras_beneficio_contrato import (
    ValidadorRegrasBeneficioContratoMargemLivre,
)
from contract.constants import (
    EnumContratoStatus,
    EnumTipoPlano,
    EnumTipoProduto,
    NomeAverbadoras,
)
from contract.products.cartao_beneficio.validators.arquivo_posicionais import (
    ajustar_posicoes,
    check_data_in_last,
    check_plano,
    get_maior_sequencial,
    remove_first_line_starting_with,
    write_initial_content,
    write_trailer,
    escrever_arrecadacao,
    count_reg,
    identificar_parcela,
    check_data_in_range,
)

logger = logging.getLogger('digitacao')


@shared_task
def validar_contrato_assync(payload, token_envelope, numero_cpf, user):
    from contract.api.views import finalizar_formalizacao
    from contract.api.views import valida_status_score
    from contract.constants import STATUS_REPROVADOS
    from documentscopy.services import analyse_cpf

    contratos = Contrato.objects.filter(token_envelope=token_envelope)
    contratos_com_erro = []
    contratos_com_documentos_pendentes = []
    for contrato in contratos:
        if not StatusContrato.objects.filter(
            contrato=contrato,
            nome__in=STATUS_REPROVADOS,
        ).exists():
            produto = Produtos.objects.filter(
                tipo_produto=contrato.tipo_produto
            ).first()
            if contrato.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
                produto = Produtos.objects.filter(
                    tipo_produto=EnumTipoProduto.CARTAO_BENEFICIO
                ).first()
            serializer = AtualizarContratoSerializer(
                contrato, data=payload, partial=True
            )
            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                cartao_beneficio = CartaoBeneficio.objects.filter(
                    contrato=contrato
                ).first()
                if contrato.is_main_proposal and contrato.envelope.status_unico:
                    if settings.ENVIRONMENT != EnvironmentEnum.PROD.value:
                        analyse_cpf(contrato, cartao_beneficio)
                    else:
                        valida_status_score(
                            contrato,
                            cartao_beneficio,
                            contrato.envelope.erro_unico,
                            contrato.envelope.erro_restritivo_unico,
                        )
                error, erro_restritivo = process_contrato(
                    contrato, cartao_beneficio, serializer, numero_cpf, produto
                )
            elif contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                contrato_portabilidade = Portabilidade.objects.filter(
                    contrato=contrato
                ).first()
                if contrato.is_main_proposal and contrato.envelope.status_unico:
                    analyse_cpf(contrato, contrato_portabilidade)
                error, erro_restritivo = process_contrato(
                    contrato, contrato_portabilidade, serializer, numero_cpf, produto
                )
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refin = Refinanciamento.objects.get(contrato=contrato)
                    port = Portabilidade.objects.get(contrato=contrato)
                    port.refresh_from_db()
                    refin.status = port.status
                    refin.save(update_fields=['status'])
            elif contrato.tipo_produto in (EnumTipoProduto.MARGEM_LIVRE,):
                contrato_margem_livre = MargemLivre.objects.filter(
                    contrato=contrato
                ).first()
                if contrato.is_main_proposal and contrato.envelope.status_unico:
                    analyse_cpf(contrato, contrato_margem_livre)
                error, erro_restritivo = process_contrato(
                    contrato, contrato_margem_livre, serializer, numero_cpf, produto
                )
            else:
                continue

            if error or erro_restritivo:
                contratos_com_erro.append(contrato.pk)

            elif produto.comprovante_residencia and produto.documento_pessoal:
                if (
                    not contrato.enviado_comprovante_residencia
                    and not contrato.enviado_documento_pessoal
                ):
                    contratos_com_documentos_pendentes.append(contrato.pk)

            elif produto.comprovante_residencia:
                if not contrato.enviado_comprovante_residencia:
                    contratos_com_documentos_pendentes.append(contrato.pk)

            elif produto.documento_pessoal:
                if not contrato.enviado_documento_pessoal:
                    contratos_com_documentos_pendentes.append(contrato.pk)
            contrato.regras_validadas = True
            contrato.save()

    user = UserProfile.objects.get(identifier=user)
    finalizar_formalizacao(token_envelope, user)

    if contratos_com_erro or contratos_com_documentos_pendentes:
        logger.info({
            'msg': 'Alguns contratos apresentaram problemas.',
            'contratos_com_erro': contratos_com_erro,
            'contratos_com_documentos_pendentes': contratos_com_documentos_pendentes,
        })

    else:
        logger.info(f'{token_envelope} - Todos os contratos atualizados com sucesso.')


def process_contrato(contrato, campo_status, serializer, numero_cpf, produto):
    from documentscopy.services import BPOProcessor

    try:
        if not serializer.is_valid():
            return True, False

        contrato_set = serializer.save()

        if not contrato_set:
            return True, False

        elif produto.comprovante_residencia and produto.documento_pessoal:
            if (
                not contrato.enviado_comprovante_residencia
                and not contrato.enviado_documento_pessoal
            ):
                return False, False

        elif produto.documento_pessoal:
            if not contrato.enviado_documento_pessoal:
                return False, False

        elif produto.comprovante_residencia:
            if not contrato.enviado_comprovante_residencia:
                return False, False

        consulta_bureau = consulta_regras_hub(numero_cpf, contrato)
        consulta_regras = consulta_bureau['regras']

        error, erro_restritivo = process_regras_contrato(contrato, consulta_regras)

        if contrato.is_main_proposal and not erro_restritivo:
            processor = BPOProcessor(contrato, campo_status)

            if processor.bpo is not None:
                return error, erro_restritivo

        save_contract_status(contrato, campo_status, error, erro_restritivo)

        if not erro_restritivo:
            # TODO: Remove card paradinha feature flag
            feature_flagged_condition = contrato.is_main_proposal
            if settings.ENVIRONMENT != EnvironmentEnum.PROD.value:
                is_port_or_refin = contrato.tipo_produto in (
                    EnumTipoProduto.PORTABILIDADE,
                    EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
                )
                feature_flagged_condition = (
                    not is_port_or_refin or contrato.is_main_proposal
                )

            if feature_flagged_condition:
                proposal_status = (
                    ContractStatus.CHECAGEM_MESA_CORBAN.value
                    if contrato.corban and contrato.corban.mesa_corban
                    else ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                )
            else:
                proposal_status = (
                    ContractStatus.AGUARDA_FINALIZACAO_PROPOSTA_PRINCIPAL.value
                )

            campo_status.status = proposal_status
            campo_status.save()
            StatusContrato.objects.create(
                contrato=contrato,
                nome=proposal_status,
            )
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                refin = Refinanciamento.objects.get(contrato=contrato)
                port = Portabilidade.objects.get(contrato=contrato)
                port.refresh_from_db()
                refin.status = port.status
                refin.save(update_fields=['status'])

        return error, erro_restritivo
    except Exception as e:
        logger.error(
            f'{contrato.cliente.id_unico} - Ocorreu um erro ao realizar a chamada do hub, contate o suporte. {e}'
        )


def process_regras_contrato(contrato, consulta_regras):
    error = False
    erro_restritivo = False
    consulta_regras = exclude_all_check_rules(consulta_regras)
    for elemento in consulta_regras:
        descricao = elemento['descricao']
        regra_aprovada, restritiva, msg = process_regra_aprovada(elemento)

        if ValidacaoContrato.objects.filter(
            contrato=contrato, mensagem_observacao=descricao
        ).exists():
            validar_check = ValidacaoContrato.objects.get(
                contrato=contrato, mensagem_observacao=descricao
            )

            validar_check.checked = regra_aprovada
            validar_check.retorno_hub = msg
            validar_check.save()
        else:
            ValidacaoContrato.objects.create(
                contrato=contrato,
                mensagem_observacao=descricao,
                checked=regra_aprovada,
                retorno_hub=msg,
            )

        if restritiva and not regra_aprovada:
            erro_restritivo = True

        if not restritiva and not regra_aprovada:
            error = True

    return error, erro_restritivo


def process_regra_aprovada(elemento):
    regra_aprovada = elemento['regra_aprovada']
    restritiva = elemento['restritiva']
    descricao = elemento.get('descricao', '')
    msg = ''
    erro_ocr = False
    erro_endereco = False
    ocr = False
    endereco = False

    if regra_aprovada is not True and regra_aprovada is not False:
        if 'ocr' in regra_aprovada:
            ocr = True
        if 'endereco' in regra_aprovada:
            endereco = True
    if ocr:
        regra_ocr = regra_aprovada.get('ocr')
        for regras_validadas in regra_ocr:
            if not regras_validadas['aprovada']:
                msg += f"{regras_validadas['campo']}-> Cliente: {regras_validadas['backoffice']}, Documento: {regras_validadas['most']}\n"
                erro_ocr = True
        regra_aprovada = not erro_ocr
    if endereco:
        regra_endereco = regra_aprovada.get('endereco')
        for regras_validadas in regra_endereco:
            if not regras_validadas['aprovada']:
                msg += f"{regras_validadas['campo']}-> Cliente: {regras_validadas['backoffice']}, Documento: {regras_validadas['most']}\n"
                erro_endereco = True
        regra_aprovada = not erro_endereco
    if 'NOME_MAE' in descricao and not regra_aprovada:
        msg += elemento.get('msg', '')

    return regra_aprovada, restritiva, msg


def save_contract_status(contrato, campo_status, error, erro_restritivo):
    if error:
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        # if contrato.tipo_produto in (
        #     EnumTipoProduto.CARTAO_BENEFICIO,
        #     EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
        #     EnumTipoProduto.CARTAO_CONSIGNADO,
        # ):
        #     if (
        #         campo_status.convenio.convenio_inss
        #         and campo_status.convenio.digitacao_manual
        #     ):
        #         if (
        #             ultimo_status.nome
        #             != ContractStatus.ANDAMENTO_CHECAGEM_DATAPREV.value
        #         ):
        #             alterar_status(
        #                 contrato,
        #                 campo_status,
        #                 EnumContratoStatus.MESA,
        #                 ContractStatus.ANDAMENTO_CHECAGEM_DATAPREV.value,
        #             )
        #     else:
        #         if (
        #             ultimo_status.nome
        #             != ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
        #         ):
        #             contrato.status = EnumContratoStatus.MESA
        #             if campo_status:
        #                 campo_status.status = (
        #                     ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
        #                 )
        #             StatusContrato.objects.create(
        #                 contrato=contrato,
        #                 nome=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
        #             )

        if contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            EnumTipoProduto.MARGEM_LIVRE,
        ):
            corban_flag = contrato.corban
            contrato.status = EnumContratoStatus.MESA
            if contrato.is_main_proposal:
                if corban_flag.mesa_corban and ultimo_status.nome not in [
                    ContractStatus.CHECAGEM_MESA_CORBAN.value,
                    ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                    ContractStatus.REPROVADO.value,
                ]:
                    if campo_status:
                        campo_status.status = ContractStatus.CHECAGEM_MESA_CORBAN.value
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.CHECAGEM_MESA_CORBAN.value,
                        descricao_mesa='Algumas regras nao foram atendidas',
                    )
                else:
                    if campo_status:
                        campo_status.status = (
                            ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value
                        )
                    StatusContrato.objects.create(
                        contrato=contrato,
                        nome=ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
                        descricao_mesa='Algumas regras nao foram atendidas',
                    )

    if erro_restritivo:
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            if ultimo_status.nome != ContractStatus.REPROVADA_FINALIZADA.value:
                contrato.status = EnumContratoStatus.MESA
                if campo_status:
                    campo_status.status = ContractStatus.REPROVADA_FINALIZADA.value
                StatusContrato.objects.create(
                    contrato=contrato, nome=ContractStatus.REPROVADA_FINALIZADA.value
                )

        elif contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            EnumTipoProduto.MARGEM_LIVRE,
        ):
            if ultimo_status.nome != ContractStatus.REPROVADA_POLITICA_INTERNA.value:
                contrato.status = EnumContratoStatus.MESA
                if campo_status:
                    campo_status.status = (
                        ContractStatus.REPROVADA_POLITICA_INTERNA.value
                    )
                StatusContrato.objects.create(
                    contrato=contrato,
                    nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                )

    if campo_status:
        campo_status.save()

    contrato.save()


def mock(size, char):
    return ''.rjust(size, char)


def format_telefone(telefone):
    if telefone is None:
        return ''.rjust(3, '0'), ''.ljust(9, '0')
    telefone_formatado = (
        f'{telefone}'.replace('(', '')
        .replace(')', '')
        .replace('-', '')
        .replace(' ', '')
    )
    ddd = telefone_formatado[:2].rjust(3, '0')
    numero = telefone_formatado[2:].ljust(9, '0')[-9:]
    return ddd, numero


def get_maior_sequencial(nome_archive):
    try:
        maior_sequencial = ArquivoGenerali.objects.filter(
            nmDocumento__contains=nome_archive
        ).aggregate(Max('sequencial'))['sequencial__max']
        return maior_sequencial if maior_sequencial is not None else 0
    except ArquivoGenerali.DoesNotExist:
        return 1


def generate_nome_arquivo(operacao_sequencial, maior_sequencial, today):
    maior_sequencial_nome = f'{maior_sequencial:06}'
    return (
        f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"
    )


def send_archive_to_ftp(local_file_path, nome_arquivo, chamado):
    try:
        # Informações do servidor FTP

        ftp_host = settings.GENREALI_FTP_HOST
        ftp_user = settings.GENREALI_FTP_USER
        ftp_password = settings.GENREALI_FTP_PASSWORD
        ftp_port = settings.GENREALI_FTP_PORT
        remote_directory = f'{settings.GENERALI_FTP_PATH}'.replace('NAME', chamado)

        # Nome do arquivo remoto
        transport = paramiko.Transport(str(ftp_host), int(ftp_port))
        transport.connect(username=ftp_user, password=ftp_password)
        logger.info('Conectado no SFTP')
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.chdir(remote_directory)
        logger.info(f'Alterado para o {remote_directory}')
        logger.info(f'O arquivo esta vindo do {local_file_path.name}')
        sftp.put(f'{local_file_path.name}', f'{nome_arquivo}')
        logger.info(f'o arquivo foi enviado para {remote_directory}/teste.txt')
    except IOError as e:
        logger.error(f'Erro de IO ao enviar arquivo via SFTP: {e}')
    except Exception as e:
        logger.error(f'Erro desconhecido ao enviar arquivo via SFTP: {e}')


# def write_initial_content(destino, today_str, sequencial_do_registro, chamado):
#     destino.write(
#         f"0{chamado['produto']}{chamado['apolice']}{today_str}{'000001'}{'1.8'.ljust(6, ' ')}{chamado['cd_operacao']}{mock(1254, ' ')}{sequencial_do_registro}\n"
#     )


def check_second_line(filename):
    try:
        with open(filename, 'r') as file:
            lines = file.readlines()
            print(lines)
            return bool(lines[1].strip()) if len(lines) >= 2 else False
    except Exception as e:
        logger.error(f'erro {e}')
        return False


# Configurar o cliente do S3
s3 = boto3.client('s3')


@shared_task()
def process_and_upload_file():
    """
    Processa um arquivo baixado do S3 e, se necessário, carrega-o em um servidor FTP.
    """

    if settings.ORIGIN_CLIENT == 'PINE':
        operacao_sequencial_lista = [
            'BANCOPINEVIDA',
            'BANCOPINESIAPE',
            'BANCOPINEPRESTINSSOURO',
            'BANCOPINEPRESTCPOURO',
            'BANCOPINEPRESTINSSDIAMANTE',
            'BANCOPINEPRESTCPDIAMANTE',
        ]

    elif settings.ORIGIN_CLIENT == 'BRB':
        operacao_sequencial_lista = 'BRBVIDAINSS'

    # TODO: Ajustar quando tiver funcionalidade da Digimais
    elif settings.ORIGIN_CLIENT == 'DIGIMAIS':
        operacao_sequencial_lista = ['BANCOPINEVIDA']

    for operacao_sequencial in operacao_sequencial_lista:
        maior_sequencial = (
            get_maior_sequencial(operacao_sequencial)
            if get_maior_sequencial(operacao_sequencial) > 0
            else 1
        )
        maior_sequencial_nome = f'{maior_sequencial}'.rjust(6, '0')

        today = datetime.now()

        nomeArquivo = f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"

        # Crie um diretório temporário para trabalhar com o arquivo
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, nomeArquivo)

            # Baixe o arquivo do S3 para o diretório temporário
            try:
                s3.download_file(settings.BUCKET_SEGUROS, nomeArquivo, local_path)
            except Exception as e:
                logger.error(f'Erro ao baixar o arquivo {nomeArquivo} do S3:', e)
                print(f'Erro ao baixar o arquivo {nomeArquivo} do S3:', e)

            # Verifique a segunda linha do arquivo
            if check_second_line(local_path):
                with open(local_path, 'r') as destino:
                    send_archive_to_ftp(
                        destino, nomeArquivo, operacao_sequencial
                    )  # ENVIA O ARQUIVO PARA O FTP
                logger.error(f'Arquivo {nomeArquivo} processado e enviado com sucesso:')
                ArquivoGenerali.objects.create(
                    nmDocumento=nomeArquivo,
                    sequencial=(
                        maior_sequencial + 1 if maior_sequencial + 1 is not None else 0
                    ),
                ).save()

            logger.error('Não existe arquivo')


class PropostaInsercaoMargemLivre:
    def __init__(self, contrato, tx_mes_contrato, nm_base_jurus, tx_multa_contrato):
        self.contrato = contrato
        self.tx_mes_contrato = tx_mes_contrato
        self.nm_base_jurus = nm_base_jurus
        self.tx_multa_contrato = tx_multa_contrato
        self.response = None
        self.decoded_response = None

    def _prepare_data(self):
        self.contrato_margem_livre = MargemLivre.objects.filter(
            contrato=self.contrato
        ).first()
        self.in100 = DadosIn100.objects.filter(
            numero_beneficio=self.contrato.numero_beneficio
        ).first()
        self.dados_bancarios_cliente = DadosBancarios.objects.filter(
            Q(cliente=self.contrato.cliente)
            & (
                Q(conta_tipo=EnumTipoConta.CORRENTE_PESSOA_FISICA)
                | Q(conta_tipo=EnumTipoConta.POUPANCA_PESSOA_FISICA)
            )
        ).last()

        self.nu_ddd_telefone, self.nu_telefone = separar_numero_ddd(
            str(self.contrato.cliente.telefone_celular)
        )
        self.headers = {
            'Authorization': f'Bearer {autenticacao_hub()}',
            'Content-Type': 'application/json',
        }
        numero_banco = self.dados_bancarios_cliente.conta_banco
        partes = numero_banco.split()
        numero_conta_banco = partes[0]
        if self.contrato.cliente.documento_tipo in ['2', 2]:
            tipo_documento = 'cnh'
        if self.contrato.cliente.documento_tipo in ['1', 1]:
            tipo_documento = 'rg'
        disbursement_date_str = str(self.contrato_margem_livre.dt_desembolso)
        self.payload = {
            'NmEndpoint': 'debt',
            'NmVerb': 'POST',
            'JsonBody': {
                'borrower': {
                    'is_pep': False,
                    'name': self.contrato.cliente.nome_cliente,
                    'gender': traduzir_sexo(self.contrato.cliente.sexo),
                    'marital_status': traduzir_estado_civil(
                        self.contrato.cliente.estado_civil
                    ),
                    'document_identification_number': self.contrato.cliente.documento_numero,
                    'document_identification_type': tipo_documento,
                    'document_identification_date': str(
                        self.contrato.cliente.documento_data_emissao
                    ),
                    'phone': {
                        'country_code': '055',
                        'area_code': self.nu_ddd_telefone,
                        'number': self.nu_telefone,
                    },
                    'address': {
                        'street': self.contrato.cliente.endereco_logradouro,
                        'state': self.contrato.cliente.endereco_uf,
                        'city': self.contrato.cliente.endereco_cidade,
                        'neighborhood': self.contrato.cliente.endereco_bairro,
                        'number': str(self.contrato.cliente.endereco_numero),
                        'postal_code': self.contrato.cliente.endereco_cep,
                        'complement': self.contrato.cliente.endereco_complemento,
                    },
                    'role_type': 'issuer',
                    'birth_date': str(self.contrato.cliente.dt_nascimento),
                    'mother_name': self.contrato.cliente.nome_mae,
                    'person_type': 'natural',
                    'nationality': 'Brasileiro',
                    'individual_document_number': formatar_cpf(
                        self.contrato.cliente.nu_cpf
                    ),
                },
                'financial': {
                    'first_due_date': str(
                        self.contrato_margem_livre.dt_vencimento_primeira_parcela
                    ),
                    'installment_face_value': float(
                        self.contrato_margem_livre.vr_parcelas
                    ),
                    'disbursement_date': disbursement_date_str,
                    'limit_days_to_disburse': 7,
                    'number_of_installments': int(
                        self.contrato_margem_livre.qtd_parcelas
                    ),
                    'interest_type': 'pre_price_days',
                    'monthly_interest_rate': float(self.contrato.taxa_efetiva_mes)
                    / 100,
                    'fine_configuration': {
                        'monthly_rate': float(self.tx_mes_contrato),
                        'interest_base': self.nm_base_jurus,
                        'contract_fine_rate': self.tx_multa_contrato,
                    },
                    'credit_operation_type': 'ccb',
                    'interest_grace_period': 0,
                    'principal_grace_period': 0,
                },
                'simplified': True,
                'collaterals': [
                    {
                        'percentage': 1,
                        'collateral_data': {
                            'benefit_number': int(self.in100.numero_beneficio),
                            'state': self.contrato.cliente.endereco_uf,
                        },
                        'collateral_type': 'social_security',
                    }
                ],
                'disbursement_bank_account': {
                    'name': self.contrato.cliente.nome_cliente,
                    'bank_code': numero_conta_banco,
                    'account_type': traduzir_tipo_conta(
                        self.dados_bancarios_cliente.conta_tipo
                    ),
                    'branch_number': str(self.dados_bancarios_cliente.conta_agencia),
                    'account_number': str(self.dados_bancarios_cliente.conta_numero),
                    'account_digit': str(self.dados_bancarios_cliente.conta_digito),
                    'document_number': formatar_cpf(self.contrato.cliente.nu_cpf),
                    'transfer_method': 'ted',
                },
                'purchaser_document_number': settings.CONST_CNPJ_CESSIONARIO,
                'additional_data': {
                    'contract': {
                        'contract_number': 'BYX' + str(self.contrato.id).rjust(10, '0')
                    }
                },
            },
        }

    def _set_response(self):
        from handlers import qitech

        validador = ValidadorBeneficio(self.contrato, self.in100)
        analise_beneficio = validador.validar()

        validador_morte_idade = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contrato, self.in100
        )
        analise_regras_morte_idade = validador_morte_idade.validar()

        if (
            analise_beneficio['aprovada']
            and analise_regras_morte_idade['regra_aprovada']
        ):
            if not analise_beneficio['in100_retornada']:
                atualizar_status_contratos(
                    self.contrato,
                    EnumContratoStatus.DIGITACAO,
                    ContractStatus.AGUARDANDO_RETORNO_IN100.value,
                    '-',
                    user=None,
                )
            else:
                qitech = qitech.QiTech()
                self.response = (
                    qitech.insert_free_margin_proposal_financial_portability(
                        self.payload.get('JsonBody')
                    )
                )
                self.decoded_response = qitech.decode_body(self.response.json())
        else:
            # Caso tenha motivo na análise de benefício, usa ele,
            # Caso contrário, utiliza o motivo de regras de morte e idade.
            motivo = analise_beneficio.get('motivo')
            if motivo == '-':
                motivo = analise_regras_morte_idade.get('motivo', '-')

            atualizar_status_contratos(
                self.contrato,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                motivo,
                user=None,
            )
            self.response = False
            self.decoded_response = False

    def _send_to_hub(self):
        """
        Método que envia as informações de volta para a QITech e atualiza o status do contrato.
        """
        validador = ValidadorBeneficio(self.contrato, self.in100)
        analise_beneficio = validador.validar()

        validador_morte_idade = ValidadorRegrasBeneficioContratoMargemLivre(
            self.contrato, self.in100
        )
        analise_regras_morte_idade = validador_morte_idade.validar()

        if (
            analise_beneficio['aprovada']
            and analise_regras_morte_idade['regra_aprovada']
        ):
            if not analise_beneficio['in100_retornada']:
                atualizar_status_contratos(
                    self.contrato,
                    EnumContratoStatus.DIGITACAO,
                    ContractStatus.AGUARDANDO_RETORNO_IN100.value,
                    '-',
                    user=None,
                )
            else:
                return requests.request(
                    'POST',
                    f'{settings.CONST_HUB_URL}/api/Formalizacao/QiTechExecute',
                    headers=self.headers,
                    data=json.dumps(self.payload),
                )
        else:
            # Caso tenha motivo na análise de benefício, usa ele,
            # Caso contrário, utiliza o motivo de regras de morte e idade.
            motivo = analise_beneficio.get('motivo')
            if motivo == '-':
                motivo = analise_regras_morte_idade.get('motivo', '-')

            atualizar_status_contratos(
                self.contrato,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADA_POLITICA_INTERNA.value,
                motivo,
                user=None,
            )
            response = False
        return response

    def _handle_response(self, response):
        if not response:
            pass
        elif response.status_code in (200, 201, 202):
            self._process_success_response(response)
        else:
            self._process_error_response(response)

    def _process_success_response(self, response):
        contrato_margem_livre = MargemLivre.objects.filter(
            contrato=self.contrato
        ).first()
        json_obj_response = self.decoded_response
        try:
            url_ccb = json_obj_response['data']['contract']['urls'][0]
            contrato_margem_livre.document_key_QiTech_CCB = json_obj_response['data'][
                'borrower'
            ]['document_number']
            contrato_margem_livre.related_party_key = json_obj_response['data'][
                'borrower'
            ]['related_party_key']
            created_at_str = json_obj_response['data']['collaterals'][0]['created_at']
            contrato_margem_livre.dt_envio_proposta_CIP = datetime.strptime(
                created_at_str, '%Y-%m-%dT%H:%M:%S.%f'
            ).date()
            contrato_margem_livre.collateral_key = json_obj_response['data'][
                'collaterals'
            ][0]['collateral_key']
            contrato_margem_livre.chave_proposta = json_obj_response['key']
            contrato_margem_livre.sucesso_insercao_proposta = True
            installments = json_obj_response['data']['disbursement_options'][0].get(
                'installments', []
            )
            first_due_date = installments[0].get('due_date')
            last_due_date = installments[-1].get('due_date')

            contrato_margem_livre.dt_vencimento_primeira_parcela = (
                datetime.fromisoformat(first_due_date).date()
            )
            contrato_margem_livre.dt_vencimento_ultima_parcela = datetime.fromisoformat(
                last_due_date
            ).date()

            contrato_margem_livre.save()

            if url_ccb.startswith('http'):
                AnexoContrato.objects.create(
                    contrato=self.contrato,
                    anexo_url=url_ccb,
                    nome_anexo=(
                        f'CCB Gerada pela Financeira - Contrato {self.contrato.pk}'
                    ),
                    anexo_extensao='pdf',
                    tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                )
                self.contrato.is_ccb_generated = True
                contrato_margem_livre.ccb_gerada = True
                contrato_margem_livre.save()
                logger.info(
                    f'{self.contrato.cliente.nu_cpf} - Contrato({self.contrato.pk}): Proposta inserida na QITECH.\n Payload {self.payload}'
                )
                atualizar_status_contratos(
                    self.contrato,
                    EnumContratoStatus.AGUARDANDO_FORMALIZACAO,
                    ContractStatus.FORMALIZACAO_CLIENTE.value,
                    '-',
                    user=None,
                )
                # portabilidade.status = ContractStatus.FORMALIZACAO_CLIENTE.value

            else:
                logger.error(
                    f'{self.cliente.id_unico} - Ocorreu um erro ao tentar obter a CCB da Financeira.\n Payload {self.payload}',
                    exc_info=True,
                )
                raise Exception('Ocorreu um erro ao tentar obter a ccb da Financeira.')
        except Exception as e:
            print('Erro:', e)

    def _process_error_response(self, response):
        contrato_margem_livre = MargemLivre.objects.filter(
            contrato=self.contrato
        ).first()
        json_obj_response = self.decoded_response
        try:
            contrato_margem_livre.insercao_sem_sucesso = json_obj_response
            contrato_margem_livre.sucesso_insercao_proposta = False
            contrato_margem_livre.save()
            agora = datetime.now()
            formatado = agora.strftime('%d/%m/%Y %H:%M:%S')
            LogWebhook.objects.create(
                chamada_webhook=f'WEBHOOK QITECH ERRO - INSERÇÃO DA PROPOSTA(MARGEM LIVRE) {formatado}',
                log_webhook=json_obj_response,
            )
            logger.error(
                f'{self.contrato.cliente.id_unico} - Ocorreu um erro ao tentar inserir a Proposta Margem Livre\n Payload {self.payload}',
                exc_info=True,
            )
        except Exception as e:
            print('Erro:', e)
        raise Exception('Ocorreu um erro ao tentar Inserir a Proposta.')

    def insere(self):
        self._prepare_data()
        self._set_response()
        self._handle_response(self.response)


def insere_proposta_margem_livre_financeira_hub(
    contrato, tx_mes_contrato, nm_base_jurus, tx_multa_contrato
):
    PropostaInsercaoMargemLivre(
        contrato, tx_mes_contrato, nm_base_jurus, tx_multa_contrato
    ).insere()


@shared_task()
def gerar_token_e_buscar_beneficio(
    cpf_cliente, averbadora, token_contrato, codigo_convenio
):
    aceite_in100 = AceiteIN100.objects.get(cpf_cliente=cpf_cliente)
    data_hoje = date.today()
    if (
        aceite_in100.data_vencimento_token is not None
        and data_hoje > aceite_in100.data_vencimento_token
        or aceite_in100.data_vencimento_token is None
    ):
        autorizacao_consulta_digital(
            cpf_cliente,
            EnumCanalAutorizacaoDigital.DIGITAL_VIA_CORRESPONDENTE,
            aceite_in100,
            averbadora,
            codigo_convenio,
        )
    tokenAutorizacao = aceite_in100.token_in100
    contrato = Contrato.objects.get(token_contrato=token_contrato)
    contrato_cartao = contrato.contrato_cartao_beneficio.first()
    cliente_cartao = contrato.cliente_cartao_contrato.get()

    if settings.ENVIRONMENT != 'PROD' and not tokenAutorizacao:
        alterar_status(
            contrato,
            contrato_cartao,
            EnumContratoStatus.MESA,
            ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
            observacao='CPF informado não existe na Dataprev',
        )
        return

    consulta_obj = consulta_beneficio(cpf_cliente, tokenAutorizacao, averbadora)

    if consulta_obj == 'Erro Tecnico':
        alterar_status(
            contrato,
            contrato_cartao,
            EnumContratoStatus.MESA,
            ContractStatus.ERRO_CONSULTA_DATAPREV.value,
            observacao='Erro tecnico ao tentar consultar benefício',
        )
        return
    else:
        numero_beneficio = cliente_cartao.numero_matricula
        # Verificando se o benefício do contrato está na resposta da consulta_obj
        matching_beneficio = next(
            (
                b
                for b in consulta_obj['beneficios']
                if str(b['numeroBeneficio']) == cliente_cartao.numero_matricula
            ),
            None,
        )

        if not matching_beneficio:
            alterar_status(
                contrato,
                contrato_cartao,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
                observacao='Não foi localizado o número do benefício para o CPF do cliente',
            )
            return
        elif (
            not matching_beneficio['elegivelEmprestimo']
            or matching_beneficio['bloqueadoEmprestimo']
        ):
            alterar_status(
                contrato,
                contrato_cartao,
                EnumContratoStatus.CANCELADO,
                ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
                observacao='Benefício não está liberado para contratação do cartão ou empréstimo',
            )
            return
        else:
            detalhe_beneficio, simulacao = consulta_margem_inss(
                cpf_cliente,
                tokenAutorizacao,
                averbadora,
                numero_beneficio,
                contrato,
                contrato_cartao,
            )
            try:
                create_dados_beneficio(aceite_in100, detalhe_beneficio)
            except Exception:
                pass
            if detalhe_beneficio == 'Erro Simulacao':
                alterar_status(
                    contrato,
                    contrato_cartao,
                    EnumContratoStatus.MESA,
                    ContractStatus.ERRO_CONSULTA_DATAPREV.value,
                    observacao=simulacao['error'],
                )
                return
            elif detalhe_beneficio == 'Erro Tecnico':
                alterar_status(
                    contrato,
                    contrato_cartao,
                    EnumContratoStatus.MESA,
                    ContractStatus.ERRO_CONSULTA_DATAPREV.value,
                    observacao='Erro tecnico ao tentar consultar margem',
                )
                return
            else:
                convenio = contrato_cartao.convenio

                # Verifica se a pensão alimentícia está apta para contratação
                pensao_alimenticia = PensaoAlimenticiaINSS.objects.filter(
                    convenio=convenio,
                    codigo=detalhe_beneficio['pensaoAlimenticia']['codigo'],
                ).first()
                if not pensao_alimenticia or not pensao_alimenticia.permite_contratacao:
                    alterar_status(
                        contrato,
                        contrato_cartao,
                        EnumContratoStatus.MESA,
                        ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
                        observacao='O Benefício do cliente não atende as regras internas de elegibilidade',
                    )
                    return

                # Verifica se a espécie do benefício está apta para contratação
                especie_beneficio = EspecieBeneficioINSS.objects.filter(
                    convenio=convenio,
                    codigo=detalhe_beneficio['especieBeneficio']['codigo'],
                ).first()
                if not especie_beneficio or not especie_beneficio.permite_contratacao:
                    alterar_status(
                        contrato,
                        contrato_cartao,
                        EnumContratoStatus.MESA,
                        ContractStatus.REPROVADO_CONSULTA_DATAPREV.value,
                        observacao='O Tipo/Espécie do benefício do cliente não atende as regras internas de elegibilidade',
                    )
                    return


def agendar_consulta(contrato, convenio):
    now = datetime.now().time()
    next_opening_time = datetime.combine(datetime.now(), convenio.horario_func_inicio)
    cpf_cliente = contrato.cliente.nu_cpf
    averbadora = convenio.averbadora
    token_contrato = contrato.token_contrato

    if now > convenio.horario_func_fim:
        next_opening_time += timedelta(days=1)

    # Agende a tarefa com o Celery
    gerar_token_e_buscar_beneficio.apply_async(
        (cpf_cliente, averbadora, token_contrato, convenio.pk), eta=next_opening_time
    )


@shared_task
def envia_info_inss_pine(contrato_pk, request=None):
    def _show_message(message, level):
        logging_func = logging.info if level == 'info' else logging.error
        logging_func(message)
        if request:
            messages_func = getattr(messages, level)
            messages_func(request, message)

    contrato = (
        Contrato.objects.prefetch_related(
            'contrato_validacoes', 'cliente__realiza_reserva_cliente'
        )
        .select_related('cliente')
        .get(pk=contrato_pk)
    )
    try:
        reserva_margem: RealizaReserva = contrato.cliente.realiza_reserva_cliente.last()
        cliente_cartao: ClienteCartaoBeneficio = contrato.cliente_cartao_contrato.get()
        if reserva_margem and reserva_margem.codigo_retorno == 'BD':
            dossies_antigos_validos = DossieINSS.objects.filter(
                codigo_retorno='BD', contrato=contrato
            )
            if not dossies_antigos_validos.exists():
                anexo_contrato_qs = AnexoContrato.objects.select_related(
                    'contrato'
                ).filter(
                    contrato=contrato,
                    nome_anexo__iregex=r'^termo-de-adesao-.*-assinado$',
                    tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                )
                if anexo_contrato_qs.exists():
                    anexo_contrato = anexo_contrato_qs.first()

                    score_qs = contrato.contrato_validacoes.filter(
                        retorno_hub__icontains='SCORE APROVADO Valor:'
                    )

                    score_obj = score_qs.first()

                    score_re = re.search(
                        r'SCORE APROVADO Valor:\s*(\d+\.?\d*)',
                        score_obj.retorno_hub if score_obj else '',
                    )

                    score = Decimal(score_re[1]) if score_re else Decimal(0.0)
                    cliente = contrato.cliente

                    # Key: Chave de consulta a banco
                    # Value: chave para envio do dado na payload
                    relacao_anexos_payload = {
                        EnumTipoAnexo.SELFIE: 'registroBiometricoFacial',
                        EnumTipoAnexo.DOCUMENTO_FRENTE: 'documentoOficialComFotoFrente',
                        EnumTipoAnexo.DOCUMENTO_VERSO: 'documentoOficialComFotoVerso',
                    }

                    payload_anexos = {}

                    for anexo in AnexoContrato.objects.select_related(
                        'contrato'
                    ).filter(
                        contrato=contrato, tipo_anexo__in=relacao_anexos_payload.keys()
                    ):
                        if anexo.anexo_url:
                            tipo_anexo = anexo.tipo_anexo
                            payload_anexos[relacao_anexos_payload[tipo_anexo]] = (
                                url_to_base64(anexo.anexo_url)
                            )

                    cnh_qs = AnexoContrato.objects.select_related('contrato').filter(
                        contrato=contrato, tipo_anexo=EnumTipoAnexo.CNH
                    )

                    doc_frente = payload_anexos.get('documentoOficialComFotoFrente')
                    doc_verso = payload_anexos.get('documentoOficialComFotoVerso')
                    if cnh_qs.exists() and not (doc_frente and doc_verso):
                        anexo_cnh_b64 = url_to_base64(cnh_qs.first().anexo_url)
                        payload_anexos['documentoOficialComFotoFrente'] = (
                            doc_frente if doc_frente else anexo_cnh_b64
                        )
                        payload_anexos['documentoOficialComFotoVerso'] = (
                            doc_verso if doc_verso else anexo_cnh_b64
                        )

                    buff_payload_anexos = {}

                    for key, value in payload_anexos.items():
                        if is_pdf(value):
                            buff_payload_anexos[key] = convert_pdf_base64_to_image(
                                value
                            )
                        else:
                            buff_payload_anexos[key] = value

                    payload_anexos = buff_payload_anexos.copy()

                    payload = {
                        'averbadora': {
                            'nomeAverbadora': NomeAverbadoras.DATAPREV_PINE.value,
                            'operacao': 'incluirInformacaoContrato',
                        },
                        'payloadInfoINSS': {
                            'numeroBeneficio': cliente_cartao.numero_matricula,
                            'ip': contrato.ip_publico_assinatura,
                            'numeroContrato': str(contrato.pk),
                            'latitude': contrato.latitude,
                            'longitude': contrato.longitude,
                            'codigoSolicitante': 643,
                            'indicadorValidacaoComDocOficial': True,
                            'dispositivo': 'NavegadorWeb',
                            'indicadorAnalfabetismo': False,
                            'indicadorAssinaturaCertDigitalICPBrasil': False,
                            'contratoEmprestimo': url_to_base64(
                                anexo_contrato.anexo_url
                            ),
                            'dataHoraAssinatura': anexo_contrato.anexado_em.strftime(
                                '%d%m%Y%H%M%S'
                            ),
                            'score': float(score),
                            **payload_anexos,
                        },
                    }

                    response = requests.post(
                        settings.HUB_AVERBADORA_URL,
                        json=payload,
                    )
                    try:
                        response_json = response.json()
                    except requests.exceptions.JSONDecodeError:
                        _show_message(
                            f'Erro na resposta do INSS, {response.text}', 'error'
                        )
                        return

                    data_envio = timezone.now()
                    payload_dossie_inss = {
                        'cpf': cliente.nu_cpf,
                        'matricula': cliente_cartao.numero_matricula,
                        'contrato': contrato,
                        'data_envio': data_envio,
                        'hash_operacao': response_json.get('hashOperacao'),
                    }

                    codigo = response_json.get('codigo')

                    if codigo == 'BD':
                        payload_dossie_inss['codigo_retorno'] = 'BD'
                        message_res = 'Informações adicionais enviada com sucesso.'
                        level_res = 'info'
                    else:
                        detalhe_erro = response_json.get('erros', [])
                        codigo_retorno = ','.join([
                            erro.get('codigo') for erro in detalhe_erro
                        ])
                        payload_dossie_inss['detalhe_erro'] = detalhe_erro
                        payload_dossie_inss['codigo_retorno'] = codigo_retorno
                        message_res = 'Não foi possível enviar as informações adicionais. Consulte o Dossiê INSS'
                        level_res = 'warning'

                    DossieINSS.objects.create(**payload_dossie_inss)
                    _show_message(message_res, level_res)
                else:
                    _show_message(
                        'Não foi possível enviar as informações adicionais. Não foi encontrado o termo de adesão assinado.',
                        'warning',
                    )
            else:
                _show_message(
                    f'As informações adicionais já foram enviadas para o contrato {contrato.pk}, consulte o Dossiê INSS',
                    'warning',
                )
        else:
            _show_message(
                f'A Reserva de margem não foi feita para o contrato {contrato.pk}',
                'warning',
            )
    except RealizaReserva.DoesNotExist:
        _show_message(
            f'A Reserva de margem não foi feita para o contrato {contrato.pk}',
            'warning',
        )
    except Exception as e:
        _show_message(
            f'Ocorreu um erro ao enviar a informação para o INSS: {repr(e)}', 'error'
        )


@shared_task
def generali_arrecadacao_async():
    planos = BeneficiosContratado.objects.filter(
        nome_operadora='Generali', tipo_plano='Prata'
    ).exclude(Q(status=4))

    for beneficiocontratado in planos:
        contract = Contrato.objects.get(id=beneficiocontratado.contrato_emprestimo.pk)

        beneficios = BeneficiosContratado.objects.get(id=beneficiocontratado.pk)
        pk_beneficio = beneficiocontratado.plano.pk

        for plano in contract.contrato_planos_contratados.filter():
            cliente_cartao = contract.cliente_cartao_contrato.get()
            plano = plano.plano
            if plano.pk == pk_beneficio:
                if beneficios.status != 4:
                    if plano.tipo_plano == EnumTipoPlano.PRATA:
                        cf = float(beneficios.premio_bruto)
                        cf = f'{cf:.2f}'
                        operacao_sequencial, cnpj = check_plano(plano)
                        maior_sequencial = (
                            get_maior_sequencial(operacao_sequencial)
                            if get_maior_sequencial(operacao_sequencial) > 0
                            else 1
                        )

                        maior_sequencial_nome = f'{maior_sequencial}'.rjust(6, '0')
                        today = datetime.now()
                        today_str = today.strftime('%Y%m%d')

                        nomeArquivo = f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"

                        id_seq = f'{cliente_cartao.id_conta_dock}'
                        nova_id_seq = id_seq
                        identificacao_seguro = (
                            plano.codigo_sucursal
                            + plano.codigo_ramo
                            + plano.codigo_operacao
                            + plano.codigo_plano
                        )

                        if len(identificacao_seguro + nova_id_seq) < 18:
                            zeros_a_adicionar = 18 - len(
                                identificacao_seguro + nova_id_seq
                            )
                            nova_id_seq = '0' * zeros_a_adicionar + nova_id_seq
                        try:
                            identificacao_nova = identificacao_seguro + nova_id_seq
                        except Exception:
                            identificacao_nova = f'{identificacao_seguro + nova_id_seq.rjust(18 - len(identificacao_seguro), "0")}'[
                                :18
                            ]

                        with tempfile.TemporaryDirectory() as temp_dir:
                            data_venda = datetime.strftime(contract.criado_em, '%Y%m%d')
                            data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
                            data_venda_ajuste += relativedelta(
                                months=plano.quantidade_parcelas
                            )
                            data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')
                            qtd = (
                                beneficios.validade
                                if beneficios.validade is not None
                                else (
                                    '24'
                                    if plano.tipo_plano == EnumTipoPlano.PRATA
                                    else '01'
                                )
                            )
                            qtd_parcela = identificar_parcela(
                                f'{data_venda}',
                                f'{qtd}',
                                f'{data_fim_vigencia}',
                            )
                            plano_codigo = plano.codigo_plano
                            data_c = contract.criado_em.strftime('%Y%m%d')
                            produto = f'{plano.codigo_produto}'.ljust(5, ' ')
                            apolice = f'{plano.apolice}'.rjust(10, '0')
                            codigo_operacao = plano.codigo_operacao
                            plano = f'{plano.codigo_plano}'.ljust(10, ' ')
                            cf = f'{cf}'.replace('.', '').replace(',', '')
                            cnpj = f'{cnpj}'.rjust(15, '0')
                            sequencial_registro = 1
                            sequencial_do_registro = f'{sequencial_registro}'.rjust(
                                6, '0'
                            )
                            local_path = os.path.join(temp_dir, nomeArquivo)

                            # Baixe o arquivo do S3 se ele existir
                            file_exists_in_s3 = True
                            s3 = boto3.client(
                                's3',
                                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                            )
                            try:
                                s3.download_file(
                                    settings.BUCKET_SEGUROS,
                                    nomeArquivo,
                                    local_path,
                                )
                            except Exception as e:
                                print(
                                    'Arquivo ainda nao existente na s3, iremos cria-lo',
                                    e,
                                )
                                file_exists_in_s3 = False

                            with open(local_path, 'a') as destino:
                                if not file_exists_in_s3:
                                    logger.info(
                                        'iniciou o processo de inclusão do header'
                                    )
                                    write_initial_content(
                                        destino,
                                        produto,
                                        apolice,
                                        today_str,
                                        maior_sequencial_nome,
                                        codigo_operacao,
                                    )
                            with open(local_path, 'a') as destino:
                                remove_first_line_starting_with(
                                    start_text='9', local_path=destino
                                )
                                dado_retorno, _ = check_data_in_range(
                                    start_index=1295, end_index=1300, local_path=destino
                                )
                                if dado_retorno:
                                    sequencial_do_registro = int(dado_retorno) + 1
                                    sequencial_do_registro = (
                                        f'{sequencial_do_registro}'.rjust(6, '0')
                                    )

                                escrever_arrecadacao(
                                    destino,
                                    produto,
                                    apolice,
                                    plano_codigo,
                                    f'{identificacao_nova}'.rjust(20, ' '),
                                    f'{qtd_parcela}'.ljust(3, ' '),
                                    data_c,
                                    f'{cf}'.rjust(15, '0'),
                                    f'{cnpj}'.rjust(15, '0'),
                                    sequencial_do_registro,
                                    motivo='A',
                                )
                                beneficios.qtd_arrecadacao = (
                                    1
                                    if beneficios.qtd_arrecadacao is None
                                    else int(beneficios.qtd_arrecadacao) + 1
                                )
                                beneficios.save()
                            with open(local_path, 'a') as destino:
                                dado_retorno, _ = check_data_in_range(
                                    start_index=1295,
                                    end_index=1300,
                                    local_path=destino,
                                )
                                if dado_retorno:
                                    sequencial_do_registro = int(dado_retorno) + 1
                                    sequencial_do_registro = (
                                        f'{sequencial_do_registro}'.rjust(6, '0')
                                    )
                                count = count_reg(destino) + 2
                                count = f'{count}'.rjust(6, '0')
                                write_trailer(destino, count, sequencial_do_registro)
                            with open(local_path, 'a') as destino:
                                ajustar_posicoes(destino)

                            s3.upload_file(
                                local_path, settings.BUCKET_SEGUROS, nomeArquivo
                            )
    return True
