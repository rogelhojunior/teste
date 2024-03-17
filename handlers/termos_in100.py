import hashlib
import io
import logging
import tempfile
from datetime import datetime, timedelta

import boto3
from django.conf import settings
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from contract.products.cartao_beneficio.termos import s3_cliente
from contract.termos import pegar_nome_cidade
from core.models import Cliente
from core.models.aceite_in100 import (
    AceiteIN100,
    DocumentoAceiteIN100,
    HistoricoAceiteIN100,
)
from core.utils import word_coordinates_in_pdf

logger = logging.getLogger('digitacao')


def aceite_in100(id_cliente, latitude, longitude, ip_publico, produto):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open('static/TERMO DE AUTORIZAÇÃO PARA ACESSO A DADOS - v2.pdf', 'rb')
        )
        output_pdf = PdfFileWriter()

        cliente = Cliente.objects.get(id=id_cliente)

        numero_cpf = cliente.nu_cpf
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        dados_cliente_hash = (
            str(ip_publico)
            + str(numero_cpf)
            + str(data_atual)
            + str(latitude)
            + str(longitude)
        )

        hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()

        num_pages = input_pdf.getNumPages()

        data_hoje = datetime.now()
        nome_cidade = pegar_nome_cidade(latitude, longitude)

        # Definir as "novas páginas" como nulas inicialmente
        new_page_first = None
        new_page_last = None

        for page_num in range(num_pages):
            page = input_pdf.getPage(page_num)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont('Helvetica', 9)

            # Defina as coordenadas x e y dependendo do número da página
            if page_num == 0:
                # NOME
                x = 45
                y = 733
                can.drawString(x, y, cliente.nome_cliente)

                # CPF
                x = 420
                y = 733
                can.drawString(x, y, cliente.nu_cpf)

                x = 45
                y = 210
                # Adicione a hash
                can.drawString(
                    x,
                    y,
                    (
                        (f'{hash.upper()}' + f' | {nome_cidade} - DATA/HORA: ')
                        + str(data_hoje)
                        + ' | IP: '
                    )
                    + str(ip_publico),
                )
            elif page_num == num_pages - 1:  # Se for a última página
                x = 45
                y = 400
                # Adicione a hash
                can.drawString(
                    x,
                    y,
                    (
                        (f'{hash.upper()}' + f' | {nome_cidade} - DATA/HORA: ')
                        + str(data_hoje)
                        + ' | IP: '
                    )
                    + str(ip_publico),
                )
            can.save()
            # Obtenha a página com o hash como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Determine qual "nova página" deve ser atualizada
            if page_num == 0:
                new_page_first = new_page
            elif page_num == num_pages - 1:  # Se for a última página
                new_page_last = new_page

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Adicione a página ao PDF de saída
            output_pdf.addPage(page)

        # Mesclando a página original com a página atualizada para a primeira e última página
        if new_page_first is not None:
            output_pdf.getPage(0).mergePage(new_page_first)
        if new_page_last is not None:
            output_pdf.getPage(num_pages - 1).mergePage(new_page_last)

        # Salve o arquivo de saída
        with open(f'{temp_dir}/termo-in100-cartao.pdf', 'wb') as outputStream:
            output_pdf.write(outputStream)

        # abre o arquivo PDF que foi salvo anteriormente
        # with open(f'{temp_dir}/termo-in100-cartao.pdf', 'rb') as f:
        #     # lê os dados do arquivo em um objeto BytesIO
        #     file_stream = io.BytesIO(f.read())

        return salva_no_s3(temp_dir, output_pdf, cliente, data_hoje, produto, hash)


def aceite_in100_pine(id_cliente, latitude, longitude, ip_publico, produto):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open(
                'static/TERMO DE AUTORIZAÇÃO INSS - CARTÃO BENEFÍCIO - v3.pdf',
                'rb',
            )
        )
        output_pdf = PdfFileWriter()

        cliente = Cliente.objects.get(id=id_cliente)
        numero_cpf = cliente.nu_cpf
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        dados_cliente_hash = (
            str(ip_publico)
            + str(numero_cpf)
            + str(data_atual)
            + str(latitude)
            + str(longitude)
        )

        hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()

        num_pages = input_pdf.getNumPages()

        data_hoje = datetime.now()
        nome_cidade = pegar_nome_cidade(latitude, longitude)

        # Definir as "novas páginas" como nulas inicialmente
        new_page_first = None
        new_page_last = None

        for page_num in range(num_pages):
            page = input_pdf.getPage(page_num)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont('Helvetica', 9)

            # Defina as coordenadas x e y dependendo do número da página
            if page_num == 0:
                # NOME
                x = 80
                y = 568
                can.drawString(x, y, cliente.nome_cliente)

                # CPF
                x = 420
                y = 568
                can.drawString(x, y, cliente.nu_cpf)

            elif page_num == num_pages - 1:  # Se for a última página
                # x = 40
                # y = 152

                # Data
                x = 115
                y = 615

                data = datetime.now()
                formato_extenso = data.strftime('%d de %B de %Y')

                can.drawString(x, y, f'{nome_cidade}, {formato_extenso}')

                x = 40
                y = 570
                # Adicione a hash
                can.drawString(
                    x,
                    y,
                    (
                        (f'{hash.upper()}' + f' | {nome_cidade} - DATA/HORA: ')
                        + str(data_hoje)
                        + ' | IP: '
                    )
                    + str(ip_publico),
                )

            can.save()
            # Obtenha a página com o hash como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Determine qual "nova página" deve ser atualizada
            if page_num == 0:
                new_page_first = new_page
            elif page_num == num_pages - 1:  # Se for a última página
                new_page_last = new_page

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Adicione a página ao PDF de saída
            output_pdf.addPage(page)

        # Mesclando a página original com a página atualizada para a primeira e última página
        if new_page_first is not None:
            output_pdf.getPage(0).mergePage(new_page_first)
        if new_page_last is not None:
            output_pdf.getPage(num_pages - 1).mergePage(new_page_last)

        # Salve o arquivo de saída
        with open(f'{temp_dir}/termo-in100-cartao.pdf', 'wb') as outputStream:
            output_pdf.write(outputStream)

        # abre o arquivo PDF que foi salvo anteriormente
        # with open(f'{temp_dir}/termo-in100-cartao.pdf', 'rb') as f:
        #     # lê os dados do arquivo em um objeto BytesIO
        #     file_stream = io.BytesIO(f.read())

        return salva_no_s3(temp_dir, output_pdf, cliente, data_hoje, produto, hash)


def aceite_in100_digimais(id_cliente, latitude, longitude, ip_publico, produto):
    pdf_path = 'static/digimais/termo-de-autorizacao-do-beneficiario-inss-v2.pdf'

    def fill_accept_digimais_first_section(canvas_pdf, customer):
        name_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Eu, ', word_order=0
        )
        cpf_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='sob o n.º', word_order=0
        )

        if name_coord and customer.nome_cliente:
            canvas_pdf.drawString(
                name_coord.get('same_line_x'),
                name_coord.get('same_line_y'),
                customer.nome_cliente,
            )

        if cpf_coord and customer.nu_cpf:
            canvas_pdf.drawString(
                cpf_coord.get('same_line_x'),
                cpf_coord.get('same_line_y'),
                customer.nu_cpf,
            )

    def fill_accept_digimais_second_section(canvas_pdf, customer):
        name_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='1. Nome Completo:', word_order=0
        )
        cpf_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='2. CPF N.º:', word_order=0
        )
        birthdate_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='3. Data de Nascimento:', word_order=0
        )

        if name_coord and customer.nome_cliente:
            canvas_pdf.drawString(
                name_coord.get('next_line_x'),
                name_coord.get('next_line_y'),
                customer.nome_cliente,
            )

        if cpf_coord and customer.nu_cpf:
            canvas_pdf.drawString(
                cpf_coord.get('next_line_x'),
                cpf_coord.get('next_line_y'),
                customer.nu_cpf,
            )

        if birthdate_coord and customer.dt_nascimento:
            canvas_pdf.drawString(
                birthdate_coord.get('next_line_x'),
                birthdate_coord.get('next_line_y'),
                customer.dt_nascimento.strftime('%d/%m/%Y'),
            )

    # def fill_accept_digimais_third_section(canvas_pdf, benefit):
    #     benefit_number_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='1. Número do Benefício', word_order=0
    #     )
    #     benefit_situation_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='2. Situação do Benefício', word_order=0
    #     )
    #     benefit_type_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='3. Espécie de benefício', word_order=0
    #     )
    #     benefit_indication_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='4. Indicação de que', word_order=0
    #     )
    #     benefit_date_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='5. Data da Cessação', word_order=0
    #     )
    #     has_legal_representative_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='6. Possui Representante Legal', word_order=0
    #     )
    #     has_attorney_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='7. Possui Procurador', word_order=0
    #     )
    #     has_entity_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='8. Possui Entidade', word_order=0
    #     )
    #     has_alimony_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='9. Pensão Alimentícia', word_order=0
    #     )
    #     is_blocked_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='10. Bloqueado', word_order=0
    #     )
    #     medical_expertise_date_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='11. Data da última Perícia', word_order=0
    #     )
    #     dispatch_date_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='12. Data do Despacho', word_order=0
    #     )
    #     is_elegible_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='13. Elegível para Empréstimo', word_order=0
    #     )

    #     if benefit_number_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_number_coord.get('next_line_x'),
    #             benefit_number_coord.get('next_line_y'),
    #             'benefit_number_coord',
    #         )
    #     if benefit_situation_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_situation_coord.get('next_line_x'),
    #             benefit_situation_coord.get('next_line_y'),
    #             'benefit_situation_coord',
    #         )
    #     if benefit_type_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_type_coord.get('next_line_x'),
    #             benefit_type_coord.get('next_line_y'),
    #             'benefit_type_coord',
    #         )
    #     if benefit_indication_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_indication_coord.get('next_line_x'),
    #             benefit_indication_coord.get('next_line_y'),
    #             'benefit_indication_coord',
    #         )
    #     if benefit_date_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_date_coord.get('next_line_x'),
    #             benefit_date_coord.get('next_line_y'),
    #             'benefit_date_coord',
    #         )
    #     if has_legal_representative_coord and benefit:
    #         canvas_pdf.drawString(
    #             has_legal_representative_coord.get('next_line_x'),
    #             has_legal_representative_coord.get('next_line_y'),
    #             'x',
    #         )
    #     if has_attorney_coord and benefit:
    #         canvas_pdf.drawString(
    #             has_attorney_coord.get('next_line_x'),
    #             has_attorney_coord.get('next_line_y'),
    #             'x',
    #         )
    #     if has_entity_coord and benefit:
    #         canvas_pdf.drawString(
    #             has_entity_coord.get('next_line_x'),
    #             has_entity_coord.get('next_line_y'),
    #             'x',
    #         )
    #     if has_alimony_coord and benefit:
    #         canvas_pdf.drawString(
    #             has_alimony_coord.get('next_line_x'),
    #             has_alimony_coord.get('next_line_y'),
    #             'x',
    #         )
    #     if is_blocked_coord and benefit:
    #         canvas_pdf.drawString(
    #             is_blocked_coord.get('next_line_x'),
    #             is_blocked_coord.get('next_line_y'),
    #             'x',
    #         )
    #     if medical_expertise_date_coord and benefit:
    #         canvas_pdf.drawString(
    #             medical_expertise_date_coord.get('next_line_x'),
    #             medical_expertise_date_coord.get('next_line_y'),
    #             'medical_expertise_date_coord',
    #         )
    #     if dispatch_date_coord and benefit:
    #         canvas_pdf.drawString(
    #             dispatch_date_coord.get('next_line_x'),
    #             dispatch_date_coord.get('next_line_y'),
    #             'dispatch_date_coord',
    #         )
    #     if is_elegible_coord and benefit:
    #         canvas_pdf.drawString(
    #             is_elegible_coord.get('next_line_x'),
    #             is_elegible_coord.get('next_line_y'),
    #             'x',
    #         )

    # def fill_accept_digimais_fourth_section(canvas_pdf, benefit):
    #     benefit_uf_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='1. UF onde o beneficiário', word_order=0
    #     )
    #     benefit_credit_type_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='2. Tipo de Crédito', word_order=0
    #     )
    #     benefit_financial_institution_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='3. indicação da Instituição', word_order=0
    #     )
    #     benefit_agency_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='4. Agência Pagadora ', word_order=0
    #     )
    #     benefit_account_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='5. Conta-corrente', word_order=0
    #     )
    #     available_margin_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='6. Margem Consignável Disponível', word_order=0
    #     )
    #     available_card_margin_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path,
    #         word='7. Margem Consignável Disponível para Cartão',
    #         word_order=0,
    #     )
    #     card_limit_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='8. Valor Limite para Cartão', word_order=0
    #     )
    #     loan_quantity_coord = word_coordinates_in_pdf(
    #         pdf_path=pdf_path, word='9. Quantidade de empréstimos', word_order=0
    #     )

    #     if benefit_uf_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_uf_coord.get('next_line_x'),
    #             benefit_uf_coord.get('next_line_y'),
    #             'benefit_uf_coord',
    #         )
    #     if benefit_credit_type_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_credit_type_coord.get('next_line_x'),
    #             benefit_credit_type_coord.get('next_line_y'),
    #             'benefit_credit_type_coord',
    #         )
    #     if benefit_financial_institution_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_financial_institution_coord.get('next_line_x'),
    #             benefit_financial_institution_coord.get('next_line_y'),
    #             'benefit_financial_institution_coord',
    #         )
    #     if benefit_agency_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_agency_coord.get('next_line_x'),
    #             benefit_agency_coord.get('next_line_y'),
    #             'benefit_agency_coord',
    #         )
    #     if benefit_account_coord and benefit:
    #         canvas_pdf.drawString(
    #             benefit_account_coord.get('next_line_x'),
    #             benefit_account_coord.get('next_line_y'),
    #             'benefit_account_coord',
    #         )
    #     if available_margin_coord and benefit:
    #         canvas_pdf.drawString(
    #             available_margin_coord.get('next_line_x'),
    #             available_margin_coord.get('next_line_y'),
    #             'available_margin_coord',
    #         )
    #     if available_card_margin_coord and benefit:
    #         canvas_pdf.drawString(
    #             available_card_margin_coord.get('next_line_x'),
    #             available_card_margin_coord.get('next_line_y'),
    #             'available_card_margin_coord',
    #         )
    #     if card_limit_coord and benefit:
    #         canvas_pdf.drawString(
    #             card_limit_coord.get('next_line_x'),
    #             card_limit_coord.get('next_line_y'),
    #             'card_limit_coord',
    #         )
    #     if loan_quantity_coord and benefit:
    #         canvas_pdf.drawString(
    #             loan_quantity_coord.get('next_line_x'),
    #             loan_quantity_coord.get('next_line_y'),
    #             'loan_quantity_coord',
    #         )

    def fill_accept_digimais_hash_sections(canvas_pdf, date_location, hash_text):
        hash_first_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Assinatura Eletrônica', word_order=0
        )
        date_location_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Local e Data', word_order=0
        )
        hash_second_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Assinatura Eletrônica', word_order=1
        )

        fix_y_coord = 5

        if hash_first_coord:
            canvas_pdf.drawString(
                hash_first_coord.get('previous_line_start_x'),
                hash_first_coord.get('previous_line_start_y'),
                hash_text,
            )
        if date_location_coord:
            canvas_pdf.drawString(
                date_location_coord.get('previous_line_x'),
                date_location_coord.get('previous_line_y') - fix_y_coord,
                date_location,
            )
        if hash_second_coord:
            canvas_pdf.drawString(
                hash_second_coord.get('previous_line_start_x'),
                hash_second_coord.get('previous_line_start_y') - fix_y_coord,
                hash_text,
            )

    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(open(pdf_path, 'rb'))
        output_pdf = PdfFileWriter()

        cliente = Cliente.objects.get(id=id_cliente)

        dados_cliente_hash = (
            str(id_cliente) + str(latitude) + str(longitude) + str(ip_publico)
        )
        hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()

        num_pages = input_pdf.getNumPages()

        data_hoje = datetime.now()
        nome_cidade = pegar_nome_cidade(latitude, longitude)

        # Definir as "novas páginas" como nulas inicialmente
        new_page_first = None
        new_page_last = None

        for page_num in range(num_pages):
            page = input_pdf.getPage(page_num)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont('Helvetica', 9)

            # Defina as coordenadas x e y dependendo do número da página
            if page_num == 0:
                fill_accept_digimais_first_section(canvas_pdf=can, customer=cliente)
                fill_accept_digimais_second_section(canvas_pdf=can, customer=cliente)
                # fill_accept_digimais_third_section(canvas_pdf=can)
                # fill_accept_digimais_fourth_section(canvas_pdf=can)

            elif page_num == num_pages - 1:  # Se for a última página
                hash_text = f'{hash.upper()} | {nome_cidade} - DATA/HORA: {str(data_hoje)} | IP: {str(ip_publico)}'
                date_location = f'{nome_cidade}, {data_hoje.strftime("%d/%m/%Y")}'

                fill_accept_digimais_hash_sections(
                    canvas_pdf=can, date_location=date_location, hash_text=hash_text
                )

            can.save()
            # Obtenha a página com o hash como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Determine qual "nova página" deve ser atualizada
            if page_num == 0:
                new_page_first = new_page
            elif page_num == num_pages - 1:  # Se for a última página
                new_page_last = new_page

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Adicione a página ao PDF de saída
            output_pdf.addPage(page)

        # Mesclando a página original com a página atualizada para a primeira e última página
        if new_page_first is not None:
            output_pdf.getPage(0).mergePage(new_page_first)
        if new_page_last is not None:
            output_pdf.getPage(num_pages - 1).mergePage(new_page_last)

        # Salve o arquivo de saída
        with open(f'{temp_dir}/termo-in100-cartao.pdf', 'wb') as outputStream:
            output_pdf.write(outputStream)

        # abre o arquivo PDF que foi salvo anteriormente
        # with open(f'{temp_dir}/termo-in100-cartao.pdf', 'rb') as f:
        #     # lê os dados do arquivo em um objeto BytesIO
        #     file_stream = io.BytesIO(f.read())

        return salva_no_s3(temp_dir, output_pdf, cliente, data_hoje, produto, hash)


def salva_no_s3(temp_dir, output_pdf, cliente, data_hoje, produto, hash):
    # Salve o arquivo de saída
    with open(f'{temp_dir}/termo-in100-cartao.pdf', 'wb') as outputStream:
        output_pdf.write(outputStream)

    # abre o arquivo PDF que foi salvo anteriormente
    with open(f'{temp_dir}/termo-in100-cartao.pdf', 'rb') as f:
        # lê os dados do arquivo em um objeto BytesIO
        file_stream = io.BytesIO(f.read())

    # Conecta ao S3
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS_IN100)
    bucket_name = settings.BUCKET_NAME_TERMOS_IN100
    nome_pasta = str(cliente.nu_cpf)

    # Salva o arquivo no S3
    bucket.upload_fileobj(
        file_stream,
        f'{nome_pasta}/termo-in100-cartao.pdf',
        ExtraArgs={'ContentType': 'application/pdf'},
    )

    object_key = f'{nome_pasta}/termo-in100-cartao.pdf'
    # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

    url = s3_cliente.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=31536000,
    )

    data_vencimento_aceite = data_hoje + timedelta(days=45)

    aceite_in100 = AceiteIN100.objects.filter(cpf_cliente=cliente.nu_cpf).first()
    if aceite_in100:
        historico = HistoricoAceiteIN100(
            aceite_original=aceite_in100,
            canal=aceite_in100.canal,
            hash_assinatura=aceite_in100.hash_assinatura,
            data_aceite=aceite_in100.data_aceite,
            data_vencimento_aceite=aceite_in100.data_vencimento_aceite,
            produto=aceite_in100.produto,
        )
        historico.save()

        aceite_in100.data_vencimento_aceite = data_vencimento_aceite
        aceite_in100.data_aceite = data_hoje
        aceite_in100.hash_assinatura = hash.upper()
        aceite_in100.produto = produto
        aceite_in100.save()

    else:
        aceite_in100 = AceiteIN100.objects.create(
            cpf_cliente=cliente.nu_cpf,
            hash_assinatura=hash.upper(),
            data_vencimento_aceite=data_vencimento_aceite,
            produto=produto,
        )

    termo_in100 = DocumentoAceiteIN100.objects.create(
        aceite_in100=aceite_in100, nome_anexo='termo-in100-cartao.pdf', anexo_url=url
    )

    return termo_in100.anexo_url
