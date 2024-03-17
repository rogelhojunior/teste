from datetime import date, datetime


def calcular_idade(data_nascimento_str):
    today = date.today()

    # Verificar se self.data_nascimento_str é uma string ou uma data
    if isinstance(data_nascimento_str, date):
        # Se for uma data, usar diretamente
        nascimento = data_nascimento_str
    else:
        # Se for uma string, converter para data
        nascimento = datetime.strptime(data_nascimento_str, '%d/%m/%Y').date()

    idade_cliente = today.year - nascimento.year

    # Ajustar a idade se ainda não chegou o aniversário deste ano
    if today.month < nascimento.month or (
        today.month == nascimento.month and today.day < nascimento.day
    ):
        idade_cliente -= 1

    return idade_cliente


def validar_idade_cliente_maxima_minima(idade_cliente, idade_minima, idade_maxima):
    return idade_minima <= idade_cliente <= idade_maxima
