from api_log.models import LogCliente, QitechRetornos
from core.models import Cliente


def create_log_records(
    client: Cliente,
    data: dict,
    log_type: str,
) -> None:
    client_log, _ = LogCliente.objects.get_or_create(cliente=client)
    QitechRetornos.objects.create(
        log_api_id=client_log.pk,
        cliente=client,
        retorno=data,
        tipo=log_type,
    )
