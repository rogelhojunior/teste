from django.core.management.base import BaseCommand

from handlers.contrato import verificar_saques_pendentes


class Command(BaseCommand):
    help = 'Estornar Saque.'

    def handle(self, *args, **options):
        verificar_saques_pendentes()
