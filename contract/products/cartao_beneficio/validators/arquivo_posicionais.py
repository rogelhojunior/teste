from datetime import datetime

from django.conf import settings
from django.db.models import Max

from contract.constants import EnumArquivosSeguros
from contract.products.cartao_beneficio.validators.bissexto import (
    calcular_dias_de_vigencia,
    eh_bissexto,
)
from core.models import ArquivoGenerali
from core.models import BeneficiosContratado


def get_maior_sequencial(nome_archive):
    try:
        maior_sequencial = ArquivoGenerali.objects.filter(
            nmDocumento__contains=nome_archive
        ).aggregate(Max('sequencial'))['sequencial__max']
        return maior_sequencial if maior_sequencial is not None else 0
    except ArquivoGenerali.DoesNotExist:
        return 1


def check_plano(plano):
    if settings.ORIGIN_CLIENT == 'PINE':
        cnpj_empresa = '62144175000120'

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

    elif settings.ORIGIN_CLIENT == 'BRB':
        operacao_sequencial = 'BRBVIDAINSS'
        cnpj_empresa = '33136888000143'

    # TODO: Ajustar quando tiver funcionalidade da Digimais
    elif settings.ORIGIN_CLIENT == 'DIGIMAIS':
        operacao_sequencial = 'BANCOPINEVIDA'
        cnpj_empresa = '62144175000120'

    return operacao_sequencial, cnpj_empresa


def mock(size, char):
    return ''.rjust(size, char)


def write_cancelamento(
    destino,
    produto,
    apolice,
    plano,
    cnpj_empresa,
    identificacao_seguro,
    dt_cancelamento,
    codigo_cancelamento,
    vr_restituicao,
    sequencial_do_registro,
):
    destino.write(
        f"{2}{produto[:5]}{apolice[:10]}{plano[:10]}{cnpj_empresa[:15]}{identificacao_seguro[:20]}{dt_cancelamento}{codigo_cancelamento}{vr_restituicao}{mock(1206, ' ')}{sequencial_do_registro}\n"
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
    motivo='A',
):
    if qtd_parcela == 0:
        qtd_parcela = 1
    plano = f'{plano}'.ljust(10, ' ')
    qtd_parcela = str(qtd_parcela)[:3]
    destino.write(
        f"3{produto[:5]}{apolice[:10]}{plano[:10]}{cnpj_empresa[:15]}{identificacao_nova[:20]}{qtd_parcela}{today_str[:8]}{today_str[:8]}{nova_vl_premio[:15]}{motivo}{mock(1198, ' ')}{sequencial_do_registro[:6]}\n"
    )


def remove_first_line_starting_with(start_text, local_path):
    with open(local_path.name, 'r') as file:
        lines = file.readlines()

    for i, line in enumerate(lines):
        if line.startswith(start_text):
            del lines[i]

    with open(local_path.name, 'w') as file:
        file.writelines(lines)


def check_data_in_last(start_text, start_index, end_index, local_path):
    try:
        with open(local_path.name, 'r') as file:
            lines = file.readlines()

        last_line_index = []

        for i, line in enumerate(lines):
            if line.startswith(start_text):
                last_line_index.append(
                    i
                )  # Atualiza o índice da última linha encontrada

        extracted_text = False
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
            dados = []
            for dado_extraido in lines:
                dados.append(dado_extraido[start_index:end_index])

            first_date = lines[-1][0]
            last_line = max(dados, key=lambda x: int(x))
            extracted_text = last_line

        return extracted_text, first_date
    except Exception:
        return False, False


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


def count_reg(destino):
    with open(destino.name, 'r') as arquivo:
        linhas = arquivo.readlines()
        count = 0

    for line in linhas:
        if not line.startswith(('0', '9')):
            count += 1

    return count


def ajustar_posicoes(destino):
    with open(destino.name, 'r') as arquivo:
        linhas = arquivo.readlines()

    # Ordenar as linhas primeiro pela primeira coluna e depois pela sequência numérica
    linhas_ordenadas = sorted(linhas, key=lambda x: (int(x[0]), int(x[-5:])))
    i_registro = 1
    for i in range(len(linhas_ordenadas)):
        linha = linhas_ordenadas[i]
        novo_dado = f'{i_registro}'.rjust(6, '0')
        # Modifique os caracteres de 1295 a 1300 conforme necessário
        linha_modificada = linha[:1294] + f'{novo_dado}' + linha[1300:]

        # Atualize a linha na lista de linhas ordenadas
        linhas_ordenadas[i] = linha_modificada

        i_registro += 1  # Incrementar o contador

    # Escrever as linhas ordenadas de volta para o arquivo
    with open(destino.name, 'w') as arquivo_ordenado:
        arquivo_ordenado.writelines(linhas_ordenadas)


def write_trailer(destino, count_data, sequencial_do_registro):
    destino.write(
        f"{9}{f'{count_data}'.rjust(6, '0')}{mock(1287, ' ')}{sequencial_do_registro}\n"
    )


def write_initial_content(
    destino, produto, apolice, today_str, sequencial_do_registro, codigo_operacao
):
    destino.write(
        f"{0}{produto[:5]}{apolice[:10]}{today_str[:8]}{sequencial_do_registro}{'1.8'.rjust(6, '0')[:6]}{codigo_operacao[:3]}{mock(1255, ' ')[:1255]}{sequencial_do_registro[:6]}\n"
    )


def calcular_cf(
    plano,
    contract,
    diferenca,
    inicio_vigencia: datetime,
    data_fim_vigencia: datetime,
    beneficios: BeneficiosContratado,
):
    td = diferenca + 1

    if eh_bissexto(datetime.today().year):
        tv = calcular_dias_de_vigencia(
            inicio_vigencia,
            datetime(
                data_fim_vigencia.year,
                data_fim_vigencia.month,
                data_fim_vigencia.day,
            ),
        )
    else:
        tv = calcular_dias_de_vigencia(
            inicio_vigencia,
            datetime(
                data_fim_vigencia.year,
                data_fim_vigencia.month,
                data_fim_vigencia.day,
            ),
        )

    premio_liquido = beneficios.premio_liquido
    cf = float(premio_liquido) - ((float(premio_liquido) / int(tv)) * int(td))
    cf = '{:.2f}'.format(cf)

    return td, tv, cf


def criar_nome_arquivo(operacao_sequencial):
    today = datetime.now()
    maior_sequencial = get_maior_sequencial(operacao_sequencial) or 1
    maior_sequencial_nome = f'{maior_sequencial}'.rjust(6, '0')
    nome_arquivo = (
        f"{operacao_sequencial}_{maior_sequencial_nome}_{today.strftime('%d%m%Y')}.txt"
    )
    return nome_arquivo


def criar_identificacao_nova(identificacao_seguro, nova_id_seq):
    if len(identificacao_seguro + nova_id_seq) < 18:
        zeros_a_adicionar = 18 - len(identificacao_seguro + nova_id_seq)
        nova_id_seq = '0' * zeros_a_adicionar + nova_id_seq
    try:
        identificacao_nova = identificacao_seguro + nova_id_seq
    except Exception:
        identificacao_nova = f'{identificacao_seguro + nova_id_seq.rjust(18 - len(identificacao_seguro), "0")}'[
            :18
        ]

    return identificacao_nova


def identificar_parcela(data_inicio, quantidade_parcelas, data_fim_vigencia):
    # Ajuste do formato para 'YYYYMMDD'
    data_inicio = datetime.strptime(data_inicio, '%Y%m%d')
    data_final = datetime.strptime(data_fim_vigencia, '%d/%m/%Y')
    data_atual = datetime.strptime(datetime.now().strftime('%d/%m/%Y'), '%d/%m/%Y')

    total_dias = (data_final - data_inicio).days
    dias_decorridos = (data_atual - data_inicio).days

    # Calcular a parcela atual
    parcela_atual = int((dias_decorridos / total_dias) * int(quantidade_parcelas))
    if parcela_atual == 0:
        parcela_atual = 1

    return parcela_atual
