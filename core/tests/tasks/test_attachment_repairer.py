import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from contract.models.anexo_contrato import AnexoContrato
from contract.models.anexo_contrato.anexo_contrato_amazon_s3_interface import (
    AnexoContratoAmazonS3Interface,
)
from contract.models.contratos import Contrato
from contract.models.envelope_contratos import EnvelopeContratos
from core.tasks.repair_attachments import AttachmentRepairer


class TestAttachmentRepairer(unittest.TestCase):
    def setUp(self):
        self.contract = MagicMock()
        self.user = MagicMock()
        self.attachment_repairer = AttachmentRepairer(self.contract, self.user)

    @patch('tempfile.mkdtemp')
    def test_init(self, mock_mkdtemp):
        mock_mkdtemp.return_value = '/tmp'
        repairer = AttachmentRepairer(self.contract, self.user)
        self.assertEqual(repairer.temp_folder, '/tmp')

    @patch.object(AttachmentRepairer, 'find_uncorrupted_contract')
    @patch.object(AttachmentRepairer, 'send_overwriter_request')
    def test_repair(self, mock_send_request, mock_find_contract):
        mock_find_contract.return_value = self.contract
        self.attachment_repairer.repair()
        mock_find_contract.assert_called_once()
        mock_send_request.assert_not_called()

    @patch.object(AttachmentRepairer, 'find_uncorrupted_contract')
    @patch.object(AttachmentRepairer, 'send_overwriter_request')
    def test_repair_with_different_contract(
        self, mock_send_request, mock_find_contract
    ):
        different_contract = MagicMock()
        mock_find_contract.return_value = different_contract
        self.attachment_repairer.repair()
        mock_find_contract.assert_called_once()
        self.assertEqual(
            mock_send_request.call_count, len(different_contract.attachments)
        )

    @patch.object(AnexoContrato, 'download')
    @patch.object(AttachmentRepairer, 'send_overwriter_request')
    def test_first_contract_on_envelope(self, mock_send_request, mock_download):
        # create envelope
        envelope = EnvelopeContratos.objects.create()

        # create contracts
        contract_1 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        contract_2 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        # create attachments
        AnexoContrato.objects.create(contrato=contract_1, tipo_anexo=1)

        AnexoContrato.objects.create(contrato=contract_2, tipo_anexo=1)

        self.attachment_repairer = AttachmentRepairer(contract_1, self.user).repair()
        mock_download.assert_not_called()
        mock_send_request.assert_not_called()

    @patch.object(AnexoContrato, 'download')
    @patch.object(AttachmentRepairer, 'send_overwriter_request')
    def test_not_first_contract_on_envelope(self, mock_send_request, mock_download):
        # create envelope
        envelope = EnvelopeContratos.objects.create()

        # create contracts
        contract_1 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        contract_2 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        # create attachments
        AnexoContrato.objects.create(contrato=contract_1, tipo_anexo=1)

        AnexoContrato.objects.create(contrato=contract_2, tipo_anexo=1)

        self.attachment_repairer = AttachmentRepairer(contract_2, self.user).repair()
        self.assertEqual(mock_download.call_count, 1)
        self.assertEqual(mock_send_request.call_count, 1)

    @patch.object(AnexoContrato, 'download')
    @patch.object(AttachmentRepairer, 'send_overwriter_request')
    def test_not_first_contract_on_envelope_more_than_one_att(
        self, mock_send_request, mock_download
    ):
        # create envelope
        envelope = EnvelopeContratos.objects.create()

        # create contracts
        contract_1 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        contract_2 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        # create attachments
        AnexoContrato.objects.create(contrato=contract_1, tipo_anexo=1)

        AnexoContrato.objects.create(contrato=contract_2, tipo_anexo=1)

        AnexoContrato.objects.create(contrato=contract_1, tipo_anexo=2)

        AnexoContrato.objects.create(contrato=contract_2, tipo_anexo=2)

        self.attachment_repairer = AttachmentRepairer(contract_2, self.user).repair()
        self.assertEqual(mock_download.call_count, 2)
        self.assertEqual(mock_send_request.call_count, 2)

    @patch.object(AnexoContrato, 'download')
    @patch.object(AttachmentRepairer, 'send_overwriter_request')
    def test_not_repair_pdfs(self, mock_send_request, mock_download):
        # create envelope
        envelope = EnvelopeContratos.objects.create()

        # create contracts
        contract_1 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        contract_2 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        # create attachments
        AnexoContrato.objects.create(
            contrato=contract_1, tipo_anexo=1, anexo_extensao='anything'
        )

        AnexoContrato.objects.create(
            contrato=contract_2,
            tipo_anexo=1,
            anexo_extensao='anything',
        )

        AnexoContrato.objects.create(
            contrato=contract_1, tipo_anexo=2, anexo_extensao='pdf'
        )

        AnexoContrato.objects.create(
            contrato=contract_2, tipo_anexo=2, anexo_extensao='pdf'
        )

        self.attachment_repairer = AttachmentRepairer(contract_2, self.user).repair()
        self.assertEqual(mock_download.call_count, 1)
        self.assertEqual(mock_send_request.call_count, 1)

    @patch('contract.models.anexo_contrato.download_using_get_request')
    @patch.object(AnexoContratoAmazonS3Interface, 'download_file_from_s3')
    @patch.object(AttachmentRepairer, 'send_overwriter_request')
    def test_download_with_requests_library(
        self, mock_send_request, mock_download, mock_get_download
    ):
        # mock functions
        mock_download.side_effect = ClientError(
            error_response={'Error': {'code': 'test'}}, operation_name='test'
        )

        # create envelope
        envelope = EnvelopeContratos.objects.create()

        # create contracts
        contract_1 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        contract_2 = Contrato.objects.create(
            token_envelope=envelope.token_envelope, tipo_produto=1, cd_contrato_tipo=1
        )

        # create attachments
        AnexoContrato.objects.create(contrato=contract_1, tipo_anexo=1)
        AnexoContrato.objects.create(contrato=contract_2, tipo_anexo=1)

        # execute repair
        self.attachment_repairer = AttachmentRepairer(contract_2, self.user).repair()

        # assert values
        self.assertEqual(mock_get_download.call_count, 1)
