import io
import os

import boto3
import requests
from botocore.exceptions import ClientError
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from contract.choices import TIPOS_ANEXO
from contract.constants import EnumTipoAnexo, EnumTipoProduto
from handlers.aws_boto3 import Boto3Manager


# Retrieve the Contrato model using get_model, this avoid circular import error
class AnexoContrato(models.Model):
    contrato = models.ForeignKey(
        'contract.Contrato', verbose_name='Contrato', on_delete=models.CASCADE
    )
    tipo_anexo = models.SmallIntegerField(
        verbose_name='Tipo do anexo', choices=TIPOS_ANEXO, null=True, blank=True
    )
    nome_anexo = models.CharField(verbose_name='Nome do anexo', max_length=300)
    anexo_extensao = models.CharField(verbose_name='Código extensão', max_length=10)
    anexo_url = models.URLField(
        verbose_name='URL do documento', max_length=500, null=True, blank=True
    )
    arquivo = models.FileField(
        verbose_name='Documento', null=True, blank=True, upload_to='cliente'
    )
    anexado_em = models.DateTimeField(verbose_name='Anexado em', auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True, default=None)
    active = models.BooleanField(verbose_name='Ativo', default=True)

    def save(self, *args, **kwargs):
        MAX_SIZE = 20000000  # 20 MB
        VALID_EXTENSIONS = ('png', 'jpg', 'jpeg', 'tiff', 'pdf')
        if self.anexo_extensao and self.anexo_extensao not in VALID_EXTENSIONS:
            raise ValidationError(
                f'Extensão inválida, formatos aceitos: {VALID_EXTENSIONS}'
            )

        if self.arquivo and self.arquivo.size < MAX_SIZE:
            raise ValidationError('O Tamanho do arquivo não pode exceder 20 MB')

        super(AnexoContrato, self).save(*args, **kwargs)

    def delete(self):
        if self.tipo_anexo in [EnumTipoAnexo.TERMOS_E_ASSINATURAS, EnumTipoAnexo.CCB]:
            return

        self.active = False
        self.deleted_at = timezone.now()
        self.save()

    @property
    def name_with_extension(self) -> str:
        """Return the name of the file with the extension."""
        return f'{self.nome_anexo}.{self.anexo_extensao}'

    @property
    def is_stored_on_s3(self) -> bool:
        """
        Checks if this attachment file is stored on a amazon S3 bucket.

        Returns:
            bool: True if the attachment file is stored on a amazon S3
            bucket, False otherwise.
        """
        return 's3.amazonaws.com' in self.anexo_url

    def extract_object_key_from_url(self) -> str:
        """
        Extract the object key from attribute 'anexo_url'.

        Returns:
            str: The object key.
        """
        url = self.anexo_url
        return url.split('.com/')[1].split('?')[0]

    def extract_bucket_name_from_url(self) -> str:
        """
        Extract the S3 bucket name from attribute 'anexo_url'.

        Returns:
            str: The object key.
        """
        url = self.anexo_url
        return url.split('/')[2].split('.')[0]

    @property
    def get_attachment_url(self) -> str:
        """
        Checks if anexo_url is from amazonaws, because there are some urls from google storage.
        Gets original URL without query params
        Generates presigned key if url is not expired yet.
        """
        boto3_manager = Boto3Manager()
        return boto3_manager.get_url_with_new_expiration(self.anexo_url)

    def __str__(self):
        return self.nome_anexo

    class Meta:
        verbose_name = 'Contrato - Anexo'
        verbose_name_plural = 'Contrato - Anexos'

    def download(self, directory: str) -> str:
        """
        Download an attachment from storage server (S3).

        Args:
            directory (str): The directory where the file will be downloaded.

        Returns:
            str: the path to the file that was downloaded
        """
        from contract.models.anexo_contrato.anexo_contrato_amazon_s3_interface import (
            AnexoContratoAmazonS3Interface,
        )

        destination_path = os.path.join(directory, self.name_with_extension)
        try:
            # try to download using S# interface
            s3_interface = AnexoContratoAmazonS3Interface(self)
            s3_interface.download_file_from_s3(destination_path)
        except ClientError:
            download_using_get_request(self.anexo_url, destination_path)
        return destination_path


def download_using_get_request(url: str, path_to_save: str):
    """
    Download content from a given URL using a GET request and save it to
    a local file.

    Args:
        url (str): The URL from which to download content.
        path_to_save (str): The local file path where the downloaded
        content will be saved.

    Raises:
        requests.exceptions.RequestException: If the GET request
        encounters an error.
        OSError: If there are issues with opening or writing to the
        local file.

    Note:
        This function performs a GET request to the specified URL,
        checks for any errors in the response, and writes the content to
        the specified local file in binary mode ('wb').

    Example:
        download_using_get_request('https://example.com/file.txt',
        '/path/to/save/file.txt')
    """
    response = requests.get(url)
    response.raise_for_status()
    with open(path_to_save, 'wb') as file:
        file.write(response.content)


@receiver(post_save, sender=AnexoContrato)
def handle_post_save(sender, instance, created, **kwargs):
    s3_cliente = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    if (
        instance.contrato.tipo_produto
        in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        )
        and instance.arquivo
    ):
        file_stream = io.BytesIO(instance.arquivo.read())
        # Conecta ao S3
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(settings.BUCKET_NAME_AMIGOZ)
        bucket_name = settings.BUCKET_NAME_AMIGOZ
        nome_pasta = str(instance.contrato.token_contrato)
        # Salva o arquivo no S3
        nome_arquivo = str(instance.arquivo)
        nome_arquivo_extensao = nome_arquivo.split('.')[1]
        if nome_arquivo_extensao not in {'png', 'jpg', 'jpeg', 'pdf'}:
            nome_arquivo_extensao = 'jpg'
        # print(nome_arquivo_extensao)
        if nome_arquivo_extensao == 'pdf':
            bucket.upload_fileobj(
                file_stream,
                f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}',
                ExtraArgs={'ContentType': 'application/pdf'},
            )
        else:
            bucket.upload_fileobj(
                file_stream,
                f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}',
                ExtraArgs={'ContentType': 'image/jpg'},
            )

        object_key = f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}'

        url = s3_cliente.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=31536000,
        )
        instance.anexo_url = url
        instance.anexo_extensao = nome_arquivo_extensao
        instance.arquivo.delete()
        contrato = apps.get_model('contract', 'Contrato').objects.get(
            token_contrato=instance.contrato.token_contrato
        )
        if instance.tipo_anexo == EnumTipoAnexo.CNH:
            contrato.pendente_documento = False
        if instance.tipo_anexo == EnumTipoAnexo.COMPROVANTE_ENDERECO:
            contrato.pendente_endereco = False
        if instance.tipo_anexo == EnumTipoAnexo.DOCUMENTO_VERSO:
            contrato.pendente_documento = False
        contrato.save()
        instance.save()

    if (
        instance.contrato.tipo_produto
        in (
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
            EnumTipoProduto.INSS_CORBAN,
        )
        and instance.arquivo
    ):
        file_stream = io.BytesIO(instance.arquivo.read())
        # Conecta ao S3
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(settings.BUCKET_NAME_INSS)
        bucket_name = settings.BUCKET_NAME_INSS
        nome_pasta = str(instance.contrato.token_contrato)
        # Salva o arquivo no S3
        nome_arquivo = str(instance.arquivo)
        nome_arquivo_extensao = nome_arquivo.split('.')[1]
        if nome_arquivo_extensao not in {'png', 'jpg', 'jpeg', 'pdf'}:
            nome_arquivo_extensao = 'jpg'
        # print(nome_arquivo_extensao)
        if nome_arquivo_extensao == 'pdf':
            bucket.upload_fileobj(
                file_stream,
                f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}',
                ExtraArgs={'ContentType': 'application/pdf'},
            )
        else:
            bucket.upload_fileobj(
                file_stream,
                f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}',
                ExtraArgs={'ContentType': 'image/jpg'},
            )

        object_key = f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}'

        url = s3_cliente.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=31536000,
        )
        instance.anexo_url = url
        instance.anexo_extensao = nome_arquivo_extensao
        instance.arquivo.delete()

        contrato = apps.get_model('contract', 'Contrato').objects.get(
            token_contrato=instance.contrato.token_contrato
        )
        if instance.tipo_anexo == EnumTipoAnexo.CNH:
            contrato.pendente_documento = False
        if instance.tipo_anexo == EnumTipoAnexo.COMPROVANTE_ENDERECO:
            contrato.pendente_endereco = False
        if instance.tipo_anexo == EnumTipoAnexo.DOCUMENTO_VERSO:
            contrato.pendente_documento = False
        contrato.save()
        instance.save()

    if (
        instance.contrato.tipo_produto in (EnumTipoProduto.PORTABILIDADE,)
        and instance.arquivo
    ):
        file_stream = io.BytesIO(instance.arquivo.read())
        # Conecta ao S3
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(settings.BUCKET_NAME_PORTABILIDADE)
        bucket_name = settings.BUCKET_NAME_PORTABILIDADE
        nome_pasta = str(instance.contrato.token_contrato)
        # Salva o arquivo no S3
        nome_arquivo = str(instance.arquivo)
        nome_arquivo_extensao = nome_arquivo.split('.')[1]
        if nome_arquivo_extensao not in {'png', 'jpg', 'jpeg', 'pdf'}:
            nome_arquivo_extensao = 'jpg'
        # print(nome_arquivo_extensao)
        if nome_arquivo_extensao == 'pdf':
            bucket.upload_fileobj(
                file_stream,
                f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}',
                ExtraArgs={'ContentType': 'application/pdf'},
            )
        else:
            bucket.upload_fileobj(
                file_stream,
                f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}',
                ExtraArgs={'ContentType': 'image/jpg'},
            )

        object_key = f'{nome_pasta}/{instance.nome_anexo}.{nome_arquivo_extensao}'

        url = s3_cliente.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=31536000,
        )
        instance.anexo_url = url
        instance.anexo_extensao = nome_arquivo_extensao
        instance.arquivo.delete()

        contrato = apps.get_model('contract', 'Contrato').objects.get(
            token_contrato=instance.contrato.token_contrato
        )
        if instance.tipo_anexo == EnumTipoAnexo.CNH:
            contrato.pendente_documento = False
        if instance.tipo_anexo == EnumTipoAnexo.COMPROVANTE_ENDERECO:
            contrato.pendente_endereco = False
        if instance.tipo_anexo == EnumTipoAnexo.DOCUMENTO_VERSO:
            contrato.pendente_documento = False
        contrato.save()
        instance.save()
