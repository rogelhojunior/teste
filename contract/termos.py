import datetime
import hashlib
import io
import logging
import tempfile

import boto3
import newrelic.agent
import pytz
import requests
from django.conf import settings

# from django.utils.text import slugify
from geopy.geocoders import Nominatim
from PyPDF2 import PdfFileReader, PdfFileWriter, PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from rest_framework.response import Response
from rest_framework.status import HTTP_500_INTERNAL_SERVER_ERROR
from slugify import slugify

from contract.constants import EnumTipoAnexo, EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from core.utils import word_coordinates_in_pdf
from handlers.confia import (
    get_documento_stream_confia_adapter,
    get_signed_documents,
    is_feature_active_for_confia,
    process_anexo_confia,
)

logger = logging.getLogger('digitacao')

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


def assinatura_termos_uso(contrato, latitude, longitude, ip_publico):
    try:
        anexo = AnexoContrato.objects.filter(
            contrato=contrato, tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS
        ).first()
        cliente = contrato.cliente
        numero_cpf = cliente.nu_cpf
        brasilia_tz = pytz.timezone('America/Sao_Paulo')
        data_atual = datetime.datetime.now(brasilia_tz).strftime('%Y-%m-%d %H:%M:%S')

        nome_cidade = pegar_nome_cidade(latitude, longitude)

        dados_cliente_hash = (
            ip_publico + numero_cpf + data_atual + str(latitude) + str(longitude)
        )
        hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()
        contrato.hash_assinatura = hash
        contrato.save()
        # Conecta ao S3
        # s3 = boto3.resource('s3')
        if settings.ENVIRONMENT == 'PROD':
            # bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS)
            bucket_name = f'{settings.BUCKET_NAME_TERMOS}'

        elif contrato.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            # bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS)
            bucket_name = f'{settings.BUCKET_NAME_TERMOS}'
        elif contrato.tipo_produto in (
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
            EnumTipoProduto.INSS_CORBAN,
            EnumTipoProduto.MARGEM_LIVRE,
        ):
            # bucket = s3.Bucket('termos-inss-stage')  # precisa migrar
            bucket_name = 'termos-inss-stage'
        nome_pasta = str(contrato.token_contrato)

        documentos = [anexo.anexo_url]
        termos_assinados_confia = None
        if is_feature_active_for_confia():
            termos_e_assinaturas = get_signed_documents(cliente.id_confia)
            termos_assinados_confia = process_anexo_confia(
                termos_e_assinaturas, anexo.nome_anexo
            )

        for doc in documentos:
            with tempfile.TemporaryDirectory() as temp_dir:
                response = requests.get(doc)
                documento_stream = termos_assinados_confia or io.BytesIO(
                    response.content
                )
                input_pdf = PdfReader(documento_stream)
                output_pdf = PdfWriter()

                num_pages = input_pdf.getNumPages()
                for page_num in range(len(input_pdf.pages)):
                    page = input_pdf.pages[page_num]
                    output_pdf.add_page(page)

                page = input_pdf.getPage(num_pages - 1)

                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)

                # Defina a fonte e o tamanho da fonte
                can.setFont('Helvetica', 9)

                # Adicione o texto ao objeto canvas
                x = 10
                y = 100
                can.drawString(x, y, 'Assinatura eletrônica:')
                x = 10
                y = 90
                can.drawString(
                    x,
                    y,
                    f'{hash.upper()} | {nome_cidade} - DATA/HORA: {str(data_atual)} | IP: {str(ip_publico)}',
                )

                can.save()

                # Obtenha a página com o texto como um objeto PdfFileReader
                new_page = PdfFileReader(packet).getPage(0)

                # Mesclando a página original com a página atualizada
                page.mergePage(new_page)

                nome_documento = 'ccb'
                with open(
                    f'{temp_dir}/{nome_documento}-portabilidade.pdf', 'wb'
                ) as outputStream:
                    output_pdf.write(outputStream)
                with open(f'{temp_dir}/{nome_documento}-portabilidade.pdf', 'rb') as f:
                    s3_cliente.upload_fileobj(
                        f,
                        bucket_name,
                        f'{nome_pasta}/{nome_documento}-portabilidade.pdf',
                        ExtraArgs={'ContentType': 'application/pdf'},
                    )
                    new_object_key = f'{nome_pasta}/{nome_documento}-portabilidade.pdf'
                    # PARA VISUALIZAÇÃO
                    url = s3_cliente.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': new_object_key},
                        ExpiresIn=31536000,
                    )

                    anexo, _ = AnexoContrato.objects.update_or_create(
                        contrato=contrato,
                        nome_anexo=f'{nome_documento}-{contrato.get_tipo_produto_display()}',
                        defaults={
                            'tipo_anexo': 15,
                            'anexo_extensao': 'pdf',
                            'anexo_url': url,
                        },
                    )
        contrato.save()
    except Exception:
        newrelic.agent.notice_error()
        return Response(
            {'Erro': 'Houve um erro ao Assinar os Termos.'},
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


def assinar_termos(bucket_name, contrato, latitude, longitude, ip_publico):
    from datetime import datetime

    cliente = contrato.cliente
    numero_cpf = cliente.nu_cpf
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    data_atual = datetime.now(brasilia_tz).strftime('%Y-%m-%d %H:%M:%S')
    data_sem_hora = datetime.now().strftime('%Y-%m-%d')
    data_formatada = datetime.strptime(data_sem_hora, '%Y-%m-%d').strftime(
        '%d de %B de %Y'
    )
    hora_atual = datetime.now().strftime('%H:%M:%S')

    # ip_publico = requests.get('https://api.ipify.org/').text

    # Obtém a localização atual do dispositivo
    # g = geocoder.ip('me')

    # Obtém as coordenadas de latitude e longitude da localização atual
    # latitude, longitude = g.latlng

    nome_cidade = pegar_nome_cidade(latitude, longitude)

    dados_cliente_hash = (
        str(ip_publico)
        + str(numero_cpf)
        + str(data_atual)
        + str(latitude)
        + str(longitude)
    )
    hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()

    contrato.hash_assinatura = hash
    contrato.ip_publico_assinatura = ip_publico
    contrato.save()

    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
        EnumTipoProduto.SAQUE_COMPLEMENTAR,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        if is_feature_active_for_confia():
            termos_e_assinaturas = get_signed_documents(cliente.id_confia)

        anexos = AnexoContrato.objects.filter(contrato=contrato)
        nome_pasta = contrato.token_contrato
        for anexo in anexos:
            if (
                anexo.tipo_anexo == EnumTipoAnexo.TERMOS_E_ASSINATURAS
                and 'assinado' not in anexo.nome_anexo
            ):
                nome_anexo = slugify(anexo.nome_anexo)
                object_key = f'{nome_pasta}/{nome_anexo}.{anexo.anexo_extensao}'
                if is_feature_active_for_confia():
                    documento_stream = get_documento_stream_confia_adapter(
                        termos_e_assinaturas, bucket_name, object_key, nome_anexo
                    )
                else:
                    documento_stream = download_arquivo_s3_base64(
                        bucket_name, object_key
                    )
                input_pdf = PdfFileReader(documento_stream)
                output_pdf = PdfFileWriter()
                num_pages = input_pdf.getNumPages()
                for page_num in range(input_pdf.getNumPages()):
                    page = input_pdf.getPage(page_num)
                    output_pdf.addPage(page)

                # Obtenha a página 0 do PDF
                # if 'regulamento-cartao' in nome_anexo or 'termos-ccb' in nome_anexo:
                #     page = input_pdf.getPage(num_pages - 1)
                # else:
                #     page = input_pdf.getPage(num_pages - 2)

                page = input_pdf.getPage(num_pages - 1)

                # Cria uma nova página
                packet = io.BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                can.setFont('Helvetica', 9)

                # Adicione o texto ao objeto canvas
                if 'termo-de-adesao' in nome_anexo:
                    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
                        pdf_path = (
                            'static/digimais/termo-de-adesao-cartao-de-credito-v1.pdf'
                        )

                        hash_coord = word_coordinates_in_pdf(
                            pdf_path=pdf_path,
                            word='Assinatura Eletrônica',
                            word_order=0,
                            fix_y=-5,
                        )

                        name_coord = word_coordinates_in_pdf(
                            pdf_path=pdf_path,
                            word='Nome:',
                            word_order=0,
                        )

                        cpf_coord = word_coordinates_in_pdf(
                            pdf_path=pdf_path, word='CPF:', word_order=0, fix_x=5
                        )

                        if hash_coord:
                            x = hash_coord.get('previous_line_start_x')
                            y = hash_coord.get('previous_line_start_y')

                        if name_coord:
                            can.drawString(
                                name_coord.get('same_line_x'),
                                name_coord.get('same_line_y'),
                                cliente.nome_cliente,
                            )

                        if cpf_coord:
                            can.drawString(
                                cpf_coord.get('same_line_x'),
                                cpf_coord.get('same_line_y'),
                                numero_cpf,
                            )

                    else:
                        if contrato.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
                            x = 30
                            y = 330

                        elif contrato.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
                            x = 40
                            y = 290

                elif (
                    'termos-ccb' in nome_anexo
                    or 'termos-ccb-saque-complementar' in nome_anexo
                    or 'termos-ccb-saque-parcelado' in nome_anexo
                ):
                    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
                        from handlers.ccb import CCB

                        ccb_interface = CCB(numero_cpf, contrato.id)
                        ccb_interface.assinar_ccb(
                            contract_id=contrato.id, documento='digimais'
                        )
                        continue

                    else:
                        x = 42
                        y = 620

                elif 'regulamento-cartao' in nome_anexo:
                    x = 40
                    y = 10

                elif 'termo-de-autorizacao-inss' in nome_anexo:
                    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
                        pdf_path = 'static/digimais/termo-de-autorizacao-do-beneficiario-inss-v2.pdf'

                        hash_first_coord = word_coordinates_in_pdf(
                            pdf_path=pdf_path,
                            word='Assinatura Eletrônica',
                            word_order=0,
                        )
                        hash_second_coord = word_coordinates_in_pdf(
                            pdf_path=pdf_path,
                            word='Assinatura Eletrônica',
                            word_order=1,
                        )

                        fix_y_coord = 5

                        if hash_first_coord:
                            x = hash_first_coord.get('previous_line_start_x')
                            y = hash_first_coord.get('previous_line_start_y')

                        if hash_second_coord:
                            hash_text = f'{hash.upper()} | {nome_cidade} - DATA/HORA: {str(datetime.today())} | IP: {str(ip_publico)}'
                            can.drawString(
                                hash_second_coord.get('previous_line_start_x'),
                                hash_second_coord.get('previous_line_start_y')
                                - fix_y_coord,
                                hash_text,
                            )

                    else:
                        x = 40
                        y = 570

                elif 'termo-de-consentimento' in nome_anexo:
                    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
                        pdf_path = 'static/digimais/termo-de-consentimento-cartao-consignado-de-beneficio-v2.pdf'

                        if hash_coord := word_coordinates_in_pdf(
                            pdf_path=pdf_path,
                            word='Assinatura Eletrônica',
                            word_order=0,
                        ):
                            x = hash_coord.get('previous_line_start_x')
                            y = hash_coord.get('previous_line_start_y')

                    else:
                        x = 40
                        y = 205

                elif 'termo-vida-inss' in nome_anexo:
                    x = 40
                    y = 165

                elif 'termo-vida-siape' in nome_anexo:
                    x = 42
                    y = 65

                elif 'termo-ouro-inss' in nome_anexo:
                    x = 15
                    y = 340
                elif 'termo-ouro-demais-convenios' in nome_anexo:
                    x = 15
                    y = 329

                    x_city = 60
                    y_city = 343
                    can.drawString(x_city, y_city, nome_cidade)

                    date = datetime.today()
                    x_day = 225
                    y_day = 343
                    can.drawString(x_day, y_day, f'{date.day}')

                    x_month = 254
                    y_month = 343
                    can.drawString(x_month, y_month, f'{date.month}')

                    x_year = 272
                    y_yeas = 343
                    can.drawString(x_year, y_yeas, f'{date.year}')

                    x_nome = 51
                    y_nome = 263
                    can.drawString(x_nome, y_nome, f'{cliente.nome_cliente}')

                    x_cpf = 51
                    y_cpf = 229
                    can.drawString(x_cpf, y_cpf, f'{cliente.nu_cpf}')

                elif 'termo-diamante-inss' in nome_anexo:
                    x = 15
                    y = 338

                    x_city = 70
                    y_city = 353
                    can.drawString(x_city, y_city, nome_cidade)

                    date = datetime.today()
                    x_day = 231
                    y_day = 353
                    can.drawString(x_day, y_day, f'{date.day}')

                    x_month = 254
                    y_month = 353
                    can.drawString(x_month, y_month, f'{date.month}')

                    x_year = 278
                    y_year = 353
                    can.drawString(x_year, y_year, f'{date.year}')

                    x_nome = 70
                    y_nome = 273
                    can.drawString(x_nome, y_nome, f'{cliente.nome_cliente}')

                    x_cpf = 60
                    y_cpf = 238
                    can.drawString(x_cpf, y_cpf, f'{cliente.nu_cpf}')

                elif 'termo-diamante-demais-convenios' in nome_anexo:
                    x = 15
                    y = 340

                    x_city = 70
                    y_city = 399
                    can.drawString(x_city, y_city, nome_cidade)

                    date = datetime.today()
                    x_day = 227
                    y_day = 399
                    can.drawString(x_day, y_day, f'{date.day}')

                    x_month = 246
                    y_month = 399
                    can.drawString(x_month, y_month, f'{date.month}')

                    x_year = 272
                    y_yeas = 399
                    can.drawString(x_year, y_yeas, f'{date.year}')

                    x_nome = 51
                    y_nome = 319
                    can.drawString(x_nome, y_nome, f'{cliente.nome_cliente}')

                    x_cpf = 42
                    y_cpf = 286
                    can.drawString(x_cpf, y_cpf, f'{cliente.nu_cpf}')

                elif 'termo-vida-prata-sabemi' in nome_anexo:
                    from contract.terms.sabemi import SabemiLifeInsuranceSilverTerm

                    sabemi_silver = SabemiLifeInsuranceSilverTerm()
                    sabemi_silver.sign_term(contract_id=contrato.id)
                    continue

                elif 'termo-vida-ouro-prestamista-sabemi' in nome_anexo:
                    from contract.terms.sabemi import (
                        SabemiLifeInsuranceMoneyLenderGoldTerm,
                    )

                    sabemi_gold = SabemiLifeInsuranceMoneyLenderGoldTerm()
                    sabemi_gold.sign_term(contract_id=contrato.id)
                    continue

                elif 'termo-vida-diamante-prestamista-sabemi' in nome_anexo:
                    from contract.terms.sabemi import (
                        SabemiLifeInsuranceMoneyLenderDiamondTerm,
                    )

                    sabemi_diamond = SabemiLifeInsuranceMoneyLenderDiamondTerm()
                    sabemi_diamond.sign_term(contract_id=contrato.id)
                    continue

                can.drawString(
                    x,
                    y,
                    (
                        (f'{hash.upper()}' + f' | {nome_cidade} - DATA/HORA: ')
                        + str(data_atual)
                        + ' | IP: '
                    )
                    + str(ip_publico),
                )

                if 'termo-de-adesao' in nome_anexo:
                    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
                        nome_cidade = pegar_nome_cidade(latitude, longitude)
                        data = datetime.today()
                        formato_extenso = data.strftime('%d de %B de %Y')

                        pdf_path = (
                            'static/digimais/termo-de-adesao-cartao-de-credito-v1.pdf'
                        )

                        date_location = f'{nome_cidade}, {formato_extenso}'

                        if date_location_coord := word_coordinates_in_pdf(
                            pdf_path=pdf_path,
                            word='Local e Data',
                            word_order=0,
                            fix_y=-5,
                        ):
                            can.drawString(
                                date_location_coord.get('previous_line_x'),
                                date_location_coord.get('previous_line_y'),
                                date_location,
                            )

                    else:
                        if contrato.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
                            # Local
                            x = 80
                            y = 448
                            can.drawString(x, y, nome_cidade)

                            # Data
                            x = 75
                            y = 436
                            can.drawString(x, y, data_formatada)

                        elif contrato.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
                            # Local
                            x = 80
                            y = 410
                            can.drawString(x, y, nome_cidade)

                            # Data
                            x = 80
                            y = 398.5
                            can.drawString(x, y, data_formatada)

                if 'termo-de-autorizacao-inss' in nome_anexo:
                    # Assinando termo in100
                    nome_cidade = pegar_nome_cidade(latitude, longitude)
                    data = datetime.today()
                    formato_extenso = data.strftime('%d de %B de %Y')

                    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
                        pdf_path = 'static/digimais/termo-de-autorizacao-do-beneficiario-inss-v2.pdf'

                        date_location = f'{nome_cidade}, {formato_extenso}'

                        date_location_coord = word_coordinates_in_pdf(
                            pdf_path=pdf_path, word='Local e Data', word_order=0
                        )

                        fix_y_coord = 5

                        if date_location_coord:
                            can.drawString(
                                date_location_coord.get('previous_line_x'),
                                date_location_coord.get('previous_line_y')
                                - fix_y_coord,
                                date_location,
                            )

                    else:
                        # Data
                        x = 115
                        y = 615
                        can.drawString(x, y, f'{nome_cidade}, {formato_extenso}')

                if 'termo-de-consentimento' in nome_anexo:
                    # Assinando termo de consentimento
                    nome_cidade = pegar_nome_cidade(latitude, longitude)
                    data = datetime.today()
                    formato_extenso = data.strftime('%d de %B de %Y')

                    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
                        pdf_path = 'static/digimais/termo-de-consentimento-cartao-consignado-de-beneficio-v2.pdf'
                        date_location = (
                            f'{nome_cidade}, {formato_extenso}, {hora_atual}'
                        )

                        if date_location_coord := word_coordinates_in_pdf(
                            pdf_path=pdf_path,
                            word='Local e Data',
                            word_order=0,
                        ):
                            can.drawString(
                                date_location_coord.get('previous_line_x'),
                                date_location_coord.get('previous_line_y'),
                                date_location,
                            )

                    else:
                        # Localização
                        x = 190
                        y = 333
                        can.drawString(x, y, f'{nome_cidade}')

                        # Data e hora
                        x = 190
                        y = 316
                        can.drawString(x, y, f'{formato_extenso}, {hora_atual}')

                from datetime import datetime

                if 'termo-vida-inss' in nome_anexo:
                    # Assinando termo de consentimento
                    nome_cidade = pegar_nome_cidade(latitude, longitude)
                    data = datetime.today()
                    formato_extenso = data.strftime('%d de %B de %Y')

                    # Extrair dia, mês e ano
                    dia = data.day
                    mes = data.month
                    ano = data.year

                    # Localização
                    x = 85
                    y = 238
                    can.drawString(x, y, f'{nome_cidade}')

                    # Dia
                    x = 263
                    y = 238
                    can.drawString(x, y, f'{dia}')
                    # Mes
                    x = 290
                    y = 238
                    can.drawString(x, y, f'{mes}')
                    # Ano
                    x = 313
                    y = 238
                    can.drawString(x, y, f'{ano}')
                    # Nome Cliente
                    x = 80
                    y = 128
                    can.drawString(x, y, f'{cliente.nome_cliente}')
                    # CPF
                    x = 72
                    y = 112
                    can.drawString(x, y, f'{cliente.nu_cpf}')

                if 'termo-vida-siape' in nome_anexo:
                    # Assinando termo de consentimento
                    nome_cidade = pegar_nome_cidade(latitude, longitude)
                    data = datetime.today()
                    formato_extenso = data.strftime('%d de %B de %Y')

                    # Extrair dia, mês e ano
                    dia = data.day
                    mes = data.month
                    ano = data.year

                    # Localização
                    x = 86
                    y = 121
                    can.drawString(x, y, f'{nome_cidade}')

                    # Dia
                    x = 272
                    y = 121
                    can.drawString(x, y, f'{dia}')
                    # Mes
                    x = 297
                    y = 121
                    can.drawString(x, y, f'{mes}')
                    # Ano
                    x = 321
                    y = 121
                    can.drawString(x, y, f'{ano}')

                    # Nome Cliente
                    x = 83
                    y = 93
                    can.drawString(x, y, f'{cliente.nome_cliente}')
                    # CPF
                    x = 72
                    y = 77
                    can.drawString(x, y, f'{cliente.nu_cpf}')

                if 'termo-ouro-inss' in nome_anexo:
                    # Assinando termo de consentimento
                    nome_cidade = pegar_nome_cidade(latitude, longitude)
                    data = datetime.today()
                    formato_extenso = data.strftime('%d de %B de %Y')

                    # Extrair dia, mês e ano
                    dia = data.day
                    mes = data.month
                    ano = data.year

                    # Localização
                    x = 55
                    y = 375
                    can.drawString(x, y, f'{nome_cidade}')

                    # Dia
                    x = 223
                    y = 375
                    can.drawString(x, y, f'{dia}')
                    # Mes
                    x = 247
                    y = 375
                    can.drawString(x, y, f'{mes}')
                    # Ano
                    x = 270
                    y = 375
                    can.drawString(x, y, f'{ano}')
                    # Nome Cliente
                    x = 50
                    y = 293
                    can.drawString(x, y, f'{cliente.nome_cliente}')
                    # CPF
                    x = 40
                    y = 258
                    can.drawString(x, y, f'{cliente.nu_cpf}')

                can.save()

                # Obtenha a página com o texto como um objeto PdfFileReader
                new_page = PdfFileReader(packet).getPage(0)

                # Mesclando a página original com a página atualizada
                page.mergePage(new_page)

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_filename = f'{nome_anexo}_editado_temp.pdf'
                    with open(f'{temp_dir}/{temp_filename}', 'wb') as output_file:
                        output_pdf.write(output_file)

                    new_object_key = f'{nome_pasta}/{nome_anexo}-assinado.pdf'
                    with open(f'{temp_dir}/{temp_filename}', 'rb') as file_to_upload:
                        s3 = boto3.resource('s3')
                        bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS)

                        s3 = boto3.resource('s3')
                        bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS)
                        bucket_name = settings.BUCKET_NAME_TERMOS
                        bucket.upload_fileobj(
                            file_to_upload,
                            new_object_key,
                            ExtraArgs={'ContentType': 'application/pdf'},
                        )

                        url = s3_cliente.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': bucket_name, 'Key': new_object_key},
                            ExpiresIn=31536000,
                        )

                        anexo, _ = AnexoContrato.objects.update_or_create(
                            contrato=contrato,
                            nome_anexo=f'{nome_anexo}-assinado',
                            defaults={
                                'tipo_anexo': EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                                'anexo_extensao': 'pdf',
                                'anexo_url': url,
                            },
                        )


def download_arquivo_s3_base64(bucket_name, object_key):
    url = s3_cliente.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=31536000,
    )
    # Baixe o arquivo usando a URL presigned
    response = requests.get(url)
    documento_bytes = response.content

    return io.BytesIO(documento_bytes)


def pegar_nome_cidade(latitude, longitude):
    geolocator = Nominatim(user_agent='meu_app', timeout=30)
    localizacao = geolocator.reverse((latitude, longitude), language='pt')
    try:
        cidade = (
            localizacao.raw['address'].get('town')
            or localizacao.raw['address'].get('city')
            or localizacao.raw['address'].get('village')
            or localizacao.raw['address'].get('municipality')
        )
    except Exception as e:
        logger.error(f'Erro ao consultar nome da cidade (pegar_nome_cidade): {e}')
        cidade = ''
    return cidade
