from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional

from rest_framework import serializers

from contract.constants import ContractTypeEnum
from simulacao.constants import EnumContaTipo
from simulacao.exceptions.serializer import (
    CPFLengthException,
    InsufficientFreeMarginForContract,
    InvalidCPFException,
)
from simulacao.utils import DateUtils

# TODO: Doc Dataclass https://docs.python.org/3/library/dataclasses.html


@dataclass
class OpcaoContrato:
    vr_contrato_max: float = 0.0
    vr_contrato_min: float = 0.0
    vr_parcela_max: float = 0.0
    vr_parcela_min: float = 0.0
    qt_parcelas: int = 0
    tx_efetiva_mes: float = 0.0
    tx_efetiva_ano: float = 0.0
    tx_cet_mes: float = 0.0
    tx_cet_ano: float = 0.0
    vr_tarifa_cadastro: float = 0.0
    vr_liberado_cliente: float = 0.0
    vr_parcela_calculada: float = 0.0
    vr_contrato: float = 0.0
    fl_seguro: bool = False
    vr_seguro: float = 0.0
    vr_iof: float = 0.0
    vr_iof_adicional: float = 0.0
    dt_vencimento_primeira_parcela: Optional[date] = None
    dt_vencimento_ultima_parcela: Optional[date] = None
    vr_juros_total: float = 0.0
    dt_liberado_cliente: Optional[date] = None
    dt_desembolso: Optional[date] = None
    valor_simulacao_dentro_faixa_idade: bool = True


@dataclass
class DadosBancariosBeneficiario:
    cd_banco: int = 0
    nu_agencia: str = ''
    nu_conta: str = ''
    nm_banco: str = ''
    cd_conta_tipo: EnumContaTipo = 1


@dataclass
class RestricaoOperacao:
    vr_op_min: float = 0.0
    vr_op_max: float = 0.0


@dataclass
class SimularContrato:
    dt_nascimento: str = ''
    cd_inss_beneficio_tipo: int = 0
    vr_margem_livre: float = 0.0
    vr_contrato: float = 0.0
    vr_parcela: float = 0.0
    opcoes_contrato: list = field(default_factory=list)
    restricao_operacao: RestricaoOperacao = field(default_factory=RestricaoOperacao)
    lista_taxas: list[float] = field(default_factory=list)

    # TODO: Remove when use pydantic
    def as_dict(self):
        return asdict(self)


class OpcaoContratoSerializer(serializers.Serializer):
    vr_contrato_max = serializers.FloatField()
    vr_contrato_min = serializers.FloatField()
    vr_parcela_max = serializers.FloatField()
    vr_parcela_min = serializers.FloatField()
    qt_parcelas = serializers.IntegerField()
    tx_efetiva_mes = serializers.FloatField()
    tx_efetiva_ano = serializers.FloatField()
    tx_cet_mes = serializers.FloatField()
    tx_cet_ano = serializers.FloatField()
    vr_tarifa_cadastro = serializers.FloatField()
    vr_liberado_cliente = serializers.FloatField()
    vr_parcela_calculada = serializers.FloatField()
    vr_contrato = serializers.FloatField()
    fl_seguro = serializers.BooleanField()
    vr_seguro = serializers.FloatField()
    vr_iof = serializers.FloatField()
    vr_iof_adicional = serializers.FloatField()
    dt_vencimento_primeira_parcela = serializers.DateTimeField()
    dt_vencimento_ultima_parcela = serializers.DateTimeField()
    vr_juros_total = serializers.FloatField()
    dt_liberado_cliente = serializers.DateTimeField()
    dt_desembolso = serializers.DateTimeField()

    class Meta:
        fields = '__all__'


class RestricaoOperacaoSerializer(serializers.Serializer):
    vr_op_min = serializers.FloatField()
    vr_op_max = serializers.FloatField()

    class Meta:
        fields = '__all__'


class DadosBancariosBeneficiarioSerializer(serializers.Serializer):
    cd_banco = serializers.IntegerField()
    nu_agencia = serializers.CharField()
    nu_conta = serializers.CharField()
    nm_banco = serializers.CharField()
    cd_conta_tipo = serializers.ChoiceField(
        choices=[(tag.name, tag.value) for tag in EnumContaTipo]
    )

    class Meta:
        fields = '__all__'


class SimulateContractSerializer(serializers.Serializer):
    """
    Serializer for contract simulation.

    Attributes
    ----------
    numero_cpf : str
        CPF (Brazilian Social Security Number) of the beneficiary. Must have exactly 11 numeric digits.
    numero_beneficio : int
        Benefit number related to the beneficiary.
    dt_nascimento : DateField
        Birthdate of the beneficiary.
    codigo_beneficio : int
        Benefit code related to the beneficiary.
    margem_livre : float
        Available margin for the contract.
    valor_contrato : float
        Total value of the contract.
    tipo_contrato : ChoiceField
        Type of contract. Choices based on the `ContractTypeEnum`.
    valor_parcela : float, optional
        Value of the installment.
    valor_taxa : float, optional
        Tax value for the contract.
    opcoes_contrato : OpcaoContratoSerializer, optional
        Contract options, as a list of serialized objects.
    restricao_operacao : RestricaoOperacaoSerializer, optional
        Operational restrictions, as a serialized object.
    dados_bancarios_beneficiario : DadosBancariosBeneficiarioSerializer, optional
        Bank details of the beneficiary, as a serialized object.
    lista_taxas : ListField, optional
        List of tax rates, as a list of floats.

    Methods
    -------
    validate_margem_livre(free_margin: float) -> float
        Validate if the free margin is greater than zero.
    validate_numero_cpf(cpf: str) -> str
        Validate if the CPF is valid.
    """

    numero_cpf = serializers.CharField(
        required=True,
        allow_null=False,
        max_length=14,
    )
    numero_beneficio = serializers.IntegerField(
        required=True,
        allow_null=False,
    )
    dt_nascimento = serializers.DateField(
        format=DateUtils('dmy', '/').get_date_format().strip(),
        input_formats=[DateUtils('dmy', '/').get_date_format().strip()],
        required=True,
        allow_null=False,
    )
    codigo_beneficio = serializers.IntegerField(
        required=True,
        allow_null=False,
    )
    margem_livre = serializers.FloatField(
        required=True,
        allow_null=False,
    )
    valor_contrato = serializers.FloatField(
        required=True,
        allow_null=False,
    )
    tipo_contrato = serializers.ChoiceField(
        choices=[(e.value, e.name) for e in ContractTypeEnum],
        required=True,
        allow_null=False,
    )
    valor_parcela = serializers.FloatField(required=False)
    valor_taxa = serializers.FloatField(
        required=False,
    )
    opcoes_contrato = OpcaoContratoSerializer(many=True, required=False)
    restricao_operacao = RestricaoOperacaoSerializer(required=False)
    dados_bancarios_beneficiario = DadosBancariosBeneficiarioSerializer(required=False)
    lista_taxas = serializers.ListField(required=False, child=serializers.FloatField())

    def validate_margem_livre(self, free_margin: float):
        """
        Validates the available margin for the contract.

        Parameters
        ----------
        free_margin : float
            The available margin for the contract.

        Returns
        -------
        float
            Returns the available margin if it's greater than zero.

        Raises
        ------
        InsufficientFreeMarginForContract
            If the available margin is zero or negative.
        """
        if free_margin > 0:
            return free_margin
        raise InsufficientFreeMarginForContract

    def validate_numero_cpf(self, cpf: str) -> str:
        """
        Validates the CPF of the beneficiary.

        Parameters
        ----------
        cpf : str
            The CPF number to validate.

        Returns
        -------
        str
            Returns the cleaned CPF if it's valid.

        Raises
        ------
        CPFLengthException
            If the CPF length is not 11.
        InvalidCPFException
            If the CPF is not a valid number.
        """
        cleaned_cpf = ''.join(filter(str.isdigit, cpf))

        if len(cleaned_cpf) != 11:
            raise CPFLengthException

        if cleaned_cpf == cleaned_cpf[0] * 11:
            raise InvalidCPFException

        for i in range(9, 11):
            value = sum(
                int(a) * b
                for a, b in zip(cleaned_cpf[:i], range(i + 1, 1, -1), strict=False)
            )
            digit = (value * 10) % 11
            if digit == 10:
                digit = 0
            if str(digit) != cleaned_cpf[i]:
                raise InvalidCPFException

        return cpf

    class Meta:
        fields = '__all__'
