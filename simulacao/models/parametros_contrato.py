from pydantic.dataclasses import dataclass


@dataclass
class OpcoesContratoParametros:
    prazo: int = 0
    vr_contrato_min: float = 0.0
    vr_contrato_max: float = 0.0
    vr_parcela_min: float = 0.0
    vr_parcela_max: float = 0.0
    tx_juros: float = 0.0
    vr_contrato_calculado: float = 0.0
    vr_parcela_calculada: float = 0.0
