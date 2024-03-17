import hashlib
import io
import logging
import tempfile

import newrelic.agent
import requests
from django.conf import settings
from django.utils import timezone
from PyPDF2 import PdfFileReader, PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from contract.constants import EnumTipoAnexo, EnumTipoProduto
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Contrato
from contract.models.envelope_contratos import EnvelopeContratos
from contract.termos import pegar_nome_cidade, assinatura_termos_uso, assinar_termos
from core.models import Cliente, ParametrosBackoffice
from handlers.aws_boto3 import Boto3Manager
from handlers.confia import prepare_and_process_document_signature

logger = logging.getLogger('digitacao')


class SignContractTermsOfUse:
    def __init__(
        self,
        contrato: Contrato,
        public_ip: str,
        latitude: int,
        longitude: int,
    ):
        self.contract: Contrato = contrato
        self.client: Cliente = self.contract.cliente
        self.public_ip: str = public_ip
        self.latitude: int = latitude
        self.longitude: int = longitude

        self.city_name: str = pegar_nome_cidade(latitude, longitude)
        self.folder_name: str = str(contrato.token_contrato)
        self.current_datetime: str = timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')
        self.bucket_name: str = self.get_bucket_name()

        self.boto_manager = Boto3Manager()

    def update_client_hash(self):
        dados_cliente_hash: str = (
            self.public_ip
            + self.client.nu_cpf
            + self.current_datetime
            + str(self.latitude)
            + str(self.longitude)
        )
        self.contract.hash_assinatura = hashlib.md5(
            dados_cliente_hash.encode('utf-8')
        ).hexdigest()
        self.contract.save(update_fields=['hash_assinatura'])

    def flag_contract_signature(self):
        self.contract.contrato_assinado = True
        self.contract.save(update_fields=['contrato_assinado'])

    def get_bucket_name(self):
        if settings.ENVIRONMENT == 'PROD' or self.contract.tipo_produto in (
            EnumTipoProduto.PORTABILIDADE,
            EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO,
        ):
            bucket_name = f'{settings.BUCKET_NAME_TERMOS}'
        elif self.contract.tipo_produto in (
            EnumTipoProduto.INSS,
            EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
            EnumTipoProduto.INSS_CORBAN,
            EnumTipoProduto.MARGEM_LIVRE,
        ):
            bucket_name = 'termos-inss-stage'
        else:
            raise NotImplementedError('Tipo de produto não mapeado')
        return bucket_name

    def set_string_on_canvas(self, packet: io.BytesIO) -> canvas.Canvas:
        can = canvas.Canvas(packet, pagesize=letter)

        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        # Adicione o texto ao objeto canvas
        x, y = 10, 100
        can.drawString(x, y, 'Assinatura eletrônica:')
        x, y = 10, 90
        can.drawString(
            x,
            y,
            str(self.contract.hash_assinatura.upper())
            + f' | {self.city_name} - DATA/HORA: '
            + str(self.current_datetime)
            + ' | IP: '
            + str(self.public_ip),
        )

        return can.save()

    @staticmethod
    def get_anexo_file_obj(anexo: AnexoContrato) -> io.BytesIO:
        response = requests.get(anexo.anexo_url)
        return io.BytesIO(response.content)

    @staticmethod
    def get_output_pdf(input_pdf: PdfReader) -> PdfWriter:
        output_pdf = PdfWriter()
        for page_num in range(len(input_pdf.pages)):
            page = input_pdf.pages[page_num]
            output_pdf.add_page(page)
        return output_pdf

    def sign_term(self, anexo: AnexoContrato):
        with tempfile.TemporaryDirectory() as temp_dir:
            anexo_file_obj = self.get_anexo_file_obj(anexo)
            input_pdf = PdfReader(anexo_file_obj)
            output_pdf = self.get_output_pdf(input_pdf)
            page = input_pdf.getPage(input_pdf.getNumPages() - 1)
            packet = io.BytesIO()

            self.set_string_on_canvas(packet)

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            anexo_nome = (
                'Portabilidade'
                if 'Portabilidade' in anexo.nome_anexo
                else 'Refinanciamento'
            )

            nome_documento = f'ccb-{anexo_nome.lower()}'

            with open(f'{temp_dir}/{nome_documento}', 'wb') as outputStream:
                output_pdf.write(outputStream)
            with open(f'{temp_dir}/{nome_documento}', 'rb') as f:
                self.boto_manager.upload_fileobj(
                    file=f,
                    bucket_name=self.bucket_name,
                    object_key=f'{self.folder_name}/{nome_documento}',
                    extra_args={'ContentType': 'application/pdf'},
                )
                new_object_key = f'{self.folder_name}/{nome_documento}'
                # PARA VISUALIZAÇÃO
                url = self.boto_manager.generate_presigned_url(
                    bucket_name=self.bucket_name,
                    object_key=new_object_key,
                    expiration_time=31536000,
                )

                anexo, _ = AnexoContrato.objects.update_or_create(
                    contrato=self.contract,
                    nome_anexo=f'ccb-{anexo_nome}',
                    defaults={
                        'tipo_anexo': EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                        'anexo_extensao': 'pdf',
                        'anexo_url': url,
                    },
                )

    def execute(self):
        self.update_client_hash()
        try:
            for anexo in AnexoContrato.objects.filter(
                contrato=self.contract,
                tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
            ):
                self.sign_term(anexo)
            self.flag_contract_signature()
            return True
        except Exception as e:
            newrelic.agent.notice_error()
            logger.critical(
                f'[{self.contract.get_tipo_produto_display()}] - Houve um erro ao assinar a CCB',
                extra={'erro': str(e)},
            )
            return False


class SignFormalizationTerms:
    def __init__(
        self, token_envelope: str, latitude: int, longitude: int, public_ip: str
    ):
        self.token_envelope = token_envelope
        self.latitude: int = latitude
        self.longitude: int = longitude
        self.public_ip: str = public_ip

        self.is_envelope_signed = False

    def get_valid_attachments(self, contract, tipos_anexo):
        return [
            (attachment.anexo_url, attachment.tipo_anexo)
            for attachment in AnexoContrato.objects.filter(
                contrato=contract, tipo_anexo__in=tipos_anexo, anexo_url__isnull=False
            )
        ]

    def validate_geolocation(self, contract: Contrato):
        backoffice_params = ParametrosBackoffice.objects.filter(
            tipoProduto=contract.tipo_produto
        ).first()
        if backoffice_params.geolocalizacao_exigida:
            if not self.latitude or not self.longitude:
                raise ValidationError('Localização não encontrada.')
            if not self.public_ip:
                raise ValidationError('IP não foi encontrado.')
            if pegar_nome_cidade(self.latitude, self.longitude) in ['', None]:
                raise ValidationError(
                    'Problema na localização, não foi possível pegar o nome da cidade.'
                )

    def sign_benefit_card(self, contract: Contrato) -> bool:
        assinar_termos(
            settings.BUCKET_NAME_TERMOS,
            contract,
            self.latitude,
            self.longitude,
            self.public_ip,
        )

        contract.contrato_assinado = True
        contract.save(update_fields=['contrato_assinado'])
        return True

    def sign_portability_or_free_margin(self, contract: Contrato) -> bool:
        assinatura_termos_uso(contract, self.latitude, self.longitude, self.public_ip)
        contract.contrato_assinado = True
        contract.save(update_fields=['contrato_assinado'])
        return True

    def prepare_for_confia(self, contract: Contrato, envelope: EnvelopeContratos):
        if envelope and envelope.id_transacao_confia:
            tipos_anexo = [
                EnumTipoAnexo.DOCUMENTO_FRENTE,
                EnumTipoAnexo.FRENTE_CNH,
                EnumTipoAnexo.DOCUMENTO_VERSO,
            ]
            if valid_attachments := self.get_valid_attachments(contract, tipos_anexo):
                urls_anexos, tipos_anexos = zip(*valid_attachments, strict=False)
                prepare_and_process_document_signature(
                    urls_anexos,
                    envelope.id_transacao_confia,
                    tipos_anexos,
                    self.latitude,
                    self.longitude,
                )

    def process_products_signature(self) -> bool:
        contract = Contrato.objects.filter(token_envelope=self.token_envelope).first()
        self.validate_geolocation(contract=contract)

        contract.latitude = self.latitude
        contract.longitude = self.longitude
        contract.save(update_fields=['latitude', 'longitude'])

        contract.cliente.IP_Cliente = self.public_ip
        contract.cliente.save(update_fields=['IP_Cliente'])

        self.prepare_for_confia(
            contract,
            EnvelopeContratos.objects.filter(
                token_envelope=self.token_envelope
            ).first(),
        )

        for contract in Contrato.objects.filter(token_envelope=self.token_envelope):
            if contract.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.SAQUE_COMPLEMENTAR,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                self.is_envelope_signed = self.sign_benefit_card(contract=contract)
            elif contract.tipo_produto in (
                EnumTipoProduto.PORTABILIDADE,
                EnumTipoProduto.INSS,
                EnumTipoProduto.INSS_REPRESENTANTE_LEGAL,
                EnumTipoProduto.INSS_CORBAN,
                EnumTipoProduto.MARGEM_LIVRE,
            ):
                self.is_envelope_signed = self.sign_portability_or_free_margin(
                    contract=contract
                )
            elif contract.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                self.is_envelope_signed = SignContractTermsOfUse(
                    contract, self.public_ip, self.latitude, self.longitude
                ).execute()

    def execute(self):
        try:
            self.process_products_signature()
            if self.is_envelope_signed:
                return Response(data={'Documentos assinados com sucesso!'})
            return Response(data={'Documentos já assinados!'})
        except ValidationError as e:
            return Response(
                data={'Erro': e.detail},
                status=HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            newrelic.agent.notice_error()
            logger.error(
                f'Erro ao assinar os termos para o contrato {self.token_envelope}, {e}',
                exc_info=True,
            )

            return Response(
                {'Erro': 'Houve um erro ao Assinar os Termos na formalização.'},
                status=HTTP_500_INTERNAL_SERVER_ERROR,
            )
