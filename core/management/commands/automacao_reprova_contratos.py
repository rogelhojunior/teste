from django.core.management.base import BaseCommand

from contract.products.portabilidade.tasks import automacao_reprova_contratos_async


class Command(BaseCommand):
    help = 'Reprova Contratos.'

    def handle(self, *args, **options):
        automacao_reprova_contratos_async()
