import json
import logging
import os
from datetime import datetime

import requests
from celery import shared_task
from django.conf import settings
from slugify import slugify

from api_log.models import (
    LogAtualizacaoCadastral,
    LogCliente,
    LogEnvioDossie,
    LogTransferenciaSaque,
)
from contract.constants import EnumTipoAnexo, EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import CartaoBeneficio, Contrato, SaqueComplementar
from core.constants import EnumTipoDocumento
from core.models.cliente import Cliente, ClienteInss, DadosBancarios
from core.utils import download_files_and_create_zip, remover_acentos
from handlers.dock_formalizacao import (
    ajustes_financeiros,
    lancamento_saque_parcelado_fatura,
)
from handlers.email import enviar_email

logger = logging.getLogger('digitacao')


@shared_task
def atualizacao_cadastral(cliente_cpf):
    url = f'{settings.URL_BRB_BASE}/consignado/cliente/v3/'

    cliente = Cliente.objects.get(nu_cpf=cliente_cpf)

    nome = cliente.nome_cliente
    cpf = cliente.nu_cpf.replace('.', '').replace('-', '')
    sexo = cliente.sexo.upper()
    nomeMae = cliente.nome_mae
    salario = round(float(cliente.renda), 2)

    # Nascimento
    dataNascimento = cliente.dt_nascimento
    localNascimento = cliente.endereco_logradouro
    ufNascimento = cliente.endereco_uf

    # Documento identificacao
    dataEmissaoDocumento = cliente.documento_data_emissao
    numeroDocumento = cliente.documento_numero
    ufDocumento = cliente.get_documento_uf_display()
    orgaoEmissorDocumento = cliente.documento_orgao_emissor
    if cliente.documento_tipo == EnumTipoDocumento.RG:
        tipoDocumento = 'CARTEIRA_IDENTIDADE'
    else:
        tipoDocumento = 'CARTEIRA_MOTORISTA'

    clienteInss = ClienteInss.objects.get(cliente=cliente)
    matricula = clienteInss.nu_beneficio

    # Endereco
    ufEndereco = cliente.endereco_uf
    cidadeEndereco = remover_acentos(f'{cliente.endereco_cidade}')
    bairroEndereco = remover_acentos(f'{cliente.endereco_bairro}')
    cepEndereco = cliente.endereco_cep.replace('-', '')
    logradouroEndereco = remover_acentos(f'{cliente.endereco_logradouro}')
    tipoLogradouroEndereco = remover_acentos(f'{cliente.tipo_logradouro}')
    numeroEndereco = cliente.endereco_numero
    complementoEndereco = remover_acentos(f'{cliente.endereco_complemento}')

    # Celular
    dddTelefone, numeroCelular = cliente.telefone_ddd

    email = cliente.email

    # Contra Bancaria
    dadosBancario = DadosBancarios.objects.filter(cliente=cliente).last()
    agencia = dadosBancario.conta_agencia or ''
    contaCorrente = dadosBancario.conta_numero or ''
    codigoBanco = dadosBancario.conta_banco[:3] or ''

    payload = json.dumps({
        'nome': f'{nome}',
        'cpf': f'{cpf}',
        'sexo': f'{sexo}',
        'nomeMae': f'{nomeMae}',
        'salario': salario,
        'nascimento': {
            'data': f'{dataNascimento}',
            'local': f'{localNascimento}',
            'uf': f'{ufNascimento}',
        },
        'documentoIdentificacao': {
            'dataEmissao': f'{dataEmissaoDocumento}',
            'numero': f'{numeroDocumento}',
            'uf': f'{ufDocumento}',
            'tipo': f'{tipoDocumento}',
            'orgaoEmissor': f'{orgaoEmissorDocumento}',
        },
        'matricula': f'{matricula}',
        'endereco': {
            'uf': f'{ufEndereco}',
            'cidade': f'{cidadeEndereco}',
            'bairro': f'{bairroEndereco}',
            'cep': f'{cepEndereco}',
            'logradouro': f'{logradouroEndereco}',
            'tipoLogradouro': f'{tipoLogradouroEndereco}',
            'numero': f'{numeroEndereco}',
            'complemento': f'{complementoEndereco}',
        },
        'telefone': {'ddd': f'{dddTelefone}', 'numero': f'{numeroCelular}'},
        'celular': {'ddd': f'{dddTelefone}', 'numero': f'{numeroCelular}'},
        'email': f'{email}',
        'contaBancaria': {
            'agencia': f'{agencia}',
            'contaCorrente': f'{contaCorrente}',
            'codigoBanco': f'{codigoBanco}',
        },
    })

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic NjI4YjQ5NjctNTI2Mi00OWVkLTg4OWUtNzg5YmI4NzViY2IzOjc3Y2E0ZDgwLWMyYjMtNDYyNS05NmU0LTMxMTBmODRmM2Y1Yg==',
        'Cookie': 'TS01c591c4=01172f7146a5647ad5a5660ba7c573b4a2e4322345364835db2a80d78d7cf0d460c06ffc4982ba0326d0240b0dbcb217a413c3cc73',
    }

    response = requests.request('POST', url, headers=headers, data=payload)
    # response_dict = json.loads(response.text)

    log_api, _ = LogCliente.objects.get_or_create(cliente=cliente)
    LogAtualizacaoCadastral.objects.create(
        log_api=log_api,
        cliente=cliente,
        payload_envio=payload,
        payload=response,
        tipo_chamada='Atualização Cadastral - BRB',
    )

    return True


def transferencia_saque(cliente_cpf, contrato_id):
    cliente = Cliente.objects.get(nu_cpf=cliente_cpf)
    contrato = Contrato.objects.get(pk=contrato_id)
    if contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        contrato_seq = SaqueComplementar.objects.get(contrato=contrato)
        valorFinanciado = float(contrato_seq.valor_lancado_fatura)
    elif contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        contrato_seq = CartaoBeneficio.objects.get(contrato=contrato)
        valorFinanciado = float(contrato_seq.valor_financiado)

    if contrato_seq.saque_parcelado:
        quantidadeParcelas = contrato_seq.qtd_parcela_saque_parcelado
    else:
        quantidadeParcelas = 1
    cliente_cpf = cliente_cpf.replace('.', '').replace('-', '')
    # Obter a data atual
    data_atual = datetime.now()
    data_operacao = data_atual.strftime('%Y-%m-%d')

    url = f'{settings.URL_BRB_BASE}/consignado/margem-livre/v2'

    payload = json.dumps({
        'cpf': f'{cliente_cpf}',
        'numeroContrato': f'{contrato_id}',
        'convenio': 'INSS',
        'siglaPlano': 'INSSCART1',
        'valorFinanciado': valorFinanciado,
        'valorTarifa': 0,
        'valorOutros': 0,
        'dataOperacao': f'{data_operacao}',
        'quantidadeParcelas': quantidadeParcelas,
        'tipoConta': 'TED',
    })
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic NjI4YjQ5NjctNTI2Mi00OWVkLTg4OWUtNzg5YmI4NzViY2IzOjc3Y2E0ZDgwLWMyYjMtNDYyNS05NmU0LTMxMTBmODRmM2Y1Yg==',
    }

    response = requests.request('POST', url, headers=headers, data=payload)

    log_api, _ = LogCliente.objects.get_or_create(cliente=cliente)
    LogTransferenciaSaque.objects.create(
        log_api=log_api,
        cliente=cliente,
        payload_envio=payload,
        payload=response.text,
        tipo_chamada='Transferência Saque',
    )
    print('Transferencia saque:', response.text)

    return response.status_code


@shared_task(bind=True, max_retries=0)  # set max_retries to 0
def retorno_saque(self, contrato_id, retry_count=0):
    url = f'{settings.URL_BRB_BASE}/consignado/margem-livre/v3/contratos/{contrato_id}/status'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic NjI4YjQ5NjctNTI2Mi00OWVkLTg4OWUtNzg5YmI4NzViY2IzOjc3Y2E0ZDgwLWMyYjMtNDYyNS05NmU0LTMxMTBmODRmM2Y1Yg==',
    }

    response = requests.get(url, headers=headers)
    response_data = json.loads(response.text)
    contrato = Contrato.objects.get(pk=contrato_id)

    log_api, _ = LogCliente.objects.get_or_create(cliente=contrato.cliente)
    LogTransferenciaSaque.objects.create(
        log_api=log_api,
        cliente=contrato.cliente,
        payload=response_data,
        tipo_chamada='Retorno Saque',
    )

    if (
        response.status_code == 200
        and response_data['statusContrato']['situacao'] == 'AGUARDANDO PAGAMENTO'
    ):
        if retry_count < 5:  # Numero maximo de tentativas
            logger.info(
                f'{contrato.cliente.nome_cliente} - Erro ao consultar retorno do saque, vamos tentar novamente',
                exc_info=True,
            )
            retorno_saque.apply_async(
                args=[contrato_id, retry_count + 1], countdown=30 * 60
            )
        else:
            logger.error(
                f'{contrato.cliente.nome_cliente} - Erro ao consultar retorno do saque, sem mais tentativas',
                exc_info=True,
            )
            enviar_email(
                f'Alerta: A tentativa de verificar o retorno do saque do cliente {contrato.cliente.nome_cliente} para o '
                f'contrato número {contrato} falhou.'
            )
    elif (
        response.status_code == 200
        and response_data['statusContrato']['situacao'] == 'PAGO'
    ):
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            contrato_seq = CartaoBeneficio.objects.filter(contrato=contrato).first()
        elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            contrato_seq = SaqueComplementar.objects.filter(contrato=contrato).first()

        if contrato_seq.saque_parcelado:
            lancamento_saque_parcelado_fatura(
                contrato.pk, contrato_seq.id
            )  # Chama sem o argumento retry_count
        else:
            ajustes_financeiros(
                contrato.id, contrato_seq.id
            )  # Chama sem o argumento retry_count

    else:
        logger.error(
            f'{contrato.cliente.nome_cliente} - Erro ao consultar retorno do saque',
            exc_info=True,
        )


@shared_task
def envio_dossie(cliente_cpf, token_contrato, possui_saque, saque_parcelado):
    contrato = Contrato.objects.get(token_contrato=token_contrato)
    cliente = Cliente.objects.get(nu_cpf=cliente_cpf)
    nome_pasta = str(contrato.token_contrato)
    nome_pasta_enevelope = str(contrato.token_envelope)
    nome_pasta_cliente = str(cliente.nu_cpf)

    cpf_slugify = cliente.nu_cpf.replace('.', '').replace('-', '')

    data_emissao = contrato.criado_em or ''
    data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
    data_emissao_slugify = slugify(data_emissao)
    data_emissao_slugify = data_emissao_slugify.replace('-', '')

    anexos = AnexoContrato.objects.filter(contrato=contrato)
    tipos_permitidos = [
        EnumTipoAnexo.DOCUMENTO_FRENTE,
        EnumTipoAnexo.DOCUMENTO_VERSO,
        EnumTipoAnexo.CNH,
        EnumTipoAnexo.SELFIE,
        EnumTipoAnexo.COMPROVANTE_ENDERECO,
    ]

    nomes_arquivos = [
        (
            nome_pasta_enevelope
            if anexo.tipo_anexo == EnumTipoAnexo.SELFIE
            else nome_pasta
        )
        + '/'
        + (
            anexo.nome_anexo
            if anexo.tipo_anexo == EnumTipoAnexo.SELFIE
            else f'{anexo.nome_anexo}.{anexo.anexo_extensao}'
        )
        + ('.jpg' if anexo.tipo_anexo == EnumTipoAnexo.SELFIE else '')
        for anexo in anexos
        if anexo.tipo_anexo in tipos_permitidos
    ]

    if possui_saque or saque_parcelado:
        buckets = {
            'bucket_termos': {
                'bucket_name': settings.BUCKET_NAME_TERMOS,
                'files': [
                    f'{nome_pasta}/termos-ccb-saque-parcelado-{cpf_slugify}-{data_emissao_slugify}-assinado.pdf',
                    f'{nome_pasta}/termo-de-adesao-{cpf_slugify}-{data_emissao_slugify}.pdf',
                    f'{nome_pasta}/regulamento-cartao-{cpf_slugify}-{data_emissao_slugify}.pdf',
                ],
            },
            'bucket_in100': {
                'bucket_name': settings.BUCKET_NAME_TERMOS_IN100,
                'files': [f'{nome_pasta_cliente}/termo-in100-cartao.pdf'],
            },
            'bucket_documentos': {
                'bucket_name': settings.BUCKET_NAME_AMIGOZ,
                'files': nomes_arquivos,
            },
        }
    else:
        buckets = {
            'bucket_termos': {
                'bucket_name': settings.BUCKET_NAME_TERMOS,
                'files': [
                    f'{nome_pasta}/termo-de-adesao-{cpf_slugify}-{data_emissao_slugify}.pdf',
                    f'{nome_pasta}/regulamento-cartao-{cpf_slugify}-{data_emissao_slugify}.pdf',
                ],
            },
            'bucket_in100': {
                'bucket_name': settings.BUCKET_NAME_TERMOS_IN100,
                'files': [f'{nome_pasta_cliente}/termo-in100-cartao.pdf'],
            },
            'bucket_documentos': {
                'bucket_name': settings.BUCKET_NAME_AMIGOZ,
                'files': nomes_arquivos,
            },
        }

    assinatura_ccb = {
        'ip': contrato.ip_publico_assinatura,
        'cpf_responsavel': cliente.nu_cpf,
        'latitude': contrato.latitude,
        'longitude': contrato.longitude,
        'hash': contrato.hash_assinatura,
    }

    with open('temp/assinatura_ccb.json', 'w') as json_file:
        json.dump(assinatura_ccb, json_file)

    buckets['bucket_documentos']['files'].append('assinatura_ccb.json')

    file_path = download_files_and_create_zip(buckets)

    url = f'{settings.URL_BRB_BASE}/v1.0.0/consignados/{contrato.pk}/dossies'

    with open(file_path, 'rb') as file:
        payload = file.read()

    headers = {
        'Content-Type': 'application/octet-stream',
        'Authorization': 'Basic NjI4YjQ5NjctNTI2Mi00OWVkLTg4OWUtNzg5YmI4NzViY2IzOjc3Y2E0ZDgwLWMyYjMtNDYyNS05NmU0LTMxMTBmODRmM2Y1Yg==',
    }

    response = requests.request('POST', url, headers=headers, data=payload)

    log_api, _ = LogCliente.objects.get_or_create(cliente=cliente)
    LogEnvioDossie.objects.create(
        log_api=log_api,
        cliente=cliente,
        payload=response.text,
        tipo_chamada='Envio de Dossiê',
    )

    # deleta o arquivo temporário após enviar para a API
    os.remove(file_path)
