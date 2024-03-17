import base64
import base64 as b64
import io
import json
import logging

import boto3
import requests
from django.conf import settings
from PIL import Image
from slugify import slugify

from contract.constants import EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Contrato, MargemLivre, Portabilidade
from contract.products.consignado_inss.models.dados_in100 import DadosIn100
from core.constants import EnumTipoContrato
from core.utils import consulta_cliente
from handlers.aws_boto3 import Boto3Manager

logger = logging.getLogger('digitacao')

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


# CONSULTAS REALIZADAS PARA VALIDAR A EXISTENCIA DE DOCUMENTOS ALEM DE CONVERSOES DE ARQUIVOS


def upload_base64(
    nome_arquivo,
    arquivo_base64,
    nome_pasta,
    contrato: Contrato,
    mime_type='image/jpg',
):
    """
    Uploads a base64-encoded file to an Amazon S3 bucket and returns a
        pre-signed URL for accessing the uploaded file.

    Args:
        nome_arquivo (str): The desired name of the uploaded file.
        arquivo_base64 (str): The base64-encoded file data to be uploaded.
        nome_pasta (str): The name of the folder within the S3 bucket
            where the file will be stored.
        contrato (Contrato): An object representing the contract associated
            with the S3 bucket.
        mime_type (str, optional): The MIME type of the file, defaults to
            'image/jpg'.

    Returns:
        str: A pre-signed URL for accessing the uploaded file in the S3
            bucket.

    This function decodes the base64 data, connects to an Amazon S3 bucket,
    and uploads the file with the specified name and MIME type to the
    given folder. It then generates a pre-signed URL for accessing the
    uploaded file.

    Note:
    The 'Contrato' object is assumed to have a 'bucket_name' attribute,
    representing the name of the S3 bucket where the file will be uploaded.
    """
    formated_base64 = str(arquivo_base64)
    transform_base64 = formated_base64.split(';base64,')[1]

    binary_data = base64.b64decode(transform_base64)
    bucket_name = contrato.bucket_name
    nome_arquivo = slugify(nome_arquivo)
    extensao = mime_type.split('/')[-1]
    object_key = f'{nome_pasta}/{nome_arquivo}.{extensao}'

    # Define o caminho do arquivo PDF a ser salvo
    file_stream = io.BytesIO(binary_data)

    boto3_manager = Boto3Manager()
    bucket = boto3_manager.get_bucket(bucket_name)
    # Salva o arquivo no S3

    bucket.upload_fileobj(
        file_stream,
        object_key,
        ExtraArgs={'ContentType': mime_type},
    )

    return boto3_manager.generate_presigned_url(
        bucket_name=bucket_name,
        object_key=object_key,
        expiration_time=31536000,
    )


def is_png(base64_string: str) -> bool:
    png_header_base64 = 'iVBORw0KGgo'

    # Verifica se a string base64 começa com o cabeçalho de PNG
    return base64_string.startswith(png_header_base64)


def is_pdf(base64_string: str) -> bool:
    # Os primeiros bytes de um arquivo PDF são "%PDF", que codificados em base64 podem variar ligeiramente
    # dependendo dos bytes seguintes. No entanto, a maioria dos arquivos PDF vai começar com "JVBER" em base64.
    pdf_header_base64 = 'JVBER'

    # Verifica se a string base64 começa com o cabeçalho de PDF
    return base64_string.startswith(pdf_header_base64)


def base64_to_jpeg(base64_string: str) -> bytes:
    try:
        # Decodifica a string base64 para obter os dados da imagem
        image_data = base64.b64decode(base64_string)

        # Carrega a imagem a partir dos dados decodificados
        image = Image.open(io.BytesIO(image_data))

        # Converte a imagem para o modo RGB se estiver no modo RGBA
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Salva a imagem em um buffer como JPEG
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')

        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        return str(e)


def url_to_base64(url):
    response = requests.get(url)
    img = io.BytesIO(response.content)
    base64_string = base64.b64encode(img.getvalue()).decode('utf-8')
    if is_png(base64_string):
        base64_string = base64_to_jpeg(base64_string)
    return base64_string


# FUNÇÃO QUE CONVERTE O BASE64 EM NA IMAGEM DA SELFIE E ARMAZENA NO BACKEND
def converter_base64_selfie(nome_arquivo, arquivo_base64, nome_pasta, contrato):
    bucket_name = contrato.bucket_name
    object_key = f'{nome_pasta}/{nome_arquivo}.jpg'
    binary_data = base64.b64decode(arquivo_base64)

    # Define o caminho do arquivo a ser salvo
    file_stream = io.BytesIO(binary_data)

    # Salva o arquivo no S3
    boto3_manager = Boto3Manager()
    bucket = boto3_manager.get_bucket(bucket_name)

    bucket.upload_fileobj(
        file_stream,
        object_key,
        ExtraArgs={'ContentType': 'image/jpg'},
    )

    return boto3_manager.generate_presigned_url(
        bucket_name=bucket_name,
        object_key=object_key,
        expiration_time=31536000,
    )


def consulta_regras_hub(numero_cpf, contrato):
    """
    Metódo ultilizado para consulta de regras no hub
    """
    tipo_doc = None
    documento_formatado = {}
    img_base_64_formatada = {}
    tipo_produto_operacao = ''
    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        bucket = settings.BUCKET_NAME_AMIGOZ
    if contrato.tipo_produto in (
        EnumTipoProduto.PORTABILIDADE,
        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
    ):
        bucket = settings.BUCKET_NAME_PORTABILIDADE
    if contrato.tipo_produto in (
        EnumTipoProduto.INSS,
        EnumTipoProduto.INSS_CORBAN,
        EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
        EnumTipoProduto.MARGEM_LIVRE,
    ):
        bucket = settings.BUCKET_NAME_INSS

    try:
        cliente = consulta_cliente(numero_cpf)
        documento_identificacao = AnexoContrato.objects.filter(contrato=contrato)
        # formated_data = datetime.datetime.strptime(cliente.dt_nascimento, "%d/%m/%Y")
        # formated_data = formated_data.strftime("%Y-%m-%d")
        formated_data = cliente.dt_nascimento

        # VERIFICA OS DOCUMENTOS DO CLIENTE
        for doc in documento_identificacao:
            # DE ACORDO COM O TIPO VALIDA SE É CNH,RG OU  COMPROVANTE DE ENDEREÇO
            tipo = doc.tipo_anexo
            # CASO SEJA VERSO DO RG OU CNH (3 - RG / 8 - CNH / 13 - CNH frente)
            if tipo in [8, 3, 13]:
                # Faz o upload do arquivo
                nome_pasta = str(contrato.token_contrato)

                tipo_doc = tipo

                response = {}
                try:
                    response = s3_cliente.get_object(
                        Bucket=bucket,
                        Key=f'{nome_pasta}/{doc.nome_anexo}.{doc.anexo_extensao}',
                    )
                except Exception:
                    try:
                        response = s3_cliente.get_object(
                            Bucket=bucket,
                            Key=f'{nome_pasta}/{doc.nome_anexo}.jpg',
                        )
                    except Exception:
                        try:
                            response = s3_cliente.get_object(
                                Bucket=bucket,
                                Key=f'{nome_pasta}/{slugify(doc.nome_anexo)}.{doc.anexo_extensao}',
                            )
                        except Exception:
                            try:
                                response = s3_cliente.get_object(
                                    Bucket=bucket,
                                    Key=f'{nome_pasta}/{slugify(doc.nome_anexo)}.jpg',
                                )
                            except Exception as e:
                                logger.error(
                                    f'[CONSULTA REGRAS HUB] Erro ao tentar recuperar o documento: {e}',
                                    extra={
                                        'document_key': f'Key: {nome_pasta}/{slugify(doc.nome_anexo)}.{doc.anexo_extensao}'
                                    },
                                )

                file_content = response['Body'].read()
                file_content = b64.b64encode(file_content).decode('utf-8')
                # documento = str(converter_arquivo_base64(file_content))
                # documento_formatado = documento[2:len(file_content) - 1]
                documento_formatado = file_content
            # CASO SEJA COMPROVANTE DE RESIDENCIA
            if tipo == 6:
                # Faz o upload do arquivo
                nome_pasta = f'{contrato.token_contrato}'

                response = {}
                try:  # TODO: CORRIGIR
                    response = s3_cliente.get_object(
                        Bucket=bucket,
                        Key=f'{nome_pasta}/{doc.nome_anexo}.{doc.anexo_extensao}',
                    )
                except Exception:
                    try:
                        response = s3_cliente.get_object(
                            Bucket=bucket,
                            Key=f'{nome_pasta}/{doc.nome_anexo}.jpg',
                        )
                    except Exception:
                        try:
                            response = s3_cliente.get_object(
                                Bucket=bucket,
                                Key=f'{nome_pasta}/{slugify(doc.nome_anexo)}.{doc.anexo_extensao}',
                            )
                        except Exception:
                            try:
                                response = s3_cliente.get_object(
                                    Bucket=bucket,
                                    Key=f'{nome_pasta}/{slugify(doc.nome_anexo)}.jpg',
                                )
                            except Exception as e:
                                logger.error(
                                    f'[CONSULTA REGRAS HUB] Erro ao tentar recuperar o documento: {e}',
                                    extra={
                                        'document_key': f'Key: {nome_pasta}/{slugify(doc.nome_anexo)}.{doc.anexo_extensao}'
                                    },
                                )

                file_content = response['Body'].read()
                file_content = b64.b64encode(file_content).decode('utf-8')
                # img_base_64 = str(converter_arquivo_base64(file_content))
                # img_base_64_formatada = img_base_64[2:len(file_content) - 1]
                img_base_64_formatada = file_content

        url = settings.HUB_ANALISE_CONTRATO_URL

        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            tipo_produto_operacao = 'happy-cartao-beneficio'
            payload = json.dumps({
                'contrato': {
                    'tipoProduto': EnumTipoProduto.CARTAO_BENEFICIO,
                    'nuContratoFacta': '3423423423',
                    'nuLote': '3423423423',
                    'cdContratoTipo': contrato.cd_contrato_tipo,
                },
                'endereco': {
                    'cep': f'{cliente.endereco_cep}',
                    'estado': f'{cliente.endereco_uf}',
                    'cidade': f'{cliente.endereco_cidade}',
                    'bairro': f'{cliente.endereco_bairro}',
                    'logradouro': f'{cliente.endereco_logradouro}',
                    'numero': f'{cliente.endereco_numero}',
                },
                'cliente': {
                    'nmCliente': f'{cliente.nome_cliente}',
                    'dtNascimento': f'{formated_data}',
                    'nmMae': f'{cliente.nome_mae}',
                    'dsEstadoCivil': f'{cliente.estado_civil}',
                    'nmOrgaoEmissorRg': f'{cliente.documento_orgao_emissor}',
                    'nmUfOrgaoEmissorRg': f'{cliente.documento_orgao_emissor}',
                    'nmEnderecoResidencialTipo': 1,
                    'nuCpf': f'{cliente.nu_cpf}',
                    'nmEnderecoResidencialLogradouro': f'{cliente.endereco_logradouro}',
                    'nmEnderecoResidencialNumero': f'{cliente.endereco_numero}',
                    'nmEnderecoResidencialComplemento': f'{cliente.endereco_complemento}',
                    'nmEnderecoResidencialBairro': f'{cliente.endereco_bairro}',
                    'nmEnderecoResidencialCidade': f'{cliente.endereco_cidade}',
                    'nmEnderecoResidencialUf': f'{cliente.endereco_uf}',
                    'nuEnderecoResidencialCep': f'{cliente.endereco_cep}',
                    'nuDddTelefoneCelular': f'{cliente.telefone_celular}',
                    'nmSexo': f'{cliente.sexo}',
                    'dsNaturalidade': f'{cliente.naturalidade}',
                    'nuDoc': f'{cliente.documento_numero}',
                    'tipoDoc': f'{tipo_doc}',
                    'dtEmissaoRg': f'{cliente.documento_data_emissao}',
                    'nmPai': f'{cliente.nome_pai}',
                },
                'base64': {
                    'arquivo': f'{img_base_64_formatada}',
                    'documento': f'{documento_formatado}',
                },
                'anexos': [],
                'operacao': tipo_produto_operacao,
            })
            headers = {'Content-Type': 'application/json'}
        if contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.MARGEM_LIVRE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            tipo_produto_operacao = 'happy-portabilidade'
            if contrato.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
            ):
                portabilidade = Portabilidade.objects.filter(contrato=contrato).first()
                taxa_efetiva_mes = str(portabilidade.taxa / 100)
                valor_contrato = str(portabilidade.saldo_devedor)
            if contrato.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
                margem_livre = MargemLivre.objects.filter(contrato=contrato).first()
                taxa_efetiva_mes = str(contrato.taxa_efetiva_mes / 100)
                valor_contrato = str(margem_livre.vr_contrato)
            # dados_bancarios_cliente = DadosBancarios.objects.filter(
            #     cliente=cliente
            # ).first()
            dados_in_100 = DadosIn100.objects.filter(
                numero_beneficio=contrato.numero_beneficio
            ).first()
            payload = json.dumps({
                'contrato': {
                    'nuContratoFacta': '3423423423',
                    'nuLote': '3423423423',
                    'cdContratoTipo': EnumTipoContrato.PORTABILIDADE,
                    'nuCnpjCorrespondente': str(contrato.corban.corban_CNPJ),
                    'dtDigitacao': str(contrato.criado_em),
                    'dtContrato': str(contrato.criado_em),
                    'txCETAno': str(contrato.cet_ano),
                    'txCETMes': str(contrato.cet_mes),
                    'txEfetivaAno': str(contrato.taxa_efetiva_ano),
                    'txEfetivaMes': taxa_efetiva_mes,
                    'vrContrato': valor_contrato,
                    'vrIof': str(contrato.vr_iof),
                    'vrLiberadoCliente': str(contrato.vr_liberado_cliente),
                    'vrTAC': str(contrato.vr_tac),
                    'vrSeguro': str(contrato.vr_seguro),
                    'tipoProduto': str(EnumTipoProduto.PORTABILIDADE),
                },
                'cliente': {
                    'nmCliente': cliente.nome_cliente,
                    'dtNascimento': str(cliente.dt_nascimento),
                    'nmMae': cliente.nome_mae,
                    'nmSexo': cliente.sexo,
                    'dsEstadoCivil': cliente.estado_civil,
                    'nmEmail': cliente.email,
                    'nuCpf': cliente.nu_cpf,
                    'dtEmissaoRg': str(cliente.documento_data_emissao),
                    'nmOrgaoEmissorRg': cliente.documento_orgao_emissor,
                    'nmUfOrgaoEmissorRg': cliente.get_documento_uf_display(),
                    'nmEnderecoResidencialLogradouro': cliente.endereco_logradouro,
                    'nmEnderecoResidencialNumero': cliente.endereco_numero,
                    'nmEnderecoResidencialComplemento': cliente.endereco_complemento,
                    'nmEnderecoResidencialBairro': cliente.endereco_bairro,
                    'nmEnderecoResidencialCidade': cliente.endereco_cidade,
                    'nmEnderecoResidencialUf': cliente.endereco_uf,
                    'nuEnderecoResidencialCep': cliente.endereco_cep,
                    'nuDddTelefoneCelular': cliente.telefone_celular,
                    'vrRenda': str(cliente.renda),
                    'nuRG': str(cliente.documento_numero),
                },
                'beneficio': {
                    'ufBeneficio': str(dados_in_100.uf_beneficio),
                    'tipoBeneficio': str(dados_in_100.cd_beneficio_tipo),
                    'vrBeneficio': str(dados_in_100.valor_beneficio),
                    'dtConcessaoBeneficio': str(dados_in_100.dt_expedicao_beneficio),
                    'codigo': str(dados_in_100.numero_beneficio),
                },
                'anexos': [],
                'operacao': tipo_produto_operacao,
            })
            headers = {'Content-Type': 'application/json'}
        response = requests.request('POST', url, headers=headers, data=payload)

        return json.loads(response.text)
    except Exception as e:
        print(e)


def consulta_regras_hub_cliente(numero_cpf, contrato):
    """
    Metódo ultilizado para consulta de regras no hub
    """
    tipo_produto_operacao = ''
    # if contrato.tipo_produto in (EnumTipoProduto.PORTABILIDADE,):
    #     bucket = settings.BUCKET_NAME_PORTABILIDADE

    try:
        cliente = consulta_cliente(numero_cpf)
        formated_data = cliente.dt_nascimento
        # VERIFICA OS DOCUMENTOS DO CLIENTE
        url = settings.HUB_ANALISE_CONTRATO_URL
        if contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.MARGEM_LIVRE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            tipo_produto_operacao = 'happy-portabilidade-cliente'
            # portabilidade = Portabilidade.objects.filter(contrato=contrato).first()
            payload = json.dumps({
                'contrato': {
                    'tipoProduto': EnumTipoProduto.PORTABILIDADE,
                    'nuContratoFacta': '3423423423',
                    'nuLote': '3423423423',
                    'cdContratoTipo': EnumTipoContrato.PORTABILIDADE,
                },
                'cliente': {
                    'nmCliente': f'{cliente.nome_cliente}',
                    'dtNascimento': f'{formated_data}',
                    'nmMae': f'{cliente.nome_mae}',
                    'dsEstadoCivil': f'{cliente.estado_civil}',
                    'nmOrgaoEmissorRg': f'{cliente.documento_orgao_emissor}',
                    'nmUfOrgaoEmissorRg': f'{cliente.documento_orgao_emissor}',
                    'nmEnderecoResidencialTipo': 1,
                    'nuCpf': f'{cliente.nu_cpf}',
                    'nmEnderecoResidencialLogradouro': f'{cliente.endereco_logradouro}',
                    'nmEnderecoResidencialNumero': f'{cliente.endereco_numero}',
                    'nmEnderecoResidencialComplemento': f'{cliente.endereco_complemento}',
                    'nmEnderecoResidencialBairro': f'{cliente.endereco_bairro}',
                    'nmEnderecoResidencialCidade': f'{cliente.endereco_cidade}',
                    'nmEnderecoResidencialUf': f'{cliente.endereco_uf}',
                    'nuEnderecoResidencialCep': f'{cliente.endereco_cep}',
                    'nuDddTelefoneCelular': f'{cliente.telefone_celular}',
                    'nmSexo': f'{cliente.sexo}',
                    'dsNaturalidade': f'{cliente.naturalidade}',
                    'nuRG': f'{cliente.documento_numero}',
                    'dtEmissaoRg': f'{cliente.documento_data_emissao}',
                    'nmPai': f'{cliente.nome_pai}',
                },
                'anexos': [],
                'operacao': tipo_produto_operacao,
            })

        headers = {'Content-Type': 'application/json'}

        response = requests.request('POST', url, headers=headers, data=payload)

        return json.loads(response.text)
    except Exception as e:
        print(e)


def consulta_regras_hub_receita_corban(numero_cpf, contrato):
    """
    Metódo ultilizado para consulta de regras no hub
    """
    tipo_produto_operacao = ''
    # if contrato.tipo_produto in (EnumTipoProduto.PORTABILIDADE,):
    #     bucket = settings.BUCKET_NAME_PORTABILIDADE

    try:
        cliente = consulta_cliente(numero_cpf)
        formated_data = cliente.dt_nascimento
        # VERIFICA OS DOCUMENTOS DO CLIENTE
        url = settings.HUB_ANALISE_CONTRATO_URL

        if contrato.tipo_produto in (
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
            EnumTipoProduto.INSS_CORBAN,
        ):
            tipo_produto_operacao = 'happy-inss'
        if contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            tipo_produto_operacao = 'happy-portabilidade-receita'
            # portabilidade = Portabilidade.objects.filter(contrato=contrato).first()
            payload = json.dumps({
                'contrato': {
                    'tipoProduto': contrato.tipo_produto,
                    'nuContratoFacta': '3423423423',
                    'nuLote': '3423423423',
                    'cdContratoTipo': contrato.cd_contrato_tipo,
                },
                'cliente': {
                    'nmCliente': f'{cliente.nome_cliente}',
                    'dtNascimento': f'{formated_data}',
                    'nmMae': f'{cliente.nome_mae}',
                    'dsEstadoCivil': f'{cliente.estado_civil}',
                    'nmOrgaoEmissorRg': f'{cliente.documento_orgao_emissor}',
                    'nmUfOrgaoEmissorRg': f'{cliente.documento_orgao_emissor}',
                    'nmEnderecoResidencialTipo': 1,
                    'nuCpf': f'{cliente.nu_cpf}',
                    'nmEnderecoResidencialLogradouro': f'{cliente.endereco_logradouro}',
                    'nmEnderecoResidencialNumero': f'{cliente.endereco_numero}',
                    'nmEnderecoResidencialComplemento': f'{cliente.endereco_complemento}',
                    'nmEnderecoResidencialBairro': f'{cliente.endereco_bairro}',
                    'nmEnderecoResidencialCidade': f'{cliente.endereco_cidade}',
                    'nmEnderecoResidencialUf': f'{cliente.endereco_uf}',
                    'nuEnderecoResidencialCep': f'{cliente.endereco_cep}',
                    'nuDddTelefoneCelular': f'{cliente.telefone_celular}',
                    'nmSexo': f'{cliente.sexo}',
                    'dsNaturalidade': f'{cliente.naturalidade}',
                    'nuRG': f'{cliente.documento_numero}',
                    'dtEmissaoRg': f'{cliente.documento_data_emissao}',
                    'nmPai': f'{cliente.nome_pai}',
                },
                'anexos': [],
                'operacao': tipo_produto_operacao,
            })
            headers = {'Content-Type': 'application/json'}

        response = requests.request('POST', url, headers=headers, data=payload)

        return json.loads(response.text)
    except Exception as e:
        print(e)
