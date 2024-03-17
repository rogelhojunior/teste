import re


# Função para aplicar os padrões de regex e converter camelCase para snake_case
def camel_para_snake_case(nome_parametro):
    regex_patterns = {
        'upper': re.compile(r'([A-Z]+)'),
        'special': re.compile(r'[^a-zA-Z0-9]+'),
        'start': re.compile(r'^_+'),
    }
    nome_parametro = regex_patterns['upper'].sub(r'_\1', nome_parametro).lower()
    nome_parametro = regex_patterns['special'].sub('_', nome_parametro)
    nome_parametro = regex_patterns['start'].sub('', nome_parametro)
    return nome_parametro


# Função para converter chaves do dicionário para o novo padrão de snake_case
def converter_parametros(obj):
    if isinstance(obj, dict):
        simulacao = {}
        for parametro, valor in obj.items():
            novo_parametro = camel_para_snake_case(parametro)
            novo_valor = converter_parametros(valor)
            simulacao[novo_parametro] = novo_valor
        return simulacao
    elif isinstance(obj, list):
        return [converter_parametros(item) for item in obj]
    else:
        return obj
