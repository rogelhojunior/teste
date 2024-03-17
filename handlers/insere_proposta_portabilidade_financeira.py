import logging

logger = logging.getLogger('digitacao')


def traduzir_sexo(sexo_extenso: str) -> str:
    """
    Translates a Portuguese gender into English.

    Args:
        sexo_extenso (str): The gender in Portuguese ('masculino' or 'feminino').

    Returns:
        str: The gender in English ('male' or 'female'). Returns an empty string if the input is not recognized.
    """
    if sexo_extenso:
        if sexo_extenso.lower() == 'masculino':
            return 'male'
        elif sexo_extenso.lower() == 'feminino':
            return 'female'

    return ''


def traduzir_estado_civil(estado_civil_extenso: str) -> str:
    """
    Translates a Portuguese marital status into English.

    Args:
        estado_civil_extenso (str): The marital status in Portuguese.

    Returns:
        str: The marital status in English. Returns an empty string if the input is not recognized.
    """
    if estado_civil_extenso:
        if estado_civil_extenso.lower() == 'solteiro(a)':
            return 'single'
        elif estado_civil_extenso.lower() == 'casado(a)':
            return 'married'
        elif estado_civil_extenso.lower() == 'divorciado(a)':
            return 'divorced'
        elif estado_civil_extenso.lower() in {'viuvo(a)', 'viúvo(a)'}:
            return 'widower'
    return ''
