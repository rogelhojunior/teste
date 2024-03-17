import hashlib
import logging
import os
import re
import sys
import tempfile
import uuid
from datetime import date, datetime
from typing import Optional
from slugify import slugify
from zipfile import ZipFile
import copy
import boto3
import fitz
import newrelic.agent
from django.apps import apps
from django.conf import settings
from django.db.models import Model
from django.db.models.query import QuerySet
from pydantic import HttpUrl
from rest_framework.request import Request
from text_unidecode import unidecode

from contract.constants import (
    EnumTipoMargem,
    EnumTipoProduto,
    NomeAverbadoras,
    EnumTipoPendencia,
)
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.constants import (
    EnumContratoStatus,
)
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.models.convenio import (
    Convenios,
    ProdutoConvenio,
)
from core.services.shorten_url.short_url_manager import ShortURLManager
from contract.models.regularizacao_contrato import RegularizacaoContrato


logger = logging.getLogger('digitacao')

s3 = boto3.resource(
    service_name='s3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name='us-east-1',
)


def consulta_cliente(numero_cpf):
    """
    Consulta o cliente pelo numero do CPF
    """
    clientes = apps.get_model('core', 'Cliente')
    cliente, _ = clientes.objects.get_or_create(nu_cpf=numero_cpf)
    return cliente


def formatar_valor_grande(valor):
    return re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1.', f'{valor:.2f}')


def generate_uuid():
    generated_uuid = uuid.uuid4()
    return str(generated_uuid)


def get_dados_convenio(averbadora, codigo_convenio):
    convenios = Convenios.objects.filter(
        pk=codigo_convenio, averbadora=averbadora, ativo=True
    ).first()

    if not convenios:
        return None

    senha_convenio = convenios.senha_convenio
    usuario_convenio = convenios.usuario_convenio
    # verba_convenio = convenios.verba # NAO EXISTE MAIS
    verba_convenio = ''
    url_convenio = convenios.url

    return (
        senha_convenio,
        usuario_convenio,
        verba_convenio,
        url_convenio,
        convenios,
    )


def import_module_by_path(path):
    name = os.path.splitext(os.path.basename(path))[0]
    if sys.version_info[0] == 2:
        # Python 2
        import imp

        return imp.load_source(name, path)
    elif sys.version_info[:2] <= (3, 4):
        # Python 3, version <= 3.4
        from importlib.machinery import SourceFileLoader

        return SourceFileLoader(name, path).load_module()
    else:
        # Python 3, after 3.4
        import importlib.util

        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def real_br_money_mask(my_value):
    if my_value is None:
        return 0
    a = '{:,.2f}'.format(float(my_value))
    b = a.replace(',', 'v')
    c = b.replace('.', ',')
    return c.replace('v', '.')


def calcular_idade(nascimento):
    """
    Função que calcula a idade de uma pessoa.
    """
    today = date.today()
    try:
        return (
            today.year
            - nascimento.year
            - ((today.month, today.day) < (nascimento.month, nascimento.day))
        )
    except Exception as e:
        logger.error(f'Erro ao calcular idade: {e}')
        return 0


def generate_short_url(long_url: HttpUrl) -> Optional[str]:
    try:
        aws3_link_service = ShortURLManager().aws3_link
        return aws3_link_service(long_url=long_url).get_shortened_url()
    except Exception:
        logger.exception('Something wrong when trying to shorten the URL')
        newrelic.agent.notice_error()
        return None


def gerar_link_aceite_in100(cpf, produto):
    from core.models import ParametrosBackoffice

    if produto == EnumTipoProduto.CARTAO_BENEFICIO:
        parametros_backoffice = ParametrosBackoffice.objects.get(
            ativo=True, tipoProduto=EnumTipoProduto.CARTAO_BENEFICIO
        )
    elif produto == EnumTipoProduto.CARTAO_CONSIGNADO:
        parametros_backoffice = ParametrosBackoffice.objects.get(
            ativo=True, tipoProduto=EnumTipoProduto.CARTAO_CONSIGNADO
        )

    url = parametros_backoffice.url_formalizacao
    cpf_formatado = cpf.replace('.', '').replace('-', '')
    url_formalizacao_longa = f'{url}/autorizacao-in100/{cpf_formatado}'

    return generate_short_url(long_url=url_formalizacao_longa)


def is_value_in_enum(value, enum):
    return value in enum.__dict__.values()


def remover_acentos(texto):
    return unidecode(texto)


def download_files_and_create_zip(buckets):
    os.makedirs('temp', exist_ok=True)

    for bucket in buckets.values():
        for file_name in bucket['files']:
            if '/' in file_name:
                directory = '/'.join(file_name.split('/')[:-1])
                os.makedirs(f'temp/{directory}', exist_ok=True)
            try:
                if file_name != 'assinatura_ccb.json':
                    s3.Bucket(bucket['bucket_name']).download_file(
                        file_name, f'temp/{file_name}'
                    )
            except Exception as e:
                print(
                    f"Error downloading {file_name} from bucket {bucket['bucket_name']}. Error: {str(e)}"
                )

    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
        with ZipFile(tmp_zip.name, 'w') as zip_file:
            for folder, _, filenames in os.walk('temp'):
                for filename in filenames:
                    zip_file.write(
                        os.path.join(folder, filename),
                        arcname=os.path.join(folder.replace('temp/', ''), filename),
                    )

        return tmp_zip.name


def alterar_status(
    contrato,
    contrato_seq,
    prox_status_contrato,
    prox_status_contrato_seq,
    user=None,
    observacao=None,
):
    from contract.models.status_contrato import StatusContrato

    if contrato.tipo_produto in [
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ]:
        contrato_seq.refresh_from_db()
        contrato.status = prox_status_contrato
        contrato_seq.status = prox_status_contrato_seq
        contrato_seq.save()
        contrato.save()
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        # Dicionário de parâmetros para a criação do objeto StatusContrato
        params = {'contrato': contrato, 'nome': prox_status_contrato_seq}
        contrato.refresh_from_db()
        contrato_seq.refresh_from_db()

        if user:
            params['created_by'] = user

        # Se tiver observação (não é None), adiciona ao dicionário
        if observacao:
            params['descricao_mesa'] = observacao

        # Verifica se o último status é diferente do próximo status e, se for,
        # O status ERRO_SOLICITACAO_SAQUE pode repetir
        # cria o novo status
        if (
            ultimo_status.nome != prox_status_contrato_seq
            or prox_status_contrato_seq == ContractStatus.ERRO_SOLICITACAO_SAQUE.value
        ):
            StatusContrato.objects.create(**params)

    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        contrato.status = prox_status_contrato
        contrato_seq.status = prox_status_contrato_seq
        contrato_seq.save(update_fields=['status'])
        contrato.save(update_fields=['status'])
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        params = {'contrato': contrato, 'nome': prox_status_contrato_seq}

        if user:
            params['created_by'] = user

        if (
            ultimo_status.nome != prox_status_contrato_seq
            or prox_status_contrato_seq == ContractStatus.ERRO_SOLICITACAO_SAQUE.value
        ):
            StatusContrato.objects.create(**params)
    elif contrato.tipo_produto in (
        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        EnumTipoProduto.PORTABILIDADE,
    ):
        contrato.status = prox_status_contrato
        contrato_seq.status = prox_status_contrato_seq
        contrato_seq.save(update_fields=['status'])
        contrato.save(update_fields=['status'])
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        params = {'contrato': contrato, 'nome': prox_status_contrato_seq}

        if observacao:
            params['descricao_mesa'] = observacao
        if user:
            params['created_by'] = user

        if prox_status_contrato_seq == ContractStatus.REPROVADO.value:
            port = contrato.contrato_portabilidade.first()
            port.status = prox_status_contrato_seq
            port.save(update_fields=['status'])

        if ultimo_status.nome != prox_status_contrato_seq:
            StatusContrato.objects.create(**params)
    else:
        contrato.status = prox_status_contrato
        contrato_seq.status = prox_status_contrato_seq
        contrato_seq.save(update_fields=['status'])
        contrato.save(update_fields=['status'])
        ultimo_status = StatusContrato.objects.filter(contrato=contrato).last()
        params = {'contrato': contrato, 'nome': prox_status_contrato_seq}

        if observacao:
            params['descricao_mesa'] = observacao
        if user:
            params['created_by'] = user

        if ultimo_status.nome != prox_status_contrato_seq:
            StatusContrato.objects.create(**params)


def upload_to_s3(file, nome_anexo, extensao, nome_pasta):
    """
    Carrega um arquivo no S3 e retorna uma URL presigned.

    :param file: O objeto de arquivo a ser carregado.
    :param nome_anexo: Nome base para o arquivo.
    :param extensao: Extensão do arquivo (por exemplo, "pdf" ou "jpg").
    :param nome_pasta: Nome da pasta (ou prefixo) sob a qual o arquivo deve ser salvo.
    :return: URL presigned para o arquivo carregado.
    """

    # Crie a conexão com S3 e defina o nome do bucket
    s3 = boto3.resource('s3')
    buket_name_s3 = settings.BUCKET_NAME_TERMOS
    bucket = s3.Bucket(buket_name_s3)

    # Configurar nome da pasta e caminho do objeto
    object_key = f'{nome_pasta}/{nome_anexo}.{extensao}'

    # Configure o tipo de conteúdo
    content_type = 'application/pdf' if extensao == 'pdf' else 'image/jpg'
    bucket.upload_fileobj(file, object_key, ExtraArgs={'ContentType': content_type})

    # Gere a URL e retorne
    s3_cliente = boto3.client('s3')
    return s3_cliente.generate_presigned_url(
        'get_object',
        Params={'Bucket': buket_name_s3, 'Key': object_key},
        ExpiresIn=31536000,
    )


def handle_multiple_objects(model, **lookup):
    """
    Remove all objects matched by the lookup except the first one.
    """
    qs = model.objects.filter(**lookup)
    if qs.count() > 1:
        for obj in qs[1:]:
            obj.delete()


def word_coordinates_in_pdf(
    pdf_path: str, word: str, word_order: int = 0, fix_x: int = 0, fix_y: int = 0
) -> dict:
    """
    Generates options of coordinates for a specific word in a PDF document.

    Args:
        pdf_path (str): The path to the PDF document.
        word (str): The word to search for in the PDF document.
        word_order (int, optional): The order of the word occurrence to retrieve the coordinates for. Defaults to 0.
        fix_x (int, optional): The amount to fix the X coordinates by. Defaults to 0.
        fix_y (int, optional): The amount to fix the Y coordinates by. Defaults to 0.

    Returns:
        dict: A dictionary containing the coordinates of the word on the page. If the word_order is out of range, an empty dictionary is returned.
    """
    coordinates_list = []

    pdf_document = fitz.open(pdf_path)

    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]

        page_text = page.get_text()

        if word in page_text:
            height_position_in_array = 3
            margin = 30

            space_to_next_word = 3
            space_to_next_line = 11
            space_to_same_line_before = 15

            for match in page.search_for(word):
                initial_x, initial_y, final_x, final_y = match

                page_bound = page.bound()
                page_height = page_bound[height_position_in_array]

                initial_y = page_height - initial_y
                final_y = page_height - final_y

                initial_x = round(initial_x)
                initial_y = round(initial_y)
                final_x = round(final_x)
                final_y = round(final_y)

                same_line_x = final_x + space_to_next_word
                same_line_y = round(((initial_y - final_y) / 4) + final_y)

                next_line_x = initial_x + space_to_next_word
                next_line_y = final_y - space_to_next_line

                previous_line_x = initial_x
                previous_line_y = initial_y + space_to_next_line

                previous_line_start_x = margin
                previous_line_start_y = initial_y + space_to_next_line

                same_line_before_x = initial_x - space_to_same_line_before
                same_line_before_y = same_line_y

                if fix_x:
                    same_line_x = same_line_x + fix_x
                    next_line_x = next_line_x + fix_x
                    previous_line_x = previous_line_x + fix_x
                    previous_line_start_x += fix_x
                    same_line_before_x = same_line_before_x + fix_x

                if fix_y:
                    same_line_y = same_line_y + fix_y
                    next_line_y = next_line_y + fix_y
                    previous_line_y = previous_line_y + fix_y
                    previous_line_start_y = previous_line_start_y + fix_y
                    same_line_before_y = same_line_before_y + fix_y

                coordinates_list.append({
                    'same_line_x': same_line_x,
                    'same_line_y': same_line_y,
                    'next_line_x': next_line_x,
                    'next_line_y': next_line_y,
                    'previous_line_x': previous_line_x,
                    'previous_line_y': previous_line_y,
                    'previous_line_start_x': previous_line_start_x,
                    'previous_line_start_y': previous_line_start_y,
                    'same_line_before_x': same_line_before_x,
                    'same_line_before_y': same_line_before_y,
                })

    pdf_document.close()

    return coordinates_list[word_order] if word_order < len(coordinates_list) else {}


def get_product_details(convenio, tipo_produto, tipo_margem):
    try:
        if produto := ProdutoConvenio.objects.filter(
            convenio=convenio, produto=tipo_produto, tipo_margem=tipo_margem
        ).first():
            return {
                'idProduto': produto.produto,
                'tipoProduto': produto.get_tipo_produto_display(),
            }

        return None

    except ProdutoConvenio.DoesNotExist:
        return None


def filter_valid_margins(response_data, convenio, averbadora):
    valid_data = []
    if averbadora == NomeAverbadoras.FACIL:
        MARGEM_TO_PRODUTO = {
            'Margem Cartao de Credito': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_CONSIGNADO,
            },
            'Margem Cartao': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_CONSIGNADO,
            },
            'Margem Cartao Beneficio': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            'Margem Cartão de Benefício': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            'Cartão Benefício (Compras)': {
                'margem': 'Margem Compra',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            'Cartão Benefício (Saque)': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            'Margem Cartao Beneficio (Saque)': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            'Margem Beneficio': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
        }
    elif averbadora == NomeAverbadoras.DATAPREV_PINE:
        MARGEM_TO_PRODUTO = {
            'Cartão Consignado': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_CONSIGNADO,
            },
            'Cartão Benefício': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
        }
    elif averbadora == NomeAverbadoras.ZETRASOFT:
        MARGEM_TO_PRODUTO = {
            'Cartão Benefício - Saque': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            'Cartão Benefício - Compra': {
                'margem': 'Margem Compra',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            'Cartão Consignado - Saque': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_CONSIGNADO,
            },
            'Cartão Consginado - Compra': {
                'margem': 'Margem Compra',
                'produto': EnumTipoProduto.CARTAO_CONSIGNADO,
            },
        }
    elif averbadora == NomeAverbadoras.NEOCONSIG:
        MARGEM_TO_PRODUTO = {
            '44': {
                'margem': 'Margem Compra',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '45': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '661': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1525': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1529': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1533': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1539': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1541': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1543': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1545': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1526': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1537': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1519': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_CONSIGNADO,
            },
            '1521': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1530': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1522': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1531': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1534': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1524': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1528': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1532': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1535': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1538': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1540': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1542': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1544': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1546': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1527': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1523': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
            '1536': {
                'margem': 'Margem Saque',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
        }
    elif averbadora == NomeAverbadoras.SERPRO:
        MARGEM_TO_PRODUTO = {
            '35012': {
                'margem': 'Margem Unica',
                'produto': EnumTipoProduto.CARTAO_BENEFICIO,
            },
        }

    MARGEM_ENUM_MAP = {
        'Margem Compra': EnumTipoMargem.MARGEM_COMPRA,
        'Margem Saque': EnumTipoMargem.MARGEM_SAQUE,
        'Margem Unica': EnumTipoMargem.MARGEM_UNICA,
    }

    # Se response_data for um dicionário único, transforme-o em uma lista
    if isinstance(response_data, dict):
        response_data = [response_data]

    for item in response_data:
        tipo_margem = item.get('tipoMargem')
        if tipo_margem and tipo_margem in MARGEM_TO_PRODUTO:
            product_info = MARGEM_TO_PRODUTO[tipo_margem]
            tipo_produto = product_info['produto']
            margem_name = product_info['margem']

            # Here we pass the enum value instead of string
            margem_enum_value = MARGEM_ENUM_MAP[margem_name]
            if product_details := get_product_details(
                convenio, tipo_produto, margem_enum_value
            ):
                new_item = {
                    **item,
                    **product_details,
                    'tipoMargem': margem_enum_value,  # Keep the enum value
                }
                valid_data.append(new_item)

    return valid_data


def calcular_idade_cliente(cliente):
    today = date.today()
    nascimento = cliente.dt_nascimento
    idade_cliente = today.year - nascimento.year

    if today.month < nascimento.month or (
        today.month == nascimento.month and today.day < nascimento.day
    ):
        idade_cliente -= 1
    return idade_cliente


def formatar_cpf(cpf):
    """Formata o CPF no formato xxx.xxx.xxx-xx"""
    cpf = str(
        cpf
    ).zfill(
        11
    )  # Garante que o CPF tenha 11 dígitos, preenchendo com zeros à esquerda se necessário
    return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'


def gerar_hash_assinatura(ip, cpf, latitude, longitude, data=None):
    # Para garantir a integridade dos dados, existe a opção de utilizar a mesma
    # data que será armazenada no banco de dados durante a geração do hash.

    now = data if data else datetime.now()
    data_atual = now.strftime('%Y-%m-%d %H:%M:%S')
    dados_cliente_hash = (
        str(ip) + str(cpf) + str(data_atual) + str(latitude) + str(longitude)
    )
    return hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()


def unify_querysets(model: Model, querysets: list) -> QuerySet:
    """Given a model and a list of querysets of that model return
    the union of all querysets."""
    empty_queryset = model.objects.none()
    return empty_queryset.union(*querysets)


def extract_request_options_int_list(request: Request, parameter_name: str) -> set:
    """Given a Request and a name, extract the list of options with the given
    name from the request, convert the values to in and them return it
    as a set."""
    values = request.POST.getlist(parameter_name)
    int_values = [int(n) for n in values]
    return set(int_values)


def get_intersection(set1: set, set2: set) -> set:
    """Return set intersection (a set of the common elements)."""
    return set(set1) & set(set2)


class ProductQueryGenerator:
    """
    This class group all the query filters for products to execute them
    at once.

    Attributes:
        - queryset: the queryset to use as base in the queries;
        - export_type: the given export_type parameter (passed by request);
        - init_date: the given init_date parameter (passed by request);
        - end_date: the given end_date parameter (passed by request);
        - status: the given status parameter (passed by request);
        - product_types: the given product_types options (passed by request);
        - generated_querysets: all the result querysets.
    """

    def __init__(
        self,
        queryset: QuerySet,
        export_type: str,
        init_date: datetime,
        end_date: datetime,
        status: int,
        product_types: set,
    ):
        self.queryset = queryset
        self.export_type = export_type
        self.init_date = init_date
        self.end_date = end_date
        self.status = status
        self.product_types = product_types
        self.generated_querysets = []

    def add_querysets_for_products(self, export_class, products: set) -> None:
        """
        Given one ExportContractsReporst subclass generate the querysets
        for the products and include them on the generated_querysets
        class attribute.

        Args:
            - export_class: a class that extends from ExportContractsReport.
            This class will be used to apply the query rules;
            - products: the products to filter using this class.
        """
        if intersection_values := get_intersection(self.product_types, products):
            for product in intersection_values:
                self.add_queryset_for_product(export_class, product)

    def add_queryset_for_product(
        self,
        export_class,
        product: int,
    ) -> None:
        """
        Given one ExportContractsReporst subclass generate the queryset
        for the product and include it on the generated_querysets
        class attribute.

        Args:
            - export_class: a class that extends from ExportContractsReport.
            This class will be used to apply the query rules;
            - product: the product to filter using the class.
        """
        export_object = export_class(
            self.queryset,
            self.export_type,
            product,
            self.init_date,
            self.end_date,
            self.status,
        )
        queryset = export_object.get_queryset()
        self.generated_querysets.append(queryset)


def exclude_all_check_rules(rules):
    ALL_CHECK_RULES = ['PEP', 'OBITO', 'NOME_MAE', 'NASCIMENTO']
    filtered_rules = copy.deepcopy(rules)
    already_excluded = 0
    for index, element in enumerate(rules):
        for rule in ALL_CHECK_RULES:
            if rule in element.get('descricao'):
                del filtered_rules[index - already_excluded]
                already_excluded += 1
    return filtered_rules


def upload_to_s3_documentos_cliente(file, nome_anexo, extensao, nome_pasta):
    """
    Carrega um arquivo no S3 e retorna uma URL presigned.

    :param file: O objeto de arquivo a ser carregado.
    :param nome_anexo: Nome base para o arquivo.
    :param extensao: Extensão do arquivo (por exemplo, "pdf" ou "jpg").
    :param nome_pasta: Nome da pasta (ou prefixo) sob a qual o arquivo deve ser salvo.
    :return: URL presigned para o arquivo carregado.
    """

    # Crie a conexão com S3 e defina o nome do bucket
    s3 = boto3.resource('s3')
    buket_name_s3 = settings.BUCKET_NAME_AMIGOZ
    bucket = s3.Bucket(buket_name_s3)

    # Configurar nome da pasta e caminho do objeto
    object_key = f'{nome_pasta}/{nome_anexo}.{extensao}'

    # Configure o tipo de conteúdo
    content_type = 'application/pdf' if extensao == 'pdf' else 'image/jpg'
    bucket.upload_fileobj(file, object_key, ExtraArgs={'ContentType': content_type})

    # Gere a URL e retorne
    s3_cliente = boto3.client('s3')
    return s3_cliente.generate_presigned_url(
        'get_object',
        Params={'Bucket': buket_name_s3, 'Key': object_key},
        ExpiresIn=31536000,
    )


def processar_pendencia(
    contrato, cartao_beneficio, pendente, motivo_pendencia, arquivo, user
):
    if pendente == 'contracheque':
        tipo_pendencia = EnumTipoPendencia.CONTRACHEQUE.value
    elif pendente == 'adicional':
        tipo_pendencia = EnumTipoPendencia.DEMAIS_ANEXOS_DE_AVERBACAO.value
    elif pendente == 'senha':
        tipo_pendencia = EnumTipoPendencia.SENHA_DE_AVERBACAO.value

    nome_anexo = slugify(arquivo.name.split('.')[0])
    extensao = arquivo.name.split('.')[-1]

    url = upload_to_s3_documentos_cliente(
        arquivo, nome_anexo, extensao, str(contrato.token_contrato)
    )
    pendencia = RegularizacaoContrato.objects.create(
        contrato=contrato,
        tipo_pendencia=tipo_pendencia,
        mensagem_pendencia=motivo_pendencia,
        nome_pendencia=user,
        nome_anexo_pendencia=nome_anexo,
        anexo_extensao_pendencia=extensao,
        anexo_url_pendencia=url,
    )
    pendencia.save()
    status_cartao = ContractStatus.PENDENCIAS_AVERBACAO_CORBAN.value
    contrato.status = EnumContratoStatus.MESA
    cartao_beneficio.status = status_cartao
    cartao_beneficio.save()
    contrato.save()
    StatusContrato.objects.create(
        contrato=contrato,
        nome=status_cartao,
        created_by=user,
        descricao_mesa=motivo_pendencia,
    )
