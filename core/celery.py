import os

from celery import Celery
from celery.signals import setup_logging
from kombu import Queue

# Define o módulo de configuração do Django para 'CELERY'.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Cria a instância de aplicação Celery.
app = Celery('core')

# Carrega qualquer configuração personalizada do Celery a partir do seu arquivo de configuração do Django.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.task_queues = (
    Queue('celery', routing_key='celery'),
    Queue('reports', routing_key='reports'),
    Queue('recalculation', routing_key='recalculation'),
    Queue('light_operations', routing_key='light_operations'),
    Queue('heavy_operations', routing_key='heavy_operations'),
)


@setup_logging.connect
def config_loggers(*args, **kwags):
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)
