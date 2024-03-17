import base64
from serasa_sdk.enums import TipoArquivo
from contract.constants import EnumTipoAnexo, EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from contract.products.cartao_beneficio.models.convenio import (
    Convenios,
    ProdutoConvenio,
)
from contract.models.contratos import Contrato
from documentscopy.enums import BPO
from documentscopy.models import BPOConfig, BPORow
from handlers.confia import download_arquivo_s3_base64
from .utils import get_subordinate_ids_at_all_levels
from custom_auth.models import Corban
from serasa_sdk import Client
from most_sdk import Client as MostClient
from .models import MostProtocol, SerasaProtocol
from contract.models.contratos import CartaoBeneficio, MargemLivre, Portabilidade
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.portabilidade.api.views import (
    approve_contract_automatic,
    refuse_contract,
)

DEFAULT_RETURNS = {
    'COM RISCO - FACEMATCH': {
        'message': 'Facematch não válidada - Dcto desatualizado',
        'front': 'Enviar documento de identificação atualizado - Não foi possível realizar comparação com a Selfie',
    },
    'AUSENTE - DOCUMENTO': {
        'message': 'Documento de identificação não enviado',
        'front': 'Favor enviar documento de identificação - Não foi identificado nenhum documento',
    },
    'NÃO PASSÍVEL DE ANÁLISE - SELFIE INVÁLIDA': {
        'message': 'Selfie divergente',
        'front': 'Favor solicitar nova selfie do cliente , Selfie divergente e/ou consta mais de uma pessoa na foto',
    },
    'COM RISCO - FOTO DE FOTO DA SELFIE': {
        'message': 'Selfie inválida - Foto de foto',
        'front': 'Proposta recusada devido a Selfie ser uma foto de foto',
    },
    'NÃO PASSÍVEL DE ANÁLISE - DOCUMENTO ILEGÍVEL/INCOMPLETO': {
        'message': 'Documento de identificação ilegível/cortado e ou Rasurado',
        'front': 'Favor enviar documento de identificação sem cortes e/ou sem rasuras',
    },
    'AUSENTE - FACE DO DOCUMENTO': {
        'message': 'Documento de identificação incompleto',
        'front': 'Favor enviar documento de identificação completo frente e verso',
    },
    'AUSENTE - SELFIE': {
        'message': 'Falta Selfie',
        'front': 'Favor enviar Selfie do cliente',
    },
    'NÃO PASSÍVEL DE ANÁLISE - DOCUMENTO NÃO ACEITO': {
        'message': 'Documento de identifcação não aceito',
        'front': 'Favor enviar documento de identificação original válido (CNH, RG e Militar)',
    },
    'COM RISCO CPF DIVERGENTE': {
        'message': 'Documento de identificação de outro cliente',
        'front': 'Favor enviar documento de identificação do cliente - Documento apresentado é de outra pessoa',
    },
    'COM RISCO - AUTOFRAUDE': {
        'message': 'CPF com restrição - Base negativa',
        'front': 'Cliente com  restrição interna',
    },
    'COM RISCO - VALIDAÇÃO CADASTRAL': {
        'message': 'CPF com restrição - Validação cadastral',
        'front': 'Cliente com restrição interna',
    },
    'COM RISCO - ALTA REINCIDÊNCIA': {
        'message': 'CPF com restrição - Alta Reincidência',
        'front': 'Cliente com restrição interna',
    },
}

SELFIE_STATUS = ['NÃO PASSÍVEL DE ANÁLISE - SELFIE INVÁLIDA', 'AUSENTE - SELFIE']
DOCUMENT_STATUS = [
    'NÃO PASSÍVEL DE ANÁLISE - DOCUMENTO NÃO ACEITO',
    'COM RISCO - FACEMATCH',
    'AUSENTE - DOCUMENTO',
    'NÃO PASSÍVEL DE ANÁLISE - DOCUMENTO ILEGÍVEL/INCOMPLETO',
    'AUSENTE - FACE DO DOCUMENTO',
]
DISAPPROVE_STATUS = [
    'COM RISCO - FOTO DE FOTO DA SELFIE',
    'COM RISCO - DOCUMENTO DE IDENTIFICAÇÃO',
    'COM RISCO - VALIDAÇÃO CADASTRAL',
    'COM RISCO - APONTAMENTO CPF',
    'COM RISCO - BIOMETRIA',
    'COM RISCO - BASE NEGATIVA',
    'COM RISCO - AUTOFRAUDE',
    'COM RISCO - TOMADOR NÃO ASSINA',
    'COM RISCO - ALTA REINCIDÊNCIA',
]


class BPOProcessor:
    def __init__(self, contract: Contrato, product_contract):
        self.contract = contract
        self.product_contract = product_contract
        self.parameter = self.get_parameter()
        self.bpo = self.get_bpo()
        self.processor = None

    def get_parameter(self):
        if store_parameter := BPOConfig.objects.filter(
            products=self.contract.tipo_produto, stores=self.contract.corban
        ).first():
            return store_parameter

        corban_master = Corban.objects.get(
            corban_CNPJ=self.contract.corban.corban_CNPJ
        ).parent_corban

        if corban_parameter := BPOConfig.objects.filter(
            products=self.contract.tipo_produto, corbans=corban_master, stores=None
        ).first():
            return corban_parameter

        if product_parameter := BPOConfig.objects.filter(
            products=self.contract.tipo_produto, corbans=None, stores=None
        ).first():
            return product_parameter

        return None

    def get_bpo(self):
        if not self.parameter:
            return None

        rules = BPORow.objects.filter(parameter=self.parameter)

        if self.contract.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
            contract_amount = self.product_contract.vr_contrato
        elif self.contract.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            contract_amount = self.contract.limite_pre_aprovado
        elif self.contract.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            withdrawal = self.contract.contrato_saque_complementar.last()
            contract_amount = withdrawal.valor_saque
        else:
            contract_amount = self.product_contract.saldo_devedor

        return next(
            (
                rule.bpo
                for rule in rules
                if float(rule.amount_from)
                < float(contract_amount)
                < float(rule.amount_to)
            ),
            None,
        )

    def get_processor(self):
        match self.bpo:
            case BPO.SERASA.value:
                return SerasaProcessor(contract=self.contract)
            case _:
                return None

    def execute(self):
        if self.bpo is None:
            raise NotImplementedError

        if self.processor is None:
            self.processor = self.get_processor()

        self.processor.execute()


class SerasaProcessor(BPOProcessor):
    def __init__(self, contract: Contrato):
        self.client = Client()
        self.contract = contract
        self.attachments = self.get_attachments()

    def get_attachments(self):
        document_attachments = [
            EnumTipoAnexo.DOCUMENTO_FRENTE,
            EnumTipoAnexo.DOCUMENTO_VERSO,
            EnumTipoAnexo.CNH,
            EnumTipoAnexo.FRENTE_CNH,
            EnumTipoAnexo.VERSO_CNH,
        ]

        attachments = []

        contract_attachments = AnexoContrato.objects.filter(
            contrato=self.contract, tipo_anexo__in=document_attachments, active=True
        )

        for attachment in contract_attachments:
            buffer = download_arquivo_s3_base64(
                bucket_name=attachment.extract_bucket_name_from_url(),
                object_key=attachment.extract_object_key_from_url(),
            )

            document_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            attachments.append({
                'arquivo': document_base64,
                'tipo': TipoArquivo.DOC_IDENTIFICACAO.value,
            })

        selfies = AnexoContrato.objects.filter(
            contrato=self.contract, tipo_anexo=EnumTipoAnexo.SELFIE, active=True
        )

        for attachment in selfies:
            buffer = download_arquivo_s3_base64(
                bucket_name=attachment.extract_bucket_name_from_url(),
                object_key=attachment.extract_object_key_from_url(),
            )

            document_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            attachments.append({
                'arquivo': document_base64,
                'tipo': TipoArquivo.FOTO.value,
            })

        return attachments

    def execute(self):
        cpf = self.contract.cliente.nu_cpf.replace('.', '').replace('-', '')

        if SerasaProtocol.objects.filter(
            cpf=cpf, contract=self.contract, processed=False
        ).exists():
            return

        response = self.client.digitalizacao.send(
            cpf=cpf, contrato=self.contract.id, files=self.attachments
        )

        SerasaProtocol.objects.create(
            cpf=cpf, contract=self.contract, protocol=response.get('cod_registro')
        )


def get_stores_by_corbans(corbans):
    subordinate_ids = set()

    for id in corbans:
        corban = Corban.objects.get(id=id)

        subordinate_ids.update(get_subordinate_ids_at_all_levels(corban))

    return Corban.objects.filter(id__in=subordinate_ids)


def get_entities_by_products(products):
    entities_ids = (
        ProdutoConvenio.objects.filter(produto__in=products)
        .order_by('convenio__nome')
        .values_list('convenio__id', flat=True)
    )

    return Convenios.objects.filter(id__in=entities_ids)


def process_serasa_protocol(protocol):
    from core.api.views import refuse_card_contract

    checked = protocol.result == 'SEM RISCO APARENTE'

    ValidacaoContrato.objects.update_or_create(
        contrato=protocol.contract,
        mensagem_observacao='Documentoscopia',
        defaults={
            'retorno_hub': protocol.result,
            'checked': checked,
        },
    )

    message = ''
    front = ''
    sub_contract = None

    if default_message := DEFAULT_RETURNS.get(protocol.result):
        message = default_message.get('message', '')
        front = default_message.get('front', '')

    if protocol.contract.tipo_produto in [
        EnumTipoProduto.PORTABILIDADE,
        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
    ]:
        sub_contract = Portabilidade.objects.get(contrato=protocol.contract)
        refuse_function = refuse_contract
    elif protocol.contract.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
        sub_contract = MargemLivre.objects.get(contrato=protocol.contract)
        refuse_function = refuse_contract
    else:
        sub_contract = CartaoBeneficio.objects.filter(
            contrato=protocol.contract
        ).first()
        refuse_function = refuse_card_contract

    if protocol.result in DISAPPROVE_STATUS:
        return refuse_function(protocol.contract, message)

    if not checked:
        StatusContrato.objects.create(
            contrato=protocol.contract,
            descricao_mesa=message,
            descricao_front=front,
            nome=ContractStatus.PENDENTE_DOCUMENTACAO.value,
        )
        if sub_contract:
            sub_contract.status = ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value
            sub_contract.save()

        if protocol.result in SELFIE_STATUS:
            protocol.contract.selfie_pendente = True
        elif protocol.result in DOCUMENT_STATUS:
            protocol.contract.pendente_documento = True

        protocol.contract.save()
    else:
        approve_contract_automatic(protocol.contract)


def analyse_cpf(contract, sub_contract=None):
    cpf = contract.cliente.nu_cpf
    birthdate = str(contract.cliente.dt_nascimento)

    client = MostClient()
    if MostProtocol.objects.filter(
        cpf=cpf, contract=contract, processed=False
    ).exists():
        return

    response = client.enrichment.send(
        query='BYX_PF_01',
        cpf=cpf,
        birthdate=birthdate,
    )

    MostProtocol.objects.create(
        cpf=cpf, contract=contract, protocol=response.get('processId')
    )

    if sub_contract:
        sub_contract.status = ContractStatus.VALIDACOES_AUTOMATICAS.value
        sub_contract.save(update_fields=['status'])

    StatusContrato.objects.create(
        contrato=contract,
        nome=ContractStatus.VALIDACOES_AUTOMATICAS.value,
        descricao_mesa='',
    )


def process_most_protocol(protocol):
    from contract.api.views import valida_status_score
    from core.api.views import refuse_card_contract

    checked = protocol.result == 'REGULAR'

    ValidacaoContrato.objects.update_or_create(
        contrato=protocol.contract,
        mensagem_observacao='Situação CPF',
        defaults={
            'retorno_hub': protocol.result,
            'checked': checked,
        },
    )

    sub_contract = None

    if protocol.contract.tipo_produto in [
        EnumTipoProduto.PORTABILIDADE,
        EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
    ]:
        sub_contract = Portabilidade.objects.get(contrato=protocol.contract)
        refuse_function = refuse_contract
    elif protocol.contract.tipo_produto == EnumTipoProduto.MARGEM_LIVRE:
        sub_contract = MargemLivre.objects.get(contrato=protocol.contract)
        refuse_function = refuse_contract
    else:
        sub_contract = CartaoBeneficio.objects.filter(
            contrato=protocol.contract
        ).first()
        refuse_function = refuse_card_contract

    if hasattr(sub_contract, 'CPF_dados_divergentes'):
        sub_contract.CPF_dados_divergentes = not checked
        sub_contract.save(update_fields=['CPF_dados_divergentes'])

    if checked:
        valida_status_score(
            protocol.contract,
            sub_contract,
            protocol.contract.envelope.erro_unico,
            protocol.contract.envelope.erro_restritivo_unico,
        )

    if not checked:
        message = f'Situação cadastral diferente de regular - {protocol.result}'

        return refuse_function(protocol.contract, message)
