import json
import logging
import time

import boto3
import botocore
from django.conf import settings

from message_bus.mapper import EventProcessorMapping


class SQSListener:
    """
    An Amazon SQS message listener that processes messages based on event names.

    ATTENTION !! DO NOT CALL THIS CLASS DIRECTLY, THE EVENT BROKER SHOULD BE USED ONLY BE PRODUCERS AND CONSUMERS !!
    """

    def __init__(self):
        self.sqs = boto3.client(
            'sqs',
            region_name='us-east-1',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.message = None
        self.QUEUE_URL = (
            'https://sqs.us-east-1.amazonaws.com/256139846389/originacao-backend.fifo'
        )

    def listen_queue(
        self, max_number_of_messages=10, visibility_timeout=30, wait_time_seconds=5
    ):
        """
        Listen messages from the SQS queue in batches and handle them. This is the main entry point for the SQS
        consumers.

        Parameters:
        - max_number_of_messages: The maximum number of messages to return. Amazon SQS never returns more messages
                                  than this value (however, fewer messages might be returned). This allows you to
                                  control how many messages your application should attempt to process at a time.
        - visibility_timeout: The duration (in seconds) that the received messages are hidden from subsequent retrieve
                              requests after being retrieved by a ReceiveMessage request. This allows your application
                              time to process each message before it becomes available in the queue again. If a message
                              is not deleted before the visibility timeout expires, it will be returned to the queue.
        - wait_time_seconds: The duration (in seconds) for which the call waits for a message to arrive in the queue
                             before returning. If no messages arrive within this time, the call will return an empty
                             list. By adjusting this value, you can control how long your queue listen should wait when
                             there are no messages in the queue.

        After messages are consumed, they are processed and removed from the queue.
        """
        attempt = 0
        while True:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=self.QUEUE_URL,
                    AttributeNames=['All'],
                    MaxNumberOfMessages=max_number_of_messages,
                    VisibilityTimeout=visibility_timeout,
                    WaitTimeSeconds=wait_time_seconds,
                )
                logging.info(f'Response: {response}')
                self._process_messages(response)
                attempt = 0

            except botocore.exceptions.BotoCoreError as e:
                logging.error(f'Error consuming messages: {e}')
                self._backoff_exponential(attempt)
                attempt += 1

            except Exception as e:
                logging.error(f'Unexpected error: {e}')

    @staticmethod
    def _backoff_exponential(attempt, max_delay=60, multiplier=1):
        """
        Implement an exponential backoff strategies.
        """
        delay = min(max_delay, (2**attempt) * multiplier)
        time.sleep(delay)

    def _process_messages(self, response):
        """
        Process the messages from the response.
        """
        if messages := response.get('Messages'):
            for message in messages:
                self.message = message
                if self._handle_single_message(message):
                    self._remove_message(message)
                    print(
                        f"Message processed and deleted: {message['MessageId']}"
                    )  # Mensagem processada e deletada
        else:
            print('No messages in queue')  # Nenhuma mensagem na fila
            logging.info('No messages in queue')

    def _handle_single_message(self, message):
        """
        Handle a single message by processing its event.
        Returns True if the message is processed successfully, False otherwise.
        """
        try:
            sqs_message = message
            sqs_message = sqs_message.get('Body')
            sqs_message = json.loads(sqs_message)
            event_name = sqs_message.get('event_name')
            body = sqs_message.get('message')
            print(body)
            if event_name:
                self._handle_event(event_name, body)
                return True
            else:
                logging.error(
                    f'Message does not have the expected structure: {message}'
                )
                raise ValueError('Message does not have the expected structure')

        except json.JSONDecodeError as e:
            logging.error(f'Error decoding message: {message}, error: {e}')
            return False

        except Exception as e:
            logging.error(f'Error handling message: {e}')
            return False

    def _handle_event(self, event_name, event_body):
        """
        Handle the event of the given name.
        """
        event_processor_mapping = EventProcessorMapping()
        event_processor_mapping = event_processor_mapping.get_mapping()
        try:
            if event_name in event_processor_mapping:
                event_processor_mapping[event_name](event_body)
            else:
                raise ValueError(f'Unknown event: {event_name}')
        except Exception as e:
            self.sqs.delete_message(
                QueueUrl=self.QUEUE_URL, ReceiptHandle=self.message['ReceiptHandle']
            )
            logging.error(f'Error handling event: {e}')
            raise

    def _remove_message(self, message):
        """ "
        Remove the message from the queue.
        """
        try:
            self.sqs.delete_message(
                QueueUrl=self.QUEUE_URL, ReceiptHandle=message['ReceiptHandle']
            )
        except Exception as e:
            logging.error(f'Error removing message: {e}')
            raise
