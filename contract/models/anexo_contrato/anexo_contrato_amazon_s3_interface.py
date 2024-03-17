"""
Module-level docstring - This should describe the purpose and usage of the module.

This module contains a class that interacts with Amazon S3 for downloading and uploading files.
"""

# third
import boto3
from django.conf import settings

# local
from contract.models.anexo_contrato import AnexoContrato


class AnexoContratoAmazonS3Interface:
    """
    AnexoContratoAmazonS3Interface - Provides methods to interact with Amazon S3.

    This class allows you to download and upload files to Amazon S3, using attributes from
    the AnexoContrato model to connect with S3.

    Args:
        anexo_contrato (AnexoContrato): An instance of the AnexoContrato model.

    Attributes:
        s3 (boto3.resource): A Boto3 S3 resource for connecting to Amazon S3.

    Methods:
        - download_file_from_s3(local_file_path)
        - upload_file_to_s3(file_path)
    """

    def __init__(self, anexo_contrato: AnexoContrato):
        """
        Initializes the AnexoContratoAmazonS3Interface.

        Args:
            anexo_contrato (AnexoContrato): An instance of the AnexoContrato model.
        """
        self.anexo_contrato = anexo_contrato
        self.s3 = boto3.resource(
            's3',
            region_name='us-east-1',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    @property
    def object_key(self) -> str:
        """
        Generates object key, necessary to access one specific file inside
        S3.

        Returns:
            str: The object key.
        """
        return self.anexo_contrato.extract_object_key_from_url()

    @property
    def bucket_name(self) -> str:
        """
        Generates bucket name, necessary to access one specific bucket inside
        S3.

        Returns:
            str: The bucket name.
        """
        return self.anexo_contrato.extract_bucket_name_from_url()

    @property
    def is_s3(self) -> bool:
        """
        Checks if this attachment file is stored on a amazon S3 bucket.

        Returns:
            bool: True if the attachment file is stored on a amazon S3
            bucket, False otherwise.
        """
        return self.anexo_contrato.is_stored_on_s3

    def download_file_from_s3(self, local_file_path: str):
        """
        Download a file from Amazon S3 to a local file.

        Args:
            local_file_path (str): The local file path where the S3 file
            will be saved.
        """
        self.s3.Bucket(self.bucket_name).download_file(self.object_key, local_file_path)

    def upload_file_to_s3(self, file_path: str):
        """
        Upload a local file to Amazon S3.

        Args:
            file_path (str): The local file path to upload to S3.

        Returns:
            bool: True if the upload is successful, False if there's an error.
        """
        # Upload the local file to S3
        self.s3.Bucket(self.bucket_name).upload_file(file_path, self.object_key)
