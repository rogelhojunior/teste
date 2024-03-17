from datetime import datetime
from urllib.parse import parse_qsl, urlparse

import boto3
from django.conf import settings
from rest_framework.exceptions import ValidationError


class Boto3Manager:
    """
    Class for managing boto3, always creating boto3 with the credentials from the django settings.
    Usage:
        boto3_manager = Boto3Manager()
        client = boto3_manager.client.generate_presigned_url(*args)
        resource = boto3_manager.resource
    """

    def __init__(self, region_name='us-east-1', service_name='s3'):
        """
        Initializes the variables, allowing the region and service to be modified in the constructor.
        Args:
            region_name (str): The AWS region (default is 'us-east-1').
            service_name (str): The AWS service name (default is 's3').
        """
        self.service_name = service_name
        self.region_name = region_name
        self.aws_access_key_id = settings.AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY

        self.client_instance = None
        self.resource_instance = None

    def get_configs(self):
        """
        Returns all the necessary credentials to configure the resources or boto3 client.
        Returns:
            dict: A dictionary with the required configurations.
        """
        return {
            'service_name': self.service_name,
            'region_name': self.region_name,
            'aws_access_key_id': self.aws_access_key_id,
            'aws_secret_access_key': self.aws_secret_access_key,
        }

    @property
    def client(self):
        """
        Property to return a boto3 client.
        Has a lower level of abstraction.
        Returns:
            botocore.client.BaseClient: A configured boto3 client object.
        """
        if not self.client_instance:
            self.client_instance = boto3.client(**self.get_configs())
        return self.client_instance

    @property
    def resource(self):
        """
        Property to return a boto3 resource.
        Recommended for S3. Higher level of abstraction.
        Returns:
            boto3.resources.base.ServiceResource: A configured boto3 resource object.
        """
        if not self.resource_instance:
            self.resource_instance = boto3.resource(**self.get_configs())
        return self.resource_instance

    def validar_bucket_service_name(self):
        """
        Validates if the service is S3 when intending to use something specific to S3.
        Raises:
            ValidationError: If the service name is not 's3'.
        """
        if self.service_name != 's3':
            raise ValidationError({
                'erro': 'O service name para acessar o bucket precisa ser s3!'
            })

    def get_bucket(self, bucket_name):
        """
        Obtains the instance of the specified bucket.
        Args:
            bucket_name (str): The name of the bucket you want to retrieve.
        Returns:
            boto3.resources.factory.s3.Bucket: An instance of the bucket with the specified name.
        """
        self.validar_bucket_service_name()
        return self.resource.Bucket(bucket_name)

    def generate_presigned_url(
        self,
        bucket_name: str,
        object_key: str,
        expiration_time: int = 600,
        operation_name='get_object',
    ) -> str:
        """
        Obtains a URL for the bucket with expiration time for that specific URL.
        Args:
            bucket_name (str): Original bucket.
            object_key (str): URL of the original object to have the expiration time.
            expiration_time (int): Expiration time in seconds, default is 600 (10 minutes - 60*10).
            operation_name (str): Generate presigned URL operation, default is 'get_object'.
        Returns:
            str: URL of the resource.
        """
        return self.client.generate_presigned_url(
            operation_name,
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration_time,
        )

    def upload_fileobj(self, file, bucket_name, object_key, extra_args=None):
        """
        Uploads a file-like object to the specified bucket.
        Args:
            file (file-like object): The file-like object to be uploaded.
            bucket_name (str): The name of the bucket to which the file will be uploaded.
            object_key (str): The key of the object in the bucket.
            extra_args (dict): Extra arguments to be passed to the upload_fileobj method.
        """
        self.validar_bucket_service_name()
        return self.client.upload_fileobj(
            file, bucket_name, object_key, ExtraArgs=extra_args
        )

    @staticmethod
    def is_timestamp_expired(timestamp: str) -> bool:
        """
        Verifies expiration time based on expires str
        Gets utc hour from expires_timestamp
        Gets current utc hour
        Args:
            timestamp: Expiration time in timestamp str
        Returns:
            bool: Evaluation of expiration time
        """
        if timestamp:
            expires_datetime = datetime.utcfromtimestamp(int(timestamp))
            current_datetime = datetime.utcnow()
            return current_datetime > expires_datetime
        return True

    def get_url_with_new_expiration(
        self,
        anexo_url: str,
        new_expiration_time: int = 600,
    ) -> str:
        """
        Checks if anexo_url is from amazonaws, because there are some urls from google storage.
        Gets original URL without query params
        Generates presigned key if url is not expired yet.
        Args:
            anexo_url: Original URL to be applied new expiration
            new_expiration_time: New expiration time (default 600 - 10m)
        Returns:
            str: new url with expiration time applied, or same url if isn't from AWS.
        """

        if anexo_url and 's3.amazonaws.com' in anexo_url:
            parsed_url = urlparse(anexo_url)
            url_expiration = dict(parse_qsl(parsed_url.query)).get('Expires')
            # TODO remove this feature flag when its done.
            if True or self.is_timestamp_expired(url_expiration):
                object_key = parsed_url.path[1:]
                bucket_name = parsed_url.hostname.split('.')[0]
                return self.generate_presigned_url(
                    bucket_name=bucket_name,
                    object_key=object_key,
                    expiration_time=new_expiration_time,
                )
        return anexo_url
