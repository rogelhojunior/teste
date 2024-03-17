import hashlib
import io
import logging
import tempfile
from datetime import datetime

import boto3
import newrelic.agent
import requests
from dateutil.relativedelta import relativedelta
from django.conf import settings
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from slugify import slugify

# from api_log.models import ConsultaMatricula
from contract.constants import EnumTipoAnexo
from contract.models.anexo_contrato import AnexoContrato
from contract.models.contratos import CartaoBeneficio, Contrato
from contract.termos import pegar_nome_cidade
from core.choices import TIPOS_CONTA
from core.models import Cliente
from core.models.cliente import ClienteCartaoBeneficio, DadosBancarios
from custom_auth.models import UserProfile

logger = logging.getLogger('digitacao')


def real_br_money_mask(my_value):
    if my_value is None:
        return 0
    a = '{:,.2f}'.format(float(my_value))
    b = a.replace(',', 'v')
    c = b.replace('.', ',')
    return c.replace('v', '.')


class CCB:
    def __init__(
        self, person=None, contract_id=None, s3=None, bucket=None, bucket_name=None
    ):
        self.person = person
        self.contract_id = contract_id

        self.s3 = boto3.resource(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.s3_cliente = boto3.client(
            's3',
            region_name='us-east-1',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = self.s3.Bucket(settings.BUCKET_NAME_TERMOS)
        self.bucket_name = settings.BUCKET_NAME_TERMOS

    def assinar_ccb(self, contract_id, documento):
        try:
            try:
                contrato = Contrato.objects.filter(pk=contract_id).first()
                if contrato is None:
                    return {
                        'message': f'Esse contrato não existe {contract_id}',
                        'status': 404,
                    }
            except Contrato.DoesNotExist as e:
                logger.error(f'Contrato não existe (assinar_ccb): {e}')
                return {'message': 'Contrato não existe', 'status': 404}

            token_contrato = contrato.token_contrato or ''
            nome_pasta = str(token_contrato)
            dados_cliente_hash = (
                str(contrato.cliente.pk)
                + str(contrato.latitude)
                + str(contrato.longitude)
                + str(contrato.ip_publico_assinatura)
            )
            hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()
            nome_cidade = pegar_nome_cidade(contrato.latitude, contrato.longitude)
            data_hoje = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

            anexos = AnexoContrato.objects.filter(contrato=contrato)
            for anexo in anexos:
                if (
                    anexo.tipo_anexo == EnumTipoAnexo.TERMOS_E_ASSINATURAS
                    and 'assinado' not in anexo.nome_anexo
                ):
                    cpf_slugify = contrato.cliente.nu_cpf.replace('.', '').replace(
                        '-', ''
                    )
                    data_emissao = contrato.criado_em or ''
                    data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
                    data_emissao_slugify = slugify(data_emissao)
                    data_emissao_slugify = data_emissao_slugify.replace('-', '')
                    nome_anexo = slugify(anexo.nome_anexo)
                    if (
                        f'termos-ccb-{documento}-{cpf_slugify}-{data_emissao_slugify}'
                        in nome_anexo
                    ):
                        object_key = f'{nome_pasta}/{nome_anexo}.{anexo.anexo_extensao}'
                        documento_stream = self.download_arquivo_s3_base64(
                            self.bucket_name, object_key
                        )
                        input_pdf = PdfFileReader(documento_stream)
                        output_pdf = PdfFileWriter()

                        num_pages = input_pdf.getNumPages()
                        for page_num in range(input_pdf.getNumPages()):
                            page = input_pdf.getPage(page_num)
                            output_pdf.addPage(page)

                        # Obtenha a página 0 do PDF
                        page = (
                            input_pdf.getPage(num_pages - 1)
                            if (
                                'regulamento-cartao' in nome_anexo
                                or 'termos-ccb' in nome_anexo
                            )
                            else input_pdf.getPage(num_pages - 2)
                        )
                        # Cria uma nova página
                        packet = io.BytesIO()
                        can = canvas.Canvas(packet, pagesize=letter)
                        can.setFont('Helvetica', 9)
                        can.setFont('Helvetica', 8)
                        if (
                            len(
                                (
                                    (
                                        f'{hash.upper()}'
                                        + f' | {nome_cidade} - DATA/HORA: '
                                    )
                                    + str(data_hoje)
                                    + ' | IP: '
                                )
                                + str(contrato.ip_publico_assinatura)
                            )
                            >= 79
                        ):
                            can.drawString(120, 80, f'{hash.upper()}')
                            can.drawString(
                                120, 71, f'{nome_cidade} - DATA/HORA: {str(data_hoje)}'
                            )
                            can.drawString(
                                120, 62, f'IP: {str(contrato.ip_publico_assinatura)}'
                            )
                        else:
                            y = 70

                            x = 120
                            can.drawString(
                                x,
                                y,
                                (
                                    (
                                        f'{hash.upper()}'
                                        + f' | {nome_cidade} - DATA/HORA: '
                                    )
                                    + str(data_hoje)
                                    + ' | IP: '
                                )
                                + str(contrato.ip_publico_assinatura),
                            )

                        can.setFont('Helvetica', 9)
                        formatted_date = datetime.strptime(
                            data_hoje, '%d/%m/%Y %H:%M:%S'
                        ).strftime('%d/%m/%Y')
                        can.drawString(100, 163, f'{formatted_date}')
                        can.save()

                        # Obtenha a página com o texto como um objeto PdfFileReader
                        new_page = PdfFileReader(packet).getPage(0)

                        # Mesclando a página original com a página atualizada
                        page.mergePage(new_page)

                        with tempfile.TemporaryDirectory() as temp_dir:
                            temp_filename = f'{nome_anexo}_editado_temp.pdf'
                            with open(
                                f'{temp_dir}/{temp_filename}', 'wb'
                            ) as output_file:
                                output_pdf.write(output_file)

                            new_object_key = (
                                f'{nome_pasta}/{nome_anexo}-{contrato.pk}-assinado.pdf'
                            )

                            with open(
                                f'{temp_dir}/{temp_filename}', 'rb'
                            ) as file_to_upload:
                                self.bucket.upload_fileobj(
                                    file_to_upload,
                                    new_object_key,
                                    ExtraArgs={'ContentType': 'application/pdf'},
                                )

                                url = self.s3_cliente.generate_presigned_url(
                                    'get_object',
                                    Params={
                                        'Bucket': self.bucket_name,
                                        'Key': new_object_key,
                                    },
                                    ExpiresIn=31536000,
                                )

                                AnexoContrato.objects.create(
                                    contrato=contrato,
                                    tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                                    nome_anexo=f'{nome_anexo}-assinado',
                                    anexo_extensao='pdf',
                                    anexo_url=url,
                                )

                                return {
                                    'message': 'CCB ASSINADA.',
                                    'status': 200,
                                    'url': url,
                                }
            return {'message': 'Erro ao assinar CCB.', 'status': 500}

        except Exception:
            newrelic.agent.notice_error()
            return {'message': 'Erro ao assinar CCB.', 'status': 500}

    def cria_ccb(self, documento, matricula=''):
        try:
            s3_cliente = boto3.client(
                's3',
                region_name='us-east-1',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    contrato = Contrato.objects.filter(pk=self.contract_id).first()
                    if contrato is None:
                        return {
                            'message': f'Esse contrato não existe {self.contract_id}',
                            'status': 404,
                        }
                except Contrato.DoesNotExist as e:
                    logger.error(f'Contrato não existe (assinar_ccb): {e}')
                    return {'message': 'Contrato não existe', 'status': 404}

                try:
                    cliente = contrato.cliente
                except Cliente.DoesNotExist as e:
                    logger.error(f'Cliente não existe (cria_ccb): {e}')
                    return {'message': 'Cliente não existe!', 'status': 404}
                except Exception as e:
                    logger.error(f'Erro ao obter cliente (cria_ccb): {e}')
                    return {'message': 'Erro ao obter cliente', 'status': 500}

                dados_bancario = DadosBancarios.objects.filter(
                    cliente=cliente.pk
                ).last()
                # matricula = ConsultaMatricula.objects.filter(cliente=cliente.id)

                # if not matricula.exists():
                #     return {'message': 'Matricula não existe', 'status': 404}

                # matricula = matricula.first()
                usuario = UserProfile.objects.get(pk=contrato.created_by_id)

                if self.contract_id is None:
                    return {
                        'message': 'Contrato não existe tente com um contrato valido',
                        'status': 404,
                    }

                cartao = CartaoBeneficio.objects.filter(contrato=contrato).first()

                if not cartao:
                    return {'message': 'Cartão não existe', 'status': 404}

                try:
                    cliente_cartao = contrato.cliente_cartao_contrato.get()
                except ClienteCartaoBeneficio.DoesNotExist:
                    return {'message': 'Cartão não existe', 'status': 404}
                """
                    Cartão
                """
                cedula_n = str(cartao.pk) or ''
                valor_saque = str(real_br_money_mask(cartao.valor_saque)) or ''
                data_emissao = contrato.criado_em or ''
                token_contrato = contrato.token_contrato or ''
                data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
                valor_parcela = cartao.valor_parcela or 0
                qtd_parcela_saque_parcelado_campo = (
                    str(cartao.qtd_parcela_saque_parcelado)
                    if cartao.qtd_parcela_saque_parcelado is not None
                    else '0'
                )
                qtd_parcela_saque_parcelado = (
                    str(cartao.qtd_parcela_saque_parcelado)
                    if cartao.qtd_parcela_saque_parcelado is not None
                    else '1'
                )
                taxa_efetiva_mes = (
                    str(round(contrato.taxa, 2)) if contrato.taxa is not None else ''
                )
                taxa_efetiva_ano = (
                    str(round(contrato.taxa_efetiva_ano, 2))
                    if contrato.taxa_efetiva_ano is not None
                    else ''
                )
                iof_total = str(real_br_money_mask(contrato.vr_iof_total))
                cet_am_cartao = (
                    '{:.2f}'.format(contrato.cet_mes)
                    if contrato.cet_mes is not None
                    else ''
                )
                cet_aa_cartao = (
                    '{:.2f}'.format(contrato.cet_ano)
                    if contrato.cet_ano is not None
                    else ''
                )
                banco_titular = (
                    dados_bancario.conta_banco if dados_bancario is not None else ''
                )
                # data_hoje = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                # nome_cidade = pegar_nome_cidade(contrato.latitude, contrato.longitude)
                # dados_cliente_hash = (
                #     str(cliente.pk)
                #     + str(contrato.latitude)
                #     + str(contrato.longitude)
                #     + str(contrato.ip_publico_assinatura)
                # )
                # hash = hashlib.md5(dados_cliente_hash.encode('utf-8')).hexdigest()

                data_contrato = contrato.criado_em or ''
                vencimento_final_pri = 0
                vencimento_final_fatura = 0
                if data_contrato is not None:
                    vencimento_pri_fatura = data_contrato + relativedelta(months=1)

                    meses = 1
                    if qtd_parcela_saque_parcelado != 'None':
                        meses = qtd_parcela_saque_parcelado

                    vencimento_ultima_fatura = data_contrato + relativedelta(
                        months=int(meses)
                    )

                    vencimento_final_pri = (
                        vencimento_pri_fatura.strftime('%d/%m/%Y') or ''
                    )
                    vencimento_final_fatura = (
                        vencimento_ultima_fatura.strftime('%d/%m/%Y') or ''
                    )

                valor_tt_devido = str(real_br_money_mask(cartao.valor_financiado))
                margem_consignavel = (
                    str(real_br_money_mask(cliente_cartao.margem_atual)) or ''
                )

                """
                Cet do contrato
                """
                cet_am_contrato = (
                    '{:.2f}'.format(contrato.cet_mes)
                    if contrato.cet_mes is not None
                    else '0,00'
                )
                cet_aa_contrato = (
                    '{:.2f}'.format(contrato.cet_ano)
                    if contrato.cet_ano is not None
                    else '0,00'
                )
                # tarifa_cadastro = '0,00'
                # tarifa_saque = '0,00'
                valor_total_a_pagar = (
                    str(real_br_money_mask(cartao.valor_total_a_pagar)) or ''
                )

                # vr_seguro = (
                #     str(real_br_money_mask(contrato.vr_seguro))
                #     if contrato.vr_seguro is not None
                #     else '0,00'
                # )

                # try:
                #     valor_financiado = str(
                #         real_br_money_mask(contrato_saque.valor_lancado_fatura)
                #     )
                # except:
                #     valor_financiado = 0

                """
                Fonte pagadora
                """
                fonte_pagadora = cliente_cartao.convenio.fontepagadora_set.last()

                input_pdf = PdfFileReader(open(f'static/{documento}/ccb.pdf', 'rb'))

                output_pdf = PdfFileWriter()

                num_pages = input_pdf.getNumPages()
                # new_page_first = None
                # new_page_last = None

                for page_num in range(num_pages):
                    page = input_pdf.getPage(page_num)
                    packet = io.BytesIO()
                    can = canvas.Canvas(packet, pagesize=letter)
                    can.setFont('Helvetica', 9)

                    # Defina as coordenadas x e y dependendo do número da página
                    if page_num == 0:
                        cords_person = {
                            'nome': [28, 665],
                            'sexo': {'Masculino': [520, 664], 'Feminino': [480, 664]},
                            'cpf': [28, 635],
                            'rg': [162, 635],
                            'orgao_emissor': [295, 635],
                            'estado_emissao': [400, 635],
                            'estado_civil': [495, 635],
                            'data_emissao': [420, 635],
                            'data_nascimento': [28, 608],
                            'email': [165, 608],
                            'enderco': [28, 581],
                            'bairro': [382, 581],
                            'cidade': [28, 553],
                            'estado': [345, 553],
                            'cep': [373, 553],
                            'ddd': [456, 553],
                            'telefone': [490, 553],
                        }
                        cords_extra = {
                            'fonte_pagadora': [30, 502],
                            'matricula_beneficio': [364, 502],
                            'nome_banco': [28, 453],
                            'agencia': [173, 453],
                            'num_conta': [318, 453],
                            'tipo_conta': [448, 453],
                            'fonte_pagadoras': [300, 397],
                            'nome': [28, 358],
                            'cpf': [453, 358],
                        }
                        cords_cartao = {
                            'cedula': [28, 292],
                            'valor_solicitado': [215, 292],
                            'data_emissao': [405, 292],
                            'liberado_cliente': [28, 264],
                            'credito_financiado': [183, 264],
                            'valor_parcela': [352, 263],
                            'quantidade_parcela': [470, 263],
                            'tx_juros_mensal': [28, 235],
                            'tx_juros_anual': [160, 235],
                            'iof': [329, 235],
                            'cet_mes': [469, 235],
                            'cet_ano': [28, 205],
                            'vencimento_1p': [150, 205],
                            'ultima_parcela': [280, 205],
                            'valor_total_devido': [438, 205],
                            'margem_consignavel': [28, 174],
                            'seguro_cartao_protegido': [187, 174],
                            'valor': [260, 175],
                        }
                        cords_cet = {
                            'iof': [28, 96],
                            'tarifa_cad': [138, 96],
                            'tarifa_saque': [308, 96],
                            'seguro': [469, 96],
                            'cet_am': [28, 65],
                            'cet_aa': [103, 65],
                            'somatorio_parcelas': [190, 65],
                        }
                        x = cords_extra['fonte_pagadoras'][0]
                        y = cords_extra['fonte_pagadoras'][1]
                        can.drawString(x, y, 'x')

                        x = cords_cet['somatorio_parcelas'][0]
                        y = cords_cet['somatorio_parcelas'][1]
                        can.drawString(x, y, f'{valor_total_a_pagar}')

                        x = cords_cet['cet_aa'][0]
                        y = cords_cet['cet_aa'][1]
                        can.drawString(x, y, cet_aa_contrato)

                        x = cords_cet['cet_am'][0]
                        y = cords_cet['cet_am'][1]
                        can.drawString(x, y, cet_am_contrato)

                        x = cords_cet['seguro'][0]
                        y = cords_cet['seguro'][1]
                        can.drawString(x, y, '0,00')

                        x = cords_cet['tarifa_saque'][0]
                        y = cords_cet['tarifa_saque'][1]
                        can.drawString(x, y, '0,00')

                        x = cords_cet['tarifa_cad'][0]
                        y = cords_cet['tarifa_cad'][1]
                        can.drawString(x, y, '0,00')

                        x = cords_cet['iof'][0]
                        y = cords_cet['iof'][1]
                        can.drawString(x, y, iof_total)

                        x = cords_cartao['valor'][0]
                        y = cords_cartao['valor'][1]
                        can.drawString(x, y, ' ')

                        x = cords_cartao['seguro_cartao_protegido'][0]
                        y = cords_cartao['seguro_cartao_protegido'][1]
                        can.drawString(x, y, 'x')

                        x = cords_cartao['margem_consignavel'][0]
                        y = cords_cartao['margem_consignavel'][1]
                        can.drawString(x, y, margem_consignavel)

                        x = cords_cartao['valor_total_devido'][0]
                        y = cords_cartao['valor_total_devido'][1]
                        can.drawString(x, y, valor_tt_devido)

                        x = cords_cartao['ultima_parcela'][0]
                        y = cords_cartao['ultima_parcela'][1]
                        can.drawString(x, y, vencimento_final_fatura)

                        x = cords_cartao['vencimento_1p'][0]
                        y = cords_cartao['vencimento_1p'][1]
                        can.drawString(x, y, vencimento_final_pri)

                        x = cords_cartao['cet_ano'][0]
                        y = cords_cartao['cet_ano'][1]
                        can.drawString(x, y, cet_aa_cartao)

                        x = cords_cartao['cet_mes'][0]
                        y = cords_cartao['cet_mes'][1]
                        can.drawString(x, y, cet_am_cartao)

                        x = cords_cartao['iof'][0]
                        y = cords_cartao['iof'][1]
                        can.drawString(x, y, iof_total)

                        x = cords_cartao['tx_juros_anual'][0]
                        y = cords_cartao['tx_juros_anual'][1]
                        can.drawString(x, y, taxa_efetiva_ano)

                        x = cords_cartao['tx_juros_mensal'][0]
                        y = cords_cartao['tx_juros_mensal'][1]
                        can.drawString(x, y, taxa_efetiva_mes)

                        x = cords_cartao['quantidade_parcela'][0]
                        y = cords_cartao['quantidade_parcela'][1]
                        can.drawString(x, y, qtd_parcela_saque_parcelado_campo)

                        x = cords_cartao['valor_parcela'][0]
                        y = cords_cartao['valor_parcela'][1]
                        can.drawString(x, y, f'{valor_parcela}')

                        x = cords_cartao['credito_financiado'][0]
                        y = cords_cartao['credito_financiado'][1]
                        can.drawString(x, y, f'{valor_saque}')

                        x = cords_cartao['liberado_cliente'][0]
                        y = cords_cartao['liberado_cliente'][1]
                        can.drawString(x, y, valor_saque)

                        x = cords_cartao['data_emissao'][0]
                        y = cords_cartao['data_emissao'][1]
                        can.drawString(x, y, data_emissao)

                        x = cords_cartao['valor_solicitado'][0]
                        y = cords_cartao['valor_solicitado'][1]
                        can.drawString(x, y, valor_saque)

                        x = cords_cartao['cedula'][0]
                        y = cords_cartao['cedula'][1]
                        can.drawString(x, y, cedula_n)

                        x = cords_extra['cpf'][0]
                        y = cords_extra['cpf'][1]
                        can.drawString(x, y, cliente.nu_cpf)

                        x = cords_extra['nome'][0]
                        y = cords_extra['nome'][1]
                        can.drawString(x, y, cliente.nome_cliente)

                        x = cords_extra['tipo_conta'][0]
                        y = cords_extra['tipo_conta'][1]
                        can.setFont('Helvetica', 7)

                        try:
                            can.drawString(
                                x,
                                y,
                                f'{dict(TIPOS_CONTA).get(dados_bancario.conta_tipo, "")}',
                            )
                        except Exception as e:
                            logger.error(
                                f'Erro ao desenhar o tipo da conta (cria_ccb): {e}'
                            )
                            can.drawString(x, y, 0)

                        can.setFont('Helvetica', 9)

                        x = cords_extra['num_conta'][0]
                        y = cords_extra['num_conta'][1]

                        try:
                            can.drawString(x, y, dados_bancario.conta_numero)
                        except Exception as e:
                            logger.error(
                                f'Erro ao desenhar o número da conta (cria_ccb): {e}'
                            )
                            can.drawString(x, y, '0')

                        x = cords_extra['agencia'][0]
                        y = cords_extra['agencia'][1]

                        try:
                            can.drawString(x, y, dados_bancario.conta_agencia)
                        except Exception as e:
                            logger.error(
                                f'Erro ao desenhar o número da agência (cria_ccb): {e}'
                            )
                            can.drawString(x, y, '0')

                        x = cords_extra['nome_banco'][0]
                        y = cords_extra['nome_banco'][1]
                        can.drawString(x, y, f'{banco_titular}')

                        x = cords_extra['matricula_beneficio'][0]
                        y = cords_extra['matricula_beneficio'][1]
                        can.drawString(x, y, f'{matricula}')

                        x = cords_extra['fonte_pagadora'][0]
                        y = cords_extra['fonte_pagadora'][1]
                        can.drawString(
                            x, y, fonte_pagadora.razao_social if fonte_pagadora else ''
                        )

                        x = cords_person['estado_civil'][0]
                        y = cords_person['estado_civil'][1]
                        can.drawString(x, y, cliente.estado_civil)

                        dddTelefone, numeroCelular = cliente.telefone_ddd
                        x = cords_person['ddd'][0]
                        y = cords_person['ddd'][1]
                        can.drawString(x, y, dddTelefone)

                        x = cords_person['telefone'][0]
                        y = cords_person['telefone'][1]
                        can.drawString(x, y, numeroCelular)

                        x = cords_person['cep'][0]
                        y = cords_person['cep'][1]
                        can.drawString(x, y, cliente.endereco_cep)

                        x = cords_person['estado'][0]
                        y = cords_person['estado'][1]
                        can.drawString(x, y, cliente.endereco_uf)

                        x = cords_person['cidade'][0]
                        y = cords_person['cidade'][1]
                        can.drawString(x, y, cliente.endereco_cidade)

                        x = cords_person['bairro'][0]
                        y = cords_person['bairro'][1]
                        can.drawString(x, y, cliente.endereco_bairro)

                        x = cords_person['enderco'][0]
                        y = cords_person['enderco'][1]
                        can.drawString(
                            x,
                            y,
                            f'{cliente.endereco_logradouro}, {cliente.endereco_numero}, {cliente.endereco_complemento}',
                        )

                        x = cords_person['email'][0]
                        y = cords_person['email'][1]
                        can.drawString(x, y, cliente.email)

                        x = cords_person['data_nascimento'][0]
                        y = cords_person['data_nascimento'][1]
                        can.drawString(
                            x,
                            y,
                            f'{datetime.strftime(cliente.dt_nascimento, "%d/%m/%Y")}',
                        )

                        x = cords_person['nome'][0]
                        y = cords_person['nome'][1]
                        can.drawString(x, y, cliente.nome_cliente)

                        sexo = cliente.sexo
                        if sexo == 'Feminino':
                            x = cords_person['sexo']['Feminino'][0]
                            y = cords_person['sexo']['Feminino'][1]

                        elif sexo == 'Masculino':
                            x = cords_person['sexo']['Masculino'][0]
                            y = cords_person['sexo']['Masculino'][1]
                        can.drawString(x, y, 'X')

                        # CPF
                        x = cords_person['cpf'][0]
                        y = cords_person['cpf'][1]
                        can.drawString(x, y, cliente.nu_cpf)

                        # RG
                        x = cords_person['rg'][0]
                        y = cords_person['rg'][1]
                        can.drawString(x, y, cliente.documento_numero)

                        # ORG EMISSOR
                        x = cords_person['orgao_emissor'][0]
                        y = cords_person['orgao_emissor'][1]
                        can.drawString(x, y, cliente.documento_orgao_emissor)

                        # ESTADO
                        x = cords_person['estado_emissao'][0]
                        y = cords_person['estado_emissao'][1]
                        can.drawString(x, y, f'{cliente.get_documento_uf_display()}')

                        # DT EMISSAO
                        x = cords_person['data_emissao'][0]
                        y = cords_person['data_emissao'][1]
                        can.drawString(
                            x,
                            y,
                            f'{datetime.strftime(cliente.documento_data_emissao, "%d/%m/%Y")}',
                        )
                    elif page_num == 1:
                        cords_emp = {
                            'empresa': [28, 640],
                            'cnpj_empresa': [443, 640],
                            'endereco_empresa': [28, 611],
                            'ddd_empresa': [376, 611],
                            'telefone_empresa': [413, 611],
                            'nome_correspondente': [28, 580],
                            'cpf_correspondente': [460, 580],
                        }
                        x = cords_emp['cpf_correspondente'][0]
                        y = cords_emp['cpf_correspondente'][1]
                        can.drawString(x, y, f'{usuario.identifier}')

                        x = cords_emp['nome_correspondente'][0]
                        y = cords_emp['nome_correspondente'][1]
                        can.drawString(x, y, f'{usuario.name}')

                        x = cords_emp['ddd_empresa'][0]
                        y = cords_emp['ddd_empresa'][1]
                        can.drawString(
                            x, y, f'{usuario.corban.telefone_representante[:2]}'
                        )

                        x = cords_emp['telefone_empresa'][0]
                        y = cords_emp['telefone_empresa'][1]
                        can.drawString(
                            x, y, f'{usuario.corban.telefone_representante[2:]}'
                        )

                        x = cords_emp['endereco_empresa'][0]
                        y = cords_emp['endereco_empresa'][1]
                        can.drawString(x, y, f'{usuario.corban.corban_endereco}')

                        x = cords_emp['cnpj_empresa'][0]
                        y = cords_emp['cnpj_empresa'][1]
                        can.drawString(x, y, f'{usuario.corban.corban_CNPJ}')

                        x = cords_emp['empresa'][0]
                        y = cords_emp['empresa'][1]
                        can.drawString(x, y, f'{usuario.corban.corban_name}')
                    can.save()
                    # Obtenha a página com o hash como um objeto PdfFileReader
                    new_page = PdfFileReader(packet).getPage(0)

                    # Determine qual "nova página" deve ser atualizada
                    # if page_num == 0:
                    #     new_page_first = new_page
                    # elif page_num == num_pages - 1:  # Se for a última página
                    #     new_page_last = new_page

                    # Mesclando a página original com a página atualizada
                    page.mergePage(new_page)

                    output_pdf.addPage(page)

                with open(
                    f'{temp_dir}/CCB_{documento}_assinada.pdf', 'wb'
                ) as outputStream:
                    output_pdf.write(outputStream)

                # abre o arquivo PDF que foi salvo anteriormente
                with open(f'{temp_dir}/CCB_{documento}_assinada.pdf', 'rb') as f:
                    # lê os dados do arquivo em um objeto BytesIO
                    file_stream = io.BytesIO(f.read())

                nome_pasta = str(token_contrato)
                cpf_slugify = contrato.cliente.nu_cpf.replace('.', '').replace('-', '')

                data_emissao_slugify = slugify(data_emissao)
                data_emissao_slugify = data_emissao_slugify.replace('-', '')

                nome_arquivo = 'termos-ccb'
                nome_anexo = 'TERMOS CCB'

                # Salva o arquivo no S3
                self.bucket.upload_fileobj(
                    file_stream,
                    f'{nome_pasta}/{nome_arquivo}-{documento}-{cpf_slugify}-{data_emissao_slugify}.pdf',
                    ExtraArgs={'ContentType': 'application/pdf'},
                )

                object_key = f'{nome_pasta}/{nome_arquivo}-{documento}-{cpf_slugify}-{data_emissao_slugify}.pdf'
                # object_url = f'https://{self.bucket_name}.s3.amazonaws.com/{object_key}'

                url = s3_cliente.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': object_key},
                    ExpiresIn=31536000,
                )

                AnexoContrato.objects.create(
                    contrato=contrato,
                    tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                    nome_anexo=f'{nome_anexo}-{documento.upper()}-{cpf_slugify}-{data_emissao_slugify}',
                    anexo_extensao='pdf',
                    anexo_url=url,
                )

                return {'message': 'CCB CRIADA.', 'status': 200, 'url': url}

        except Exception:
            newrelic.agent.notice_error()
            return {'message': 'Erro ao criar CCB!', 'status': 500}

    def download_arquivo_s3_base64(self, bucket_name, object_key):
        url = self.s3_cliente.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=31536000,
        )
        # Baixe o arquivo usando a URL presigned
        response = requests.get(url)
        documento_bytes = response.content
        return io.BytesIO(documento_bytes)
