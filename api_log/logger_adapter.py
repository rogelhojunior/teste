import datetime
import socket

import boto3
from django.conf import settings


class CloudWatchLogger:
    def __init__(self, log_stream_prefix, aws_region='us-east-1'):
        self.client = boto3.client(
            'logs',
            region_name=aws_region,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.log_group = 'DjangoAppLogs'
        self.log_stream = f"{log_stream_prefix}-{socket.gethostname()}-{datetime.datetime.now().strftime('%Y-%m-%d')}"
        self.sequence_token = None
        self.create_stream()

    def create_stream(self):
        return self.client.create_log_stream(
            logGroupName=self.log_group, logStreamName=self.log_stream
        )

    def log(self, message):
        timestamp = int(
            datetime.datetime.now().timestamp() * 1000
        )  # Convert to milliseconds
        event = {'timestamp': timestamp, 'message': message}

        args = {
            'logGroupName': self.log_group,
            'logStreamName': self.log_stream,
            'logEvents': [event],
        }

        if self.sequence_token:
            args['sequenceToken'] = self.sequence_token

        response = self.client.put_log_events(**args)
        self.sequence_token = response.get('nextSequenceToken')
