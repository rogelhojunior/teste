from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Endereco:
    endereco: str
    numero: str
    complemento: Optional[str]
    bairro: str
    cidade: str
    uf: str
    cep: str


@dataclass
class Segurado:
    cpf: str
    nome: str
    data_nascimento: str
    capital: float
    genero: int
    endereco: Endereco
    email: str
    telefone_celular: str
    telefone_sms: str
    beneficiarios: List[str] = field(default_factory=list)
    agregados: List[str] = field(default_factory=list)
    numeros_sorte: List[str] = field(default_factory=list)


@dataclass
class Dp:
    codigo: int
    resposta: str
    texto: str


@dataclass
class PedidoDeSeguro:
    capital: float
    external_id: str
    data_inicio_vigencia: str
    frequencia_emissao: int
    tipo_vencimento: int
    dia_vencimento: int
    segurado: Segurado
    atividade_principal: int
    forma_pagamento: int
