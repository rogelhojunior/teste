import io
import logging
import os
import tempfile
from datetime import datetime
from decimal import Decimal

import boto3
import newrelic.agent
from dateutil.relativedelta import relativedelta
from django.conf import settings
from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.pagesizes import elevenSeventeen, letter
from reportlab.pdfgen import canvas
from slugify import slugify

from contract.constants import (
    EnumArquivosSeguros,
    EnumSeguradoras,
    EnumTipoAnexo,
    EnumTipoPlano,
    EnumTipoProduto,
)
from contract.models.anexo_contrato import AnexoContrato
from contract.products.cartao_beneficio.models.convenio import (
    Convenios,
    FontePagadora,
    ProdutoConvenio,
)
from contract.terms.sabemi import (
    SabemiLifeInsuranceMoneyLenderDiamondTerm,
    SabemiLifeInsuranceMoneyLenderGoldTerm,
    SabemiLifeInsuranceSilverTerm,
)
from core.models.cliente import Cliente, DadosBancarios
from core.utils import word_coordinates_in_pdf
from handlers.ccb import CCB

logger = logging.getLogger('digitacao')

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


def real_br_money_mask(my_value):
    if my_value is None:
        return 0
    a = '{:,.2f}'.format(float(my_value))
    b = a.replace(',', 'v')
    c = b.replace('.', ',')
    return c.replace('v', '.')


def gerar_vencimento_final(
    primeiro_vencimento: datetime, numero_de_parcelas: int
) -> str:
    """
    Calcula a data de vencimento final, retornando uma string que a
    represente.

    Args:
        primeiro_vencimento (datetime)
        numero_de_parcelas (int)

    Returns
        (str) vencimento final.
    """
    vencimento_final = primeiro_vencimento + relativedelta(months=numero_de_parcelas)
    return vencimento_final.strftime('%d/%m/%Y') or ''


def get_dados_contrato_saque_complementar(contrato, contrato_saque):
    data_emissao = contrato.criado_em or ''
    data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
    nome_titular = contrato.cliente.nome_cliente or ''
    cpf = contrato.cliente.nu_cpf or ''
    vencimento = contrato.vencimento_fatura or ''
    endereco = (
        f'{contrato.cliente.endereco_logradouro}, {contrato.cliente.endereco_numero} - {contrato.cliente.endereco_bairro}'
        or ''
    )
    cidade_uf = (
        f'{contrato.cliente.endereco_cidade}/{contrato.cliente.endereco_uf}' or ''
    )
    estado_civil = str(contrato.cliente.estado_civil) or ''
    cedula_n = str(contrato.pk) or ''
    valor_saque = str(real_br_money_mask(contrato_saque.valor_saque)) or ''
    valor_total_a_pagar = (
        str(real_br_money_mask(contrato_saque.valor_total_a_pagar)) or ''
    )

    data_contrato = contrato.criado_em or ''
    vencimento_fatura_data = data_contrato + relativedelta(months=1)
    vencimento_fatura_data = vencimento_fatura_data.replace(day=int(vencimento))

    prazo_maximo = str(vencimento_fatura_data - data_contrato) or ''
    prazo_maximo = prazo_maximo.split()[0]

    saque_parcelado = contrato_saque.saque_parcelado
    qtd_parcelas = 1
    if contrato_saque.saque_parcelado:
        qtd_parcelas = contrato_saque.qtd_parcela_saque_parcelado or qtd_parcelas
        prazo_maximo = str(qtd_parcelas) or ''

    vencimento_final = gerar_vencimento_final(
        primeiro_vencimento=vencimento_fatura_data,
        numero_de_parcelas=qtd_parcelas,
    )

    cet_am = '{:.2f}'.format(contrato.cet_mes) or ''
    cet_aa = '{:.2f}'.format(contrato.cet_ano) or ''

    taxa = contrato.taxa_efetiva_mes or ''
    if taxa != '':
        taxa = '{:.2f}'.format(taxa) or ''

    taxa_anual = contrato.taxa_efetiva_ano or ''
    taxa_anual = '{:.2f}'.format(taxa_anual) or ''

    valor_iof_total = str(real_br_money_mask(contrato.vr_iof_total)) or ''
    cliente_cartao = contrato_saque.id_cliente_cartao
    convenio = Convenios.objects.get(pk=cliente_cartao.convenio.pk)
    fonte_pagadora = FontePagadora.objects.get(convenios=convenio)
    razao_social = str(fonte_pagadora.razao_social) or ''

    token_contrato = contrato.token_contrato or ''
    if contrato.seguro:
        vr_seguro = str(real_br_money_mask(contrato.vr_seguro)) or '0.00'
    else:
        vr_seguro = '0.00'

    cliente_dados_bancarios = DadosBancarios.objects.filter(
        cliente=contrato.cliente
    ).last()
    valor_financiado = (
        str(real_br_money_mask(contrato_saque.valor_lancado_fatura)) or ''
    )
    banco_titular = cliente_dados_bancarios.conta_banco or ''
    agencia_titular = cliente_dados_bancarios.conta_agencia or ''
    conta_titular = cliente_dados_bancarios.conta_numero or ''
    tipo_conta_titular = cliente_dados_bancarios.get_conta_tipo_display() or ''
    digito_titular = cliente_dados_bancarios.conta_digito or ''

    data_emissao_slugify = slugify(data_emissao)
    data_emissao_slugify = data_emissao_slugify.replace('-', '')
    cpf_slugify = cpf.replace('.', '').replace('-', '')

    cnpj_pagador = fonte_pagadora.CNPJ or ''
    endereco_pagador = fonte_pagadora.endereco or ''

    ccb(
        data_emissao,
        nome_titular,
        cpf,
        endereco,
        cidade_uf,
        estado_civil,
        cedula_n,
        valor_saque,
        prazo_maximo,
        vencimento_final,
        cet_am,
        cet_aa,
        taxa,
        taxa_anual,
        valor_iof_total,
        razao_social,
        token_contrato,
        contrato,
        vr_seguro,
        valor_financiado,
        banco_titular,
        agencia_titular,
        conta_titular,
        tipo_conta_titular,
        digito_titular,
        data_emissao_slugify,
        cpf_slugify,
        saque_parcelado,
        valor_total_a_pagar,
        cnpj_pagador,
        endereco_pagador,
    )


def get_dados_contrato(contrato, contrato_cartao):
    # VALORES TERMOS DE ADESÃO
    data_emissao = contrato.criado_em or ''
    token_contrato = contrato.token_contrato or ''
    data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
    termo_n = str(contrato.pk) or ''
    nome_titular = contrato.cliente.nome_cliente or ''
    nacionalidade = contrato.cliente.nacionalidade or ''
    estado_civil = str(contrato.cliente.estado_civil) or ''
    rg = contrato.cliente.documento_numero or ''
    orgao_expedidor = contrato.cliente.documento_orgao_emissor or ''
    documento_data_emissao = (
        contrato.cliente.documento_data_emissao.strftime('%d/%m/%Y') or ''
    )
    nome_mae = contrato.cliente.nome_mae or ''
    cpf = contrato.cliente.nu_cpf or ''
    sexo = str(contrato.cliente.sexo) or ''
    data_nascimento = contrato.cliente.dt_nascimento or ''
    data_nascimento = data_nascimento.strftime('%d/%m/%Y') or ''
    pep = contrato.cliente.ppe or ''
    endereco = (
        f'{contrato.cliente.endereco_logradouro}, {contrato.cliente.endereco_numero} - {contrato.cliente.endereco_bairro}'
        or ''
    )
    cidade_uf = (
        f'{contrato.cliente.endereco_cidade}/{contrato.cliente.endereco_uf}' or ''
    )
    telefone = str(contrato.cliente.telefone_celular) or ''
    email = str(contrato.cliente.email) or ''
    valor_total_a_pagar = (
        str(real_br_money_mask(contrato_cartao.valor_total_a_pagar)) or ''
    )

    cliente_cartao = contrato.cliente_cartao_contrato.get()
    limite_credito = (
        str(real_br_money_mask(contrato_cartao.valor_disponivel_saque)) or ''
    )
    limite_pre_aprovado = contrato.limite_pre_aprovado or ''
    margem_consignavel = str(real_br_money_mask(cliente_cartao.margem_atual)) or ''
    saque = contrato_cartao.possui_saque or ''
    compras_a_vista_e_parceladas = True
    saque_complementar = True  # V2
    cartao_credito = True
    pagamento_contas = False
    abrangencia = 'Internacional'
    taxa_emissao = ''
    vencimento = contrato.vencimento_fatura or ''
    forma_pagamento = 'Desconto em folha'
    seguro = contrato.seguro or ''
    convenio = Convenios.objects.get(pk=contrato_cartao.convenio.pk)
    produto_convenio = ProdutoConvenio.objects.filter(
        convenio=convenio, produto=contrato.tipo_produto
    ).first()
    saque_porc = str(produto_convenio.percentual_saque) or ''
    saque_porc = saque_porc.split('.')[0]

    if contrato_cartao.possui_saque or contrato_cartao.saque_parcelado:
        cliente_dados_bancarios = DadosBancarios.objects.filter(
            cliente=contrato.cliente
        ).last()
        banco = cliente_dados_bancarios.conta_banco or ''
        agencia = cliente_dados_bancarios.conta_agencia or ''
        conta = cliente_dados_bancarios.conta_numero or ''
        remuneracao = str(real_br_money_mask(contrato.cliente.renda)) or ''

        banco_titular = cliente_dados_bancarios.conta_banco or ''
        agencia_titular = cliente_dados_bancarios.conta_agencia or ''
        conta_titular = cliente_dados_bancarios.conta_numero or ''
        tipo_conta_titular = cliente_dados_bancarios.get_conta_tipo_display() or ''
        digito_titular = cliente_dados_bancarios.conta_digito or ''

        taxa_efetiva_mes = str(round(contrato.taxa, 2))
        taxa_efetiva_ano = str(round(contrato.taxa_efetiva_ano, 2))
        iof_total = str(real_br_money_mask(contrato.vr_iof_total))
        iof_total_porcentagem = float(contrato.vr_iof_total) / 100
        iof_total_porcentagem = str(round(iof_total_porcentagem, 4))

        qtd_parcela_saque_parcelado = (
            (str(contrato_cartao.qtd_parcela_saque_parcelado) or '')
            if contrato_cartao.saque_parcelado
            else '1'
        )
    else:
        banco = ''
        agencia = ''
        conta = ''
        remuneracao = ''
        banco_titular = ''
        agencia_titular = ''
        conta_titular = ''
        tipo_conta_titular = ''
        digito_titular = ''
        taxa_efetiva_mes = ''
        taxa_efetiva_ano = ''
        iof_total = ''
        iof_total_porcentagem = ''
        qtd_parcela_saque_parcelado = '1'

    endereco_entrega = (
        f'{contrato.cliente.endereco_logradouro}, {contrato.cliente.endereco_numero} - {contrato.cliente.endereco_bairro}'
        or ''
    )
    rua_entrega = contrato.cliente.endereco_logradouro or ''
    numero_entrega = contrato.cliente.endereco_numero or ''
    bairro_entrega = contrato.cliente.endereco_bairro or ''
    cep_entrega = contrato.cliente.endereco_cep or ''
    complemento_entrega = contrato.cliente.endereco_complemento or ''
    cidade_uf_entrega = (
        f'{contrato.cliente.endereco_cidade}/{contrato.cliente.endereco_uf}' or ''
    )

    saque_parcelado = contrato_cartao.saque_parcelado

    fonte_pagadora = FontePagadora.objects.get(convenios=convenio)
    razao_social = str(fonte_pagadora.razao_social) or ''
    razao_social = str(fonte_pagadora.razao_social) or ''

    razao_social_pagador = razao_social or ''
    cnpj_pagador = fonte_pagadora.CNPJ or ''
    endereco_pagador = fonte_pagadora.endereco or ''
    email_pagador = fonte_pagadora.email or ''

    razao_social_corban = contrato.corban.corban_name or ''
    cnpj_corban = contrato.corban.corban_CNPJ or ''
    endereco_corban = contrato.corban.corban_endereco or ''
    email_corban = contrato.corban.corban_email or ''
    telefone_representante = contrato.corban.telefone_representante or ''
    loja_matriz = contrato.corban.loja_matriz or ''
    codigo_corban = str(contrato.corban.id) or ''
    nome_agente_corban = contrato.created_by.name or ''
    cpf_agente_corban = contrato.created_by.identifier or ''

    # VALORES CCB QUE NÃO ESTÃO NO TERMO DE ADESÃO:
    cedula_n = str(contrato.pk) or ''
    valor_saque = str(real_br_money_mask(contrato_cartao.valor_saque)) or ''
    valor_financiado = str(real_br_money_mask(contrato_cartao.valor_financiado)) or ''
    data_contrato = contrato.criado_em or ''
    vencimento_fatura_data = data_contrato + relativedelta(months=1)
    vencimento_fatura_data = vencimento_fatura_data.replace(day=int(vencimento))

    prazo_maximo = str(vencimento_fatura_data - data_contrato) or ''
    prazo_maximo = prazo_maximo.split()[0]

    qtd_parcelas = 1
    if contrato_cartao.saque_parcelado:
        qtd_parcelas = contrato_cartao.qtd_parcela_saque_parcelado or qtd_parcelas
        prazo_maximo = str(qtd_parcelas) or ''

    vencimento_final = gerar_vencimento_final(
        primeiro_vencimento=vencimento_fatura_data,
        numero_de_parcelas=qtd_parcelas,
    )

    cet_am = '{:.2f}'.format(contrato.cet_mes) or ''
    cet_aa = '{:.2f}'.format(contrato.cet_ano) or ''

    taxa = contrato.taxa or ''
    taxa = '{:.2f}'.format(taxa) or ''

    taxa_anual = contrato.taxa_efetiva_ano or ''
    taxa_anual = '{:.2f}'.format(taxa_anual) or ''

    valor_iof_total = str(real_br_money_mask(contrato.vr_iof_total)) or ''
    if contrato.seguro:
        vr_seguro = str(real_br_money_mask(contrato.vr_seguro)) or '0.00'
    else:
        vr_seguro = '0.00'

    data_emissao_slugify = slugify(data_emissao)
    data_emissao_slugify = data_emissao_slugify.replace('-', '')
    cpf_slugify = cpf.replace('.', '').replace('-', '')

    matricula = cliente_cartao.numero_matricula or ''
    cidade = contrato.cliente.endereco_cidade or ''
    uf = contrato.cliente.endereco_uf or ''

    dados_termo = {
        'data_emissao': data_emissao,
        'termo_n': termo_n,
        'nome_titular': nome_titular,
        'nacionalidade': nacionalidade,
        'estado_civil': estado_civil,
        'rg': rg,
        'orgao_expedidor': orgao_expedidor,
        'documento_data_emissao': documento_data_emissao,
        'cpf': cpf,
        'sexo': sexo,
        'data_nascimento': data_nascimento,
        'pep': pep,
        'endereco': endereco,
        'cidade_uf': cidade_uf,
        'cidade': cidade,
        'uf': uf,
        'telefone': telefone,
        'email': email,
        'nome_mae': nome_mae,
        'limite_credito': limite_credito,
        'limite_pre_aprovado': limite_pre_aprovado,
        'margem_consignavel': margem_consignavel,
        'saque': saque,
        'compras_a_vista_e_parceladas': compras_a_vista_e_parceladas,
        'saque_complementar': saque_complementar,
        'cartao_credito': cartao_credito,
        'pagamento_contas': pagamento_contas,
        'abrangencia': abrangencia,
        'taxa_emissao': taxa_emissao,
        'vencimento': vencimento,
        'forma_pagamento': forma_pagamento,
        'seguro': seguro,
        'saque_porc': saque_porc,
        'banco': banco,
        'agencia': agencia,
        'conta': conta,
        'endereco_entrega': endereco_entrega,
        'rua_entrega': rua_entrega,
        'numero_entrega': numero_entrega,
        'bairro_entrega': bairro_entrega,
        'cidade_uf_entrega': cidade_uf_entrega,
        'cep_entrega': cep_entrega,
        'complemento_entrega': complemento_entrega,
        'remuneracao': remuneracao,
        'razao_social_pagador': razao_social_pagador,
        'cnpj_pagador': cnpj_pagador,
        'endereco_pagador': endereco_pagador,
        'email_pagador': email_pagador,
        'banco_titular': banco_titular,
        'agencia_titular': agencia_titular,
        'conta_titular': conta_titular,
        'razao_social_corban': razao_social_corban,
        'cnpj_corban': cnpj_corban,
        'endereco_corban': endereco_corban,
        'email_corban': email_corban,
        'telefone_representante': telefone_representante,
        'loja_matriz': loja_matriz,
        'nome_agente_corban': nome_agente_corban,
        'cpf_agente_corban': cpf_agente_corban,
        'codigo_corban': codigo_corban,
        'endereco_eletronico_originador': 'https://happyconsig.com.br/',
        'token_contrato': token_contrato,
        'contrato': contrato,
        'valor_saque': valor_saque,
        'taxa_efetiva_mes': taxa_efetiva_mes,
        'taxa_efetiva_ano': taxa_efetiva_ano,
        'cet_am': cet_am,
        'cet_aa': cet_aa,
        'iof_total': iof_total,
        'iof_total_porcentagem': iof_total_porcentagem,
        'qtd_parcela_saque_parcelado': qtd_parcela_saque_parcelado,
        'data_emissao_slugify': data_emissao_slugify,
        'cpf_slugify': cpf_slugify,
        'saque_parcelado': saque_parcelado,
        'matricula': matricula,
    }

    if settings.ORIGIN_CLIENT == 'PINE' and contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_CONSIGNADO,
        EnumTipoProduto.CARTAO_BENEFICIO,
    ):
        if (
            contrato_cartao.convenio.convenio_inss
            and contrato.contrato_digitacao_manual
        ):
            aceite_in100_pine_manual(
                contrato, cpf_slugify, data_emissao_slugify, token_contrato, dados_termo
            )

        for plano in contrato.contrato_planos_contratados.filter():
            if plano.plano.seguradora.nome == EnumSeguradoras.GENERALI:
                nome_arquivo = EnumArquivosSeguros.get_nome_arquivo(
                    plano.plano.tipo_termo
                )
                termo_cotratacao_seguro(
                    plano.plano.tipo_termo,
                    nome_arquivo,
                    contrato_cartao,
                    contrato,
                    plano.plano,
                )

        termo_consentimento(
            contrato, cpf_slugify, data_emissao_slugify, token_contrato, dados_termo
        )

    elif settings.ORIGIN_CLIENT == 'DIGIMAIS' and contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_CONSIGNADO,
        EnumTipoProduto.CARTAO_BENEFICIO,
    ):
        if (
            contrato_cartao.convenio.convenio_inss
            and contrato.contrato_digitacao_manual
        ):
            aceite_in100_digimais_manual(
                contrato=contrato,
                cpf_slugify=cpf_slugify,
                data_emissao_slugify=data_emissao_slugify,
                token_contrato=token_contrato,
            )

        fill_term_agreement_digimais_manual(
            contrato=contrato,
            cpf_slugify=cpf_slugify,
            data_emissao_slugify=data_emissao_slugify,
            token_contrato=token_contrato,
        )

        for plano in contrato.contrato_planos_contratados.filter():
            if plano.plano.seguradora.nome == EnumSeguradoras.SABEMI:
                sabemi_fill_terms(
                    data=dados_termo, contract=contrato, plano=plano.plano
                )

    if (
        contrato_cartao.possui_saque or contrato_cartao.saque_parcelado
    ) and contrato.seguro:
        if settings.ORIGIN_CLIENT == 'DIGIMAIS':
            term_adhesion_digimais(data=dados_termo)

            ccb_interface = CCB(cpf, contrato.id)
            ccb_interface.cria_ccb(documento='digimais', matricula=matricula)

        else:
            termo_adesao_amigoz(dados_termo)

            ccb(
                data_emissao,
                nome_titular,
                cpf,
                endereco,
                cidade_uf,
                estado_civil,
                cedula_n,
                valor_saque,
                prazo_maximo,
                vencimento_final,
                cet_am,
                cet_aa,
                taxa,
                taxa_anual,
                valor_iof_total,
                razao_social,
                token_contrato,
                contrato,
                vr_seguro,
                valor_financiado,
                banco_titular,
                agencia_titular,
                conta_titular,
                tipo_conta_titular,
                digito_titular,
                data_emissao_slugify,
                cpf_slugify,
                saque_parcelado,
                valor_total_a_pagar,
                cnpj_pagador,
                endereco_pagador,
            )

    elif contrato_cartao.possui_saque or contrato_cartao.saque_parcelado:
        if settings.ORIGIN_CLIENT == 'DIGIMAIS':
            term_adhesion_digimais(data=dados_termo)

            ccb_interface = CCB(cpf, contrato.id)
            ccb_interface.cria_ccb(documento='digimais', matricula=matricula)

        else:
            termo_adesao_amigoz(dados_termo)

            ccb(
                data_emissao,
                nome_titular,
                cpf,
                endereco,
                cidade_uf,
                estado_civil,
                cedula_n,
                valor_saque,
                prazo_maximo,
                vencimento_final,
                cet_am,
                cet_aa,
                taxa,
                taxa_anual,
                valor_iof_total,
                razao_social,
                token_contrato,
                contrato,
                vr_seguro,
                valor_financiado,
                banco_titular,
                agencia_titular,
                conta_titular,
                tipo_conta_titular,
                digito_titular,
                data_emissao_slugify,
                cpf_slugify,
                saque_parcelado,
                valor_total_a_pagar,
                cnpj_pagador,
                endereco_pagador,
            )
    elif settings.ORIGIN_CLIENT == 'DIGIMAIS':
        term_adhesion_digimais(data=dados_termo)
    else:
        termo_adesao_amigoz(dados_termo)

    regulamento_cartao(
        nome_titular,
        token_contrato,
        contrato,
        cpf,
        data_emissao_slugify,
        cpf_slugify,
    )


def termo_adesao_amigoz(dados_termo):
    contrato = dados_termo['contrato']
    if contrato.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
        termo_adesao_amigoz_cartao_beneficio(dados_termo)
    elif contrato.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
        termo_adesao_amigoz_cartao_consignado(dados_termo)
    return


def termo_adesao_amigoz_cartao_beneficio(dados):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = PdfFileReader(
                open(
                    'static/TERMO DE ADESÃO - CARTÃO BENEFÍCIO - v2 - 08.09.2023.pdf',
                    'rb',
                )
            )
            output_pdf = PdfFileWriter()

            # Itere sobre todas as páginas do arquivo de entrada e adicione-as ao objeto PdfFileWriter
            for page_num in range(input_pdf.getNumPages()):
                page = input_pdf.getPage(page_num)
                output_pdf.addPage(page)

            # Obtenha a página 0 do PDF
            page = input_pdf.getPage(0)

            # Crie um arquivo de pacote de bytes e um objeto canvas
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Defina a fonte e o tamanho da fonte
            can.setFont('Helvetica', 9)

            # Adicione o texto ao objeto canvas

            # Termo nº:
            # x = 465
            # y = 624
            # can.drawString(x, y, termo_n)

            # Nome:
            x = 80
            y = 452
            can.drawString(x, y, dados['nome_titular'])

            # Nacionalidade:
            x = 120
            y = 434
            can.drawString(x, y, dados['nacionalidade'])

            # Estado Civil:
            x = 390
            y = 434
            can.drawString(x, y, dados['estado_civil'])

            # RG:
            x = 70
            y = 415
            can.drawString(x, y, dados['rg'])

            # Orgao expedidor:
            x = 270
            y = 415
            can.drawString(x, y, dados['orgao_expedidor'])

            # CPF:
            x = 352
            y = 415
            can.drawString(x, y, dados['cpf'])

            # sexo:
            x = 80
            y = 390
            can.drawString(x, y, dados['sexo'])

            # data nascimento:
            x = 200
            y = 385
            can.drawString(x, y, dados['data_nascimento'])

            y = 385
            # PEP
            x = 332 if dados['pep'] is True or dados['pep'] == 'true' else 372
            can.drawString(x, y, 'X')
            # Endereço:
            x = 50
            y = 350
            can.drawString(x, y, dados['endereco'])

            cidade, uf = dados['cidade_uf'].split('/')

            # Cidade:
            x = 370
            y = 365
            can.drawString(x, y, cidade)

            # UF:
            x = 350
            y = 351
            can.drawString(x, y, uf)

            # Email:
            x = 360
            y = 325
            can.drawString(x, y, dados['email'])

            # Telefone:
            x = 92
            y = 325
            can.drawString(x, y, dados['telefone'])

            # limite_credito:
            x = 130
            y = 206
            limite_pre_aprovado = round(
                dados['limite_pre_aprovado'], 2
            )  # Arredonda para 2 casas decimais se for um número float
            limite_pre_aprovado = str(limite_pre_aprovado)
            can.drawString(x, y, limite_pre_aprovado)

            # margem_consignavel:
            x = 400
            y = 192
            can.drawString(x, y, dados['margem_consignavel'])

            # Funcionalidades do Cartão:
            if dados['saque'] or dados['saque_parcelado']:
                x = 46
                y = 162
                can.drawString(x, y, 'X')

            if dados['compras_a_vista_e_parceladas']:
                x = 46
                y = 148
                can.drawString(x, y, 'X')

            if dados['saque_complementar']:
                x = 46
                y = 136
                can.drawString(x, y, 'X')

            if dados['cartao_credito']:
                x = 46
                y = 123
                can.drawString(x, y, 'X')

            if dados['pagamento_contas']:
                x = 46
                y = 112
                can.drawString(x, y, 'X')

            y = 90
            # Abrangencia
            x = 130 if dados['abrangencia'] == 'Nacional' else 192
            can.drawString(x, y, 'X')
            # Taxa Emissão:
            x = 430
            y = 90
            can.drawString(x, y, dados['taxa_emissao'])

            # Vencimento:
            x = 122
            y = 72
            can.drawString(x, y, dados['vencimento'])

            # Forma pagamento:
            x = 430
            y = 72
            can.drawString(x, y, dados['forma_pagamento'])

            can.save()

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Obtenha a página 1 do PDF
            page = input_pdf.getPage(1)

            # Crie um arquivo de pacote de bytes e um objeto canvas
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Defina a fonte e o tamanho da fonte
            can.setFont('Helvetica', 9)

            y = 740
            # Adicione o texto ao objeto canvas

            # Seguro
            x = 428 if dados['seguro'] == 'true' or dados['seguro'] else 470
            can.drawString(x, y, 'X')

            # Cep Entrega
            x = 70
            y = 612
            can.drawString(x, y, dados['cep_entrega'])

            # Rua Entrega
            x = 70
            y = 599.5
            can.drawString(x, y, dados['rua_entrega'])

            # Numero Entrega
            x = 84
            y = 586
            can.drawString(x, y, dados['numero_entrega'])

            # Bairro Entrega
            x = 75
            y = 572.5
            can.drawString(x, y, dados['bairro_entrega'])

            # Cidade/uf Entrega
            x = 110
            y = 560.5
            can.drawString(x, y, dados['cidade_uf_entrega'])

            # Complemento
            x = 115
            y = 548
            can.drawString(x, y, dados['complemento_entrega'])

            # Remuneração
            x = 260
            y = 527
            can.drawString(x, y, dados['remuneracao'])

            # Razão Social pagador
            x = 112
            y = 492.5
            can.drawString(x, y, dados['razao_social_pagador'])

            # CNPJ pagador
            x = 80
            y = 479
            can.drawString(x, y, dados['cnpj_pagador'])

            # endereço pagador
            x = 100
            y = 467
            can.drawString(x, y, dados['endereco_pagador'])

            # email pagador
            x = 80
            y = 455
            can.drawString(x, y, dados['email_pagador'])

            # banco titular
            x = 80
            y = 420
            can.drawString(x, y, dados['banco_titular'])

            # agencia titular
            x = 90
            y = 408
            can.drawString(x, y, dados['agencia_titular'])

            # conta titular
            x = 80
            y = 395
            can.drawString(x, y, dados['conta_titular'])

            # Razão Social corban
            x = 112
            y = 347
            can.drawString(x, y, dados['razao_social_corban'])

            # CNPJ corban
            x = 80
            y = 333
            can.drawString(x, y, dados['cnpj_corban'])

            # endereço corban
            x = 100
            y = 320
            can.drawString(x, y, dados['endereco_corban'])

            # email corban
            x = 80
            y = 308
            can.drawString(x, y, dados['email_corban'])

            # endereço eletrocino do originador
            x = 215
            y = 270
            can.drawString(x, y, dados['endereco_eletronico_originador'])

            # Nome do agente corban
            x = 128
            y = 256.5
            can.drawString(x, y, dados['nome_agente_corban'])

            # Cpf do agente corban
            x = 122
            y = 245
            can.drawString(x, y, dados['cpf_agente_corban'])

            can.save()

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            nome_arquivo = 'termo-de-adesao'
            nome_anexo = 'TERMO DE ADESÃO'

            salva_termo_s3(
                temp_dir,
                output_pdf,
                dados['token_contrato'],
                dados['cpf_slugify'],
                dados['data_emissao_slugify'],
                dados['contrato'],
                nome_arquivo,
                nome_anexo,
            )
    except Exception as e:
        print(e)
        print(
            'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo termo de adesão'
        )


def termo_adesao_amigoz_cartao_consignado(dados):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = PdfFileReader(
                open(
                    'static/TERMO DE ADESÃO - CARTÃO CONSIGNADO - v2 - 08.09.2023.pdf',
                    'rb',
                )
            )
            output_pdf = PdfFileWriter()

            # Itere sobre todas as páginas do arquivo de entrada e adicione-as ao objeto PdfFileWriter
            for page_num in range(input_pdf.getNumPages()):
                page = input_pdf.getPage(page_num)
                output_pdf.addPage(page)

            # Obtenha a página 0 do PDF
            page = input_pdf.getPage(0)

            # Crie um arquivo de pacote de bytes e um objeto canvas
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Defina a fonte e o tamanho da fonte
            can.setFont('Helvetica', 9)

            # Adicione o texto ao objeto canvas

            # Termo nº:
            # x = 465
            # y = 624
            # can.drawString(x, y, termo_n)

            # Nome:
            x = 80
            y = 452
            can.drawString(x, y, dados['nome_titular'])

            # Nacionalidade:
            x = 120
            y = 434
            can.drawString(x, y, dados['nacionalidade'])

            # Estado Civil:
            x = 390
            y = 434
            can.drawString(x, y, dados['estado_civil'])

            # RG:
            x = 70
            y = 415
            can.drawString(x, y, dados['rg'])

            # Orgao expedidor:
            x = 270
            y = 415
            can.drawString(x, y, dados['orgao_expedidor'])

            # CPF:
            x = 352
            y = 415
            can.drawString(x, y, dados['cpf'])

            # sexo:
            x = 80
            y = 390
            can.drawString(x, y, dados['sexo'])

            # data nascimento:
            x = 200
            y = 385
            can.drawString(x, y, dados['data_nascimento'])

            y = 385
            # PEP
            x = 332 if dados['pep'] is True or dados['pep'] == 'true' else 372
            can.drawString(x, y, 'X')
            # Endereço:
            x = 50
            y = 350
            can.drawString(x, y, dados['endereco'])

            cidade, uf = dados['cidade_uf'].split('/')

            # Cidade:
            x = 370
            y = 365
            can.drawString(x, y, cidade)

            # UF:
            x = 350
            y = 351
            can.drawString(x, y, uf)

            # Email:
            x = 360
            y = 325
            can.drawString(x, y, dados['email'])

            # Telefone:
            x = 92
            y = 325
            can.drawString(x, y, dados['telefone'])

            # limite_credito:
            x = 130
            y = 206
            limite_pre_aprovado = round(
                dados['limite_pre_aprovado']
                if bool(dados['limite_pre_aprovado'])
                else 0.0,
                2,
            )
            limite_pre_aprovado = str(limite_pre_aprovado)
            can.drawString(x, y, limite_pre_aprovado)

            # margem_consignavel:
            x = 400
            y = 192
            can.drawString(x, y, dados['margem_consignavel'])

            # Funcionalidades do Cartão:
            if dados['saque'] or dados['saque_parcelado']:
                x = 46
                y = 162
                can.drawString(x, y, 'X')

            if dados['compras_a_vista_e_parceladas']:
                x = 46
                y = 148
                can.drawString(x, y, 'X')

            if dados['saque_complementar']:
                x = 46
                y = 136
                can.drawString(x, y, 'X')

            # if dados['cartao_credito']: produto cartão consignado não assinala beneficio
            #     x = 46
            #     y = 123
            #     can.drawString(x, y, 'X')

            if dados['pagamento_contas']:
                x = 46
                y = 112
                can.drawString(x, y, 'X')

            y = 90
            # Abrangencia
            x = 130 if dados['abrangencia'] == 'Nacional' else 194
            can.drawString(x, y, 'X')
            # Taxa Emissão:
            x = 430
            y = 90
            can.drawString(x, y, dados['taxa_emissao'])

            # Vencimento:
            x = 122
            y = 72
            can.drawString(x, y, dados['vencimento'])

            # Forma pagamento:
            x = 430
            y = 72
            can.drawString(x, y, dados['forma_pagamento'])

            can.save()

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Obtenha a página 1 do PDF
            page = input_pdf.getPage(1)

            # Crie um arquivo de pacote de bytes e um objeto canvas
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Defina a fonte e o tamanho da fonte
            can.setFont('Helvetica', 9)

            y = 740
            # Adicione o texto ao objeto canvas

            # Seguro
            x = 428 if dados['seguro'] == 'true' or dados['seguro'] else 470
            can.drawString(x, y, 'X')

            # Cep Entrega
            x = 70
            y = 612
            can.drawString(x, y, dados['cep_entrega'])

            # Rua Entrega
            x = 70
            y = 600
            can.drawString(x, y, dados['rua_entrega'])

            # Numero Entrega
            x = 82
            y = 586
            can.drawString(x, y, dados['numero_entrega'])

            # Bairro Entrega
            x = 73
            y = 572
            can.drawString(x, y, dados['bairro_entrega'])

            # Cidade/uf Entrega
            x = 110
            y = 560
            can.drawString(x, y, dados['cidade_uf_entrega'])

            # Complemento
            x = 115
            y = 548
            can.drawString(x, y, dados['complemento_entrega'])

            # Remuneração
            x = 260
            y = 533
            can.drawString(x, y, dados['remuneracao'])

            # Razão Social pagador
            x = 112
            y = 502.5
            can.drawString(x, y, dados['razao_social_pagador'])

            # CNPJ pagador
            x = 80
            y = 489
            can.drawString(x, y, dados['cnpj_pagador'])

            # endereço pagador
            x = 100
            y = 477
            can.drawString(x, y, dados['endereco_pagador'])

            # email pagador
            x = 80
            y = 465
            can.drawString(x, y, dados['email_pagador'])

            # banco titular
            x = 80
            y = 437
            can.drawString(x, y, dados['banco_titular'])

            # agencia titular
            x = 90
            y = 425
            can.drawString(x, y, dados['agencia_titular'])

            # conta titular
            x = 80
            y = 412
            can.drawString(x, y, dados['conta_titular'])

            # Razão Social corban
            x = 112
            y = 364
            can.drawString(x, y, dados['razao_social_corban'])

            # CNPJ corban
            x = 80
            y = 351
            can.drawString(x, y, dados['cnpj_corban'])

            # endereço corban
            x = 100
            y = 338
            can.drawString(x, y, dados['endereco_corban'])

            # email corban
            x = 80
            y = 326
            can.drawString(x, y, dados['email_corban'])

            # endereço eletrocino do originador
            x = 215
            y = 288
            can.drawString(x, y, dados['endereco_eletronico_originador'])

            # Nome do agente corban
            x = 128
            y = 276
            can.drawString(x, y, dados['nome_agente_corban'])

            # Cpf do agente corban
            x = 122
            y = 263
            can.drawString(x, y, dados['cpf_agente_corban'])

            can.save()

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            nome_arquivo = 'termo-de-adesao'
            nome_anexo = 'TERMO DE ADESÃO'

            salva_termo_s3(
                temp_dir,
                output_pdf,
                dados['token_contrato'],
                dados['cpf_slugify'],
                dados['data_emissao_slugify'],
                dados['contrato'],
                nome_arquivo,
                nome_anexo,
            )
    except Exception as e:
        logger.error(
            f'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo termo de adesão: {e}'
        )
        print(
            'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo termo de adesão'
        )


def ccb(
    data_emissao,
    nome_titular,
    cpf,
    endereco,
    cidade_uf,
    estado_civil,
    cedula_n,
    valor_saque,
    prazo_maximo,
    vencimento_final,
    cet_am,
    cet_aa,
    taxa,
    taxa_anual,
    valor_iof_total,
    razao_social,
    token_contrato,
    contrato,
    vr_seguro,
    valor_financiado,
    banco_titular,
    agencia_titular,
    conta_titular,
    tipo_conta_titular,
    digito_titular,
    data_emissao_slugify,
    cpf_slugify,
    saque_parcelado,
    valor_total_a_pagar,
    cnpj_pagador,
    endereco_pagador,
):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = PdfFileReader(
                open('static/CCB - CARTÃO CONSIGNADO DE BENEFÍCIO - v3.pdf', 'rb')
            )
            output_pdf = PdfFileWriter()

            # Itere sobre todas as páginas do arquivo de entrada e adicione-as ao objeto PdfFileWriter
            for page_num in range(input_pdf.getNumPages()):
                page = input_pdf.getPage(page_num)
                output_pdf.addPage(page)

            # Obtenha a página 0 do PDF
            page = input_pdf.getPage(0)

            # Crie um arquivo de pacote de bytes e um objeto canvas
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Defina a fonte e o tamanho da fonte
            can.setFont('Helvetica', 9)

            # Adicione o texto ao objeto canvas
            # Data emissão:
            x = 335
            y = 714.3
            can.drawString(x, y, data_emissao)

            # Cedula:
            x = 464
            y = 714.3
            can.drawString(x, y, cedula_n)

            # nome titular:
            x = 83
            y = 645
            can.drawString(x, y, nome_titular)

            # cpf titular:
            x = 77
            y = 634.8
            can.drawString(x, y, cpf)

            # endereço titular:
            x = 97
            y = 624.2
            can.drawString(x, y, endereco)

            # cidade/uf titular:
            x = 106
            y = 614.5
            can.drawString(x, y, cidade_uf)

            # estado civil titular:
            x = 107
            y = 604
            can.drawString(x, y, estado_civil)

            # conta titular:
            x = 133
            y = 594
            can.drawString(x, y, conta_titular)

            # valor liberado:
            x = 148
            y = 504.5
            can.drawString(x, y, valor_saque)

            if saque_parcelado:
                # valor total financiado:
                x = 438
                y = 504.5
                can.drawString(x, y, valor_financiado)

                # valor total a pagar:
                x = 166
                y = 467
                can.drawString(x, y, valor_total_a_pagar)

                # Prazo maximo:
                x = 136
                y = 479
                can.drawString(x, y, prazo_maximo)

                # 7.3. Somatório das parcelas que compõe a operação:
                x = 284
                y = 381.5
                can.drawString(x, y, valor_total_a_pagar)
            else:
                # valor total a pagar:
                x = 166
                y = 467
                can.drawString(x, y, valor_financiado)

                x = 438
                y = 504.5
                can.drawString(x, y, valor_saque)

                # Prazo maximo:
                x = 136
                y = 479
                can.drawString(x, y, '1')

                # 7.3. Somatório das parcelas que compõe a operação:
                x = 284
                y = 381.5
                can.drawString(x, y, valor_financiado)

            # IOF:
            x = 355
            y = 492
            can.drawString(x, y, valor_iof_total)
            # vencimento final:
            x = 401
            y = 479
            can.drawString(x, y, vencimento_final)

            # cet_aa:
            x = 277.5
            y = 392
            # CET
            if cet_am is not None and cet_aa is not None:
                can.drawString(x, y, cet_aa)

                # cet_am:
                x = 248.5
                y = 392
                can.drawString(x, y, cet_am)
            else:
                can.drawString(x, y, ' % ao ano')

                # cet_am:
                x = 258.5
                y = 392
                can.drawString(x, y, ' % ao mês')

            # taxa mensal:
            x = 195
            y = 492
            can.drawString(x, y, taxa)

            # taxa anual:
            x = 236
            y = 492
            can.drawString(x, y, taxa_anual)

            # Tarifa de cadastros:
            x = 175
            y = 422.5
            can.drawString(x, y, '0,00')

            # Tarifa de Saque:
            x = 165
            y = 412.5
            can.drawString(x, y, '0,00')

            # Forma de liberacao:
            x = 160
            y = 281
            can.drawString(x, y, 'TED')

            # tipo de conta:
            x = 125
            y = 260
            can.drawString(x, y, tipo_conta_titular)

            # agencia:
            x = 105
            y = 250
            can.drawString(x, y, agencia_titular)

            # banco:
            x = 94
            y = 240
            can.drawString(x, y, banco_titular)

            # conta:
            x = 112
            y = 230
            can.drawString(x, y, conta_titular)

            # conta:
            x = 155
            y = 230
            can.drawString(x, y, f'/{digito_titular}')

            # Valor do seguro:
            x = 135
            y = 402
            can.drawString(x, y, vr_seguro)

            # IOF:
            x = 115.5
            y = 433
            can.drawString(x, y, valor_iof_total)

            # # VENCIMENTOS:
            # x = 55
            # y = 192.5
            # can.drawString(x, y, vencimento_final)
            #
            # # VALORES:
            # x = 160
            # y = 192.5
            # can.drawString(x, y, valor_financiado)

            # FONTE PAGADORA:
            x = 86
            y = 196
            can.drawString(x, y, razao_social)

            # CNPJ:
            x = 88
            y = 207
            can.drawString(x, y, cnpj_pagador)

            # Endereço:
            x = 102
            y = 185.5
            can.drawString(x, y, endereco_pagador)

            can.save()

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Salve o arquivo de saída
            with open(f'{temp_dir}/termos-ccb.pdf', 'wb') as outputStream:
                output_pdf.write(outputStream)

            # abre o arquivo PDF que foi salvo anteriormente
            with open(f'{temp_dir}/termos-ccb.pdf', 'rb') as f:
                # lê os dados do arquivo em um objeto BytesIO
                file_stream = io.BytesIO(f.read())

            # Conecta ao S3
            s3 = boto3.resource('s3')
            bucket = s3.Bucket(settings.BUCKET_NAME_TERMOS)
            bucket_name = settings.BUCKET_NAME_TERMOS
            nome_pasta = str(token_contrato)

            if contrato.tipo_produto in (
                EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                EnumTipoProduto.CARTAO_BENEFICIO,
                EnumTipoProduto.CARTAO_CONSIGNADO,
            ):
                if saque_parcelado:
                    # Salva o arquivo no S3
                    bucket.upload_fileobj(
                        file_stream,
                        f'{nome_pasta}/termos-ccb-saque-parcelado-{cpf_slugify}-{data_emissao_slugify}.pdf',
                        ExtraArgs={'ContentType': 'application/pdf'},
                    )

                    object_key = f'{nome_pasta}/termos-ccb-saque-parcelado-{cpf_slugify}-{data_emissao_slugify}.pdf'
                    # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

                    url = s3_cliente.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': object_key},
                        ExpiresIn=31536000,
                    )

                    AnexoContrato.objects.create(
                        contrato=contrato,
                        tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                        nome_anexo=f'TERMOS CCB SAQUE PARCELADO-{cpf_slugify}-{data_emissao_slugify}',
                        anexo_extensao='pdf',
                        anexo_url=url,
                    )
                else:
                    # Salva o arquivo no S3
                    bucket.upload_fileobj(
                        file_stream,
                        f'{nome_pasta}/termos-ccb-{cpf_slugify}-{data_emissao_slugify}.pdf',
                        ExtraArgs={'ContentType': 'application/pdf'},
                    )

                    object_key = f'{nome_pasta}/termos-ccb-{cpf_slugify}-{data_emissao_slugify}.pdf'
                    # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

                    url = s3_cliente.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': object_key},
                        ExpiresIn=31536000,
                    )

                    AnexoContrato.objects.create(
                        contrato=contrato,
                        tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                        nome_anexo=f'TERMOS CCB-{cpf_slugify}-{data_emissao_slugify}',
                        anexo_extensao='pdf',
                        anexo_url=url,
                    )

            elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
                if saque_parcelado:
                    # Salva o arquivo no S3
                    bucket.upload_fileobj(
                        file_stream,
                        f'{nome_pasta}/termos-ccb-saque-parcelado-{cpf_slugify}-{data_emissao_slugify}.pdf',
                        ExtraArgs={'ContentType': 'application/pdf'},
                    )

                    object_key = f'{nome_pasta}/termos-ccb-saque-parcelado-{cpf_slugify}-{data_emissao_slugify}.pdf'
                    # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

                    url = s3_cliente.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': object_key},
                        ExpiresIn=31536000,
                    )

                    AnexoContrato.objects.create(
                        contrato=contrato,
                        tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                        nome_anexo=f'TERMOS CCB SAQUE PARCELADO-{cpf_slugify}-{data_emissao_slugify}',
                        anexo_extensao='pdf',
                        anexo_url=url,
                    )
                else:
                    # Salva o arquivo no S3
                    bucket.upload_fileobj(
                        file_stream,
                        f'{nome_pasta}/termos-ccb-saque-complementar-{cpf_slugify}-{data_emissao_slugify}.pdf',
                        ExtraArgs={'ContentType': 'application/pdf'},
                    )

                    object_key = f'{nome_pasta}/termos-ccb-saque-complementar-{cpf_slugify}-{data_emissao_slugify}.pdf'
                    # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

                    url = s3_cliente.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': object_key},
                        ExpiresIn=31536000,
                    )

                    AnexoContrato.objects.create(
                        contrato=contrato,
                        tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                        nome_anexo=f'TERMOS CCB SAQUE COMPLEMENTAR-{cpf_slugify}-{data_emissao_slugify}',
                        anexo_extensao='pdf',
                        anexo_url=url,
                    )
    except Exception as e:
        print(e)
        print('Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo ccb')


def regulamento_cartao(
    nome_titular, token_contrato, contrato, cpf, data_emissao_slugify, cpf_slugify
):
    file_path = 'static/REGULAMENTO_-_CARTÃO_CONSIGNADO_DE_BENEFICIO_-_AMIGOZ__-_PF_-_V5_20230127_versao_TI.pdf'

    if settings.ORIGIN_CLIENT == 'DIGIMAIS':
        file_path = 'static/digimais/regulamento-cartao-beneficio-consignado-v1.pdf'

    elif settings.ORIGIN_CLIENT == 'PINE':
        file_path = (
            'static/pine/REGULAMENTO_CARTÃO_CONSIGNADO_DE_BENEFICIO_AMIGOZ_v2.pdf'
        )

    try:
        # comtypes.CoInitialize()
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = PdfFileReader(open(file_path, 'rb'))
            output_pdf = PdfFileWriter()

            # Itere sobre todas as páginas do arquivo de entrada e adicione-as ao objeto PdfFileWriter
            for page_num in range(input_pdf.getNumPages()):
                page = input_pdf.getPage(page_num)
                output_pdf.addPage(page)

            # Salve o arquivo de saída
            with open(f'{temp_dir}/regulamento-cartao.pdf', 'wb') as outputStream:
                output_pdf.write(outputStream)

            # abre o arquivo PDF que foi salvo anteriormente
            with open(f'{temp_dir}/regulamento-cartao.pdf', 'rb') as f:
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
                f'{nome_pasta}/regulamento-cartao-{cpf_slugify}-{data_emissao_slugify}.pdf',
                ExtraArgs={'ContentType': 'application/pdf'},
            )

            object_key = f'{nome_pasta}/regulamento-cartao-{cpf_slugify}-{data_emissao_slugify}.pdf'
            # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

            url = s3_cliente.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=31536000,
            )

            AnexoContrato.objects.create(
                contrato=contrato,
                tipo_anexo=EnumTipoAnexo.TERMOS_E_ASSINATURAS,
                nome_anexo=f'REGULAMENTO CARTÃO-{cpf_slugify}-{data_emissao_slugify}',
                anexo_extensao='pdf',
                anexo_url=url,
            )
            # doc.save(f"core/media/regulamento-cartao/TERMO_regulamento-{nome_titular}.docx")
        # comtypes.CoUninitialize()
    except Exception as e:
        print(e)
        print(
            'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo regulamento cartão'
        )


def aceite_in100_pine_manual(
    contrato, cpf_slugify, data_emissao_slugify, token_contrato, dados
):
    id_cliente = contrato.cliente_id
    produto = contrato.tipo_produto

    with tempfile.TemporaryDirectory() as temp_dir:
        if produto == EnumTipoProduto.CARTAO_BENEFICIO:
            input_pdf = PdfFileReader(
                open(
                    'static/TERMO DE AUTORIZAÇÃO INSS - CARTÃO BENEFÍCIO - v3.pdf',
                    'rb',
                )
            )
        elif produto == EnumTipoProduto.CARTAO_CONSIGNADO:
            input_pdf = PdfFileReader(
                open(
                    'static/TERMO DE AUTORIZAÇÃO INSS - CARTÃO CONSIGNADO - v3.pdf',
                    'rb',
                )
            )

        output_pdf = PdfFileWriter()
        cliente = Cliente.objects.get(id=id_cliente)
        num_pages = input_pdf.getNumPages()

        # Definir as "novas páginas" como nulas inicialmente
        new_page_first = None
        new_page_last = None

        for page_num in range(num_pages):
            page = input_pdf.getPage(page_num)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont('Helvetica', 9)

            # Defina as coordenadas x e y dependendo do número da página
            if page_num == 0:
                # NOME
                x = 80
                y = 568
                can.drawString(x, y, cliente.nome_cliente)

                # CPF
                x = 420
                y = 568
                can.drawString(x, y, cliente.nu_cpf)

                # Numero do contrato
                x = 495
                y = 598
                can.drawString(x, y, dados['termo_n'])

            can.save()
            # Obtenha a página com o hash como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Determine qual "nova página" deve ser atualizada
            if page_num == 0:
                new_page_first = new_page
            elif page_num == num_pages - 1:  # Se for a última página
                new_page_last = new_page

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Adicione a página ao PDF de saída
            output_pdf.addPage(page)

        # Mesclando a página original com a página atualizada para a primeira e última página
        if new_page_first is not None:
            output_pdf.getPage(0).mergePage(new_page_first)
        if new_page_last is not None:
            output_pdf.getPage(num_pages - 1).mergePage(new_page_last)

        nome_arquivo = 'termo-de-autorizacao-inss'
        nome_anexo = 'TERMO DE AUTORIZAÇÃO INSS'

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            nome_arquivo,
            nome_anexo,
        )


def termo_consentimento(
    contrato, cpf_slugify, data_emissao_slugify, token_contrato, dados_termo
):
    produto = contrato.tipo_produto

    with tempfile.TemporaryDirectory() as temp_dir:
        if produto == EnumTipoProduto.CARTAO_BENEFICIO:
            input_pdf = PdfFileReader(
                open(
                    'static/TCE - Cartão Benefício - v1 - 30.08.2023.pdf',
                    'rb',
                )
            )
        elif produto == EnumTipoProduto.CARTAO_CONSIGNADO:
            input_pdf = PdfFileReader(
                open(
                    'static/TCE - Cartão Consignado - v1 - 30.08.2023.pdf',
                    'rb',
                )
            )

        output_pdf = PdfFileWriter()
        num_pages = input_pdf.getNumPages()

        # Definir as "novas páginas" como nulas inicialmente
        new_page_first = None
        new_page_last = None

        for page_num in range(num_pages):
            page = input_pdf.getPage(page_num)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont('Helvetica', 9)

            if produto == EnumTipoProduto.CARTAO_BENEFICIO:
                # Defina as coordenadas x e y dependendo do número da página
                if page_num == 0:
                    # NOME
                    x = 90
                    y = 485
                    can.drawString(x, y, dados_termo['nome_titular'])

                    # CPF
                    x = 80
                    y = 469.5
                    can.drawString(x, y, dados_termo['cpf'])

                    # Endereço

                    x = 110
                    y = 453.5
                    can.drawString(x, y, dados_termo['endereco'])

                    # Cidade

                    x = 95
                    y = 437.5
                    can.drawString(x, y, dados_termo['cidade'])

                    # Uf

                    x = 70
                    y = 421.5
                    can.drawString(x, y, dados_termo['uf'])

                    # Nº Matricula/Benefício

                    x = 180
                    y = 406
                    can.drawString(x, y, dados_termo['matricula'])

                    # X Cartão benefício
                    x = 308
                    y = 390
                    can.drawString(x, y, 'X')

                    # # Número do Cartão
                    #
                    # x = 155
                    # y = 374
                    # can.drawString(x, y, 'adicionar aqui o numero do cartao')

            elif produto == EnumTipoProduto.CARTAO_CONSIGNADO:
                # Defina as coordenadas x e y dependendo do número da página
                if page_num == 0:
                    # NOME
                    x = 90
                    y = 490
                    can.drawString(x, y, dados_termo['nome_titular'])

                    # CPF
                    x = 80
                    y = 474.5
                    can.drawString(x, y, dados_termo['cpf'])

                    # Endereço

                    x = 110
                    y = 458.5
                    can.drawString(x, y, dados_termo['endereco'])

                    # Cidade

                    x = 95
                    y = 442.5
                    can.drawString(x, y, dados_termo['cidade'])

                    # Uf

                    x = 70
                    y = 426.5
                    can.drawString(x, y, dados_termo['uf'])

                    # Nº Matricula/Benefício

                    x = 180
                    y = 411
                    can.drawString(x, y, dados_termo['matricula'])

                    # X Cartão consignado
                    x = 100
                    y = 395
                    can.drawString(x, y, 'X')

                    # # Número do Cartão
                    #
                    # x = 155
                    # y = 379
                    # can.drawString(x, y, 'adicionar aqui o numero do cartao')

            can.save()
            # Obtenha a página com o hash como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Determine qual "nova página" deve ser atualizada
            if page_num == 0:
                new_page_first = new_page
            elif page_num == num_pages - 1:  # Se for a última página
                new_page_last = new_page

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Adicione a página ao PDF de saída
            output_pdf.addPage(page)

        # Mesclando a página original com a página atualizada para a primeira e última página
        if new_page_first is not None:
            output_pdf.getPage(0).mergePage(new_page_first)
        if new_page_last is not None:
            output_pdf.getPage(num_pages - 1).mergePage(new_page_last)

        nome_arquivo = 'termo-de-consentimento'
        nome_anexo = 'TERMO DE CONSENTIMENTO'

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            nome_arquivo,
            nome_anexo,
        )


# Digimais
def aceite_in100_digimais_manual(
    contrato, cpf_slugify, data_emissao_slugify, token_contrato
):
    pdf_path = 'static/digimais/termo-de-autorizacao-do-beneficiario-inss-v2.pdf'

    id_cliente = contrato.cliente_id

    def fill_accept_digimais_first_section(canvas_pdf, customer):
        name_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Eu, ', word_order=0
        )
        cpf_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='sob o n.º', word_order=0
        )

        if name_coord and customer.nome_cliente:
            canvas_pdf.drawString(
                name_coord.get('same_line_x'),
                name_coord.get('same_line_y'),
                customer.nome_cliente,
            )

        if cpf_coord and customer.nu_cpf:
            canvas_pdf.drawString(
                cpf_coord.get('same_line_x'),
                cpf_coord.get('same_line_y'),
                customer.nu_cpf,
            )

    def fill_accept_digimais_second_section(canvas_pdf, customer):
        name_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='1. Nome Completo:', word_order=0
        )
        cpf_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='2. CPF N.º:', word_order=0
        )
        birthdate_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='3. Data de Nascimento:', word_order=0
        )

        if name_coord and customer.nome_cliente:
            canvas_pdf.drawString(
                name_coord.get('next_line_x'),
                name_coord.get('next_line_y'),
                customer.nome_cliente,
            )

        if cpf_coord and customer.nu_cpf:
            canvas_pdf.drawString(
                cpf_coord.get('next_line_x'),
                cpf_coord.get('next_line_y'),
                customer.nu_cpf,
            )

        if birthdate_coord and customer.dt_nascimento:
            canvas_pdf.drawString(
                birthdate_coord.get('next_line_x'),
                birthdate_coord.get('next_line_y'),
                customer.dt_nascimento.strftime('%d/%m/%Y'),
            )

    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(open(pdf_path, 'rb'))
        output_pdf = PdfFileWriter()

        cliente = Cliente.objects.get(id=id_cliente)

        num_pages = input_pdf.getNumPages()

        # Definir as "novas páginas" como nulas inicialmente
        new_page_first = None
        new_page_last = None

        for page_num in range(num_pages):
            page = input_pdf.getPage(page_num)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont('Helvetica', 9)

            # Defina as coordenadas x e y dependendo do número da página
            if page_num == 0:
                fill_accept_digimais_first_section(canvas_pdf=can, customer=cliente)
                fill_accept_digimais_second_section(canvas_pdf=can, customer=cliente)

            can.save()
            # Obtenha a página com o hash como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Determine qual "nova página" deve ser atualizada
            if page_num == 0:
                new_page_first = new_page
            elif page_num == num_pages - 1:  # Se for a última página
                new_page_last = new_page

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Adicione a página ao PDF de saída
            output_pdf.addPage(page)

        # Mesclando a página original com a página atualizada para a primeira e última página
        if new_page_first is not None:
            output_pdf.getPage(0).mergePage(new_page_first)
        if new_page_last is not None:
            output_pdf.getPage(num_pages - 1).mergePage(new_page_last)

        nome_arquivo = 'termo-de-autorizacao-inss'
        nome_anexo = 'TERMO DE AUTORIZAÇÃO INSS'

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            nome_arquivo,
            nome_anexo,
        )


def fill_term_agreement_digimais_manual(
    contrato, cpf_slugify, data_emissao_slugify, token_contrato
):
    id_cliente = contrato.cliente_id

    pdf_path = (
        'static/digimais/termo-de-consentimento-cartao-consignado-de-beneficio-v2.pdf'
    )

    def fill_term_agreement_digimais_first_section(canvas_pdf, customer):
        name_coord = word_coordinates_in_pdf(
            pdf_path=pdf_path, word='Eu,', word_order=0
        )
        cpf_coord = word_coordinates_in_pdf(pdf_path=pdf_path, word='n.º', word_order=0)

        if name_coord and customer.nome_cliente:
            canvas_pdf.drawString(
                name_coord.get('same_line_x'),
                name_coord.get('same_line_y'),
                customer.nome_cliente,
            )

        if cpf_coord and customer.nu_cpf:
            canvas_pdf.drawString(
                cpf_coord.get('same_line_x'),
                cpf_coord.get('same_line_y'),
                customer.nu_cpf,
            )

    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(open(pdf_path, 'rb'))
        output_pdf = PdfFileWriter()

        cliente = Cliente.objects.get(id=id_cliente)

        num_pages = input_pdf.getNumPages()

        # Definir as "novas páginas" como nulas inicialmente
        new_page_first = None
        new_page_last = None

        for page_num in range(num_pages):
            page = input_pdf.getPage(page_num)
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFont('Helvetica', 9)

            # Defina as coordenadas x e y dependendo do número da página
            if page_num == 0:
                fill_term_agreement_digimais_first_section(
                    canvas_pdf=can, customer=cliente
                )

            can.save()
            # Obtenha a página com o hash como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Determine qual "nova página" deve ser atualizada
            if page_num == 0:
                new_page_first = new_page
            elif page_num == num_pages - 1:  # Se for a última página
                new_page_last = new_page

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            # Adicione a página ao PDF de saída
            output_pdf.addPage(page)

        # Mesclando a página original com a página atualizada para a primeira e última página
        if new_page_first is not None:
            output_pdf.getPage(0).mergePage(new_page_first)
        if new_page_last is not None:
            output_pdf.getPage(num_pages - 1).mergePage(new_page_last)

        nome_arquivo = 'termo-de-consentimento'
        nome_anexo = 'TERMO DE CONSENTIMENTO'

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            nome_arquivo,
            nome_anexo,
        )


def term_adhesion_digimais(data):
    """
    Fills the adhesion term for Digimais manually.

    Args:
        data (dict): Dictionary with all data necessary to fill the adhesion term.

    Returns:
        None
    """

    pdf_path = 'static/digimais/termo-de-adesao-cartao-de-credito-v1.pdf'

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = PdfFileReader(open(pdf_path, 'rb'))
            output_pdf = PdfFileWriter()

            # Itere sobre todas as páginas do arquivo de entrada e adicione-as ao objeto PdfFileWriter
            for page_num in range(input_pdf.getNumPages()):
                page = input_pdf.getPage(page_num)
                output_pdf.addPage(page)

            # Obtenha a página 0 do PDF
            page = input_pdf.getPage(0)

            # Crie um arquivo de pacote de bytes e um objeto canvas
            packet = io.BytesIO()
            canvas_pdf = canvas.Canvas(packet, pagesize=letter)

            # Defina a fonte e o tamanho da fonte
            canvas_pdf.setFont('Helvetica', 9)

            if name_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Nome do Cliente:',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    name_coord.get('next_line_x'),
                    name_coord.get('next_line_y'),
                    data.get('nome_titular'),
                )

            if gender_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Sexo', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    gender_coord.get('next_line_x'),
                    gender_coord.get('next_line_y'),
                    data.get('sexo'),
                )

            if cpf_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='CPF', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    cpf_coord.get('next_line_x'),
                    cpf_coord.get('next_line_y'),
                    data.get('cpf'),
                )

            if rg_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='N. º Documento de Identidade',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    rg_coord.get('next_line_x'),
                    rg_coord.get('next_line_y'),
                    data.get('rg'),
                )

            if rg_issuing_body_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Órgão Expedidor',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    rg_issuing_body_coord.get('next_line_x'),
                    rg_issuing_body_coord.get('next_line_y'),
                    data.get('orgao_expedidor'),
                )

            if rg_date_issuing_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Data Expedição',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    rg_date_issuing_coord.get('next_line_x'),
                    rg_date_issuing_coord.get('next_line_y'),
                    data.get('documento_data_emissao'),
                )

            if marital_status_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Estado Civil', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    marital_status_coord.get('next_line_x'),
                    marital_status_coord.get('next_line_y'),
                    data.get('estado_civil'),
                )

            if birthdate_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Data de Nascimento',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    birthdate_coord.get('next_line_x'),
                    birthdate_coord.get('next_line_y'),
                    data.get('data_nascimento'),
                )

            if cellphone_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Telefone (residencial/celular)',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    cellphone_coord.get('next_line_x'),
                    cellphone_coord.get('next_line_y'),
                    data.get('telefone'),
                )

            if email_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='E-mail', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    email_coord.get('next_line_x'),
                    email_coord.get('next_line_y'),
                    data.get('email'),
                )

            if address_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Endereço Residencial',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    address_coord.get('next_line_x'),
                    address_coord.get('next_line_y'),
                    data.get('endereco'),
                )

            if income_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Renda Mensal', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    income_coord.get('next_line_x'),
                    income_coord.get('next_line_y'),
                    data.get('remuneracao'),
                )

            if mother_name_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Nome da Mãe', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    mother_name_coord.get('next_line_x'),
                    mother_name_coord.get('next_line_y'),
                    data.get('nome_mae'),
                )

            pep_word_to_search = (
                'SIM' if data.get('pep') is True or data.get('pep') == 'true' else 'NÃO'
            )
            if pep_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word=pep_word_to_search,
                word_order=0,
                fix_x=5,
            ):
                canvas_pdf.drawString(
                    pep_coord.get('same_line_before_x'),
                    pep_coord.get('same_line_before_y'),
                    'X',
                )

            if employer_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Empregador', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    employer_coord.get('next_line_x'),
                    employer_coord.get('next_line_y'),
                    data.get('razao_social_pagador'),
                )

            if consigned_value_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Valor Consignado',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    consigned_value_coord.get('next_line_x'),
                    consigned_value_coord.get('next_line_y'),
                    data.get('margem_consignavel'),
                )

            if due_date_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Vencimento', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    due_date_coord.get('next_line_x'),
                    due_date_coord.get('next_line_y'),
                    data.get('vencimento'),
                )

            if payment_method_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Forma de Pagamento',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    payment_method_coord.get('next_line_x'),
                    payment_method_coord.get('next_line_y'),
                    data.get('forma_pagamento'),
                )

            bank = data.get('banco_titular')
            bank_number, bank_name = bank.split('-') if '-' in bank else (bank, None)

            if bank_name_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Banco', word_order=2, fix_x=-15
            ):
                canvas_pdf.drawString(
                    bank_name_coord.get('next_line_x'),
                    bank_name_coord.get('next_line_y'),
                    bank_name,
                )

            if bank_number_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='N.º do Banco', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    bank_number_coord.get('next_line_x'),
                    bank_number_coord.get('next_line_y'),
                    bank_number,
                )

            if bank_branch_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Agência', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    bank_branch_coord.get('next_line_x'),
                    bank_branch_coord.get('next_line_y'),
                    data.get('agencia_titular'),
                )

            if bank_account_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Dados da Conta Corrente',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    bank_account_coord.get('next_line_x'),
                    bank_account_coord.get('next_line_y'),
                    data.get('conta_titular'),
                )

            if availability_form_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='E-mail', word_order=1
            ):
                canvas_pdf.drawString(
                    availability_form_coord.get('same_line_before_x'),
                    availability_form_coord.get('same_line_before_y'),
                    'X',
                )

            if corban_company_name_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Empresa', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    corban_company_name_coord.get('next_line_x'),
                    corban_company_name_coord.get('next_line_y'),
                    data.get('razao_social_corban'),
                )

            if corban_company_cnpj_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='CNPJ', word_order=0, fix_x=-15
            ):
                canvas_pdf.drawString(
                    corban_company_cnpj_coord.get('next_line_x'),
                    corban_company_cnpj_coord.get('next_line_y'),
                    data.get('cnpj_corban'),
                )

            if corban_company_code_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='Código da Loja',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    corban_company_code_coord.get('next_line_x'),
                    corban_company_code_coord.get('next_line_y'),
                    data.get('codigo_corban'),
                )

            if corban_address_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Endereço', word_order=1, fix_x=-15
            ):
                canvas_pdf.drawString(
                    corban_address_coord.get('next_line_x'),
                    corban_address_coord.get('next_line_y'),
                    data.get('endereco_corban'),
                )

            if corban_phone_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Telefone', word_order=1, fix_x=-15
            ):
                canvas_pdf.drawString(
                    corban_phone_coord.get('next_line_x'),
                    corban_phone_coord.get('next_line_y'),
                    data.get('telefone_representante'),
                )

            if corban_name_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path, word='Nome', word_order=2, fix_x=-15
            ):
                canvas_pdf.drawString(
                    corban_name_coord.get('next_line_x'),
                    corban_name_coord.get('next_line_y'),
                    data.get('nome_agente_corban'),
                )

            if corban_document_coord := word_coordinates_in_pdf(
                pdf_path=pdf_path,
                word='CPF do Agente da Venda',
                word_order=0,
                fix_x=-15,
            ):
                canvas_pdf.drawString(
                    corban_document_coord.get('next_line_x'),
                    corban_document_coord.get('next_line_y'),
                    data.get('cpf_agente_corban'),
                )

            canvas_pdf.save()

            # Obtenha a página com o texto como um objeto PdfFileReader
            new_page = PdfFileReader(packet).getPage(0)

            # Mesclando a página original com a página atualizada
            page.mergePage(new_page)

            nome_arquivo = 'termo-de-adesao'
            nome_anexo = 'TERMO DE ADESÃO'

            salva_termo_s3(
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
        print(
            'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo termo de adesão'
        )


def salva_termo_s3(
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
        # object_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'

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
        logger.error(
            f'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo {nome_arquivo} - {e}'
        )
        print(
            f'Erro: Não foi possivel salvar o contrato, erro ao salvar arquivo {nome_arquivo}'
        )


def termo_cotratacao_seguro(tipo_termo, nome_arquivo, contrato_cartao, contrato, plano):
    if tipo_termo == EnumArquivosSeguros.VIDA_SIAPE:
        termo_vida_siape(nome_arquivo, contrato, plano)
    elif tipo_termo == EnumArquivosSeguros.VIDA_INSS:
        termo_vida_inss(nome_arquivo, contrato, plano)
    elif tipo_termo == EnumArquivosSeguros.OURO_INSS:
        termo_ouro_inss(nome_arquivo, plano, contrato)
    elif tipo_termo == EnumArquivosSeguros.DIAMANTE_INSS:
        termo_diamante_inss(nome_arquivo, plano, contrato)
    elif tipo_termo == EnumArquivosSeguros.OURO_DEMAIS_CONVENIOS:
        termo_ouro_demais_convenios(nome_arquivo, plano, contrato)
    elif tipo_termo == EnumArquivosSeguros.DIAMANTE_DEMAIS_CONVENIOS:
        termo_diamente_demais_convenios(nome_arquivo, plano, contrato)


def termo_vida_siape(nome_arquivo, contrato, plano):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open(
                f'static/{nome_arquivo}',
                'rb',
            )
        )

        output_pdf = PdfFileWriter()

        for page_num in range(input_pdf.getNumPages()):
            page = input_pdf.getPage(page_num)
            output_pdf.addPage(page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(0)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        # Número Proposta:
        x = 345
        y = 767
        can.drawString(x, y, f'{contrato.pk}')

        # Nome do Segurado:
        x = 41
        y = 490
        can.drawString(x, y, f'{contrato.cliente.nome_cliente}')

        # Nacionalidade:
        nacionalidade = contrato.cliente.nacionalidade or 'Brasileira'
        x = 41
        y = 454
        can.drawString(x, y, f'{nacionalidade}')

        # Data de Nascimento:
        data_nascimento = contrato.cliente.dt_nascimento.strftime('%d/%m/%Y') or ''
        x = 115
        y = 454
        can.drawString(x, y, f'{data_nascimento}')

        # CPF:
        x = 215
        y = 454
        can.drawString(x, y, f'{contrato.cliente.nu_cpf}')

        # Orgao Emissor:
        x = 310
        y = 454
        can.drawString(x, y, f'{contrato.cliente.documento_orgao_emissor}')

        # CEP:
        x = 443
        y = 454
        can.drawString(x, y, f'{contrato.cliente.endereco_cep}')

        # Endereço:
        x = 41
        y = 420
        can.drawString(x, y, f'{contrato.cliente.endereco_logradouro}')
        x = 41
        y = 411
        can.drawString(x, y, f'{contrato.cliente.endereco_bairro}')

        # Numero:
        x = 220
        y = 420
        can.drawString(x, y, f'{contrato.cliente.endereco_numero}')

        # Complemento:
        complemento = contrato.cliente.endereco_complemento or 'Complemento'
        x = 270
        y = 420
        can.drawString(x, y, f'{complemento}')

        # Telefone:
        # Separando o DDD e o número do telefone
        partes = contrato.cliente.telefone_celular.split()
        ddd = partes[0].strip('()')
        numero = partes[1]
        x = 450
        y = 420
        can.drawString(x, y, f'{ddd}')
        x = 468
        y = 420
        can.drawString(x, y, f'{numero}')

        data_venda = datetime.strftime(contrato.criado_em, '%Y%m%d')
        data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
        data_venda_ajuste += relativedelta(months=plano.quantidade_parcelas)
        data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')

        # Separando dia, mês e ano para data_venda
        dia_venda, mes_venda, ano_venda = (
            int(data_venda[6:]),
            int(data_venda[4:6]),
            int(data_venda[:4]),
        )

        # Separando dia, mês e ano para data_fim_vigencia
        dia_fim_vigencia, mes_fim_vigencia, ano_fim_vigencia = (
            int(data_fim_vigencia[6:]),
            int(data_fim_vigencia[4:6]),
            int(data_fim_vigencia[:4]),
        )

        # VIGENCIA SEGURO
        # INICIO
        x = 160
        y = 209
        can.drawString(x, y, f'{dia_venda}')
        x = 180
        y = 209
        can.drawString(x, y, f'{mes_venda}')
        x = 210
        y = 209
        can.drawString(x, y, f'{ano_venda}')

        # FIM
        x = 420
        y = 209
        can.drawString(x, y, f'{dia_fim_vigencia}')
        x = 440
        y = 209
        can.drawString(x, y, f'{mes_fim_vigencia}')
        x = 468
        y = 209
        can.drawString(x, y, f'{ano_fim_vigencia}')

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        token_contrato = contrato.token_contrato
        cpf = contrato.cliente.nu_cpf
        cpf_slugify = cpf.replace('.', '').replace('-', '')

        data_emissao = contrato.criado_em or ''
        data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
        data_emissao_slugify = slugify(data_emissao)
        data_emissao_slugify = data_emissao_slugify.replace('-', '')
        nome_anexo, _ = os.path.splitext(nome_arquivo)

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            slugify(nome_anexo),
            nome_anexo,
        )


def termo_vida_inss(nome_arquivo, contrato, plano):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open(
                f'static/{nome_arquivo}',
                'rb',
            )
        )

        output_pdf = PdfFileWriter()

        for page_num in range(input_pdf.getNumPages()):
            page = input_pdf.getPage(page_num)
            output_pdf.addPage(page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(0)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=elevenSeventeen)

        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        y = 790
        x = 345
        can.drawString(x, y, f'{contrato.pk}')

        # Nome do Segurado:
        x = 23
        y = 530
        can.drawString(x, y, f'{contrato.cliente.nome_cliente}')

        # Nacionalidade:
        x = 23
        y = 500
        can.drawString(x, y, f"{contrato.cliente.nacionalidade or 'Brasileira'}")

        # Data de Nascimento:
        x = 115
        y = 500
        can.drawString(x, y, contrato.cliente.dt_nascimento.strftime('%d/%m/%Y') or '')

        # CPF:
        x = 222
        y = 500
        can.drawString(x, y, f'{contrato.cliente.nu_cpf}')

        # Orgao Emissor:
        x = 342
        y = 500
        can.drawString(x, y, f'{contrato.cliente.documento_orgao_emissor}')

        # CEP:
        x = 470
        y = 500
        can.drawString(x, y, f'{contrato.cliente.endereco_cep}')

        # Endereço:
        x = 23
        y = 465
        can.drawString(x, y, f'{contrato.cliente.endereco_logradouro}')

        # Bairro:
        x = 23
        y = 456
        can.drawString(
            x,
            y,
            f'{contrato.cliente.endereco_bairro} - '
            + f'{contrato.cliente.endereco_cidade}',
        )

        # Número:
        x = 236
        y = 465
        can.drawString(x, y, f'{contrato.cliente.endereco_numero}')

        # Complemento:
        x = 285
        y = 465
        can.drawString(x, y, f"{contrato.cliente.endereco_complemento or '-'}")

        # Dado o número de telefone "(11) 97555-4545", vamos separá-lo em DDD e número de telefone.

        numero_telefone = contrato.cliente.telefone_celular

        # Separando o DDD e o número do telefone
        partes = numero_telefone.split()
        ddd = partes[0].strip('()')
        numero = partes[1]

        # Telefone - DDD:
        x = 474
        y = 465
        can.drawString(x, y, f'{ddd}')

        # Telefone - Número:
        x = 495
        y = 465
        can.drawString(x, y, f'{numero}')

        data_venda = datetime.strftime(contrato.criado_em, '%Y%m%d')
        data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
        data_venda_ajuste += relativedelta(months=plano.quantidade_parcelas)
        data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')

        # Separando dia, mês e ano para data_venda
        dia_venda, mes_venda, ano_venda = (
            int(data_venda[6:]),
            int(data_venda[4:6]),
            int(data_venda[:4]),
        )

        # Separando dia, mês e ano para data_fim_vigencia
        dia_fim_vigencia, mes_fim_vigencia, ano_fim_vigencia = (
            int(data_fim_vigencia[6:]),
            int(data_fim_vigencia[4:6]),
            int(data_fim_vigencia[:4]),
        )

        # Data Inicio:
        x = 138
        y = 253
        can.drawString(x, y, f'{dia_venda}')

        x = 168
        y = 253
        can.drawString(x, y, f'{mes_venda}')

        x = 203
        y = 253
        can.drawString(x, y, f'{ano_venda}')

        # Data Fim:
        x = 400
        y = 253
        can.drawString(x, y, f'{dia_fim_vigencia}')

        x = 428
        y = 253
        can.drawString(x, y, f'{mes_fim_vigencia}')

        x = 453
        y = 253
        can.drawString(x, y, f'{ano_fim_vigencia}')

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(1)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=elevenSeventeen)
        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        token_contrato = contrato.token_contrato
        cpf = contrato.cliente.nu_cpf
        cpf_slugify = cpf.replace('.', '').replace('-', '')

        data_emissao = contrato.criado_em or ''
        data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
        data_emissao_slugify = slugify(data_emissao)
        data_emissao_slugify = data_emissao_slugify.replace('-', '')
        nome_anexo, _ = os.path.splitext(nome_arquivo)

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            slugify(nome_anexo),
            nome_anexo,
        )


def termo_ouro_inss(nome_arquivo, plano, contrato):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open(
                f'static/{nome_arquivo}',
                'rb',
            )
        )

        output_pdf = PdfFileWriter()

        for page_num in range(input_pdf.getNumPages()):
            page = input_pdf.getPage(page_num)
            output_pdf.addPage(page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(0)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        y = 662
        x = 335
        can.drawString(x, y, f'{contrato.pk}')

        # Nome do Segurado:
        x = 32
        y = 285
        can.drawString(x, y, f'{contrato.cliente.nome_cliente}')

        # Nacionalidade:
        x = 32
        y = 248
        can.drawString(x, y, f"{contrato.cliente.nacionalidade or 'Brasileira'}")

        # Data de Nascimento:
        x = 138
        y = 248
        can.drawString(x, y, contrato.cliente.dt_nascimento.strftime('%d/%m/%Y') or '')

        # CPF:
        x = 245
        y = 248
        can.drawString(x, y, f'{contrato.cliente.nu_cpf}')

        # Orgao Emissor:
        x = 358
        y = 248
        can.drawString(x, y, f'{contrato.cliente.documento_orgao_emissor}')

        # CEP:
        x = 479
        y = 248
        can.drawString(x, y, f'{contrato.cliente.endereco_cep}')

        # Endereço:
        x = 32
        y = 217
        can.drawString(x, y, f'{contrato.cliente.endereco_logradouro}')

        # Bairro:
        x = 32
        y = 205
        can.drawString(
            x,
            y,
            f'{contrato.cliente.endereco_bairro} - '
            + f'{contrato.cliente.endereco_cidade}',
        )

        # Número:
        x = 244
        y = 215
        can.drawString(x, y, f'{contrato.cliente.endereco_numero}')

        # Complemento:
        x = 295
        y = 215
        can.drawString(x, y, f"{contrato.cliente.endereco_complemento or '-'}")

        # Dado o número de telefone "(11) 97555-4545", vamos separá-lo em DDD e número de telefone.

        numero_telefone = contrato.cliente.telefone_celular

        # Separando o DDD e o número do telefone
        partes = numero_telefone.split()
        ddd = partes[0].strip('()')
        numero = partes[1]

        # Telefone - DDD:
        x = 487
        y = 215
        can.drawString(x, y, f'{ddd}')

        # Telefone - Número:
        x = 503
        y = 215
        can.drawString(x, y, f'{numero}')

        data_venda = datetime.strftime(contrato.criado_em, '%Y%m%d')
        data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
        data_venda_ajuste += relativedelta(months=plano.quantidade_parcelas)
        data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')

        # Separando dia, mês e ano para data_venda
        dia_venda, mes_venda, ano_venda = (
            int(data_venda[6:]),
            int(data_venda[4:6]),
            int(data_venda[:4]),
        )

        # Separando dia, mês e ano para data_fim_vigencia
        dia_fim_vigencia, mes_fim_vigencia, ano_fim_vigencia = (
            int(data_fim_vigencia[6:]),
            int(data_fim_vigencia[4:6]),
            int(data_fim_vigencia[:4]),
        )

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(1)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=elevenSeventeen)
        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        # Data Inicio:
        x = 146
        y = 740
        can.drawString(x, y, f'{dia_venda}')

        x = 169
        y = 740
        can.drawString(x, y, f'{mes_venda}')

        x = 196
        y = 740
        can.drawString(x, y, f'{ano_venda}')

        # Data Fim:
        x = 407
        y = 740
        can.drawString(x, y, f'{dia_fim_vigencia}')

        x = 427
        y = 740
        can.drawString(x, y, f'{mes_fim_vigencia}')

        x = 456
        y = 740
        can.drawString(x, y, f'{ano_fim_vigencia}')

        premio_bruto = (
            float(plano.porcentagem_premio) * float(contrato.limite_pre_aprovado) / 100
        )

        iof = float(premio_bruto) * float(plano.iof) / 100

        premio_liquido = float(premio_bruto) - float(iof)

        plano_valor_segurado = Decimal(
            str(plano.valor_segurado).replace('.', '').replace(',', '.')
        )
        if contrato.limite_pre_aprovado <= plano_valor_segurado:
            valor_plano = f'{plano.valor_segurado}'.replace('.', '').replace(',', '.')
            premio_bruto = float(plano.porcentagem_premio) * float(valor_plano) / 100

            iof = float(premio_bruto) * float(plano.iof) / 100

            premio_liquido = float(premio_bruto) - float(iof)

        # Premio liquido:
        x = 53
        y = 392
        can.drawString(x, y, f'{real_br_money_mask(premio_liquido)}')

        # IOF:
        x = 160
        y = 392
        can.drawString(x, y, f'{real_br_money_mask(iof)}')

        # Premio bruto:
        x = 240
        y = 392
        can.drawString(x, y, f'{real_br_money_mask(premio_bruto)}')

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        token_contrato = contrato.token_contrato
        cpf = contrato.cliente.nu_cpf
        cpf_slugify = cpf.replace('.', '').replace('-', '')

        data_emissao = contrato.criado_em or ''
        data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
        data_emissao_slugify = slugify(data_emissao)
        data_emissao_slugify = data_emissao_slugify.replace('-', '')
        nome_anexo, _ = os.path.splitext(nome_arquivo)

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            slugify(nome_anexo),
            nome_anexo,
        )


def termo_diamante_inss(nome_arquivo, plano, contrato):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open(
                f'static/{nome_arquivo}',
                'rb',
            )
        )

        output_pdf = PdfFileWriter()

        for page_num in range(input_pdf.getNumPages()):
            page = input_pdf.getPage(page_num)
            output_pdf.addPage(page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(0)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        y = 655
        x = 340
        can.drawString(x, y, f'{contrato.pk}')

        # Nome do Segurado:
        x = 23
        y = 335
        can.drawString(x, y, f'{contrato.cliente.nome_cliente}')

        # Nacionalidade:
        x = 23
        y = 297
        can.drawString(x, y, f"{contrato.cliente.nacionalidade or 'Brasileira'}")

        # Data de Nascimento:
        x = 127
        y = 297
        can.drawString(x, y, contrato.cliente.dt_nascimento.strftime('%d/%m/%Y') or '')

        # CPF:
        x = 240
        y = 297
        can.drawString(x, y, f'{contrato.cliente.nu_cpf}')

        # Orgao Emissor:
        x = 347
        y = 297
        can.drawString(x, y, f'{contrato.cliente.documento_orgao_emissor}')
        # CEP:
        x = 460
        y = 297
        can.drawString(x, y, f'{contrato.cliente.endereco_cep}')

        # Endereço:
        x = 23
        y = 265
        can.drawString(x, y, f'{contrato.cliente.endereco_logradouro}')

        # Bairro:
        x = 23
        y = 256
        can.drawString(
            x,
            y,
            f'{contrato.cliente.endereco_bairro} - '
            + f'{contrato.cliente.endereco_cidade}',
        )

        # Número:
        x = 229
        y = 265
        can.drawString(x, y, f'{contrato.cliente.endereco_numero}')

        # Complemento:
        x = 278
        y = 265
        can.drawString(x, y, f"{contrato.cliente.endereco_complemento or '-'}")

        # Dado o número de telefone "(11) 97555-4545", vamos separá-lo em DDD e número de telefone.

        numero_telefone = contrato.cliente.telefone_celular

        # Separando o DDD e o número do telefone
        partes = numero_telefone.split()
        ddd = partes[0].strip('()')
        numero = partes[1]

        # Telefone - DDD:
        x = 463
        y = 265
        can.drawString(x, y, f'{ddd}')

        # Telefone - Número:
        x = 485
        y = 265
        can.drawString(x, y, f'{numero}')

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(1)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=elevenSeventeen)
        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        data_venda = datetime.strftime(contrato.criado_em, '%Y%m%d')
        data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
        data_venda_ajuste += relativedelta(months=plano.quantidade_parcelas)
        data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')

        # Separando dia, mês e ano para data_venda
        dia_venda, mes_venda, ano_venda = (
            int(data_venda[6:]),
            int(data_venda[4:6]),
            int(data_venda[:4]),
        )

        # Separando dia, mês e ano para data_fim_vigencia
        dia_fim_vigencia, mes_fim_vigencia, ano_fim_vigencia = (
            int(data_fim_vigencia[6:]),
            int(data_fim_vigencia[4:6]),
            int(data_fim_vigencia[:4]),
        )

        # Data Inicio:
        x = 138
        y = 730
        can.drawString(x, y, f'{dia_venda}')

        x = 162
        y = 730
        can.drawString(x, y, f'{mes_venda}')

        x = 188
        y = 730
        can.drawString(x, y, f'{ano_venda}')

        # Data Fim:
        x = 386
        y = 730
        can.drawString(x, y, f'{dia_fim_vigencia}')

        x = 407
        y = 730
        can.drawString(x, y, f'{mes_fim_vigencia}')

        x = 435
        y = 730
        can.drawString(x, y, f'{ano_fim_vigencia}')

        premio_bruto = (
            float(plano.porcentagem_premio) * float(contrato.limite_pre_aprovado) / 100
        )

        iof = float(premio_bruto) * float(plano.iof) / 100

        premio_liquido = float(premio_bruto) - float(iof)

        plano_valor_segurado = Decimal(
            str(plano.valor_segurado).replace('.', '').replace(',', '.')
        )
        if contrato.limite_pre_aprovado <= plano_valor_segurado:
            valor_plano = f'{plano.valor_segurado}'.replace('.', '').replace(',', '.')
            premio_bruto = float(plano.porcentagem_premio) * float(valor_plano) / 100

            iof = float(premio_bruto) * float(plano.iof) / 100

            premio_liquido = float(premio_bruto) - float(iof)

        # Premio liquido:
        x = 70
        y = 385
        can.drawString(x, y, f'{real_br_money_mask(premio_liquido)}')

        # IOF:
        x = 135
        y = 385
        can.drawString(x, y, f'{real_br_money_mask(iof)}')

        # Premio bruto:
        x = 210
        y = 385
        can.drawString(x, y, f'{real_br_money_mask(premio_bruto)}')

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        token_contrato = contrato.token_contrato
        cpf = contrato.cliente.nu_cpf
        cpf_slugify = cpf.replace('.', '').replace('-', '')

        data_emissao = contrato.criado_em or ''
        data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
        data_emissao_slugify = slugify(data_emissao)
        data_emissao_slugify = data_emissao_slugify.replace('-', '')
        nome_anexo, _ = os.path.splitext(nome_arquivo)

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            slugify(nome_anexo),
            nome_anexo,
        )


def termo_ouro_demais_convenios(nome_arquivo, plano, contrato):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open(
                f'static/{nome_arquivo}',
                'rb',
            )
        )

        output_pdf = PdfFileWriter()

        for page_num in range(input_pdf.getNumPages()):
            page = input_pdf.getPage(page_num)
            output_pdf.addPage(page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(0)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        y = 656
        x = 335
        can.drawString(x, y, f'{contrato.pk}')

        # Nome do Segurado:
        x = 15
        y = 300
        can.drawString(x, y, f'{contrato.cliente.nome_cliente}')

        # Nacionalidade:
        x = 15
        y = 269
        can.drawString(x, y, f'{contrato.cliente.nacionalidade or "Brasileira"}')

        # Data de Nascimento:
        x = 127
        y = 269
        can.drawString(x, y, contrato.cliente.dt_nascimento.strftime('%d/%m/%Y') or '')

        # CPF:
        x = 257
        y = 269
        can.drawString(x, y, f'{contrato.cliente.nu_cpf}')

        # Orgao Emissor:
        x = 361
        y = 269
        can.drawString(x, y, f'{contrato.cliente.documento_orgao_emissor}')
        # CEP:
        x = 460
        y = 269
        can.drawString(x, y, f'{contrato.cliente.endereco_cep}')

        # Endereço:
        x = 15
        y = 234
        can.drawString(x, y, f'{contrato.cliente.endereco_logradouro}')

        # Bairro:
        x = 15
        y = 225
        can.drawString(
            x,
            y,
            f'{contrato.cliente.endereco_bairro} - '
            + f'{contrato.cliente.endereco_cidade}',
        )

        # Número:
        x = 230
        y = 234
        can.drawString(x, y, f'{contrato.cliente.endereco_numero}')

        # Complemento:
        x = 278
        y = 234
        can.drawString(x, y, f"{contrato.cliente.endereco_complemento or '-'}")

        # Dado o número de telefone "(11) 97555-4545", vamos separá-lo em DDD e número de telefone.

        numero_telefone = contrato.cliente.telefone_celular

        # Separando o DDD e o número do telefone
        partes = numero_telefone.split()
        ddd = partes[0].strip('()')
        numero = partes[1]

        # Telefone - DDD:
        x = 468
        y = 234
        can.drawString(x, y, f'{ddd}')

        # Telefone - Número:
        x = 495
        y = 234
        can.drawString(x, y, f'{numero}')

        data_venda = datetime.strftime(contrato.criado_em, '%Y%m%d')
        data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
        data_venda_ajuste += relativedelta(months=plano.quantidade_parcelas)
        data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')

        # Separando dia, mês e ano para data_venda
        dia_venda, mes_venda, ano_venda = (
            int(data_venda[6:]),
            int(data_venda[4:6]),
            int(data_venda[:4]),
        )

        # Separando dia, mês e ano para data_fim_vigencia
        dia_fim_vigencia, mes_fim_vigencia, ano_fim_vigencia = (
            int(data_fim_vigencia[6:]),
            int(data_fim_vigencia[4:6]),
            int(data_fim_vigencia[:4]),
        )

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(1)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=elevenSeventeen)
        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        # Data Inicio:
        x = 135
        y = 680
        can.drawString(x, y, f'{dia_venda}')

        x = 155
        y = 680
        can.drawString(x, y, f'{mes_venda}')

        x = 180
        y = 680
        can.drawString(x, y, f'{ano_venda}')

        # Data Fim:
        x = 390
        y = 680
        can.drawString(x, y, f'{dia_fim_vigencia}')

        x = 410
        y = 680
        can.drawString(x, y, f'{mes_fim_vigencia}')

        x = 440
        y = 680
        can.drawString(x, y, f'{ano_fim_vigencia}')

        premio_bruto = (
            float(plano.porcentagem_premio) * float(contrato.limite_pre_aprovado) / 100
        )

        iof = float(premio_bruto) * float(plano.iof) / 100

        premio_liquido = float(premio_bruto) - float(iof)

        plano_valor_segurado = Decimal(
            str(plano.valor_segurado).replace('.', '').replace(',', '.')
        )
        if contrato.limite_pre_aprovado <= plano_valor_segurado:
            valor_plano = f'{plano.valor_segurado}'.replace('.', '').replace(',', '.')
            premio_bruto = float(plano.porcentagem_premio) * float(valor_plano) / 100

            iof = float(premio_bruto) * float(plano.iof) / 100

            premio_liquido = float(premio_bruto) - float(iof)

        # Premio liquido:
        x = 35
        y = 363
        can.drawString(x, y, f'{real_br_money_mask(premio_liquido)}')

        # IOF:
        x = 128
        y = 363
        can.drawString(x, y, f'{real_br_money_mask(iof)}')

        # Premio bruto:
        x = 215
        y = 363
        can.drawString(x, y, f'{real_br_money_mask(premio_bruto)}')

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        token_contrato = contrato.token_contrato
        cpf = contrato.cliente.nu_cpf
        cpf_slugify = cpf.replace('.', '').replace('-', '')

        data_emissao = contrato.criado_em or ''
        data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
        data_emissao_slugify = slugify(data_emissao)
        data_emissao_slugify = data_emissao_slugify.replace('-', '')
        nome_anexo, _ = os.path.splitext(nome_arquivo)

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            slugify(nome_anexo),
            nome_anexo,
        )


def termo_diamente_demais_convenios(nome_arquivo, plano, contrato):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_pdf = PdfFileReader(
            open(
                f'static/{nome_arquivo}',
                'rb',
            )
        )

        output_pdf = PdfFileWriter()

        for page_num in range(input_pdf.getNumPages()):
            page = input_pdf.getPage(page_num)
            output_pdf.addPage(page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(0)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        y = 642
        x = 335
        can.drawString(x, y, f'{contrato.pk}')

        # Nome do Segurado:
        x = 15
        y = 300
        can.drawString(x, y, f'{contrato.cliente.nome_cliente}')

        # Nacionalidade:
        x = 15
        y = 264
        can.drawString(x, y, f"{contrato.cliente.nacionalidade or 'Brasileira'}")

        # Data de Nascimento:
        x = 114
        y = 264
        can.drawString(x, y, contrato.cliente.dt_nascimento.strftime('%d/%m/%Y') or '')

        # CPF:
        x = 227
        y = 264
        can.drawString(x, y, f'{contrato.cliente.nu_cpf}')

        # Orgao Emissor:
        x = 340
        y = 264
        can.drawString(x, y, f'{contrato.cliente.documento_orgao_emissor}')
        # CEP:
        x = 454
        y = 264
        can.drawString(x, y, f'{contrato.cliente.endereco_cep}')

        # Endereço:
        x = 15
        y = 227
        can.drawString(x, y, f'{contrato.cliente.endereco_logradouro}')

        # Bairro:
        x = 15
        y = 220
        can.drawString(
            x,
            y,
            f'{contrato.cliente.endereco_bairro} - '
            + f'{contrato.cliente.endereco_cidade}',
        )

        # Número:
        x = 226
        y = 227
        can.drawString(x, y, f'{contrato.cliente.endereco_numero}')

        # Complemento:
        x = 276
        y = 227
        can.drawString(x, y, f"{contrato.cliente.endereco_complemento or '-'}")

        # Dado o número de telefone "(11) 97555-4545", vamos separá-lo em DDD e número de telefone.

        numero_telefone = contrato.cliente.telefone_celular

        # Separando o DDD e o número do telefone
        partes = numero_telefone.split()
        ddd = partes[0].strip('()')
        numero = partes[1]

        # Telefone - DDD:
        x = 462
        y = 227
        can.drawString(x, y, f'{ddd}')

        # Telefone - Número:
        x = 478
        y = 227
        can.drawString(x, y, f'{numero}')

        data_venda = datetime.strftime(contrato.criado_em, '%Y%m%d')
        data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
        data_venda_ajuste += relativedelta(months=plano.quantidade_parcelas)
        data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')

        # Separando dia, mês e ano para data_venda
        dia_venda, mes_venda, ano_venda = (
            int(data_venda[6:]),
            int(data_venda[4:6]),
            int(data_venda[:4]),
        )

        # Separando dia, mês e ano para data_fim_vigencia
        dia_fim_vigencia, mes_fim_vigencia, ano_fim_vigencia = (
            int(data_fim_vigencia[6:]),
            int(data_fim_vigencia[4:6]),
            int(data_fim_vigencia[:4]),
        )

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        # Obtenha a página 0 do PDF
        page = input_pdf.getPage(1)

        # Crie um arquivo de pacote de bytes e um objeto canvas
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=elevenSeventeen)
        # Defina a fonte e o tamanho da fonte
        can.setFont('Helvetica', 9)

        # Data Inicio:
        x = 135
        y = 728
        can.drawString(x, y, f'{dia_venda}')

        x = 155
        y = 728
        can.drawString(x, y, f'{mes_venda}')

        x = 180
        y = 728
        can.drawString(x, y, f'{ano_venda}')

        # Data Fim:
        x = 395
        y = 728
        can.drawString(x, y, f'{dia_fim_vigencia}')

        x = 417
        y = 728
        can.drawString(x, y, f'{mes_fim_vigencia}')

        x = 442
        y = 728
        can.drawString(x, y, f'{ano_fim_vigencia}')

        premio_bruto = (
            float(plano.porcentagem_premio) * float(contrato.limite_pre_aprovado) / 100
        )

        iof = float(premio_bruto) * float(plano.iof) / 100

        premio_liquido = float(premio_bruto) - float(iof)

        plano_valor_segurado = Decimal(
            str(plano.valor_segurado).replace('.', '').replace(',', '.')
        )
        if contrato.limite_pre_aprovado <= plano_valor_segurado:
            valor_plano = f'{plano.valor_segurado}'.replace('.', '').replace(',', '.')
            premio_bruto = float(plano.porcentagem_premio) * float(valor_plano) / 100

            iof = float(premio_bruto) * float(plano.iof) / 100

            premio_liquido = float(premio_bruto) - float(iof)

        # Premio liquido:
        x = 58
        y = 396
        can.drawString(x, y, f'{real_br_money_mask(premio_liquido)}')

        # IOF:
        x = 140
        y = 396
        can.drawString(x, y, f'{real_br_money_mask(iof)}')

        # Premio bruto:
        x = 210
        y = 396
        can.drawString(x, y, f'{real_br_money_mask(premio_bruto)}')

        can.save()

        # Obtenha a página com o texto como um objeto PdfFileReader
        new_page = PdfFileReader(packet).getPage(0)

        # Mesclando a página original com a página atualizada
        page.mergePage(new_page)

        token_contrato = contrato.token_contrato
        cpf = contrato.cliente.nu_cpf
        cpf_slugify = cpf.replace('.', '').replace('-', '')

        data_emissao = contrato.criado_em or ''
        data_emissao = data_emissao.strftime('%d/%m/%Y') or ''
        data_emissao_slugify = slugify(data_emissao)
        data_emissao_slugify = data_emissao_slugify.replace('-', '')
        nome_anexo, _ = os.path.splitext(nome_arquivo)

        return salva_termo_s3(
            temp_dir,
            output_pdf,
            token_contrato,
            cpf_slugify,
            data_emissao_slugify,
            contrato,
            slugify(nome_anexo),
            nome_anexo,
        )


def sabemi_fill_terms(data, contract, plano):
    if plano.tipo_plano == EnumTipoPlano.PRATA:
        sabemi_silver = SabemiLifeInsuranceSilverTerm()
        sabemi_silver.fill_term(data=data, contract=contract, plano=plano)

    elif plano.tipo_plano == EnumTipoPlano.OURO:
        sabemi_gold = SabemiLifeInsuranceMoneyLenderGoldTerm()
        sabemi_gold.fill_term(data=data, contract=contract, plano=plano)

    elif plano.tipo_plano == EnumTipoPlano.DIAMANTE:
        sabemi_diamond = SabemiLifeInsuranceMoneyLenderDiamondTerm()
        sabemi_diamond.fill_term(data=data, contract=contract, plano=plano)
