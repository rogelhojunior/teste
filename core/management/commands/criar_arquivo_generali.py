from django.core.management.base import BaseCommand

from core.tasks import process_and_upload_file


class Command(BaseCommand):
    help = 'Gerar lotes.'

    def handle(self, *args, **options):
        process_and_upload_file()
