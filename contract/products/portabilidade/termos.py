import hashlib
import io
import tempfile
from datetime import datetime

import boto3
from django.conf import settings
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from contract.termos import pegar_nome_cidade, s3_cliente
from core.models.anexo_cliente import AnexoCliente


def assinatura_termo_in100(latitude, longitude, ip_publico, cliente, in100):
    try:
        nome_cidade = pegar_nome_cidade(latitude, longitude)
        data_atual_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_atual = datetime.now().strftime('%d-%m-%Y')
        dados_cliente_hash = (
            ip_publico
            + cliente.nu_cpf
            + data_atual_hora
            + str(latitude)
            + str(longitude)
        )
        hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = PdfFileReader(open('static/TermoAutorizacaoIN100.pdf', 'rb'))
            output_pdf = PdfFileWriter()

            # Itere sobre todas as páginas do arquivo de entrada e adicione-as ao objeto PdfFileWriter
            for page_num in range(input_pdf.getNumPages()):
                page = input_pdf.getPage(page_num)
                output_pdf.addPage(page)

            # Obtenha a página 0 do PDF
            page = input_pdf.getPage(0)
            # Crie um arquivo de pacote de bytes e um objeto canvas
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Defina a fonte e o tamanho da fonte
            can.setFont('Helvetica', 9)

            # Adicione o texto ao objeto canvas
            # Nome do Cliente:
            x = 100
            y = 705
            can.drawString(x, y, cliente.nome_cliente)
            # Adicione o texto ao objeto canvas
            # CPF do Cliente:
            x = 400
            y = 705
            can.drawString(x, y, cliente.nu_cpf)
            # Adicione o texto ao objeto canvas
            # Dia da Assinatura:
            x = 185
            y = 155
            can.drawString(x, y, f'{data_atual}'[:2])
            # Adicione o texto ao objeto canvas
            # Mes da Assinatura:
            x = 225
            y = 155
            can.drawString(x, y, f'{data_atual}'[3:5])
            # Adicione o texto ao objeto canvas
            # Ano da Assinatura:
            x = 265
            y = 155
            can.drawString(x, y, f'{data_atual}'[6:])
            # Adicione o texto ao objeto canvas
            x = 30
            y = 100
            can.drawString(
                x,
                y,
                f'{hash.upper()} | {nome_cidade} - DATA/HORA: {str(data_atual_hora)} | IP: {str(ip_publico)}',
            )

            can.save()

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Salve o arquivo de saída
            with open(f'{temp_dir}/termo-in100.pdf', 'wb') as outputStream:
                output_pdf.write(outputStream)

            # abre o arquivo PDF que foi salvo anteriormente
            with open(f'{temp_dir}/termo-in100.pdf', 'rb') as f:
                # lê os dados do arquivo em um objeto BytesIO
                file_stream = io.BytesIO(f.read())

            # Conecta ao S3
            # s3 = boto3.resource(
            #     "s3",
            #     region_name='us-east-1',
            #     aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            #     aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            # )
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            # bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS_IN100)
            bucket_name = settings.BUCKET_NAME_TERMOS_IN100
            nome_pasta = str(cliente.nu_cpf)
            # Salva o arquivo no S3
            extra_args = {'ACL': 'private', 'ContentType': 'application/pdf'}
            s3.upload_fileobj(
                Fileobj=file_stream,
                Bucket=bucket_name,
                Key=f'{nome_pasta}/termo-in100.pdf',
                ExtraArgs=extra_args,
            )
            # bucket.upload_fileobj(file_stream, f"{nome_pasta}/termo-in100.pdf",
            #                       ExtraArgs={'ContentType': 'application/pdf'})

            object_key = f'{nome_pasta}/termo-in100.pdf'
            # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

            url = s3_cliente.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=31536000,
            )

            AnexoCliente.objects.create(
                cliente=cliente,
                nome_anexo='Termo_de_Autorizacao_IN100',
                anexo_extensao='pdf',
                anexo_url=url,
                anexado_em=data_atual_hora,
            )

    except Exception as e:
        print(e)
        print(
            'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo termo de autorização da IN100'
        )
