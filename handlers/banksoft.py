import json
import logging
import re
from datetime import datetime

import requests
import xmltodict
from dateutil.relativedelta import relativedelta
from django.conf import settings

from api_log.models import Banksoft, LogCliente
from contract.constants import EnumTipoProduto, EnumTipoMargem
from contract.models.contratos import CartaoBeneficio, SaqueComplementar
from contract.products.cartao_beneficio.models.convenio import Convenios
from core.models.cliente import DadosBancarios

logger = logging.getLogger('digitacao')


def real_br_money_mask(my_value):
    if my_value is None:
        return 0
    a = '{:,.2f}'.format(float(my_value))
    b = a.replace(',', 'v')
    c = b.replace('.', ',')
    return c.replace('v', '.')


def get_data_vencimento(dia_vencimento_fatura):
    # Obtém a data atual
    data_atual = datetime.now()

    # Adiciona um mês à data atual
    proxima_data = data_atual + relativedelta(months=1)

    # Se o dia do vencimento da fatura é maior do que o número de dias no próximo mês,
    # ajusta o dia para o último dia do mês
    if int(dia_vencimento_fatura) > proxima_data.day:
        dia_vencimento_fatura = proxima_data.day

    # Constrói a nova data
    nova_data = datetime(proxima_data.year, proxima_data.month, dia_vencimento_fatura)

    # Converte para string no formato desejado
    nova_data_str = nova_data.strftime('%Y-%m-%d')

    print(nova_data_str)
    return nova_data_str


def solicitar_saque_banksoft(contrato, cliente):
    """
    Solicita o saque para o Banksoft
    Integração com o Banco PINE
    """
    # TODO dar uma olhada na arquitetura dos dados bancarios para validar qual melhor forma de consulta-los
    cliente = contrato.cliente
    conta_cliente = DadosBancarios.objects.filter(cliente=cliente).last()

    tipo_produto = ''

    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        cartao_beneficio = CartaoBeneficio.objects.filter(contrato=contrato).first()
        possui_saque = cartao_beneficio.possui_saque
        possui_saque_parcelado = cartao_beneficio.saque_parcelado

        tipo_produto = (
            'CartaoBeneficio'
            if EnumTipoProduto.CARTAO_BENEFICIO == contrato.tipo_produto
            else 'CartaoConsignado'
        )

        convenio = Convenios.objects.filter(pk=cartao_beneficio.convenio.pk).first()

        cliente_cartao_beneficio = contrato.cliente_cartao_contrato.get()

    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        saque_complementar = SaqueComplementar.objects.filter(contrato=contrato).first()

        possui_saque = True
        possui_saque_parcelado = saque_complementar.saque_parcelado
        cliente_cartao_beneficio = saque_complementar.id_cliente_cartao

        if cliente_cartao_beneficio.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
            tipo_produto = 'CartaoBeneficio'
        elif cliente_cartao_beneficio.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
            tipo_produto = 'CartaoConsignado'

        convenio = Convenios.objects.filter(
            pk=cliente_cartao_beneficio.convenio.pk
        ).first()

    cliente_id = cliente.pk
    nome_cliente = cliente.nome_cliente
    nome_cliente_cartao = nome_cliente
    cliente_cpf = cliente.nu_cpf
    cliente_nascimento = f'{str(cliente.dt_nascimento)}'
    cliente_naturalidade = cliente.naturalidade or ''
    cliente_uf = cliente.endereco_uf
    cliente_nome_pai = cliente.nome_pai or ''
    cliente_nome_mae = cliente.nome_mae

    tipo_residencia = 'Outros'
    tempo_residencia = ''
    cliente_tipo_endereco = 'Residencial'
    cliente_cep = cliente.endereco_cep
    cliente_logradouro = cliente.endereco_logradouro
    cliente_endereco_numero = cliente.endereco_numero
    cliente_endereco_complemento = cliente.endereco_complemento
    cliente_endereco_bairro = cliente.endereco_bairro
    cliente_cidade = cliente.endereco_cidade
    cliente_uf = cliente.endereco_uf

    cliente_sexo = cliente.sexo
    cliente_estado_civil = cliente.estado_civil

    if cliente_estado_civil == 'Solteiro(a)':
        cliente_estado_civil = 'Solteiro'
    elif cliente_estado_civil in (
        'Casado(a)',
        'Casado',
    ):
        cliente_estado_civil = 'Casado'
    elif cliente_estado_civil in (
        'Viuvo(a)',
        'Viuvo',
    ):
        cliente_estado_civil = 'Viuvo'
    elif cliente_estado_civil in (
        'Divorciado(a)',
        'Divorciado',
    ):
        cliente_estado_civil = 'Divorciado'
    elif cliente_estado_civil in (
        'Desquitado(a)',
        'Desquitado',
    ):
        cliente_estado_civil = 'Desquitado'
    else:
        cliente_estado_civil = 'NaoDefinido'

    cliente_tipo_telefone = 'Celular'
    cliente_ddd, cliente_celular = cliente.telefone_ddd
    cliente_operadora = 'Outros'
    cliente_email = cliente.email
    cliente_renda = round(cliente.renda, 2)
    cliente_matricula = cliente_cartao_beneficio.numero_matricula
    if cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_SAQUE:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_saque, 2)
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha_saque

    elif cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_COMPRA:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_compra, 2)
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha_compra

    elif cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_saque, 2) + round(
            cliente_cartao_beneficio.margem_compra, 2
        )
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha_compra

    else:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_atual, 2)
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha

    cliente_tipo_instalacao = 'Residencial'
    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        if possui_saque:
            tipo_proposta = 'CartaoMaisSaqueRotativo'
            valor_saque = round(cartao_beneficio.valor_saque, 2)
            valor_financiado = round(cartao_beneficio.valor_financiado, 2)

            cliente_conta_banco = conta_cliente.conta_banco
            cliente_conta_agencia = conta_cliente.conta_agencia
            cliente_conta_numero = conta_cliente.conta_numero
            cliente_conta_digito = conta_cliente.conta_digito

            quantidade_parcelas = 1

        else:
            tipo_proposta = 'CartaoDeCredito'
            cliente_conta_banco = ''
            cliente_conta_agencia = ''
            cliente_conta_numero = ''
            cliente_conta_digito = ''

        valor_disponivel_saque = cartao_beneficio.valor_disponivel_saque
        if possui_saque_parcelado:
            tipo_proposta = 'CartaoMaisSaqueParcelado'
            valor_disponivel_saque = cartao_beneficio.valor_disponivel_saque
            valor_saque = round(cartao_beneficio.valor_saque, 2)
            valor_financiado = round(cartao_beneficio.valor_financiado, 2)

            cliente_conta_banco = conta_cliente.conta_banco
            cliente_conta_agencia = conta_cliente.conta_agencia
            cliente_conta_numero = conta_cliente.conta_numero
            cliente_conta_digito = conta_cliente.conta_digito

            valor_financiado = round(cartao_beneficio.valor_parcela, 2)
            quantidade_parcelas = cartao_beneficio.qtd_parcela_saque_parcelado

    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        tipo_proposta = 'CartaoSaqueComplementar'
        valor_disponivel_saque = saque_complementar.valor_disponivel_saque
        valor_saque = round(saque_complementar.valor_saque, 2)
        valor_financiado = round(saque_complementar.valor_lancado_fatura, 2)

        cliente_conta_banco = conta_cliente.conta_banco
        cliente_conta_agencia = conta_cliente.conta_agencia
        cliente_conta_numero = conta_cliente.conta_numero
        cliente_conta_digito = conta_cliente.conta_digito
        quantidade_parcelas = 1
        if possui_saque_parcelado:
            tipo_proposta = 'CartaoSaqueComplementar'
            valor_financiado = round(saque_complementar.valor_parcela, 2)
            quantidade_parcelas = saque_complementar.qtd_parcela_saque_parcelado

    limite_pre_aprovado = round(contrato.limite_pre_aprovado, 2) or ''
    possui_cnh = 'true' if cliente.documento_tipo == 'CNH' else 'false'
    cliente_documento_numero = cliente.documento_numero
    cliente_documento_data_emissao = f'{cliente.documento_data_emissao}'
    cliente_documento_orgao_emissor = cliente.documento_orgao_emissor
    cliente_documento_uf = cliente.get_documento_uf_display()

    contrato_cadastro = contrato.criado_em
    contrato_cadastro = contrato_cadastro.strftime('%Y-%m-%d')
    contrato_id = contrato.pk

    vencimento_fatura = f'{get_data_vencimento(int(contrato.vencimento_fatura))}'

    codigo_empregador_externo = convenio.pk

    if contrato.contrato_digitacao_manual or (
        (cliente_cartao_beneficio.folha is None or cliente_cartao_beneficio.folha == '')
        and (
            cliente_cartao_beneficio.folha_compra is None
            or cliente_cartao_beneficio.folha_compra == ''
        )
        and (
            cliente_cartao_beneficio.folha_saque is None
            or cliente_cartao_beneficio.folha_saque == ''
        )
    ):
        pCodigoOrgaoExterno = 999

    banksoft_usuario_externo = 'amigoz'  # TODO: Verificar quem é a promotora parceira

    codigo_historico_cliente = 0
    codigo_proponente = 0
    tipo_pessoa = 'Fisica'

    nome_convenio = f'{convenio.nome}'
    vr_iof = contrato.vr_iof_total
    cet_mes = contrato.cet_mes

    url = settings.URL_BANKSOFT

    import textwrap

    payload_part1 = textwrap.dedent(f"""
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tem="http://tempuri.org/">
      <soap:Body>
        <IncluirPropostaCartaoCompleto xmlns="http://tempuri.org/">
          <pLoginUsuario>{settings.BANKSOFT_USER}</pLoginUsuario>
          <pSenha>{settings.BANKSOFT_PASS}</pSenha>
          <pDadosCliente>
            <CodigoCliente>{cliente_id}</CodigoCliente>
            <IDExterno>{contrato_id}</IDExterno>
            <ChaveExterna></ChaveExterna>
            <CodigoHistoricoCliente>{codigo_historico_cliente}</CodigoHistoricoCliente>
            <CodigoProponente>{codigo_proponente}</CodigoProponente>
            <DadosCliente>
              <NomeCliente>{nome_cliente}</NomeCliente>
              <NomeClienteCartao>{nome_cliente_cartao}</NomeClienteCartao>
              <TipoPessoa>{tipo_pessoa}</TipoPessoa>
              <CPF>{cliente_cpf}</CPF>
              <DataNascimento>{cliente_nascimento}</DataNascimento>
              <Registro>
                <Numero>{cliente_documento_numero}</Numero>
                <DataEmissao>{cliente_documento_data_emissao}</DataEmissao>
                <LocalEmissao>{cliente_documento_orgao_emissor}</LocalEmissao>
                <UFEmissao>{cliente_documento_uf}</UFEmissao>
              </Registro>
              <CidadeNatal>{cliente_naturalidade}</CidadeNatal>
              <UFNatal>{cliente_uf}</UFNatal>
              <Sexo>{cliente_sexo}</Sexo>
              <EstadoCivil>{cliente_estado_civil}</EstadoCivil>
              <TipoResidencia>{tipo_residencia}</TipoResidencia>
              <TempoResidencia>{tempo_residencia}</TempoResidencia>
              <NomePai>{cliente_nome_pai}</NomePai>
              <NomeMae>{cliente_nome_mae}</NomeMae>
              <DadosEmpresa>
                <CNPJ></CNPJ>
                <NomeEmpresa>{nome_convenio}</NomeEmpresa>
                <DataAdmissao>2010-01-01</DataAdmissao>
                <CodigoProfissao>0</CodigoProfissao>
                <DescricaoProfissao></DescricaoProfissao>
                <Cargo></Cargo>
                <Renda>{cliente_renda}</Renda>
                <OutrasRendas>0</OutrasRendas>
                <NumeroBeneficio>{cliente_matricula}</NumeroBeneficio>
                <IdentificadorMargem></IdentificadorMargem>
                <MesAno_ContraCheque></MesAno_ContraCheque>
                <NaturezaOcupacao>NaoDefinido</NaturezaOcupacao>
              </DadosEmpresa>
              <Enderecos>
                <Endereco>
                  <TipoEndereco>{cliente_tipo_endereco}</TipoEndereco>
                  <CEP>{cliente_cep}</CEP>
                  <Logradouro>{cliente_logradouro}</Logradouro>
                  <Numero>{cliente_endereco_numero}</Numero>
                  <Complemento>{cliente_endereco_complemento}</Complemento>
                  <Bairro>{cliente_endereco_bairro}</Bairro>
                  <Cidade>{cliente_cidade}</Cidade>
                  <UF>{cliente_uf}</UF>
                  <Latitude></Latitude>
                  <Longitude></Longitude>
                </Endereco>
              </Enderecos>
    """)

    if possui_saque or possui_saque_parcelado:
        cliente_tipo_conta = 'CCIndividual'

        payload_part2 = textwrap.dedent(f"""\
                      <Telefones>
                        <Telefone>
                          <TipoTelefone>{cliente_tipo_telefone}</TipoTelefone>
                          <DDD>{cliente_ddd}</DDD>
                          <NumeroTelefone>{cliente_celular}</NumeroTelefone>
                          <Operadora>{cliente_operadora}</Operadora>
                        </Telefone>
                      </Telefones>
                      <DadosCadastro>
                        <DataDeCadastro>{contrato_cadastro}</DataDeCadastro>
                        <UsuarioInclusao></UsuarioInclusao>
                        <DataDeAlteracao>{contrato_cadastro}</DataDeAlteracao>
                        <UsuarioAlteracao></UsuarioAlteracao>
                      </DadosCadastro>
                      <Email>{cliente_email}</Email>
                      <RamoAtividade></RamoAtividade>
                      <TipoInstalacao>{cliente_tipo_instalacao}</TipoInstalacao>
                      <PossuiCNH>{possui_cnh}</PossuiCNH>
                    </DadosCliente>
                    <NomeRef1></NomeRef1>
                    <DDDRef1></DDDRef1>
                    <FoneRef1></FoneRef1>
                    <NomeRef2></NomeRef2>
                    <DDDRef2></DDDRef2>
                    <FoneRef2></FoneRef2>
                    <ReferenciaBancaria>
                      <TipoConta>{cliente_tipo_conta}</TipoConta>
                      <NumeroBanco>{cliente_conta_banco}</NumeroBanco>
                      <Agencia>{cliente_conta_agencia}</Agencia>
                      <Conta>{cliente_conta_numero}</Conta>
                      <DVConta>{cliente_conta_digito}</DVConta>
                    </ReferenciaBancaria>
                    <DadosConjuge>
                      <NomeConjuge></NomeConjuge>
                      <CPFConjuge></CPFConjuge>
                      <DataNascimentoConjuge>2079-02-02</DataNascimentoConjuge>
                      <RGConjuge></RGConjuge>
                      <RendaConjuge>0</RendaConjuge>
                    </DadosConjuge>
                  </pDadosCliente>
                  <pTipoProposta>{tipo_proposta}</pTipoProposta>
                  <pTipoProduto>{tipo_produto}</pTipoProduto>
                  <pCodigoEmpregadorExterno>{codigo_empregador_externo}</pCodigoEmpregadorExterno>
                  <pCodigoOrgaoExterno>{pCodigoOrgaoExterno}</pCodigoOrgaoExterno>
                  <pCodigoUsuarioExterno>{banksoft_usuario_externo}</pCodigoUsuarioExterno>
                  <pValorLimiteTotal>{limite_pre_aprovado}</pValorLimiteTotal>
                  <pValorLimiteSaque>{valor_disponivel_saque}</pValorLimiteSaque>
                  <pValorLimiteCompra>{limite_pre_aprovado}</pValorLimiteCompra>
                  <pValorRMC>{cliente_margem_atual}</pValorRMC>
                  <pValorSaque>{valor_saque}</pValorSaque>
                  <pValorParcela>{valor_financiado}</pValorParcela>
                  <pQuantidadeParcelas>{quantidade_parcelas}</pQuantidadeParcelas>
                  <pValorIOF>{vr_iof}</pValorIOF>
                  <pValorTC>0</pValorTC>
                  <pIDFormalizacao></pIDFormalizacao>
                  <pNumeroCartao>{cliente_cartao_beneficio.id_conta_dock}</pNumeroCartao>
                  <pNumeroContrato>{contrato.pk}</pNumeroContrato>
                  <pNumeroOperacaoConsignada></pNumeroOperacaoConsignada>
            """)
    else:
        payload_part2 = textwrap.dedent(f"""\
                  <Telefones>
                    <Telefone>
                      <TipoTelefone>{cliente_tipo_telefone}</TipoTelefone>
                      <DDD>{cliente_ddd}</DDD>
                      <NumeroTelefone>{cliente_celular}</NumeroTelefone>
                      <Operadora>{cliente_operadora}</Operadora>
                    </Telefone>
                  </Telefones>
                  <DadosCadastro>
                    <DataDeCadastro>{contrato_cadastro}</DataDeCadastro>
                    <UsuarioInclusao></UsuarioInclusao>
                    <DataDeAlteracao>{contrato_cadastro}</DataDeAlteracao>
                    <UsuarioAlteracao></UsuarioAlteracao>
                  </DadosCadastro>
                  <Email>{cliente_email}</Email>
                  <RamoAtividade></RamoAtividade>
                  <TipoInstalacao>{cliente_tipo_instalacao}</TipoInstalacao>
                  <PossuiCNH>{possui_cnh}</PossuiCNH>
                </DadosCliente>
                <NomeRef1></NomeRef1>
                <DDDRef1></DDDRef1>
                <FoneRef1></FoneRef1>
                <NomeRef2></NomeRef2>
                <DDDRef2></DDDRef2>
                <FoneRef2></FoneRef2>
                <ReferenciaBancaria>
                  <TipoConta>CCIndividual</TipoConta>
                  <NumeroBanco></NumeroBanco>
                  <Agencia></Agencia>
                  <Conta></Conta>
                  <DVConta></DVConta>
                </ReferenciaBancaria>
                <DadosConjuge>
                  <NomeConjuge></NomeConjuge>
                  <CPFConjuge></CPFConjuge>
                  <DataNascimentoConjuge>2079-02-02</DataNascimentoConjuge>
                  <RGConjuge></RGConjuge>
                  <RendaConjuge>0</RendaConjuge>
                </DadosConjuge>
              </pDadosCliente>
              <pTipoProposta>{tipo_proposta}</pTipoProposta>
              <pTipoProduto>{tipo_produto}</pTipoProduto>
              <pCodigoEmpregadorExterno>{codigo_empregador_externo}</pCodigoEmpregadorExterno>
              <pCodigoOrgaoExterno>{pCodigoOrgaoExterno}</pCodigoOrgaoExterno>
              <pCodigoUsuarioExterno>{banksoft_usuario_externo}</pCodigoUsuarioExterno>
              <pValorLimiteTotal>{limite_pre_aprovado}</pValorLimiteTotal>
              <pValorLimiteSaque>{valor_disponivel_saque}</pValorLimiteSaque>
              <pValorLimiteCompra>{limite_pre_aprovado}</pValorLimiteCompra>
              <pValorRMC>{cliente_margem_atual}</pValorRMC>
              <pValorSaque>0</pValorSaque>
              <pValorParcela>0</pValorParcela>
              <pQuantidadeParcelas>0</pQuantidadeParcelas>
              <pValorIOF>0</pValorIOF>
              <pValorTC>0</pValorTC>
              <pIDFormalizacao></pIDFormalizacao>
              <pNumeroCartao>{cliente_cartao_beneficio.id_conta_dock}</pNumeroCartao>
              <pNumeroContrato>{contrato.pk}</pNumeroContrato>
              <pNumeroOperacaoConsignada></pNumeroOperacaoConsignada>
        """)

    if (
        possui_saque
        and possui_saque_parcelado
        or not possui_saque
        and possui_saque_parcelado
    ):
        parcelas = []
        vencimento_fatura = datetime.strptime(vencimento_fatura, '%Y-%m-%d')
        for i in range(1, quantidade_parcelas + 1):
            next_vencimento = vencimento_fatura + relativedelta(months=+(i - 1))
            next_vencimento = next_vencimento.strftime('%Y-%m-%d')
            parcela = textwrap.dedent(f"""\
                    <PropostaParcela>
                          <NumeroProposta>{contrato.pk}</NumeroProposta>
                          <NumeroParcela>{i}</NumeroParcela>
                          <ValorParcela>{valor_financiado}</ValorParcela>
                          <DataVencimento>{next_vencimento}</DataVencimento>
                          <ValorPrincipal>{valor_financiado}</ValorPrincipal>
                          <ValorJuros>{cet_mes}</ValorJuros>
                          <NumeroTitulo></NumeroTitulo>
                    </PropostaParcela>
                """)
            parcelas.append(parcela)
        payload_part3 = (
            '<pListaParcelas>\n'
            + '\n'.join(parcelas)
            + '\n</pListaParcelas>\n</IncluirPropostaCartaoCompleto>\n</soap:Body>\n</soap:Envelope>'
        )
    elif possui_saque:
        payload_part3 = textwrap.dedent(f"""\
                        <pListaParcelas>
                            <PropostaParcela>
                                  <NumeroProposta>{contrato.pk}</NumeroProposta>
                                  <NumeroParcela>1</NumeroParcela>
                                  <ValorParcela>{valor_financiado}</ValorParcela>
                                  <DataVencimento>{vencimento_fatura}</DataVencimento>
                                  <ValorPrincipal>{valor_financiado}</ValorPrincipal>
                                  <ValorJuros>{cet_mes}</ValorJuros>
                                  <NumeroTitulo></NumeroTitulo>
                            </PropostaParcela>
                      </pListaParcelas>
                    </IncluirPropostaCartaoCompleto>
                  </soap:Body>
                </soap:Envelope>
                """)
    else:
        payload_part3 = textwrap.dedent(f"""\
                <pListaParcelas>
                    <PropostaParcela>
                          <NumeroProposta>{contrato.pk}</NumeroProposta>
                          <NumeroParcela>0</NumeroParcela>
                          <ValorParcela>0</ValorParcela>
                          <DataVencimento>2079-02-02</DataVencimento>
                          <ValorPrincipal>0</ValorPrincipal>
                          <ValorJuros>0</ValorJuros>
                          <NumeroTitulo></NumeroTitulo>
                    </PropostaParcela>
              </pListaParcelas>
            </IncluirPropostaCartaoCompleto>
          </soap:Body>
        </soap:Envelope>
        """)

    payload = payload_part1 + payload_part2 + payload_part3
    headers = {
        'Content-Type': 'text/xml',
        'Cookie': 'cookiesession1=678A8C3454B02B7D5DA019EF76138A4E',
    }

    response = requests.request('POST', url, headers=headers, data=payload)
    xml = response.text
    print(xml)
    xml_dict = xmltodict.parse(xml)
    json_str = json.dumps(xml_dict, indent=2)
    log_api_id = LogCliente.objects.filter(cliente=cliente).first()
    Banksoft.objects.create(
        log_api_id=log_api_id.pk,
        cliente=contrato.cliente,
        payload_enviado=payload,
        contrato=contrato.pk,
        payload=json_str,
        tipo_chamada='Solicitação Saque',
    )
    json_formated = json.loads(json_str)
    try:
        numero_da_proposta = json_formated['soap:Envelope']['soap:Body'][
            'IncluirPropostaCartaoCompletoResponse'
        ]['IncluirPropostaCartaoCompletoResult']['NumeroProposta']
        retorno = json_formated['soap:Envelope']['soap:Body'][
            'IncluirPropostaCartaoCompletoResponse'
        ]['IncluirPropostaCartaoCompletoResult']['StatusProcessamento']['Status']
        mensagem_retorno = json_formated['soap:Envelope']['soap:Body'][
            'IncluirPropostaCartaoCompletoResponse'
        ]['IncluirPropostaCartaoCompletoResult']['StatusProcessamento']['MensagemErro']
        retorno_status = 200 if retorno == 'true' else 400
    except Exception as e:
        logger.error(f'Erro recuperar retorno banksoft (solicitar_saque_banksoft): {e}')
        return 400

    try:
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            cartao_beneficio.retorno_solicitacao_saque = str(mensagem_retorno)
            cartao_beneficio.numero_proposta_banksoft = str(numero_da_proposta)
            cartao_beneficio.save(
                update_fields=[
                    'numero_proposta_banksoft',
                    'retorno_solicitacao_saque',
                ]
            )
            cartao_beneficio.refresh_from_db()

        elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            saque_complementar.retorno_solicitacao_saque = str(mensagem_retorno)
            saque_complementar.numero_proposta_banksoft = str(numero_da_proposta)
            saque_complementar.save(
                update_fields=[
                    'numero_proposta_banksoft',
                    'retorno_solicitacao_saque',
                ]
            )
            saque_complementar.refresh_from_db()
        contrato.save()
    except Exception as e:
        logger.error(
            f'Erro ao salvar dados no contrato (solicitar_saque_banksoft): {e}'
        )

    return retorno_status


def comissionamento_banksoft(contrato):
    """
    Solicita o saque para o Banksoft
    Integração com o Banco PINE
    """
    # TODO dar uma olhada na arquitetura dos dados bancarios para validar qual melhor forma de consulta-los
    cliente = contrato.cliente
    conta_cliente = DadosBancarios.objects.filter(cliente=cliente).first()

    cliente_cartao_beneficio = contrato.cliente_cartao_contrato.get()
    convenio = Convenios.objects.filter(pk=cliente_cartao_beneficio.convenio.pk).first()
    cartao_beneficio = None
    saque_complementar = None
    tipo_produto = ''
    if contrato.tipo_produto in (
        EnumTipoProduto.CARTAO_BENEFICIO,
        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
        EnumTipoProduto.CARTAO_CONSIGNADO,
    ):
        cartao_beneficio = CartaoBeneficio.objects.filter(contrato=contrato).first()

        if contrato.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
            tipo_produto = 'CartaoBeneficio'
        elif contrato.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
            tipo_produto = 'CartaoConsignado'

        if cartao_beneficio.possui_saque or cartao_beneficio.saque_parcelado:
            valor_saque = round(cartao_beneficio.valor_saque, 2)
            valor_financiado = round(cartao_beneficio.valor_financiado, 2)
            cliente_conta_banco = conta_cliente.conta_banco
            cliente_conta_agencia = conta_cliente.conta_agencia
            cliente_conta_numero = conta_cliente.conta_numero
            cliente_conta_digito = conta_cliente.conta_digito
            tipo_proposta = 'CartaoMaisSaqueRotativo'

            quantidade_parcelas = 1

        else:
            valor_saque = ''
            valor_financiado = ''
            cliente_conta_banco = ''
            cliente_conta_agencia = ''
            cliente_conta_numero = ''
            cliente_conta_digito = ''

            tipo_proposta = 'CartaoDeCredito'

        if cartao_beneficio.saque_parcelado:
            tipo_proposta = 'CartaoMaisSaqueParcelado'

            valor_financiado = round(cartao_beneficio.valor_parcela, 2)
            quantidade_parcelas = cartao_beneficio.qtd_parcela_saque_parcelado
        valor_disponivel_saque = cartao_beneficio.valor_disponivel_saque

    elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
        saque_complementar = SaqueComplementar.objects.filter(contrato=contrato).first()
        valor_saque = round(saque_complementar.valor_saque, 2)
        valor_financiado = round(saque_complementar.valor_lancado_fatura, 2)
        # limite_disponivel_total = round(saque_complementar.limite_disponivel_total, 2)
        valor_disponivel_saque = saque_complementar.valor_disponivel_saque
        tipo_proposta = 'CartaoSaqueComplementar'
        cliente_cartao_beneficio = saque_complementar.id_cliente_cartao

        if cliente_cartao_beneficio.tipo_produto == EnumTipoProduto.CARTAO_BENEFICIO:
            tipo_produto = 'CartaoBeneficio'
        elif cliente_cartao_beneficio.tipo_produto == EnumTipoProduto.CARTAO_CONSIGNADO:
            tipo_produto = 'CartaoConsignado'

        cliente_conta_banco = conta_cliente.conta_banco
        cliente_conta_agencia = conta_cliente.conta_agencia
        cliente_conta_numero = conta_cliente.conta_numero
        cliente_conta_digito = conta_cliente.conta_digito

        quantidade_parcelas = 1

        if saque_complementar.saque_parcelado:
            valor_financiado = round(saque_complementar.valor_parcela, 2)
            quantidade_parcelas = saque_complementar.qtd_parcela_saque_parcelado

    cliente_id = cliente.pk
    nome_cliente = cliente.nome_cliente
    nome_cliente_cartao = nome_cliente
    cliente_cpf = cliente.nu_cpf
    cliente_nascimento = f'{str(cliente.dt_nascimento)}'
    cliente_naturalidade = cliente.naturalidade or ''
    cliente_uf = cliente.endereco_uf
    cliente_nome_pai = cliente.nome_pai or ''
    cliente_nome_mae = cliente.nome_mae

    tipo_residencia = 'Outros'
    tempo_residencia = ''
    cliente_tipo_endereco = 'Residencial'
    cliente_cep = cliente.endereco_cep
    cliente_logradouro = cliente.endereco_logradouro
    cliente_endereco_numero = cliente.endereco_numero
    cliente_endereco_complemento = cliente.endereco_complemento
    cliente_endereco_bairro = cliente.endereco_bairro
    cliente_cidade = cliente.endereco_cidade
    cliente_uf = cliente.endereco_uf

    cliente_sexo = cliente.sexo
    cliente_estado_civil = cliente.estado_civil

    if cliente_estado_civil == 'Solteiro(a)':
        cliente_estado_civil = 'Solteiro'
    elif cliente_estado_civil in (
        'Casado(a)',
        'Casado',
    ):
        cliente_estado_civil = 'Casado'
    elif cliente_estado_civil in (
        'Viuvo(a)',
        'Viuvo',
    ):
        cliente_estado_civil = 'Viuvo'
    elif cliente_estado_civil in (
        'Divorciado(a)',
        'Divorciado',
    ):
        cliente_estado_civil = 'Divorciado'
    elif cliente_estado_civil in (
        'Desquitado(a)',
        'Desquitado',
    ):
        cliente_estado_civil = 'Desquitado'
    else:
        cliente_estado_civil = 'NaoDefinido'

    cliente_tipo_telefone = 'Celular'
    cliente_ddd, cliente_celular = cliente.telefone_ddd
    cliente_operadora = 'Outros'
    cliente_email = cliente.email
    cliente_renda = round(cliente.renda, 2)
    cliente_matricula = cliente_cartao_beneficio.numero_matricula
    if cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_SAQUE:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_saque, 2)
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha_saque

    elif cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_COMPRA:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_compra, 2)
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha_compra

    elif cliente_cartao_beneficio.tipo_margem == EnumTipoMargem.MARGEM_UNIFICADA:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_saque, 2) + round(
            cliente_cartao_beneficio.margem_compra, 2
        )
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha_compra

    else:
        cliente_margem_atual = round(cliente_cartao_beneficio.margem_atual, 2)
        pCodigoOrgaoExterno = cliente_cartao_beneficio.folha

    cliente_tipo_instalacao = 'Residencial'
    cliente_tipo_conta = 'CCIndividual'

    limite_pre_aprovado = round(contrato.limite_pre_aprovado, 2)
    possui_cnh = 'true' if cliente.documento_tipo == 'CNH' else 'false'
    cliente_documento_numero = cliente.documento_numero
    cliente_documento_data_emissao = f'{cliente.documento_data_emissao}'
    cliente_documento_orgao_emissor = cliente.documento_orgao_emissor
    cliente_documento_uf = cliente.get_documento_uf_display()

    contrato_cadastro = contrato.criado_em
    contrato_cadastro = contrato_cadastro.strftime('%Y-%m-%d')
    contrato_id = contrato.pk

    vencimento_fatura = f'{get_data_vencimento(int(contrato.vencimento_fatura))}'
    codigo_empregador_externo = convenio.pk
    if contrato.contrato_digitacao_manual or (
        cliente_cartao_beneficio.folha is None
        and cliente_cartao_beneficio.folha_compra is None
        and cliente_cartao_beneficio.folha_saque is None
    ):
        pCodigoOrgaoExterno = 999
    banksoft_usuario_externo = contrato.corban.pk
    codigo_historico_cliente = 0
    codigo_proponente = 0
    tipo_pessoa = 'Fisica'

    nome_convenio = f'{convenio.nome}'
    vr_iof = contrato.vr_iof_total
    cet_mes = contrato.cet_mes

    url = settings.URL_COMISSAO

    import textwrap

    payload_part1 = textwrap.dedent(f"""
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:tem="http://tempuri.org/">
      <soap:Body>
        <IncluirPropostaCartaoCompleto xmlns="http://tempuri.org/">
          <pLoginUsuario>{settings.BANKSOFT_USER}</pLoginUsuario>
          <pSenha>{settings.BANKSOFT_PASS}</pSenha>
          <pDadosCliente>
            <CodigoCliente>{cliente_id}</CodigoCliente>
            <IDExterno>{contrato_id}</IDExterno>
            <ChaveExterna></ChaveExterna>
            <CodigoHistoricoCliente>{codigo_historico_cliente}</CodigoHistoricoCliente>
            <CodigoProponente>{codigo_proponente}</CodigoProponente>
            <DadosCliente>
              <NomeCliente>{nome_cliente}</NomeCliente>
              <NomeClienteCartao>{nome_cliente_cartao}</NomeClienteCartao>
              <TipoPessoa>{tipo_pessoa}</TipoPessoa>
              <CPF>{cliente_cpf}</CPF>
              <DataNascimento>{cliente_nascimento}</DataNascimento>
              <Registro>
                <Numero>{cliente_documento_numero}</Numero>
                <DataEmissao>{cliente_documento_data_emissao}</DataEmissao>
                <LocalEmissao>{cliente_documento_orgao_emissor}</LocalEmissao>
                <UFEmissao>{cliente_documento_uf}</UFEmissao>
              </Registro>
              <CidadeNatal>{cliente_naturalidade}</CidadeNatal>
              <UFNatal>{cliente_uf}</UFNatal>
              <Sexo>{cliente_sexo}</Sexo>
              <EstadoCivil>{cliente_estado_civil}</EstadoCivil>
              <TipoResidencia>{tipo_residencia}</TipoResidencia>
              <TempoResidencia>{tempo_residencia}</TempoResidencia>
              <NomePai>{cliente_nome_pai}</NomePai>
              <NomeMae>{cliente_nome_mae}</NomeMae>
              <DadosEmpresa>
                <CNPJ></CNPJ>
                <NomeEmpresa>{nome_convenio}</NomeEmpresa>
                <DataAdmissao>2010-01-01</DataAdmissao>
                <CodigoProfissao>0</CodigoProfissao>
                <DescricaoProfissao></DescricaoProfissao>
                <Cargo></Cargo>
                <Renda>{cliente_renda}</Renda>
                <OutrasRendas>0</OutrasRendas>
                <NumeroBeneficio>{cliente_matricula}</NumeroBeneficio>
                <IdentificadorMargem></IdentificadorMargem>
                <MesAno_ContraCheque></MesAno_ContraCheque>
                <NaturezaOcupacao>NaoDefinido</NaturezaOcupacao>
              </DadosEmpresa>
              <Enderecos>
                <Endereco>
                  <TipoEndereco>{cliente_tipo_endereco}</TipoEndereco>
                  <CEP>{cliente_cep}</CEP>
                  <Logradouro>{cliente_logradouro}</Logradouro>
                  <Numero>{cliente_endereco_numero}</Numero>
                  <Complemento>{cliente_endereco_complemento}</Complemento>
                  <Bairro>{cliente_endereco_bairro}</Bairro>
                  <Cidade>{cliente_cidade}</Cidade>
                  <UF>{cliente_uf}</UF>
                  <Latitude></Latitude>
                  <Longitude></Longitude>
                </Endereco>
              </Enderecos>
    """)

    if cartao_beneficio is None:
        if saque_complementar is not None:
            payload_part2 = textwrap.dedent(f"""\
                      <Telefones>
                        <Telefone>
                          <TipoTelefone>{cliente_tipo_telefone}</TipoTelefone>
                          <DDD>{cliente_ddd}</DDD>
                          <NumeroTelefone>{cliente_celular}</NumeroTelefone>
                          <Operadora>{cliente_operadora}</Operadora>
                        </Telefone>
                      </Telefones>
                      <DadosCadastro>
                        <DataDeCadastro>{contrato_cadastro}</DataDeCadastro>
                        <UsuarioInclusao></UsuarioInclusao>
                        <DataDeAlteracao>{contrato_cadastro}</DataDeAlteracao>
                        <UsuarioAlteracao></UsuarioAlteracao>
                      </DadosCadastro>
                      <Email>{cliente_email}</Email>
                      <RamoAtividade></RamoAtividade>
                      <TipoInstalacao>{cliente_tipo_instalacao}</TipoInstalacao>
                      <PossuiCNH>{possui_cnh}</PossuiCNH>
                    </DadosCliente>
                    <NomeRef1></NomeRef1>
                    <DDDRef1></DDDRef1>
                    <FoneRef1></FoneRef1>
                    <NomeRef2></NomeRef2>
                    <DDDRef2></DDDRef2>
                    <FoneRef2></FoneRef2>
                    <ReferenciaBancaria>
                      <TipoConta>{cliente_tipo_conta}</TipoConta>
                      <NumeroBanco>{cliente_conta_banco}</NumeroBanco>
                      <Agencia>{cliente_conta_agencia}</Agencia>
                      <Conta>{cliente_conta_numero}</Conta>
                      <DVConta>{cliente_conta_digito}</DVConta>
                    </ReferenciaBancaria>
                    <DadosConjuge>
                      <NomeConjuge></NomeConjuge>
                      <CPFConjuge></CPFConjuge>
                      <DataNascimentoConjuge>2079-02-02</DataNascimentoConjuge>
                      <RGConjuge></RGConjuge>
                      <RendaConjuge>0</RendaConjuge>
                    </DadosConjuge>
                  </pDadosCliente>
                  <pTipoProposta>{tipo_proposta}</pTipoProposta>
                  <pTipoProduto>{tipo_produto}</pTipoProduto>
                  <pCodigoEmpregadorExterno>{codigo_empregador_externo}</pCodigoEmpregadorExterno>
                  <pCodigoOrgaoExterno>{pCodigoOrgaoExterno}</pCodigoOrgaoExterno>
                  <pCodigoUsuarioExterno>{banksoft_usuario_externo}</pCodigoUsuarioExterno>
                  <pValorLimiteTotal>{limite_pre_aprovado}</pValorLimiteTotal>
                  <pValorLimiteSaque>{valor_disponivel_saque}</pValorLimiteSaque>
                  <pValorLimiteCompra>{limite_pre_aprovado}</pValorLimiteCompra>
                  <pValorRMC>{cliente_margem_atual}</pValorRMC>
                  <pValorSaque>{valor_saque}</pValorSaque>
                  <pValorParcela>{valor_financiado}</pValorParcela>
                  <pQuantidadeParcelas>{quantidade_parcelas}</pQuantidadeParcelas>
                  <pValorIOF>{vr_iof}</pValorIOF>
                  <pValorTC>0</pValorTC>
                  <pNumeroCartao>{cliente_cartao_beneficio.id_conta_dock}</pNumeroCartao>
                  <pNumeroContrato>{contrato.pk}</pNumeroContrato>
                  <pNumeroOperacaoConsignada></pNumeroOperacaoConsignada>
            """)

            if saque_complementar.saque_parcelado:
                parcelas = []
                vencimento_fatura = datetime.strptime(vencimento_fatura, '%Y-%m-%d')
                for i in range(1, quantidade_parcelas + 1):
                    next_vencimento = vencimento_fatura + relativedelta(months=+(i - 1))
                    next_vencimento = next_vencimento.strftime('%Y-%m-%d')
                    parcela = textwrap.dedent(f"""\
                        <PropostaParcela>
                              <NumeroProposta>{contrato.pk}</NumeroProposta>
                              <NumeroParcela>{i}</NumeroParcela>
                              <ValorParcela>{valor_financiado}</ValorParcela>
                              <DataVencimento>{next_vencimento}</DataVencimento>
                              <ValorPrincipal>{valor_financiado}</ValorPrincipal>
                              <ValorJuros>{cet_mes}</ValorJuros>
                              <NumeroTitulo></NumeroTitulo>
                        </PropostaParcela>
                    """)
                    parcelas.append(parcela)
                payload_part3 = (
                    '<pListaParcelas>\n'
                    + '\n'.join(parcelas)
                    + '\n</pListaParcelas>\n</IncluirPropostaCartaoCompleto>\n</soap:Body>\n</soap:Envelope>'
                )
            else:
                payload_part3 = textwrap.dedent(f"""\
                        <pListaParcelas>
                            <PropostaParcela>
                                  <NumeroProposta>{contrato.pk}</NumeroProposta>
                                  <NumeroParcela>1</NumeroParcela>
                                  <ValorParcela>{valor_financiado}</ValorParcela>
                                  <DataVencimento>{vencimento_fatura}</DataVencimento>
                                  <ValorPrincipal>{valor_financiado}</ValorPrincipal>
                                  <ValorJuros>{cet_mes}</ValorJuros>
                                  <NumeroTitulo></NumeroTitulo>
                            </PropostaParcela>
                      </pListaParcelas>
                    </IncluirPropostaCartaoCompleto>
                  </soap:Body>
                </soap:Envelope>
                """)

    elif not cartao_beneficio.possui_saque and not cartao_beneficio.saque_parcelado:
        payload_part2 = textwrap.dedent(f"""\
                      <Telefones>
                        <Telefone>
                          <TipoTelefone>{cliente_tipo_telefone}</TipoTelefone>
                          <DDD>{cliente_ddd}</DDD>
                          <NumeroTelefone>{cliente_celular}</NumeroTelefone>
                          <Operadora>{cliente_operadora}</Operadora>
                        </Telefone>
                      </Telefones>
                      <DadosCadastro>
                        <DataDeCadastro>{contrato_cadastro}</DataDeCadastro>
                        <UsuarioInclusao></UsuarioInclusao>
                        <DataDeAlteracao>{contrato_cadastro}</DataDeAlteracao>
                        <UsuarioAlteracao></UsuarioAlteracao>
                      </DadosCadastro>
                      <Email>{cliente_email}</Email>
                      <RamoAtividade></RamoAtividade>
                      <TipoInstalacao>{cliente_tipo_instalacao}</TipoInstalacao>
                      <PossuiCNH>{possui_cnh}</PossuiCNH>
                    </DadosCliente>
                    <NomeRef1></NomeRef1>
                    <DDDRef1></DDDRef1>
                    <FoneRef1></FoneRef1>
                    <NomeRef2></NomeRef2>
                    <DDDRef2></DDDRef2>
                    <FoneRef2></FoneRef2>
                    <ReferenciaBancaria>
                      <TipoConta>CCIndividual</TipoConta>
                      <NumeroBanco></NumeroBanco>
                      <Agencia></Agencia>
                      <Conta></Conta>
                      <DVConta></DVConta>
                    </ReferenciaBancaria>
                    <DadosConjuge>
                      <NomeConjuge></NomeConjuge>
                      <CPFConjuge></CPFConjuge>
                      <DataNascimentoConjuge>2079-02-02</DataNascimentoConjuge>
                      <RGConjuge></RGConjuge>
                      <RendaConjuge>0</RendaConjuge>
                    </DadosConjuge>
                  </pDadosCliente>
                  <pTipoProposta>{tipo_proposta}</pTipoProposta>
                  <pTipoProduto>{tipo_produto}</pTipoProduto>
                  <pCodigoEmpregadorExterno>{codigo_empregador_externo}</pCodigoEmpregadorExterno>
                  <pCodigoOrgaoExterno>{pCodigoOrgaoExterno}</pCodigoOrgaoExterno>
                  <pCodigoUsuarioExterno>{banksoft_usuario_externo}</pCodigoUsuarioExterno>
                  <pValorLimiteTotal>{limite_pre_aprovado}</pValorLimiteTotal>
                  <pValorLimiteSaque>{valor_disponivel_saque}</pValorLimiteSaque>
                  <pValorLimiteCompra>{limite_pre_aprovado}</pValorLimiteCompra>
                  <pValorRMC>{cliente_margem_atual}</pValorRMC>
                  <pValorSaque>0</pValorSaque>
                  <pValorParcela>0</pValorParcela>
                  <pQuantidadeParcelas>0</pQuantidadeParcelas>
                  <pValorIOF>0</pValorIOF>
                  <pValorTC>0</pValorTC>
                  <pNumeroCartao>{cliente_cartao_beneficio.id_conta_dock}</pNumeroCartao>
                  <pNumeroContrato>{contrato.pk}</pNumeroContrato>
                  <pNumeroOperacaoConsignada></pNumeroOperacaoConsignada>
            """)

        payload_part3 = textwrap.dedent(f"""\
                    <pListaParcelas>
                        <PropostaParcela>
                              <NumeroProposta>{contrato.pk}</NumeroProposta>
                              <NumeroParcela>0</NumeroParcela>
                              <ValorParcela>0</ValorParcela>
                              <DataVencimento>2079-02-02</DataVencimento>
                              <ValorPrincipal>0</ValorPrincipal>
                              <ValorJuros>0</ValorJuros>
                              <NumeroTitulo></NumeroTitulo>
                        </PropostaParcela>
                  </pListaParcelas>
                </IncluirPropostaCartaoCompleto>
              </soap:Body>
            </soap:Envelope>
            """)
    else:
        payload_part2 = textwrap.dedent(f"""\
                      <Telefones>
                        <Telefone>
                          <TipoTelefone>{cliente_tipo_telefone}</TipoTelefone>
                          <DDD>{cliente_ddd}</DDD>
                          <NumeroTelefone>{cliente_celular}</NumeroTelefone>
                          <Operadora>{cliente_operadora}</Operadora>
                        </Telefone>
                      </Telefones>
                      <DadosCadastro>
                        <DataDeCadastro>{contrato_cadastro}</DataDeCadastro>
                        <UsuarioInclusao></UsuarioInclusao>
                        <DataDeAlteracao>{contrato_cadastro}</DataDeAlteracao>
                        <UsuarioAlteracao></UsuarioAlteracao>
                      </DadosCadastro>
                      <Email>{cliente_email}</Email>
                      <RamoAtividade></RamoAtividade>
                      <TipoInstalacao>{cliente_tipo_instalacao}</TipoInstalacao>
                      <PossuiCNH>{possui_cnh}</PossuiCNH>
                    </DadosCliente>
                    <NomeRef1></NomeRef1>
                    <DDDRef1></DDDRef1>
                    <FoneRef1></FoneRef1>
                    <NomeRef2></NomeRef2>
                    <DDDRef2></DDDRef2>
                    <FoneRef2></FoneRef2>
                    <ReferenciaBancaria>
                      <TipoConta>{cliente_tipo_conta}</TipoConta>
                      <NumeroBanco>{cliente_conta_banco}</NumeroBanco>
                      <Agencia>{cliente_conta_agencia}</Agencia>
                      <Conta>{cliente_conta_numero}</Conta>
                      <DVConta>{cliente_conta_digito}</DVConta>
                    </ReferenciaBancaria>
                    <DadosConjuge>
                      <NomeConjuge></NomeConjuge>
                      <CPFConjuge></CPFConjuge>
                      <DataNascimentoConjuge>2079-02-02</DataNascimentoConjuge>
                      <RGConjuge></RGConjuge>
                      <RendaConjuge>0</RendaConjuge>
                    </DadosConjuge>
                  </pDadosCliente>
                  <pTipoProposta>{tipo_proposta}</pTipoProposta>
                  <pTipoProduto>{tipo_produto}</pTipoProduto>
                  <pCodigoEmpregadorExterno>{codigo_empregador_externo}</pCodigoEmpregadorExterno>
                  <pCodigoOrgaoExterno>{pCodigoOrgaoExterno}</pCodigoOrgaoExterno>
                  <pCodigoUsuarioExterno>{banksoft_usuario_externo}</pCodigoUsuarioExterno>
                  <pValorLimiteTotal>{limite_pre_aprovado}</pValorLimiteTotal>
                  <pValorLimiteSaque>{valor_disponivel_saque}</pValorLimiteSaque>
                  <pValorLimiteCompra>{limite_pre_aprovado}</pValorLimiteCompra>
                  <pValorRMC>{cliente_margem_atual}</pValorRMC>
                  <pValorSaque>{valor_saque}</pValorSaque>
                  <pValorParcela>{valor_financiado}</pValorParcela>
                  <pQuantidadeParcelas>{quantidade_parcelas}</pQuantidadeParcelas>
                  <pValorIOF>{vr_iof}</pValorIOF>
                  <pValorTC>0</pValorTC>
                  <pNumeroCartao>{cliente_cartao_beneficio.id_conta_dock}</pNumeroCartao>
                  <pNumeroContrato>{contrato.pk}</pNumeroContrato>
                  <pNumeroOperacaoConsignada></pNumeroOperacaoConsignada>
            """)

        if cartao_beneficio.saque_parcelado:
            parcelas = []
            vencimento_fatura = datetime.strptime(vencimento_fatura, '%Y-%m-%d')
            for i in range(1, quantidade_parcelas + 1):
                next_vencimento = vencimento_fatura + relativedelta(months=+(i - 1))
                next_vencimento = next_vencimento.strftime('%Y-%m-%d')
                parcela = textwrap.dedent(f"""\
                        <PropostaParcela>
                              <NumeroProposta>{contrato.pk}</NumeroProposta>
                              <NumeroParcela>{i}</NumeroParcela>
                              <ValorParcela>{valor_financiado}</ValorParcela>
                              <DataVencimento>{next_vencimento}</DataVencimento>
                              <ValorPrincipal>{valor_financiado}</ValorPrincipal>
                              <ValorJuros>{cet_mes}</ValorJuros>
                              <NumeroTitulo></NumeroTitulo>
                        </PropostaParcela>
                    """)
                parcelas.append(parcela)
            payload_part3 = (
                '<pListaParcelas>\n'
                + '\n'.join(parcelas)
                + '\n</pListaParcelas>\n</IncluirPropostaCartaoCompleto>\n</soap:Body>\n</soap:Envelope>'
            )
        else:
            payload_part3 = textwrap.dedent(f"""\
                        <pListaParcelas>
                            <PropostaParcela>
                                  <NumeroProposta>{contrato.pk}</NumeroProposta>
                                  <NumeroParcela>1</NumeroParcela>
                                  <ValorParcela>{valor_financiado}</ValorParcela>
                                  <DataVencimento>{vencimento_fatura}</DataVencimento>
                                  <ValorPrincipal>{valor_financiado}</ValorPrincipal>
                                  <ValorJuros>{cet_mes}</ValorJuros>
                                  <NumeroTitulo></NumeroTitulo>
                            </PropostaParcela>
                      </pListaParcelas>
                    </IncluirPropostaCartaoCompleto>
                  </soap:Body>
                </soap:Envelope>
                """)
    payload = payload_part1 + payload_part2 + payload_part3

    print(payload)
    headers = {
        'Content-Type': 'text/xml',
        'Cookie': 'cookiesession1=678A8C3454B02B7D5DA019EF76138A4E',
    }

    response = requests.request('POST', url, headers=headers, data=payload)
    xml = response.text
    xml_dict = xmltodict.parse(xml)
    json_str = json.dumps(xml_dict, indent=2)
    print(json_str)
    log_api_id, _ = LogCliente.objects.get_or_create(cliente=cliente)
    Banksoft.objects.create(
        log_api_id=log_api_id.pk,
        cliente=contrato.cliente,
        payload_enviado=payload,
        contrato=contrato.pk,
        payload=json_str,
        tipo_chamada='Comissionamento',
    )
    # json_formated = json.loads(json_str)

    return response.status_code


def atualizar_dados_bancarios(numero_proposta, cliente_conta, contrato):
    import textwrap

    url = settings.URL_BANKSOFT
    cliente_tipo_conta = 'CCIndividual'

    numero_banco = cliente_conta.conta_banco
    # Apenas o número do banco deve ser enviado
    numero_banco = re.sub(r'\D', '', numero_banco)
    numero_agencia = cliente_conta.conta_agencia
    numero_conta = cliente_conta.conta_numero
    numero_dv_conta = cliente_conta.conta_digito
    log_api_id = LogCliente.objects.filter(cliente=cliente_conta.cliente).first()
    if numero_proposta is None:
        # Recuperando registros relevantes e ordenando por data de criação (do mais recente ao mais antigo)
        registros = Banksoft.objects.filter(
            log_api_id=log_api_id.pk,
            tipo_chamada='Solicitação Saque',
            contrato=contrato,
        ).order_by('-criado_em')

        if registro_filtrado := next(
            (
                registro
                for registro in registros
                if 'NumeroProposta'
                in json.loads(registro.payload)['soap:Envelope']['soap:Body'][
                    'IncluirPropostaCartaoCompletoResponse'
                ]['IncluirPropostaCartaoCompletoResult']
                and json.loads(registro.payload)['soap:Envelope']['soap:Body'][
                    'IncluirPropostaCartaoCompletoResponse'
                ]['IncluirPropostaCartaoCompletoResult']['NumeroProposta']
                != '0'
            ),
            None,  # valor padrão se não encontrar nenhum registro que corresponda
        ):
            numero_proposta = json.loads(registro_filtrado.payload)['soap:Envelope'][
                'soap:Body'
            ]['IncluirPropostaCartaoCompletoResponse'][
                'IncluirPropostaCartaoCompletoResult'
            ]['NumeroProposta']

    headers = {
        'Content-Type': 'text/xml',
        'Cookie': 'cookiesession1=678A8C3454B02B7D5DA019EF76138A4E',
    }

    payload = textwrap.dedent(f"""\
        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <AtualizarDadosBancarios xmlns="http://tempuri.org/">
              <pLoginUsuario>{settings.BANKSOFT_USER}</pLoginUsuario>
              <pSenha>{settings.BANKSOFT_PASS}</pSenha>
              <pNumeroProposta>{numero_proposta}</pNumeroProposta>
              <pTipoConta>{cliente_tipo_conta}</pTipoConta>
              <pNumeroBanco>{numero_banco}</pNumeroBanco>
              <pNumeroAgencia>{numero_agencia}</pNumeroAgencia>
              <pNumeroConta>{numero_conta}</pNumeroConta>
              <pNumeroDVConta>{numero_dv_conta}</pNumeroDVConta>
            </AtualizarDadosBancarios>
          </soap:Body>
        </soap:Envelope>
    """)

    response = requests.request('POST', url, headers=headers, data=payload)
    xml_dict = xmltodict.parse(response.text)
    json_str = json.dumps(xml_dict, indent=2)
    # data = json.loads(json_str)
    Banksoft.objects.create(
        log_api_id=log_api_id.pk,
        cliente=cliente_conta.cliente,
        payload_enviado=payload,
        payload=json_str,
        tipo_chamada='Atualizar Dados Bancarios',
    )
    json_formated = json.loads(json_str)
    try:
        status_processamento = json_formated['soap:Envelope']['soap:Body'][
            'AtualizarDadosBancariosResponse'
        ]['AtualizarDadosBancariosResult']['StatusProcessamento']
        retorno = status_processamento['Status']
        mensagem_retorno = status_processamento['MensagemErro']
        retorno_status = 200 if retorno == 'true' else 400
    except Exception as e:
        logger.error(f'Erro recuperar retorno banksoft (solicitar_saque_banksoft): {e}')
        return 400

    try:
        if contrato.tipo_produto in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            cartao_beneficio = CartaoBeneficio.objects.filter(contrato=contrato).first()
            cartao_beneficio.retorno_solicitacao_saque = str(mensagem_retorno)
            cartao_beneficio.save(
                update_fields=[
                    'retorno_solicitacao_saque',
                ]
            )
            cartao_beneficio.refresh_from_db()

        elif contrato.tipo_produto == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            saque_complementar = SaqueComplementar.objects.filter(
                contrato=contrato
            ).first()
            saque_complementar.retorno_solicitacao_saque = str(mensagem_retorno)
            saque_complementar.save(
                update_fields=[
                    'retorno_solicitacao_saque',
                ]
            )
            saque_complementar.refresh_from_db()
        contrato.save()
    except Exception as e:
        logger.error(
            f'Erro ao salvar dados no contrato (atualizar_dados_bancarios): {e}'
        )

    return retorno_status
