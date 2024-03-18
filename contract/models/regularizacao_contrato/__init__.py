import io
import os

import boto3
import requests
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from contract.choices import TIPOS_PENDENCIA
from contract.constants import EnumTipoProduto
from handlers.aws_boto3 import Boto3Manager


# Retrieve the Contrato model using get_model, this avoid circular import error
class RegularizacaoContrato(models.Model):
    contrato = models.ForeignKey(
        'contract.Contrato', verbose_name='Contrato', on_delete=models.CASCADE
    )
    tipo_pendencia = models.SmallIntegerField(
        verbose_name='Tipo da Pendência', choices=TIPOS_PENDENCIA, null=True, blank=True
    )

    nome_pendencia = models.ForeignKey(
        'custom_auth.UserProfile',
        verbose_name='Responsavel da Pendência',
        related_name='usuario_responsavel_pendencia',
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
    )
    mensagem_pendencia = models.CharField(
        verbose_name='Mensagem da Pendência',
        max_length=300,
        null=True,
        blank=True,
    )
    data_pendencia = models.DateTimeField(
        verbose_name='Data da Pendência', auto_now_add=True
    )

    nome_regularizacao = models.ForeignKey(
        'custom_auth.UserProfile',
        related_name='usuario_responsavel_regularizacao_pendencia',
        verbose_name='Responsavel da Regularização',
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
    )
    mensagem_regularizacao = models.CharField(
        verbose_name='Mensagem da Regularização',
        max_length=300,
        null=True,
        blank=True,
    )
    data_regularizacao = models.DateTimeField(
        verbose_name='Data da Regularização',
        auto_now_add=False,
        null=True,
        blank=True,
    )

    nome_anexo_pendencia = models.CharField(
        verbose_name='Nome do anexo - Pendência',
        max_length=300,
        null=True,
        blank=True,
    )
    anexo_extensao_pendencia = models.CharField(
        verbose_name='Código extensão - Pendência',
        max_length=10,
        null=True,
        blank=True,
    )
    anexo_url_pendencia = models.URLField(
        verbose_name='URL do documento - Pendência',
        max_length=500,
        null=True,
        blank=True,
    )
    arquivo_pendencia = models.FileField(
        verbose_name='Anexo - Pendência', null=True, blank=True, upload_to='cliente'
    )
    nome_anexo_regularizacao = models.CharField(
        verbose_name='Nome do anexo - Regularização',
        max_length=300,
        null=True,
        blank=True,
    )
    anexo_extensao_regularizacao = models.CharField(
        verbose_name='Código extensão - Regularização',
        max_length=10,
        null=True,
        blank=True,
    )
    anexo_url_regularizacao = models.URLField(
        verbose_name='URL do documento - Regularização',
        max_length=500,
        null=True,
        blank=True,
    )
    arquivo_regularizacao = models.FileField(
        verbose_name='Anexo - Regularização', null=True, blank=True, upload_to='cliente'
    )

    deleted_at = models.DateTimeField(blank=True, null=True, default=None)
    active = models.BooleanField(verbose_name='Ativo', default=True)

    def save(self, *args, **kwargs):
        MAX_SIZE = 20000000  # 20 MB
        VALID_EXTENSIONS = ('png', 'jpg', 'jpeg', 'tiff', 'pdf')

        if self.arquivo_pendencia:
            if (
                self.anexo_extensao_pendencia
                and self.anexo_extensao_pendencia not in VALID_EXTENSIONS
            ):
                raise ValidationError(
                    f'Extensão inválida, formatos aceitos: {VALID_EXTENSIONS}'
                )

            if self.arquivo_pendencia and self.arquivo_pendencia.size > MAX_SIZE:
                raise ValidationError('O Tamanho do arquivo não pode exceder 20 MB')

        elif self.arquivo_regularizacao:
            if (
                self.anexo_extensao_regularizacao
                and self.anexo_extensao_regularizacao not in VALID_EXTENSIONS
            ):
                raise ValidationError(
                    f'Extensão inválida, formatos aceitos: {VALID_EXTENSIONS}'
                )

            if (
                self.arquivo_regularizacao
                and self.arquivo_regularizacao.size > MAX_SIZE
            ):
                raise ValidationError('O Tamanho do arquivo não pode exceder 20 MB')

        super(RegularizacaoContrato, self).save(*args, **kwargs)

    def delete(self):
        self.active = False
        self.deleted_at = timezone.now()
        self.save()

    @property
    def name_with_extension_pendencia(self) -> str:
        """Return the name of the file with the extension."""

        return f'{self.nome_anexo_pendencia}.{self.anexo_extensao_pendencia}'

    @property
    def name_with_extension_regularizacao(self) -> str:
        """Return the name of the file with the extension."""

        return f'{self.nome_anexo_regularizacao}.{self.anexo_extensao_regularizacao}'

    @property
    def is_stored_on_s3_pendencia(self) -> bool:
        """
        Checks if this attachment file is stored on a amazon S3 bucket.

        Returns:
            bool: True if the attachment file is stored on a amazon S3
            bucket, False otherwise.
        """

        return 's3.amazonaws.com' in self.anexo_url_pendencia

    @property
    def is_stored_on_s3_regularizacao(self) -> bool:
        """
        Checks if this attachment file is stored on a amazon S3 bucket.

        Returns:
            bool: True if the attachment file is stored on a amazon S3
            bucket, False otherwise.
        """

        return 's3.amazonaws.com' in self.anexo_url_regularizacao

    def extract_object_key_from_url_pendencia(self) -> str:
        """
        Extract the object key from attribute 'anexo_url'.

        Returns:
            str: The object key.
        """
        url = self.anexo_url_pendencia
        return url.split('.com/')[1].split('?')[0]

    def extract_object_key_from_url_regularizacao(self) -> str:
        """
        Extract the object key from attribute 'anexo_url'.

        Returns:
            str: The object key.
        """
        url = self.anexo_url_regularizacao
        return url.split('.com/')[1].split('?')[0]

    def extract_bucket_name_from_url_pendencia(self) -> str:
        """
        Extract the S3 bucket name from attribute 'anexo_url'.

        Returns:
            str: The object key.
        """
        url = self.anexo_url_pendencia
        return url.split('/')[2].split('.')[0]

    def extract_bucket_name_from_url_regularizacao(self) -> str:
        """
        Extract the S3 bucket name from attribute 'anexo_url'.

        Returns:
            str: The object key.
        """
        url = self.anexo_url_regularizacao
        return url.split('/')[2].split('.')[0]

    @property
    def get_attachment_url_pendencia(self) -> str:
        """
        Checks if anexo_url is from amazonaws, because there are some urls from google storage.
        Gets original URL without query params
        Generates presigned key if url is not expired yet.
        """
        boto3_manager = Boto3Manager()
        url = self.anexo_url_pendencia
        return boto3_manager.get_url_with_new_expiration(url)

    @property
    def get_attachment_url_pendencia_url(self) -> str:
        """
        Checks if anexo_url is from amazonaws, because there are some urls from google storage.
        Gets original URL without query params
        Generates presigned key if url is not expired yet.
        """
        return self.anexo_url_pendencia

    @property
    def get_attachment_url_regularizacao(self) -> str:
        """
        Checks if anexo_url is from amazonaws, because there are some urls from google storage.
        Gets original URL without query params
        Generates presigned key if url is not expired yet.
        """
        boto3_manager = Boto3Manager()
        url = self.anexo_url_regularizacao
        return boto3_manager.get_url_with_new_expiration(url)

    def __str__(self):
        return self.nome_anexo_pendencia

    class Meta:
        verbose_name = 'Regularização Averbação'
        verbose_name_plural = 'Regularização Averbação'

    def download(self, directory: str, pendencia=True) -> str:
        """
        Download an attachment from storage server (S3).

        Args:
            directory (str): The directory where the file will be downloaded.

        Returns:
            str: the path to the file that was downloaded
        """
        name_with_extension = (
            self.name_with_extension_pendencia
            if pendencia
            else self.name_with_extension_regularizacao
        )
        anexo_url = (
            self.anexo_url_pendencia if pendencia else self.anexo_url_regularizacao
        )

        from contract.models.anexo_contrato.anexo_contrato_amazon_s3_interface import (
            AnexoContratoAmazonS3Interface,
        )

        destination_path = os.path.join(directory, name_with_extension)
        try:
            # try to download using S# interface
            s3_interface = AnexoContratoAmazonS3Interface(self)
            s3_interface.download_file_from_s3(destination_path)
        except ClientError:
            download_using_get_request(anexo_url, destination_path)
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


@receiver(post_save, sender=RegularizacaoContrato)
def handle_post_save(sender, instance, created, **kwargs):
    s3_cliente = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    if instance.arquivo_pendencia or instance.arquivo_regularizacao:
        s3 = boto3.resource('s3')

        bucket = ''
        bucket_name = ''

        if instance.contrato.tipo_produto is EnumTipoProduto.PORTABILIDADE:
            bucket = s3.Bucket(settings.BUCKET_NAME_PORTABILIDADE)
            bucket_name = settings.BUCKET_NAME_PORTABILIDADE

        elif instance.contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            bucket = s3.Bucket(settings.BUCKET_NAME_AMIGOZ)
            bucket_name = settings.BUCKET_NAME_AMIGOZ

        elif instance.contrato.tipo_produto in (
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
            EnumTipoProduto.INSS_CORBAN,
        ):
            bucket = s3.Bucket(settings.BUCKET_NAME_INSS)
            bucket_name = settings.BUCKET_NAME_INSS

        nome_pasta = str(instance.contrato.token_contrato)

        arquivos = []

        if instance.arquivo_pendencia:
            path = str(instance.arquivo_pendencia)
            arquivos.append({
                'nome_arquivo_extensao': path.split('.')[1],
                'nome_anexo': os.path.basename(path),
                'file_stream': io.BytesIO(instance.arquivo_pendencia.read()),
                'pendencia': True,
            })

        elif instance.arquivo_regularizacao:
            path = str(instance.arquivo_regularizacao)
            arquivos.append({
                'nome_arquivo_extensao': path.split('.')[1],
                'nome_anexo': os.path.basename(path),
                'file_stream': io.BytesIO(instance.arquivo_regularizacao.read()),
                'pendencia': False,
            })

        for arquivo in arquivos:
            nome_arquivo_extensao = arquivo['nome_arquivo_extensao']
            nome_anexo = arquivo['nome_anexo']
            pendencia = arquivo['pendencia']
            file_stream = arquivo['file_stream']

            if nome_arquivo_extensao not in {'png', 'jpg', 'jpeg', 'pdf'}:
                nome_arquivo_extensao = 'jpg'

            if nome_arquivo_extensao == 'pdf':
                bucket.upload_fileobj(
                    file_stream,
                    f'{nome_pasta}/{nome_anexo}.{nome_arquivo_extensao}',
                    ExtraArgs={'ContentType': 'application/pdf'},
                )
            else:
                bucket.upload_fileobj(
                    file_stream,
                    f'{nome_pasta}/{nome_anexo}.{nome_arquivo_extensao}',
                    ExtraArgs={'ContentType': 'image/jpg'},
                )

            object_key = f'{nome_pasta}/{nome_anexo}.{nome_arquivo_extensao}'

            url = s3_cliente.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=31536000,
            )

            if pendencia:
                instance.anexo_url_pendencia = url
                instance.nome_anexo_pendencia = nome_anexo
                instance.anexo_extensao_pendencia = nome_arquivo_extensao
                instance.arquivo_pendencia.delete()

            else:
                instance.anexo_url_regularizacao = url
                instance.nome_anexo_regularizacao = nome_anexo
                instance.anexo_extensao_regularizacao = nome_arquivo_extensao
                instance.arquivo_regularizacao.delete()

        instance.save()
