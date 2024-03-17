import base64
import io

import boto3
from django.conf import settings

"""
Arquivo para manipulação de documentos no geral
"""

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


def converter_base64(nome_arquivo, arquivo_base64, nome_pasta):
    """
    Conversão de arquivo base64 para arquivo jpg e upload no S3
    """
    formated_base64 = str(arquivo_base64)
    start = formated_base64.find(',/')
    transform_base64 = formated_base64[start:]

    binary_data = base64.b64decode(transform_base64)

    bucket = settings.BUCKET_NAME_AMIGOZ
    bucket_name = 'documentos-clientes-amigoz'

    # Define o caminho do arquivo PDF a ser salvo
    file_stream = io.BytesIO(binary_data)

    # Conecta ao S3
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)
    # Salva o arquivo no S3
    bucket.upload_fileobj(
        file_stream,
        f'{nome_pasta}/{nome_arquivo}.jpg',
        ExtraArgs={'ContentType': 'image/jpg'},
    )

    object_key = f'{nome_pasta}/{nome_arquivo}.jpg'
    return s3_cliente.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket_name, 'Key': object_key},
        ExpiresIn=31536000,
    )
