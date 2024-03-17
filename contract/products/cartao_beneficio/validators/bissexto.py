from datetime import timedelta


def eh_bissexto(ano):
    # Retorna True se o ano for bissexto, False caso contrário
    return (ano % 4 == 0 and ano % 100 != 0) or (ano % 400 == 0)


def calcular_dias_de_vigencia(data_inicio, data_fim):
    from datetime import timezone

    # Supondo que data_atual seja um objeto datetime sem informações de fuso horário
    data_atual = data_inicio.replace(tzinfo=timezone.utc)

    # Supondo que data_fim seja um objeto datetime com informações de fuso horário
    data_fim = data_fim.replace(tzinfo=timezone.utc)

    dias_de_vigencia = 0
    data_atual = data_inicio

    while data_atual < data_fim:
        dias_de_vigencia += 1
        data_atual += timedelta(days=1)

    return dias_de_vigencia
