import logging
import os
import tempfile
from datetime import datetime
from decimal import Decimal

import boto3
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Max
from unidecode import unidecode

from contract.constants import EnumArquivosSeguros, EnumTipoPlano
from contract.models.contratos import Contrato
from contract.products.cartao_beneficio.models.planos import Planos
from core.models import ArquivoGenerali, BeneficiosContratado
from core.tasks import format_telefone
from handlers.solicitar_cobranca_dock import solicitar_cobranca

logger = logging.getLogger('digitacao')

s3 = boto3.client(
    's3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


def escrever_arrecadacao(
    destino,
    produto,
    apolice,
    plano,
    identificacao_nova,
    qtd_parcela,
    today_str,
    nova_vl_premio,
    cnpj_empresa,
    sequencial_do_registro,
):
    plano = f'{plano}'.ljust(10, ' ')
    qtd_parcela = str(qtd_parcela)[:3]
    destino.write(
        f"3{produto[:5]}{apolice[:10]}{plano[:10]}{cnpj_empresa[:15]}{identificacao_nova[:20]}{qtd_parcela}{today_str[:8]}{today_str[:8]}{nova_vl_premio[:15]}A{mock(1198, ' ')}{sequencial_do_registro[:6]}\n"
    )


def ajustar_posicoes(destino):
    with open(destino.name, 'r') as arquivo:
        linhas = arquivo.readlines()

    linhas_ordenadas = sorted(linhas, key=lambda x: (int(x[0]), int(x[-5:])))

    for i_registro, i in enumerate(range(len(linhas_ordenadas)), start=1):
        linha = linhas_ordenadas[i]
        novo_dado = f'{i_registro}'.rjust(6, '0')

        linhas_ordenadas[i] = f'{linha[:1294]}{novo_dado}{linha[1300:]}'

    with open(destino.name, 'w') as arquivo_ordenado:
        arquivo_ordenado.writelines(linhas_ordenadas)


def mock(size, char):
    return ''.rjust(size, char)


def get_maior_sequencial(nome_archive):
    try:
        maior_sequencial = ArquivoGenerali.objects.filter(
            nmDocumento__contains=nome_archive
        ).aggregate(Max('sequencial'))['sequencial__max']
        return maior_sequencial if maior_sequencial is not None else 0
    except ArquivoGenerali.DoesNotExist:
        return 1


def count_reg(destino):
    with open(destino.name, 'r') as arquivo:
        linhas = arquivo.readlines()
        count = 0

    for line in linhas:
        if not line.startswith(('0', '9')):
            count += 1

    return count


def check_data_in_last(start_text, start_index, end_index, local_path):
    try:
        with open(local_path.name, 'r') as arquivo:
            lines = arquivo.readlines()

        last_line_index = [
            i for i, line in enumerate(lines) if line.startswith(start_text)
        ]

        extracted_text = False

        if last_line_index is not None:
            # Remove todas as linhas que começam com start_text, exceto a última
            lines = [
                line
                for i, line in enumerate(lines)
                if any(
                    i == index and line.startswith(start_text)
                    for index in last_line_index
                )
            ]
            dados = [dado_extraido[start_index:end_index] for dado_extraido in lines]
            first_date = lines[-1][0]
            last_line = max(dados, key=lambda x: int(x))
            extracted_text = last_line

        return extracted_text, first_date
    except Exception:
        return False, False


def write_initial_content(
    destino, produto, apolice, today_str, sequencial_do_registro, codigo_operacao
):
    destino.write(
        f"0{produto[:5]}{apolice[:10]}{today_str[:8]}{sequencial_do_registro}{'1.8'.rjust(6, '0')[:6]}{codigo_operacao[:3]}{mock(1255, ' ')[:1255]}000001\n"
    )


def write_adesao(
    destino,
    produto,
    apolice,
    plano,
    cnpj_empresa,
    identificacao_seguro,
    cpf,
    data_venda,
    data_fim_vigencia,
    nome_cliente,
    rua,
    numero_casa,
    complemento,
    bairro,
    cidade,
    estado,
    cep,
    ddd_residencial,
    telf_residencial,
    ddd_comercial,
    telef_comericial,
    dt_nascimento,
    sexo,
    estado_civil,
    tp_doc,
    num_doc,
    org_exp,
    dt_emissao_doc,
    nova_vl_seguro,
    nova_vl_premio,
    qtd_parcela,
    num_adesao,
    tp_vigencia,
    vida,
    email,
    sequencial_do_registro,
    nova_vl_liquido,
):
    plano = f'{plano}'.ljust(10, ' ')
    qtd_parcela = str(qtd_parcela)[:2]
    nova_vl_seguro = str(nova_vl_seguro).replace('.', '').replace(',', '.')
    nova_vl_premio = str(nova_vl_premio).replace('.', '').replace(',', '.')
    nova_vl_liquido = str(nova_vl_liquido).replace('.', '').replace(',', '.')
    destino.write(
        f"1{produto[:5]}{apolice[:10]}{plano[:10]}{cnpj_empresa[:15]}{identificacao_seguro[:20]}{cpf[:15]}{data_venda[:8]}{data_venda[:8]}{data_venda[:8]}{data_fim_vigencia[:8]}{unidecode(nome_cliente)[:50]}{unidecode(rua)[:50]}{unidecode(numero_casa)[:20]}{unidecode(complemento)[:50]}{unidecode(bairro)[:50]}{unidecode(cidade)[:60]}{unidecode(estado)[:2]}{cep[:8]}{ddd_residencial[:3]}{telf_residencial[:9]}{ddd_comercial[:3]}{telef_comericial[:9]}{dt_nascimento[:8]}{sexo[:1]}{estado_civil[:1]}{unidecode(tp_doc)[:10]}{unidecode(num_doc)[:20]}{unidecode(org_exp)[:15]}{dt_emissao_doc[:8]}{nova_vl_seguro[:15]}{nova_vl_premio[:15]}{qtd_parcela}{mock(20, ' ')}{num_adesao[:20]}{mock(145, ' ')}{ddd_comercial[:3]}{telef_comericial[:9]}{mock(45, ' ')}{nova_vl_liquido[:15]}{mock(350, ' ')}{unidecode(email)[:60]}{mock(110, ' ')}{sequencial_do_registro[:6]}\n"
    )


def write_trailer(destino, count_data, sequencial_do_registro):
    destino.write(
        f"9{f'{count_data}'.rjust(6, '0')}{mock(1287, ' ')}{sequencial_do_registro}\n"
    )


def remove_first_line_starting_with(start_text, local_path):
    with open(local_path.name, 'r') as file:
        lines = file.readlines()

    for i, line in enumerate(lines):
        if line.startswith(start_text):
            del lines[i]

    with open(local_path.name, 'w') as file:
        file.writelines(lines)


def check_data_in_range(start_index, end_index, local_path):
    try:
        # Lê o conteúdo atual do arquivo
        with open(local_path.name, 'r') as file:
            lines = file.readlines()

        if lines:
            last_line = lines[-1]
            data_in_range = last_line[start_index - 1 : end_index]
            first_date = last_line[0]
            return data_in_range, first_date

        return False, False
    except Exception:
        pass


def escrever_arquivo_generali(contrato, plano, cartao_beneficio, cliente_cartao):
    plano = Planos.objects.get(id=plano.pk)
    contrato = Contrato.objects.get(id=contrato.pk)

    logger.info('iniciou o processo de inclusão da generali')
    vida = f'{plano.codigo_plano}'.rjust(15, '0')

    plano_valor_segurado_str = f'{plano.valor_segurado}'
    # Convert to Decimal
    plano_valor_segurado = Decimal(
        plano_valor_segurado_str.replace('.', '').replace(',', '.')
    )
    premio_bruto = float(plano_valor_segurado) * float(plano.porcentagem_premio) / 100

    iof = float(premio_bruto) * float(plano.iof) / 100

    premio_liquido = float(premio_bruto) - float(iof)

    valor_plano = plano_valor_segurado
    if contrato.limite_pre_aprovado <= plano_valor_segurado:
        valor_plano = contrato.limite_pre_aprovado
        premio_bruto = float(valor_plano) * float(plano.porcentagem_premio) / 100

        iof = float(premio_bruto) * float(plano.iof) / 100

        premio_liquido = float(premio_bruto) - float(iof)

    if plano.tipo_plano == EnumTipoPlano.PRATA:
        valor_plano = f'{plano.valor_segurado}'.replace('.', '').replace(',', '.')
        premio_bruto = float(plano.porcentagem_premio)
        premio_liquido = float(plano.porcentagem_premio_liquido)

    data_venda = datetime.strftime(contrato.criado_em, '%Y%m%d')
    data_venda_ajuste = datetime.strptime(data_venda, '%Y%m%d')
    data_venda_ajuste += relativedelta(months=plano.quantidade_parcelas)
    data_fim_vigencia = data_venda_ajuste.strftime('%Y%m%d')
    cliente_cartao = contrato.cliente_cartao_contrato.get()

    id_seq = f'{cliente_cartao.id_conta_dock}'
    nova_id_seq = id_seq
    identificacao_seguro = (
        plano.codigo_sucursal
        + plano.codigo_ramo
        + plano.codigo_operacao
        + plano.codigo_plano
    )

    if len(identificacao_seguro + nova_id_seq) < 18:
        zeros_a_adicionar = 18 - len(identificacao_seguro + nova_id_seq)
        nova_id_seq = '0' * zeros_a_adicionar + nova_id_seq
    try:
        identificacao_nova = identificacao_seguro + nova_id_seq
    except Exception:
        identificacao_nova = f'{identificacao_seguro + nova_id_seq.rjust(18 - len(identificacao_seguro), "0")}'[
            :18
        ]

    cpf = f'{contrato.cliente.nu_cpf}'.replace('.', '').replace('-', '')
    nome_cliente = f'{contrato.cliente.nome_cliente}'.ljust(50, ' ')
    numero_casa = f'{contrato.cliente.endereco_numero}'.ljust(20, ' ')
    complemento = f'{contrato.cliente.endereco_complemento}'.ljust(50, ' ')
    bairro = f'{contrato.cliente.endereco_bairro}'.ljust(50, ' ')
    cidade = f'{contrato.cliente.endereco_cidade}'.ljust(60, ' ')
    estado = f'{contrato.cliente.endereco_uf}'
    cep = f'{contrato.cliente.endereco_cep}'.replace('-', '')
    ddd_residencial, telf_residencial = format_telefone(
        contrato.cliente.telefone_residencial
    )
    ddd_comercial, telef_comericial = format_telefone(contrato.cliente.telefone_celular)
    dt_nascimento = f'{datetime.strftime(contrato.cliente.dt_nascimento, "%Y%m%d")}'
    sexo = f'{contrato.cliente.sexo}'[:1]
    estado_civil = f'{contrato.cliente.estado_civil}'[:1]
    tp_doc = f'{contrato.cliente.documento_tipo}'.ljust(10, ' ')
    num_doc = f'{contrato.cliente.documento_numero}'.ljust(20, ' ')
    org_exp = f'{contrato.cliente.documento_orgao_emissor}'.ljust(15, ' ')
    dt_emissao_doc = (
        f'{datetime.strftime(contrato.cliente.documento_data_emissao, "%Y%m%d")}'.rjust(
            8, ' '
        )
    )
    if len(contrato.cliente.endereco_logradouro) < 3:
        rua = f'Rua {contrato.cliente.endereco_logradouro}'
    else:
        rua = contrato.cliente.endereco_logradouro

    try:
        nova_vl_seguro = '{:.2f}'.format(float(valor_plano))
        nova_vl_seguro = f'{nova_vl_seguro}'.replace(',', '').replace('.', '')
        nova_vl_premio = '{:.2f}'.format(float(premio_bruto))
        nova_vl_premio = f'{nova_vl_premio}'.replace(',', '').replace('.', '')
        nova_vl_liquido = '{:.2f}'.format(float(premio_liquido))
        nova_vl_liquido = f'{nova_vl_liquido}'.replace(',', '').replace('.', '')
    except Exception:
        nova_vl_seguro = '{:.2f}'.format(float(valor_plano))
        nova_vl_seguro = f'{nova_vl_seguro}'.replace('.', '').replace(',', '.')
        nova_vl_premio = '{:.2f}'.format(float(premio_bruto))
        nova_vl_premio = f'{nova_vl_premio}'.replace('.', '').replace(',', '.')
        nova_vl_liquido = '{:.2f}'.format(float(premio_liquido))
        nova_vl_liquido = f'{nova_vl_liquido}'.replace('.', '').replace(',', '.')

    qtd_parcela = '24' if plano.tipo_plano == EnumTipoPlano.PRATA else '01'
    num_adesao = f'{contrato.id}'.replace(' ', '').ljust(20, ' ')

    email = f'{contrato.cliente.email}'.ljust(60, ' ')

    if settings.ORIGIN_CLIENT == 'BRB':
        operacao_sequencial = 'BRBVIDAINSS'
        cnpj_empresa = '33136888000143'
        tp_vigencia = 'P.M'.ljust(15, ' ')

    elif settings.ORIGIN_CLIENT == 'DIGIMAIS':
        operacao_sequencial = 'BANCOPINEVIDA'
        cnpj_empresa = '62144175000120'
        tp_vigencia = ''.ljust(15, ' ')

    elif settings.ORIGIN_CLIENT == 'PINE':
        cnpj_empresa = '62144175000120'
        tp_vigencia = ''.ljust(15, ' ')

        if plano.tipo_termo == EnumArquivosSeguros.VIDA_INSS.value:
            operacao_sequencial = 'BANCOPINEVIDA'
        elif plano.tipo_termo == EnumArquivosSeguros.VIDA_SIAPE.value:
            operacao_sequencial = 'BANCOPINESIAPE'
        elif plano.tipo_termo == EnumArquivosSeguros.OURO_INSS.value:
            operacao_sequencial = 'BANCOPINEPRESTINSSOURO'
        elif plano.tipo_termo == EnumArquivosSeguros.OURO_DEMAIS_CONVENIOS.value:
            operacao_sequencial = 'BANCOPINEPRESTCPOURO'
        elif plano.tipo_termo == EnumArquivosSeguros.DIAMANTE_INSS.value:
            operacao_sequencial = 'BANCOPINEPRESTINSSDIAMANTE'
        elif plano.tipo_termo == EnumArquivosSeguros.DIAMANTE_DEMAIS_CONVENIOS.value:
            operacao_sequencial = 'BANCOPINEPRESTCPDIAMANTE'

    maior_sequencial = (
        get_maior_sequencial(operacao_sequencial)
        if get_maior_sequencial(operacao_sequencial) > 0
        else 1
    )
    maior_sequencial_nome = f'{maior_sequencial}'.rjust(6, '0')

    today = datetime.now()
    today_str = today.strftime('%Y%m%d')

    nomeArquivo = (
        f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = os.path.join(temp_dir, nomeArquivo)

        # Baixe o arquivo do S3 se ele existir
        file_exists_in_s3 = True
        try:
            s3.download_file(settings.BUCKET_SEGUROS, nomeArquivo, local_path)
        except Exception as e:
            print('Arquivo ainda nao existente na s3, iremos cria-lo', e)
            file_exists_in_s3 = False

        produto = f'{plano.codigo_produto}'.ljust(5, ' ')
        apolice = f'{plano.apolice}'.rjust(10, '0')
        codigo_operacao = plano.codigo_operacao
        # HEADER
        with open(local_path, 'a') as destino:
            if not file_exists_in_s3:
                logger.info('iniciou o processo de inclusão do header')
                write_initial_content(
                    destino,
                    produto,
                    apolice,
                    today_str,
                    maior_sequencial_nome,
                    codigo_operacao,
                )
        with open(local_path, 'a') as destino:
            remove_first_line_starting_with(start_text='9', local_path=destino)
            dado_retorno, _ = check_data_in_range(
                start_index=1295, end_index=1300, local_path=destino
            )
            if dado_retorno:
                sequencial_do_registro = int(dado_retorno) + 1
                sequencial_do_registro = f'{sequencial_do_registro}'.rjust(6, '0')

            logger.info('iniciou o processo de inclusão do conteudo')
            write_adesao(
                destino,
                produto,
                apolice,
                plano.codigo_plano,
                f'{cnpj_empresa}'.rjust(15, '0'),
                f'{identificacao_nova}'.rjust(20, ' '),
                f'{cpf}'.rjust(15, '0'),
                data_venda,
                data_fim_vigencia,
                f'{nome_cliente}'.ljust(50, ' '),
                f'{rua}'.ljust(50, ' '),
                f'{numero_casa}'.ljust(20, ' '),
                f'{complemento}'.ljust(50, ' '),
                f'{bairro}'.ljust(49, ' '),
                f'{cidade}'.ljust(60, ' '),
                estado,
                cep,
                ddd_residencial,
                telf_residencial,
                f'{ddd_comercial}'.ljust(3, ' '),
                f'{telef_comericial}'.ljust(9, ' '),
                f'{dt_nascimento}'.ljust(8, ' '),
                f'{sexo}'.ljust(1, ' '),
                estado_civil,
                tp_doc,
                num_doc,
                org_exp,
                dt_emissao_doc,
                f'{nova_vl_seguro}'.rjust(15, '0'),
                f'{nova_vl_premio}'.rjust(15, '0'),
                f'{qtd_parcela}'.ljust(2, ' '),
                num_adesao,
                tp_vigencia,
                vida,
                email,
                sequencial_do_registro,
                f'{nova_vl_liquido}'.rjust(15, '0'),
            )
            logger.info('iniciou o processo de inclusão do trailer')
        with open(local_path, 'a') as destino:
            if plano.tipo_plano == EnumTipoPlano.PRATA:
                dado_retorno, _ = check_data_in_range(
                    start_index=1295, end_index=1300, local_path=destino
                )
                if dado_retorno:
                    sequencial_do_registro = int(dado_retorno) + 1
                    sequencial_do_registro = f'{sequencial_do_registro}'.rjust(6, '0')
                escrever_arrecadacao(
                    destino,
                    produto,
                    apolice,
                    plano.codigo_plano,
                    f'{identificacao_nova}'.rjust(20, ' '),
                    '1'.ljust(3, ' '),
                    today_str,
                    f'{nova_vl_premio}'.rjust(15, '0'),
                    f'{cnpj_empresa}'.rjust(15, '0'),
                    sequencial_do_registro,
                )
        with open(local_path, 'a') as destino:
            dado_retorno, _ = check_data_in_range(
                start_index=1295, end_index=1300, local_path=destino
            )
            if dado_retorno:
                sequencial_do_registro = int(dado_retorno) + 1
                sequencial_do_registro = f'{sequencial_do_registro}'.rjust(6, '0')
            count = count_reg(destino) + 2
            count = f'{count}'.rjust(6, '0')
            write_trailer(destino, count, sequencial_do_registro)
        with open(local_path, 'a') as destino:
            ajustar_posicoes(destino)

        # Carregue o arquivo de volta para o S3
        logger.info('Subindo para S3')
        s3.upload_file(local_path, settings.BUCKET_SEGUROS, nomeArquivo)

        if plano.tipo_plano in (EnumTipoPlano.OURO, EnumTipoPlano.DIAMANTE):
            solicitar_cobranca(
                contrato,
                plano,
                cartao_beneficio,
                cliente_cartao,
                premio_bruto=f'{premio_bruto:.2f}',
            )
        logger.info('subiu para S3')

    obrigatorio = plano.obrigatorio
    renovacao_automatica = plano.renovacao_automatica
    logger.info('Criando os dados do beneficio')
    BeneficiosContratado.objects.create(
        id_conta_dock=cliente_cartao.id_conta_dock or '',
        id_cartao_dock=cliente_cartao.id_registro_dock or '',
        contrato_emprestimo=contrato,
        plano=plano,
        nome_operadora=plano.seguradora.get_nome_display(),
        nome_plano=plano.nome,
        obrigatorio=obrigatorio,
        identificacao_segurado=f'{identificacao_seguro + nova_id_seq}',
        valor_plano=f'{float(valor_plano):.2f}',
        premio_bruto=f'{float(premio_bruto):.2f}',
        premio_liquido=f'{float(premio_liquido):.2f}',
        renovacao_automatica=renovacao_automatica,
        cliente=contrato.cliente,
        tipo_plano=plano.get_tipo_plano_display(),
        validade=qtd_parcela,
        qtd_arrecadacao=1,
    )
    logger.info('Finalizou os dados do beneficio')
