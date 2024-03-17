from celery import shared_task
from most_sdk import Client as MostClient
from serasa_sdk import Client
from datetime import datetime

from api_log.models import LogWebhook
from .models import MostProtocol, SerasaProtocol
from .services import process_most_protocol, process_serasa_protocol


@shared_task(queue='heavy_operations')
def update_serasa_protocols():
    serasa_client = Client()

    protocols = SerasaProtocol.objects.filter(processed=False)

    for protocol in protocols:
        response = serasa_client.digitalizacao.get(protocol=protocol.protocol)

        if not response:
            continue

        result = response[0]

        formatted_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        LogWebhook.objects.create(
            chamada_webhook=f'SERASA - {protocol.cpf} - {formatted_time}',
            log_webhook=result,
        )

        if result.get('StatusRegistro') == 'Em análise':
            continue

        protocol.result = result.get('Resultado Analise')
        protocol.processed = True
        protocol.save(update_fields=['result', 'processed'])

        process_serasa_protocol(protocol)


@shared_task(queue='heavy_operations')
def update_most_protocols():
    most_client = MostClient()

    protocols = MostProtocol.objects.filter(processed=False)

    for protocol in protocols:
        try:
            response = most_client.enrichment.get(protocol=protocol.protocol)
        except Exception:
            continue

        if not response:
            continue

        result = response

        formatted_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        LogWebhook.objects.create(
            chamada_webhook=f'MOST - {protocol.cpf} - {formatted_time}',
            log_webhook=result,
        )

        if result.get('status') == 'DOING':
            continue

        if result.get('status') == 'ERROR':
            result = 'CPF INEXISTENTE'
        else:
            fields = result.get('datasets')[0].get('data')[0].get('fields')

            fields = {field['name']: field['value'] for field in fields}
            result = fields.get('situacao')

        protocol.result = result
        protocol.processed = True
        protocol.save(update_fields=['result', 'processed'])

        process_most_protocol(protocol)
