from datetime import datetime

from rest_framework.exceptions import ValidationError

from contract.exceptions.validators.products import RogadoException, WitnessException
from contract.parsers.in100 import In100Benefit
from core.api.serializers import RogadoSerializer, TestemunhaSerializer
from core.models import Rogado, Cliente, Testemunha


def update_client_with_benefit_values(client, benefit: In100Benefit) -> None:
    """
    Updates client instance
    Args:
        client: Client to be updated
        benefit: In100 Benefit instance with defined values

    """
    client.nome_cliente = benefit.name
    client.endereco_uf = benefit.state
    client.dt_nascimento = datetime.strptime(benefit.birth_date, '%d%m%Y')
    client.salario_liquido = benefit.liquid_benefit_value
    client.save(
        update_fields=[
            'nome_cliente',
            'endereco_uf',
            'dt_nascimento',
            'salario_liquido',
        ]
    )


def create_rogado(
    client: Cliente,
    rogado_payload: dict,
) -> Rogado:
    """
    Get or create Rogado instance
    Args:
        client: Client instance
        rogado_payload: Rogado payload

    Returns:
        Rogado instance

    """
    try:
        rogado_serializer = RogadoSerializer(
            data={
                'cliente_id': client.id,
                'nome': rogado_payload['nome'],
                'cpf': rogado_payload['cpf'],
                'data_nascimento': rogado_payload['data_nascimento'],
                'grau_parentesco': rogado_payload['grau_parentesco'],
                'telefone': rogado_payload['telefone'],
            }
        )
        rogado_serializer.is_valid(raise_exception=True)
        return rogado_serializer.save()
    except KeyError as e:
        raise RogadoException(description=str(e)) from e
    except ValidationError as e:
        raise RogadoException(description=e.detail) from e


def create_client_contract_witnesses(
    client: Cliente,
    witnesses_payload: list,
    contract_ids: list,
) -> Testemunha:
    """
    Create Testemunha instances
    Args:
        client: Client instance
        witnesses_payload: Testemunha object list
        contract_ids: Contract ids list

    """
    try:
        witness_serializer = TestemunhaSerializer(
            data=[
                {
                    'contratos': contract_ids,
                    'cliente_id': client.id,
                    'nome': witness['nome'],
                    'cpf': witness['cpf'],
                    'telefone': witness['telefone'],
                    'data_nascimento': witness['data_nascimento'],
                }
                for witness in witnesses_payload
            ],
            many=True,
        )

        witness_serializer.is_valid(raise_exception=True)
        return witness_serializer.save()

    except KeyError as e:
        raise WitnessException(description=str(e)) from e
    except ValidationError as e:
        raise WitnessException(description=e.detail) from e
