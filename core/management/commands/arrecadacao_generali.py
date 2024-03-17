from django.core.management.base import BaseCommand

from core.tasks import generali_arrecadacao_async


class Command(BaseCommand):
    help = 'Envio de solicitação de arrecadação.'

    def handle(self, *args, **options):
        generali_arrecadacao_async()
