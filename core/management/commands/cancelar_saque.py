from django.core.management.base import BaseCommand

from handlers.contrato import verificar_proposta_sem_solicitacao_de_correcao


class Command(BaseCommand):
    help = 'Cancelar Saque.'

    def handle(self, *args, **options):
        verificar_proposta_sem_solicitacao_de_correcao()
