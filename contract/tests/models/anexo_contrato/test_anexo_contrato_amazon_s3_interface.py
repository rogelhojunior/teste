"""
Test AnexoContratoAmazonS3Interface class.

To execute this test properly you need to set data into a fixture file.
This fiel is placed in this path:

contract/tests/fixtures/fixture_anexo_contrato_amazon_s3_interface.json

and contains data to execute this test. Before to execute the test check
if the fixture 'contract.anexocontrato' have a valid url in the field
'anexo_url', this url is pointing to a AWS uploaded image on our buckets,
you need to check if this url is still pointing to a file, if not,
please find another uploaded image and replace the attribute 'anexo_url'
with it.
"""

# built-in
import os
import shutil
import tempfile
from typing import Tuple

# third
from django.test import TestCase

# local
from contract.models.anexo_contrato import AnexoContrato
from contract.models.anexo_contrato.anexo_contrato_amazon_s3_interface import (
    AnexoContratoAmazonS3Interface,
)
from contract.models.contratos import Contrato

# constants
UPLOAD_IMAGE = 'random_image.jpg'
UPLOAD_PDF = 'random_pdf.pdf'


class TestAnexoContratoAmazonS3Interface(TestCase):
    fixtures = ['contract/tests/fixtures/fixture_anexo_contrato_amazon_s3_interface']

    def setUp(self):
        self.anexo_contrato = None
        self.s3_interface = None
        self.contrato = Contrato.objects.get(id=1)
        self.downloads_folder = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.downloads_folder)

    def test_download_file_from_s3(self):
        """
        Test that the file is being downloaded successfully.
        """
        self.anexo_contrato = AnexoContrato.objects.get(id=1)
        self.s3_interface = AnexoContratoAmazonS3Interface(self.anexo_contrato)

        # define where the file is going to be downloaded
        local_file_path = os.path.join(
            self.downloads_folder, self.anexo_contrato.name_with_extension
        )

        # execute the download function
        self.s3_interface.download_file_from_s3(local_file_path)

        # checks if the file was downloaded successfully
        self.assertTrue(os.path.isfile(local_file_path))

    def test_upload_image_to_s3(self):
        """
        Test upload an image to s3. The environment being use to test this
        function is the staging environment. So all the changes have to
        be reverted to preserve the data. This steps are done in this
        test:

        1. download the file from the AnexoContrato.
        2. create a backup of this file in the created local temp folder
        3. upload a new file.
        4. download the file uploaded and make sure that the file
        was uploaded successfully.
        5. revert the upload, uploading the backup file.
        6. check if the uploaded file was uploaded successfully.
        """
        self.anexo_contrato = AnexoContrato.objects.get(id=1)
        self.s3_interface = AnexoContratoAmazonS3Interface(self.anexo_contrato)

        # 1. download the file from the AnexoContrato.
        original_file = self.download_file_from_s3()

        # 2. create a backup of this file in the created local temp folder.
        backup_file = create_a_backup_file(original_file)
        os.remove(original_file)

        # 3. upload a new file.
        file_to_upload = self.create_copy_of_random_file(UPLOAD_IMAGE, original_file)
        self.upload_file_to_s3(original_file)
        os.remove(original_file)

        # 4. download the file uploaded and make sure that the file
        # was uploaded successfully.
        self.check_upload_was_successful(original_file, file_to_upload)

        # 5. revert the upload, uploading the backup file.
        self.revert_uploaded_changes(original_file, backup_file)

        # 6. check if the uploaded file was uploaded successfully.
        self.s3_interface.download_file_from_s3(original_file)
        self.assertTrue(os.path.isfile(original_file))
        self.assertTrue(compare_files(original_file, backup_file))

    def test_upload_pdf_to_s3(self):
        """
        Test upload a pdf to s3. The environment being use to test this
        function is the staging environment. So all the changes have to
        be reverted to preserve the data. This steps are done in this
        test:

        1. download the file from the AnexoContrato.
        2. create a backup of this file in the created local temp folder
        3. upload a new file.
        4. download the file uploaded and make sure that the file
        was uploaded successfully.
        5. revert the upload, uploading the backup file.
        6. check if the uploaded file was uploaded successfully.
        """
        self.anexo_contrato = AnexoContrato.objects.get(id=2)
        self.s3_interface = AnexoContratoAmazonS3Interface(self.anexo_contrato)

        # 1. download the file from the AnexoContrato.
        original_file = self.download_file_from_s3()

        # 2. create a backup of this file in the created local temp folder.
        backup_file = create_a_backup_file(original_file)
        os.remove(original_file)

        # 3. upload a new file.
        file_to_upload = self.create_copy_of_random_file(UPLOAD_PDF, original_file)
        self.upload_file_to_s3(original_file)
        os.remove(original_file)

        # 4. download the file uploaded and make sure that the file
        # was uploaded successfully.
        self.check_upload_was_successful(original_file, file_to_upload)

        # 5. revert the upload, uploading the backup file.
        self.revert_uploaded_changes(original_file, backup_file)

        # 6. check if the uploaded file was uploaded successfully.
        self.s3_interface.download_file_from_s3(original_file)
        self.assertTrue(os.path.isfile(original_file))
        self.assertTrue(compare_files(original_file, backup_file))

    def test_is_s3(self):
        """
        Test property AnexoContratoAmazonS3Interface.is_s3.
        """
        # when True
        anexo_contrato = AnexoContrato.objects.get(id=1)
        s3_interface = AnexoContratoAmazonS3Interface(anexo_contrato)
        self.assertTrue(s3_interface.is_s3)

        # when False
        anexo_contrato.anexo_url = 'not_amazon_s3_bucket'
        anexo_contrato.save()
        self.assertFalse(s3_interface.is_s3)

    def download_file_from_s3(self) -> str:
        """
        Download a file from s3 inside the folder defined in the
        attribute self.download_folder and return the full path to the
        file.

        Returns:
            str: path to the downloaded file.
        """
        path_to_file = os.path.join(
            self.downloads_folder, self.anexo_contrato.name_with_extension
        )
        self.s3_interface.download_file_from_s3(path_to_file)
        self.assertTrue(os.path.isfile(path_to_file))
        return path_to_file

    def create_copy_of_random_file(self, target_file: str, original_file: str):
        """
        Create a copy of the random file inside the temp local folder
        created, with the same name then the original file name. The
        name is important to make S3 upload function to override the
        existing file.

        Args:
            target_file (str): The file to upload.
            original_file (str): The path where to copy the file.

        Returns:
            str: the full path to the file chosen to be uploaded.
        """
        file_to_upload = os.path.join(get_current_directory(), target_file)
        self.assertTrue(os.path.isfile(file_to_upload))
        shutil.copy(file_to_upload, original_file)
        self.assertTrue(os.path.isfile(original_file))
        return file_to_upload

    def upload_file_to_s3(self, file_path: str):
        """
        Upload a file to amazon S3.

        Args:
            file_path (str): The original file full path
        """
        self.s3_interface.upload_file_to_s3(file_path)

    def check_upload_was_successful(self, original_file: str, uploaded_file: str):
        """
        Check if an upload was successful by comparing the original file
        to the uploaded file.

        This method downloads the original file from Amazon S3 and then
        compares it to the uploaded file. It asserts that both files
        exist and have the same content.

        Args:
            original_file (str): The path to the original file in Amazon
            S3.
            uploaded_file (str): The path to the uploaded file.

        Raises:
            AssertionError: If the original and uploaded files do not
            exist or if their contents are not the same.
        """
        self.s3_interface.download_file_from_s3(original_file)
        self.assertTrue(os.path.isfile(original_file))
        self.assertTrue(compare_files(original_file, uploaded_file))

    def revert_uploaded_changes(self, file_uploaded: str, original_backup_file: str):
        """
        Revert changes made to an uploaded file by restoring it from a
        backup. This method reverts the uploaded file to its original state
        by removing the current uploaded file, copying the original backup
        file to replace it, and then re-uploading the restored file to
        Amazon S3.

        Args:
            file_uploaded (str): The path to the uploaded file that needs to
                be reverted.
            original_backup_file (str): The path to the original backup file.
        """
        os.remove(file_uploaded)
        shutil.copy(original_backup_file, file_uploaded)
        self.s3_interface.upload_file_to_s3(file_uploaded)
        os.remove(file_uploaded)


def create_a_backup_file(target_file: str) -> str:
    """
    Create a backup file from a target file in the same directory than
    the target file is located, adding a '_backup' string before the
    file extension.

    Args:
        target_file (str): the target file to create the backup.

    Returns:
        str: the full path to the created file.
    """
    file_name, file_extension = get_name_and_extension(target_file)
    backup_file = f'{file_name}_backup.{file_extension}'
    backup_file = os.path.join(os.path.dirname(target_file), backup_file)
    shutil.copy(target_file, backup_file)
    return backup_file


def get_name_and_extension(file_path: str) -> Tuple[str, str]:
    """
    Extract the name and extension from a file path.

    Args:
        file_path (str): The path to the file.

    Returns:
        tuple: A tuple containing the file name and its extension.

    Example:
        >>> get_name_and_extension('/path/to/file.txt')
        ('file', 'txt')
    """
    file_base_name = os.path.basename(file_path)
    return file_base_name.split('.')


def get_current_directory():
    """
    Get the current directory of the Python script or module.
    """
    return os.path.dirname(os.path.abspath(__file__))


def compare_files(file1_path, file2_path):
    with open(file1_path, 'rb') as file1, open(file2_path, 'rb') as file2:
        content1 = file1.read()
        content2 = file2.read()

    return content1 == content2
