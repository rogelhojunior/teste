import hashlib
import io
import tempfile
from datetime import datetime

import boto3
from django.conf import settings
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from contract.constants import EnumTipoAnexo
from contract.models.anexo_contrato import AnexoContrato
from contract.products.cartao_beneficio.termos import s3_cliente
from contract.termos import pegar_nome_cidade
from core.models import Cliente
from core.utils import word_coordinates_in_pdf


def fill_term_agreement_digimais(id_cliente, latitude, longitude, ip_publico, contrato):
    pdf_path = (
        'static/digimais/termo-de-consentimento-cartao-consignado-de-beneficio-v2.pdf'
    )

    def fill_term_agreement_digimais_first_section(canvas_pdf, customer):
        name_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Eu,', word_order=0
        )
        cpf_coord = word_coordinates_in_pdf(pdf_path=pdf_path, word='n.º', word_order=0)

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

    def fill_term_agreement_digimais_second_section(
        canvas_pdf, date_location, hash_text
    ):
        date_location_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Local e Data', word_order=0
        )
        hash_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Assinatura Eletrônica', word_order=0
        )

        if date_location_coord:
            canvas_pdf.drawString(
                date_location_coord.get('previous_line_x'),
                date_location_coord.get('previous_line_y'),
                date_location,
            )
        if hash_coord:
            canvas_pdf.drawString(
                hash_coord.get('previous_line_start_x'),
                hash_coord.get('previous_line_start_y'),
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
                fill_term_agreement_digimais_first_section(
                    canvas_pdf=can, customer=cliente
                )

            elif page_num == num_pages - 1:  # Se for a última página
                hash_text = f'{hash.upper()} | {nome_cidade} - DATA/HORA: {str(data_hoje)} | IP: {str(ip_publico)}'
                date_location = f'{nome_cidade}, {data_hoje.strftime("%d/%m/%Y")}'

                fill_term_agreement_digimais_second_section(
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
        with open(f'{temp_dir}/termo-consentimento-cartao.pdf', 'wb') as outputStream:
            output_pdf.write(outputStream)

        # abre o arquivo PDF que foi salvo anteriormente
        # with open(f'{temp_dir}/termo-consentimento-cartao.pdf', 'rb') as f:
        #     # lê os dados do arquivo em um objeto BytesIO
        #     file_stream = io.BytesIO(f.read())

        return salva_no_s3(
            temp_dir=temp_dir, output_pdf=output_pdf, cliente=cliente, contrato=contrato
        )


def salva_no_s3(temp_dir, output_pdf, cliente, contrato):
    # Salve o arquivo de saída
    with open(f'{temp_dir}/termo-consentimento-cartao.pdf', 'wb') as outputStream:
        output_pdf.write(outputStream)

    # abre o arquivo PDF que foi salvo anteriormente
    with open(f'{temp_dir}/termo-consentimento-cartao.pdf', 'rb') as f:
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
        f'{nome_pasta}/termo-consentimento-cartao.pdf',
        ExtraArgs={'ContentType': 'application/pdf'},
    )

    object_key = f'{nome_pasta}/termo-consentimento-cartao.pdf'

    url = s3_cliente.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=31536000,
    )

    agreement_term = AnexoContrato.objects.create(
        contrato=contrato,
        tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
        nome_anexo='termo_de_consentimento_assinado',
        anexo_extensao='pdf',
        anexo_url=url,
    )

    return agreement_term.anexo_url
