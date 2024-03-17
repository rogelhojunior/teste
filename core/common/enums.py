import sys
from collections import namedtuple
from enum import Enum
from typing import Literal

EnvironmentType = Literal[
    'LOCAL',
    'DEV',
    'STAGE',
    'PROD',
]


if sys.version_info >= (3, 11):
    from enum import StrEnum

    class EnvironmentEnum(StrEnum):
        LOCAL = 'LOCAL'
        DEV = 'DEV'
        STAGE = 'STAGING'
        PROD = 'PROD'

else:

    class HTTPMethod(str, Enum):
        CONNECT = 'CONNECT'
        DELETE = 'DELETE'
        GET = 'GET'
        HEAD = 'HEAD'
        OPTIONS = 'OPTIONS'
        PATCH = 'PATCH'
        POST = 'POST'
        PUT = 'PUT'
        TRACE = 'TRACE'

    class EnvironmentEnum(str, Enum):
        LOCAL = 'LOCAL'
        DEV = 'DEV'
        STAGE = 'STAGING'
        PROD = 'PROD'


StateInfo = namedtuple(typename='StateInfo', field_names=['state_name', 'uf'])


class BrazilianStatesEnum(StateInfo, Enum):
    Acre = StateInfo('Acre', 'AC')
    Alagoas = StateInfo('Alagoas', 'AL')
    Amapa = StateInfo('Amapá', 'AP')
    Amazonas = StateInfo('Amazonas', 'AM')
    Bahia = StateInfo('Bahia', 'BA')
    Ceara = StateInfo('Ceará', 'CE')
    Distrito_Federal = StateInfo('Distrito Federal', 'DF')
    Espirito_Santo = StateInfo('Espírito Santo', 'ES')
    Goias = StateInfo('Goiás', 'GO')
    Maranhao = StateInfo('Maranhão', 'MA')
    Mato_Grosso = StateInfo('Mato Grosso', 'MT')
    Mato_Grosso_do_Sul = StateInfo('Mato Grosso do Sul', 'MS')
    Minas_Gerais = StateInfo('Minas Gerais', 'MG')
    Para = StateInfo('Pará', 'PA')
    Paraiba = StateInfo('Paraíba', 'PB')
    Parana = StateInfo('Paraná', 'PR')
    Pernambuco = StateInfo('Pernambuco', 'PE')
    Piaui = StateInfo('Piauí', 'PI')
    Rio_de_Janeiro = StateInfo('Rio de Janeiro', 'RJ')
    Rio_Grande_do_Norte = StateInfo('Rio Grande do Norte', 'RN')
    Rio_Grande_do_Sul = StateInfo('Rio Grande do Sul', 'RS')
    Rondonia = StateInfo('Rondônia', 'RO')
    Roraima = StateInfo('Roraima', 'RR')
    Santa_Catarina = StateInfo('Santa Catarina', 'SC')
    Sao_Paulo = StateInfo('São Paulo', 'SP')
    Sergipe = StateInfo('Sergipe', 'SE')
    Tocantins = StateInfo('Tocantins', 'TO')
