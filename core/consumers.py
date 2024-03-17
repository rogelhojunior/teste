import json

import boto3
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from message_bus.producers.send_face_matching_request import SendFaceMatchingRequest


class ServerAWS:
    """
    AWS Server Credentials class.

    This class maintains the AWS credentials necessary to access the S3 bucket. It retrieves these credentials from the
    environment variables.
    """

    AwsAccessKeyId = settings.AWS_ACCESS_KEY_ID
    AwsSecretAccessKey = settings.AWS_SECRET_ACCESS_KEY
    BucketName = settings.BUCKET_DEFAULT


def create_s3_client():
    """
    AWS S3 client creation method.

    This method is responsible for creating and returning an AWS S3 client using the access key ID and secret access
    key stored in the ServerAWS class.
    """
    return boto3.client(
        's3',
        region_name='us-east-1',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def create_document_resource(file_basename: str, file_name: str):
    """
    Document resource path creator.

    This method creates and returns the document resource path, which is the path to the image stored in the S3 bucket.
    """
    return f'S3://{ServerAWS.BucketName}/{file_basename}/{file_name}'


async def send_face_matching_request(unique_id, document_resource, image_url):
    """
    Face matching request sender.

    This method sends a message to the queue that contains the user ID and the document resource path. This path refers
    to the image in the S3 bucket which will be used for face matching.
    """
    event = SendFaceMatchingRequest()
    event({
        'user_uuid': unique_id,
        'document_resource': document_resource,
        'image_url': image_url,
    })


class FrontendMessageConnection(AsyncWebsocketConsumer):
    """
    Frontend Message Connection class.

    This class handles the receipt of messages from the frontend and forwards them to the backend. Currently, it
    supports one type of message: 'send_image'. This message type is used to send an image of a document to the backend
    for face matching. This process is asynchronous, so the backend will send a message to the queue and then wait for
    the result. Once the result is ready, it will be sent back to the frontend. The message parameters are the
    document resource and the user ID.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialization method.

        Initializes the super class and sets the identifier to None. For more information about how this class works,
        check the Channels documentation at: https://channels.readthedocs.io/en/stable/.
        """
        super().__init__(args, kwargs)
        self.identifier = None

    async def connect(self):
        """
        Connection handler.

        This method is invoked when the websocket is handshaking (connecting). The channel is added to a group to
        facilitate asynchronous messaging without losing the user's context.
        """
        self.identifier = self.scope['url_route']['kwargs']['unique_id']
        self.group_name = f'{self.identifier}_connection'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        """
        Disconnection handler.

        This method is invoked when the websocket is closing. The channel is removed from the group.
        """
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def _validate_message_data(self, text_data_json: dict):
        """
        Message data validation.

        This method checks if the message data is valid. If not, a message is sent back to the frontend indicating the
        data is invalid.
        """
        if not text_data_json.get('image_url') or not text_data_json.get(
            'document_resource'
        ):
            await self.send(
                text_data=json.dumps({
                    'message': 'Both image_url and document_resource must be provided.',
                    'status': False,
                })
            )

    def get_s3_file_key(self, document_part: str, extensao: str = 'jpg') -> str:
        """Gera a chave (caminho) do arquivo no S3 baseado no unique_id do usuário e na parte do documento."""
        return f'{self}_{document_part}.{extensao}'

    def generate_presigned_url(self, file_key: str) -> str:
        """Gera uma URL presignada para um arquivo no S3."""
        return self.generate_presigned_url(
            'get_object',
            Params={'Bucket': ServerAWS.BucketName, 'Key': file_key},
            ExpiresIn=3600,
        )

    async def send_message(self, event):
        await self.send(text_data=event['text'])

    async def receive(self, text_data: str):
        """
        Message receiver.
        """
        try:
            text_data_json = json.loads(text_data)
            unique_id = text_data_json.get('unique_id')
            await self._validate_message_data(text_data_json)

            s3_client = create_s3_client()

            document_file_key = self.get_s3_file_key(unique_id, 'documento_frente')
            document_image_url = self.generate_presigned_url(
                s3_client, document_file_key
            )
            selfie_file_key = self.get_s3_file_key(unique_id, 'selfie')
            selfie_image_url = self.generate_presigned_url(s3_client, selfie_file_key)

            await send_face_matching_request(
                unique_id,
                [document_file_key, selfie_file_key],
                [document_image_url, selfie_image_url],
            )

            await self.send(
                text_data=json.dumps({
                    'message': 'Image URLs generated and face matching request sent to SQS.',
                    'status': True,
                })
            )

        except Exception as e:
            await self.send(
                text_data=json.dumps({
                    'message': f'Error occurred: {str(e)}',
                    'status': False,
                })
            )
