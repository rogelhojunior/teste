import hashlib
import io
import tempfile
from datetime import datetime

import boto3
import newrelic.agent
from dateutil.relativedelta import relativedelta
from django.conf import settings
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from slugify import slugify

from contract.constants import EnumTipoAnexo
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import Contrato
from contract.termos import pegar_nome_cidade, download_arquivo_s3_base64
from core.utils import real_br_money_mask, word_coordinates_in_pdf

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


class SabemiLifeInsuranceMoneyLenderDiamondTerm:
    def __init__(self):
        self.file_path = 'static/sabemi/termo_adesao_vida_prestamista_diamante.pdf'

    def fill_term(self, data, contract, plano):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                input_pdf = PdfFileReader(open(self.file_path, 'rb'))
                output_pdf = PdfFileWriter()

                for page_num in range(input_pdf.getNumPages()):
                    page = input_pdf.getPage(page_num)
                    output_pdf.addPage(page)

                self._fill_term_first_page(
                    data=data, contract=contract, plano=plano, input_pdf=input_pdf
                )
                self._fill_term_second_page(
                    contract=contract, plano=plano, input_pdf=input_pdf
                )

                nome_arquivo = 'termo-vida-diamante-prestamista-sabemi'
                nome_anexo = 'TERMO VIDA DIAMANTE PRESTAMISTA SABEMI'

                self._save_terms_in_s3(
                    temp_dir,
                    output_pdf,
                    data.get('token_contrato'),
                    data.get('cpf_slugify'),
                    data.get('data_emissao_slugify'),
                    data.get('contrato'),
                    nome_arquivo,
                    nome_anexo,
                )

        except Exception:
            newrelic.agent.notice_error()

    def sign_term(self, contract_id):
        try:
            return_data = {'message': 'Erro ao assinar CCB.', 'status': 500}

            contract = Contrato.objects.filter(pk=contract_id).first()
            if not contract:
                return {
                    'message': f'Esse contrato não existe {contract_id}',
                    'status': 404,
                }

            contract_token = contract.token_contrato or ''
            folder_name = str(contract_token)
            customer_data_hash = f'{contract.cliente.pk}{contract.latitude}{contract.longitude}{contract.ip_publico_assinatura}'
            hash_str = hashlib.md5(customer_data_hash.encode('utf-8')).hexdigest()
            city_name = pegar_nome_cidade(contract.latitude, contract.longitude)
            today_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

            attachments = AnexoContrato.objects.filter(contrato=contract)

            issue_date = (
                contract.criado_em.strftime('%d/%m/%Y') if contract.criado_em else ''
            )
            issue_date_slugify = slugify(issue_date).replace('-', '')

            cpf_slugify = contract.cliente.nu_cpf.replace('.', '').replace('-', '')

            for attachment in attachments:
                attachment_name = slugify(attachment.nome_anexo)

                if (
                    attachment.tipo_anexo == EnumTipoAnexo.TERMOS_E_ASSINATURAS
                    and f'termo-vida-diamante-prestamista-sabemi-{cpf_slugify}-{issue_date_slugify}'
                    in attachment_name
                    and 'assinado' not in attachment.nome_anexo
                ):
                    object_key = (
                        f'{folder_name}/{attachment_name}.{attachment.anexo_extensao}'
                    )

                    s3 = boto3.resource('s3')
                    bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS)
                    bucket_name = settings.BUCKET_NAME_TERMOS
                    document_stream = download_arquivo_s3_base64(
                        bucket_name, object_key
                    )
                    input_pdf = PdfFileReader(document_stream)
                    output_pdf = PdfFileWriter()

                    for page_num in range(input_pdf.getNumPages()):
                        page = input_pdf.getPage(page_num)
                        output_pdf.addPage(page)

                    self._sign_term_last_page(
                        contract=contract,
                        city_name=city_name,
                        today_str=today_str,
                        hash_str=hash_str,
                        input_pdf=input_pdf,
                    )

                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_filename = f'{attachment_name}_editado_temp.pdf'
                        with open(f'{temp_dir}/{temp_filename}', 'wb') as output_file:
                            output_pdf.write(output_file)

                        new_object_key = f'{folder_name}/{attachment_name}-{contract.pk}-assinado.pdf'

                        with open(
                            f'{temp_dir}/{temp_filename}', 'rb'
                        ) as file_to_upload:
                            bucket.upload_fileobj(
                                file_to_upload,
                                new_object_key,
                                ExtraArgs={'ContentType': 'application/pdf'},
                            )

                            url = s3_cliente.generate_presigned_url(
                                'get_object',
                                Params={
                                    'Bucket': bucket_name,
                                    'Key': new_object_key,
                                },
                                ExpiresIn=31536000,
                            )

                            AnexoContrato.objects.create(
                                contrato=contract,
                                tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                                nome_anexo=f'{attachment_name}-assinado',
                                anexo_extensao='pdf',
                                anexo_url=url,
                            )

                            return_data = {
                                'message': 'CCB ASSINADA.',
                                'status': 200,
                                'url': url,
                            }

        except Exception:
            newrelic.agent.notice_error()

        return return_data

    def _fill_term_first_page(self, data, contract, plano, input_pdf):
        page = input_pdf.getPage(0)

        packet = io.BytesIO()
        canvas_pdf = canvas.Canvas(packet, pagesize=letter)

        canvas_pdf.setFont('Helvetica', 9)

        self._fill_term_first_section(data=data, canvas_pdf=canvas_pdf)
        self._fill_term_second_section(data=data, canvas_pdf=canvas_pdf)
        self._fill_term_third_section(
            data=data, contract=contract, plano=plano, canvas_pdf=canvas_pdf
        )

        canvas_pdf.save()

        new_page = PdfFileReader(packet).getPage(0)

        page.mergePage(new_page)

    def _fill_term_second_page(self, contract, plano, input_pdf):
        page = input_pdf.getPage(1)

        packet = io.BytesIO()
        canvas_pdf = canvas.Canvas(packet, pagesize=letter)

        canvas_pdf.setFont('Helvetica', 9)

        self._fill_term_fourth_section(
            contract=contract, plano=plano, canvas_pdf=canvas_pdf
        )

        canvas_pdf.save()

        new_page = PdfFileReader(packet).getPage(0)

        page.mergePage(new_page)

    def _fill_term_first_section(self, data, canvas_pdf):
        proposal_number = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Nº da Proposta'
        )
        if proposal_number and data.get('termo_n'):
            canvas_pdf.drawString(
                proposal_number.get('next_line_x'),
                proposal_number.get('next_line_y'),
                data.get('termo_n'),
            )

    def _fill_term_second_section(self, data, canvas_pdf):
        full_name_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Nome do Segurado'
        )
        if full_name_coord and data.get('nome_titular'):
            canvas_pdf.drawString(
                full_name_coord.get('next_line_x'),
                full_name_coord.get('next_line_y'),
                data.get('nome_titular'),
            )

        birthdate_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Data de Nascimento'
        )
        if birthdate_coord and data.get('data_nascimento'):
            canvas_pdf.drawString(
                birthdate_coord.get('next_line_x'),
                birthdate_coord.get('next_line_y'),
                data.get('data_nascimento'),
            )

        cpf_coord = word_coordinates_in_pdf(pdf_path=self.file_path, word='CPF')
        if cpf_coord and data.get('cpf'):
            canvas_pdf.drawString(
                cpf_coord.get('next_line_x'),
                cpf_coord.get('next_line_y'),
                data.get('cpf'),
            )

        issuing_body_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Órgão Emissor'
        )
        if issuing_body_coord and data.get('orgao_expedidor'):
            canvas_pdf.drawString(
                issuing_body_coord.get('next_line_x'),
                issuing_body_coord.get('next_line_y'),
                data.get('orgao_expedidor'),
            )

        nationality_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Nacionalidade'
        )
        if nationality_coord and data.get('nacionalidade'):
            canvas_pdf.drawString(
                nationality_coord.get('next_line_x'),
                nationality_coord.get('next_line_y'),
                data.get('nacionalidade'),
            )

        cep_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='CEP', word_order=2
        )
        if cep_coord and data.get('cep_entrega'):
            canvas_pdf.drawString(
                cep_coord.get('next_line_x'),
                cep_coord.get('next_line_y'),
                data.get('cep_entrega'),
            )

        address_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Endereço', word_order=2
        )
        if address_coord and data.get('rua_entrega'):
            canvas_pdf.drawString(
                address_coord.get('next_line_x'),
                address_coord.get('next_line_y'),
                data.get('rua_entrega'),
            )

        address_number_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Número', word_order=2
        )
        if address_number_coord and data.get('numero_entrega'):
            canvas_pdf.drawString(
                address_number_coord.get('next_line_x'),
                address_number_coord.get('next_line_y'),
                data.get('numero_entrega'),
            )

        address_complement_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Complemento', word_order=2
        )
        if address_complement_coord and data.get('complemento_entrega'):
            canvas_pdf.drawString(
                address_complement_coord.get('next_line_x'),
                address_complement_coord.get('next_line_y'),
                data.get('complemento_entrega'),
            )

        phone_number_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Telefone', word_order=1
        )
        if phone_number_coord and data.get('telefone'):
            canvas_pdf.drawString(
                phone_number_coord.get('next_line_x'),
                phone_number_coord.get('next_line_y'),
                data.get('telefone'),
            )

    def _fill_term_third_section(self, data, contract, plano, canvas_pdf):
        life_insurance_initial_date = datetime.strftime(contract.criado_em, '%d/%m/%Y')
        life_insurance_initial_date_obj = datetime.strptime(
            life_insurance_initial_date, '%d/%m/%Y'
        )
        life_insurance_final_date = life_insurance_initial_date_obj + relativedelta(
            months=plano.quantidade_parcelas
        )
        life_insurance_final_date = life_insurance_final_date.strftime('%d/%m/%Y')

        life_insurance_initial_date_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Início às 24h do dia'
        )
        if life_insurance_initial_date_coord and life_insurance_initial_date:
            canvas_pdf.drawString(
                life_insurance_initial_date_coord.get('same_line_x'),
                life_insurance_initial_date_coord.get('same_line_y'),
                life_insurance_initial_date,
            )

        life_insurance_final_date_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Fim às 24h do dia'
        )
        if life_insurance_final_date_coord and life_insurance_final_date:
            canvas_pdf.drawString(
                life_insurance_final_date_coord.get('same_line_x'),
                life_insurance_final_date_coord.get('same_line_y'),
                life_insurance_final_date,
            )

    def _fill_term_fourth_section(self, contract, plano, canvas_pdf):
        gross_anual_amount = round(
            float(plano.porcentagem_premio) * float(contract.limite_pre_aprovado) / 100,
            2,
        )
        iof = round(float(gross_anual_amount) * float(plano.iof) / 100, 2)
        net_annual_amount = round(float(gross_anual_amount) - float(iof), 2)

        net_annual_amount_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Prêmio anual Líquido', fix_x=50
        )
        if net_annual_amount_coord and net_annual_amount:
            canvas_pdf.drawString(
                net_annual_amount_coord.get('next_line_x'),
                net_annual_amount_coord.get('next_line_y'),
                real_br_money_mask(net_annual_amount),
            )

        iof_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='IOF', fix_x=15
        )
        if iof_coord and iof:
            canvas_pdf.drawString(
                iof_coord.get('next_line_x'),
                iof_coord.get('next_line_y'),
                real_br_money_mask(iof),
            )

        gross_anual_amount_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Prêmio anual Bruto', fix_x=45
        )
        if gross_anual_amount_coord and gross_anual_amount:
            canvas_pdf.drawString(
                gross_anual_amount_coord.get('next_line_x'),
                gross_anual_amount_coord.get('next_line_y'),
                real_br_money_mask(gross_anual_amount),
            )

    def _sign_term_last_page(self, contract, city_name, today_str, hash_str, input_pdf):
        page = input_pdf.getPage(input_pdf.getNumPages() - 1)

        packet = io.BytesIO()
        canvas_pdf = canvas.Canvas(packet, pagesize=letter)

        canvas_pdf.setFont('Helvetica', 9)

        self._sign_term_first_section(
            contract=contract,
            city_name=city_name,
            today_str=today_str,
            hash_str=hash_str,
            canvas_pdf=canvas_pdf,
        )

        canvas_pdf.save()

        new_page = PdfFileReader(packet).getPage(0)

        page.mergePage(new_page)

    def _sign_term_first_section(
        self, contract, city_name, today_str, hash_str, canvas_pdf
    ):
        sign_str_first_line = f'{hash_str.upper()}'
        sign_str_second_line = f'{city_name} - DATA/HORA: {today_str}'
        sign_str_third_line = f'IP: {contract.ip_publico_assinatura}'

        formatted_date = datetime.strptime(today_str, '%d/%m/%Y %H:%M:%S').strftime(
            '%d/%m/%Y'
        )

        city_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Cidade', word_order=6
        )
        if city_coord and city_name:
            canvas_pdf.drawString(
                city_coord.get('same_line_x'),
                city_coord.get('same_line_y'),
                city_name,
            )

        date_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Data', word_order=2
        )
        if date_coord and formatted_date:
            canvas_pdf.drawString(
                date_coord.get('same_line_x'),
                date_coord.get('same_line_y'),
                formatted_date,
            )

        sign_first_line_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Assinatura do Proponente', fix_y=20
        )
        if sign_first_line_coord and sign_str_first_line:
            canvas_pdf.drawString(
                sign_first_line_coord.get('same_line_x'),
                sign_first_line_coord.get('same_line_y'),
                sign_str_first_line,
            )

        sign_second_line_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Assinatura do Proponente', fix_y=10
        )
        if sign_second_line_coord and sign_str_second_line:
            canvas_pdf.drawString(
                sign_second_line_coord.get('same_line_x'),
                sign_second_line_coord.get('same_line_y'),
                sign_str_second_line,
            )

        sign_third_line_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Assinatura do Proponente'
        )
        if sign_third_line_coord and sign_str_third_line:
            canvas_pdf.drawString(
                sign_third_line_coord.get('same_line_x'),
                sign_third_line_coord.get('same_line_y'),
                sign_str_third_line,
            )

        full_name_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='Nome', word_order=2
        )
        if full_name_coord and contract.cliente.nome_cliente:
            canvas_pdf.drawString(
                full_name_coord.get('same_line_x'),
                full_name_coord.get('same_line_y'),
                contract.cliente.nome_cliente,
            )

        cpf_coord = word_coordinates_in_pdf(
            pdf_path=self.file_path, word='CPF', word_order=1
        )
        if cpf_coord and contract.cliente.nu_cpf:
            canvas_pdf.drawString(
                cpf_coord.get('same_line_x'),
                cpf_coord.get('same_line_y'),
                contract.cliente.nu_cpf,
            )

    def _save_terms_in_s3(
        self,
        temp_dir,
        output_pdf,
        token_contrato,
        cpf_slugify,
        data_emissao_slugify,
        contrato,
        nome_arquivo,
        nome_anexo,
    ):
        try:
            # Salve o arquivo de saída
            with open(f'{temp_dir}/{nome_arquivo}.pdf', 'wb') as outputStream:
                output_pdf.write(outputStream)

            # abre o arquivo PDF que foi salvo anteriormente
            with open(f'{temp_dir}/{nome_arquivo}.pdf', 'rb') as f:
                # lê os dados do arquivo em um objeto BytesIO
                file_stream = io.BytesIO(f.read())

            # Conecta ao S3
            s3 = boto3.resource('s3')
            bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS)
            bucket_name = settings.BUCKET_NAME_TERMOS
            nome_pasta = str(token_contrato)
            # Salva o arquivo no S3
            bucket.upload_fileobj(
                file_stream,
                f'{nome_pasta}/{nome_arquivo}-{cpf_slugify}-{data_emissao_slugify}.pdf',
                ExtraArgs={'ContentType': 'application/pdf'},
            )

            object_key = (
                f'{nome_pasta}/{nome_arquivo}-{cpf_slugify}-{data_emissao_slugify}.pdf'
            )

            url = s3_cliente.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=31536000,
            )

            AnexoContrato.objects.create(
                contrato=contrato,
                tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                nome_anexo=f'{nome_anexo}-{cpf_slugify}-{data_emissao_slugify}',
                anexo_extensao='pdf',
                anexo_url=url,
            )

        except Exception as e:
            print(e)
            print(
                f'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo {nome_arquivo}'
            )
