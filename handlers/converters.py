import base64
import io
import os

from django.core.files import File

from handlers.consultas import base64_to_jpeg, is_png, is_pdf
from pdf2image import convert_from_bytes


def get_base64_from_file(arquivo: File) -> tuple:
    """
    Transforma um arquivo para uma string base64.
    :param arquivo: Arquivo para ser convertido
    :return: Base64 string, Content type do arquivo
    """
    with arquivo.open('rb') as file:
        encoded_string = base64.b64encode(file.read()).decode('utf-8')
        nome_file = arquivo.name
        _, extensao = os.path.splitext(nome_file)
        extensao = extensao.lstrip('.')
        if extensao not in {'png', 'jpg', 'jpeg', 'pdf'}:
            extensao = 'jpg'
        content_type = 'application/pdf' if extensao == 'pdf' else 'image/jpg'
    if is_png(encoded_string):
        encoded_string = base64_to_jpeg(encoded_string)

    anexo_base64 = f'data:{content_type};base64,{encoded_string}'
    return anexo_base64, content_type


def convert_pdf_base64_to_image(base64_pdf: str, format='JPEG') -> str:
    # Verifica se a string base64 é um PDF
    if not is_pdf(base64_pdf):
        return base64_pdf  # Retorna None ou uma mensagem de erro adequada

    # Decodifica o base64 para obter o PDF em bytes
    pdf_bytes = base64.b64decode(base64_pdf)

    # Converte o PDF em bytes para imagens (uma lista, uma imagem por página)
    images = convert_from_bytes(pdf_bytes)
    # vamos assumir que você quer apenas a primeira página
    if images:
        image_buffer = io.BytesIO()
        images[0].save(image_buffer, format=format)
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode('utf-8')

        return image_base64
    else:
        return base64_pdf
