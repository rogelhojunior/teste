import logging
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from api_log.models import LogCliente, RealizaSimulacao
from contract.constants import EnumTipoMargem, NomeAverbadoras
from contract.products.cartao_beneficio.models.convenio import (
    Convenios,
    ProdutoConvenio,
    RegrasIdade,
)
from contract.products.cartao_beneficio.serializers import SimulacaoSerializer
from core.models import ParametrosBackoffice
from core.models.cliente import ClienteCartaoBeneficio
from core.utils import consulta_cliente
from handlers.simulacao_cartao import calcula_simulacao_iof


class Simulacao:
    def __init__(
        self,
        convenio_id,
        tipo_produto,
        data_nascimento_str,
        margem,
        numero_cpf,
        id_cliente_cartao,
        valor_compra_unificada=None,
        valor_saque_unificada=None,
        tipo_vinculo=None,
    ):
        self.convenio_id = convenio_id
        self.tipo_produto = tipo_produto
        self.data_nascimento_str = data_nascimento_str
        self.margem = Decimal(str(margem))
        self.numero_cpf = numero_cpf

        self.logger = logging.getLogger('digitacao')
        self.dados_adicionais = {}
        self.cliente = self.consulta_cliente()
        self.convenio = self.get_convenio()
        self.cliente_cartao_beneficio = ClienteCartaoBeneficio.objects.get(
            cliente=self.cliente, pk=id_cliente_cartao
        )
        self.produto_convenio = (
            self.get_produto_convenio()
            if valor_saque_unificada is None and valor_compra_unificada is None
            else None
        )

        self.valor_compra_unificada = (
            Decimal(valor_compra_unificada) if valor_compra_unificada else None
        )
        self.produto_convenio_compra = self.get_produto_convenio_compra()

        self.valor_saque_unificada = (
            Decimal(valor_saque_unificada) if valor_saque_unificada else None
        )
        self.produto_convenio_saque = self.get_produto_convenio_saque()
        self.tipo_vinculo = tipo_vinculo

    def consulta_cliente(self):
        return consulta_cliente(self.numero_cpf)

    def get_convenio(self):
        return Convenios.objects.get(pk=self.convenio_id, ativo=True)

    def get_produto_convenio(self):
        return ProdutoConvenio.objects.filter(
            convenio=self.convenio,
            produto=self.tipo_produto,
            tipo_margem=self.cliente_cartao_beneficio.tipo_margem,
        ).first()

    def get_produto_convenio_compra(self):
        return ProdutoConvenio.objects.filter(
            convenio=self.convenio,
            produto=self.tipo_produto,
            tipo_margem=EnumTipoMargem.MARGEM_COMPRA,
        ).first()

    def get_produto_convenio_saque(self):
        return ProdutoConvenio.objects.filter(
            convenio=self.convenio,
            produto=self.tipo_produto,
            tipo_margem=EnumTipoMargem.MARGEM_SAQUE,
        ).first()

    def validar_idade_cliente_maxima_minima(
        self, idade_cliente, idade_minima, idade_maxima
    ):
        return idade_minima <= idade_cliente <= idade_maxima

    def calcular_idade(self):
        today = date.today()

        # Verificar se self.data_nascimento_str é uma string ou uma data
        if isinstance(self.data_nascimento_str, date):
            # Se for uma data, usar diretamente
            nascimento = self.data_nascimento_str
        else:
            # Se for uma string, converter para data
            nascimento = datetime.strptime(self.data_nascimento_str, '%d/%m/%Y').date()

        idade_cliente = today.year - nascimento.year

        # Ajustar a idade se ainda não chegou o aniversário deste ano
        if today.month < nascimento.month or (
            today.month == nascimento.month and today.day < nascimento.day
        ):
            idade_cliente -= 1

        return idade_cliente

    def determinar_parametros_idade_siape(self):
        return RegrasIdade.objects.filter(
            ativo=True, tipo_vinculo_siape=self.tipo_vinculo, convenio=self.convenio
        ).first()

    def preparar_dados_adicionais(self):
        self.dados_adicionais['id'] = self.convenio.id
        self.dados_adicionais['nome'] = self.convenio.nome
        self.dados_adicionais['fixar_valor_maximo_saque'] = (
            self.convenio.fixar_valor_maximo
        )
        self.dados_adicionais['permite_saque'] = self.produto_convenio.permite_saque
        self.dados_adicionais['permite_saque_parcelado'] = (
            self.produto_convenio.permite_saque_parcelado
        )

    def preparar_dados_adicionais_margem_unificada(self):
        self.dados_adicionais['id'] = self.convenio.id
        self.dados_adicionais['nome'] = self.convenio.nome
        self.dados_adicionais['permite_saque'] = (
            self.produto_convenio_saque.permite_saque
        )
        self.dados_adicionais['permite_saque_parcelado'] = (
            self.produto_convenio_saque.permite_saque_parcelado
        )

    def realizar(self, possui_saque=None):
        registro_regras = 0
        idade_cliente = self.calcular_idade()
        try:
            if self.determinar_parametros_idade_siape():
                regra_idades = RegrasIdade.objects.filter(
                    convenio=self.convenio,
                    produto=self.tipo_produto,
                    ativo=True,
                    tipo_vinculo_siape=self.tipo_vinculo,
                )
            else:
                regra_idades = RegrasIdade.objects.filter(
                    convenio=self.convenio, produto=self.tipo_produto, ativo=True
                )

            for range in regra_idades:
                if range.idade_minima <= idade_cliente <= range.idade_maxima:
                    registro_regras += 1
                    regra_idade = RegrasIdade.objects.get(id=range.pk)

            if registro_regras > 1:
                return {'error': 'Parâmetro de regra de idade duplicada'}
            elif registro_regras == 0:
                return {
                    'error': 'Cliente não atende os requisitos de idade para contratação'
                }
        except RegrasIdade.DoesNotExist:
            return {
                'error': 'Não existem parâmetros de idade para o tipo de cartão escolhido'
            }
        valor_maximo_margem_convenio = self.produto_convenio.margem_maxima
        valor_minimo_margem_convenio = self.produto_convenio.margem_minima
        idade_minima_convenio = self.produto_convenio.idade_minima
        idade_maxima_convenio = self.produto_convenio.idade_maxima

        if self.convenio.averbadora == NomeAverbadoras.SERPRO:
            param_idade = self.determinar_parametros_idade_siape()
            if not param_idade:
                return {
                    'error': 'Não existe regra de idade para o Tipo de Viculo informado.'
                }
            idade_minima_convenio = param_idade.idade_minima
            idade_maxima_convenio = param_idade.idade_maxima
        parametros_backoffice = ParametrosBackoffice.objects.filter(
            ativo=True, tipoProduto=self.tipo_produto
        ).first()
        self.preparar_dados_adicionais()

        if (
            not valor_minimo_margem_convenio
            <= self.margem
            <= valor_maximo_margem_convenio
        ):
            return {
                'error': f'A margem informada de {self.margem} não está de acordo com os valores parametrizados no convênio (mínimo: {valor_minimo_margem_convenio}, máximo: {valor_maximo_margem_convenio}).'
            }
        convenio = self.get_convenio()

        if convenio.convenio_inss:
            folha = self.cliente_cartao_beneficio.folha

            try:
                especie_inss = convenio.convenio_especie.get(
                    codigo=folha, permite_contratacao=True
                )
            except ObjectDoesNotExist:
                return {
                    'error': 'Especie INSS não encontrada para os parâmetros fornecidos.'
                }

            if not (
                especie_inss.idade_minima <= idade_cliente <= especie_inss.idade_maxima
            ):
                return {
                    'error': 'Não existem parâmetros de idade para o benefício selecionado.'
                }

        if not regra_idade.idade_minima <= idade_cliente <= regra_idade.idade_maxima:
            return {
                'error': f'A idade informada do cliente de {idade_cliente} não está de acordo com os requisitos de Tipo de Vinculo (idade mínima: {idade_minima_convenio}, idade máxima: {idade_maxima_convenio}).'
            }
        # parametros_idade = self.determinar_suborgao_parametros_idade()
        limite_pre_aprovado = round(self.margem * regra_idade.fator, 2)

        if limite_pre_aprovado > regra_idade.limite_maximo_credito:
            limite_pre_aprovado = regra_idade.limite_maximo_credito
        elif limite_pre_aprovado < regra_idade.limite_minimo_credito:
            return {
                'error': 'Cliente não atende os requisitos de idade para contratação'
            }

        if limite_pre_aprovado <= 0:
            return {
                'error': 'Não existem parâmetros de idade para o benefício selecionado.'
            }

        percentual_saque = self.produto_convenio.percentual_saque / 100
        valor_saque = round(limite_pre_aprovado * percentual_saque, 2)

        simulacao = calcula_simulacao_iof(
            valor_saque,
            self.produto_convenio,
            parametros_backoffice,
            possui_saque=possui_saque,
        )

        self.dados_adicionais['valor_minimo_saque'] = (
            self.produto_convenio.vr_minimo_saque
        )
        self.dados_adicionais['valor_maximo_saque'] = round(
            float(limite_pre_aprovado)
            * float(self.produto_convenio.percentual_saque / 100),
            2,
        )
        self.dados_adicionais['valor_minimo_saque_parcelado'] = (
            self.produto_convenio.saque_parc_val_total
        )
        if regra_idade:
            grupos_parcelas_saque_parcelado = [
                regra_idade.grupo_parcelas,
                regra_idade.grupo_parcelas_2,
                regra_idade.grupo_parcelas_3,
                regra_idade.grupo_parcelas_4,
            ]
            grupos_validos = [
                grupo for grupo in grupos_parcelas_saque_parcelado if int(grupo) > 0
            ]
            grupos_validos_ordenados = sorted(grupos_validos, key=lambda x: int(x))
            self.dados_adicionais['grupos_parcelas_saque_parcelado'] = (
                grupos_validos_ordenados
            )
        log_api_id, _ = LogCliente.objects.get_or_create(cliente=self.cliente)
        simulacao_obj = RealizaSimulacao.objects.create(
            log_api=log_api_id,
            cliente=self.cliente,
            matricula=self.cliente_cartao_beneficio.numero_matricula,
            limite_pre_aprovado=limite_pre_aprovado,
            convenio=self.convenio.id,
            valor_saque=valor_saque,
        )

        serializer_simulacao = SimulacaoSerializer(simulacao_obj)
        return (serializer_simulacao.data, self.dados_adicionais, simulacao)

    def processar_margem_compra(self):
        idade_cliente = self.calcular_idade()
        valor_maximo_margem_convenio = self.produto_convenio_compra.margem_maxima
        valor_minimo_margem_convenio = self.produto_convenio_compra.margem_minima
        if not (
            valor_minimo_margem_convenio
            <= self.valor_compra_unificada
            <= valor_maximo_margem_convenio
        ):
            return {
                'error': f'A margem compra informada de {self.valor_saque_unificada} não está de acordo com os valores parametrizados no convênio (mínimo: {valor_minimo_margem_convenio}, máximo: {valor_maximo_margem_convenio}).'
            }
        idade_minima_convenio = self.produto_convenio_compra.idade_minima
        idade_maxima_convenio = self.produto_convenio_compra.idade_maxima

        return (
            {'success': 'Margem Compra validada'}
            if idade_minima_convenio <= idade_cliente <= idade_maxima_convenio
            else {
                'error': f'A idade informada do cliente de {idade_cliente} não está de acordo com as idades parametrizados no convênio (idade mínima: {idade_minima_convenio}, idade máxima: {idade_maxima_convenio}).'
            }
        )

    def processar_margem_saque(self):
        idade_cliente = self.calcular_idade()
        valor_maximo_margem_convenio = self.produto_convenio_saque.margem_maxima
        valor_minimo_margem_convenio = self.produto_convenio_saque.margem_minima
        if not (
            valor_minimo_margem_convenio
            <= self.valor_saque_unificada
            <= valor_maximo_margem_convenio
        ):
            return {
                'error': f'A margem saque informada de {self.valor_saque_unificada} não está de acordo com os valores parametrizados no convênio (mínimo: {valor_minimo_margem_convenio}, máximo: {valor_maximo_margem_convenio}).'
            }
        idade_minima_convenio = self.produto_convenio_saque.idade_minima
        idade_maxima_convenio = self.produto_convenio_saque.idade_maxima

        return (
            {'success': 'Margem Saque validada'}
            if idade_minima_convenio <= idade_cliente <= idade_maxima_convenio
            else {
                'error': f'A idade informada do cliente de {idade_cliente} não está de acordo com as idades parametrizados no convênio (idade mínima: {idade_minima_convenio}, idade máxima: {idade_maxima_convenio}).'
            }
        )

    def realizar_simulacao_margem_unificada(self, possui_saque=None):
        registro_regras = 0
        idade_cliente = self.calcular_idade()
        try:
            if self.determinar_parametros_idade_siape():
                regra_idades = RegrasIdade.objects.filter(
                    convenio=self.convenio,
                    produto=self.tipo_produto,
                    ativo=True,
                    tipo_vinculo_siape=self.tipo_vinculo,
                )
            else:
                regra_idades = RegrasIdade.objects.filter(
                    convenio=self.convenio, produto=self.tipo_produto, ativo=True
                )

            for range in regra_idades:
                if range.idade_minima <= idade_cliente <= range.idade_maxima:
                    registro_regras += 1
                    regra_idade = RegrasIdade.objects.get(id=range.pk)

            if registro_regras > 1:
                return {'error': 'Parâmetro de regra de idade duplicada'}
            elif registro_regras == 0:
                return {
                    'error': 'Cliente não atende os requisitos de idade para contratação'
                }
        except RegrasIdade.DoesNotExist:
            return {
                'error': 'Não existem parâmetros de idade para o tipo de cartão escolhido'
            }

        fator_margem_compra = regra_idade.fator_compra
        fator_margem_saque = regra_idade.fator_saque

        parametros_backoffice = ParametrosBackoffice.objects.filter(
            ativo=True, tipoProduto=self.tipo_produto
        ).first()
        self.preparar_dados_adicionais_margem_unificada()

        limite_pre_aprovado_compra = round(
            self.valor_compra_unificada * fator_margem_compra, 2
        )
        limite_pre_aprovado_saque = round(
            self.valor_saque_unificada * fator_margem_saque, 2
        )
        limite_pre_aprovado = (
            limite_pre_aprovado_saque + limite_pre_aprovado_compra
        )  # TODO AQUI

        if limite_pre_aprovado > regra_idade.limite_maximo_credito:
            limite_pre_aprovado = regra_idade.limite_maximo_credito
        elif limite_pre_aprovado < regra_idade.limite_minimo_credito:
            return {
                'error': 'Cliente não atende os requisitos de idade para contratação'
            }

        percentual_saque = self.produto_convenio_saque.percentual_saque / 100
        valor_saque = round(limite_pre_aprovado_saque * percentual_saque, 2)

        simulacao = calcula_simulacao_iof(
            valor_saque,
            self.produto_convenio_saque,
            parametros_backoffice,
            possui_saque=possui_saque,
        )
        self.dados_adicionais['limite_pre_aprovado_compra'] = limite_pre_aprovado_compra
        self.dados_adicionais['limite_pre_aprovado_saque'] = limite_pre_aprovado_saque
        self.dados_adicionais['valor_minimo_saque'] = (
            self.produto_convenio_saque.vr_minimo_saque
        )
        self.dados_adicionais['valor_maximo_saque'] = round(
            float(limite_pre_aprovado_saque)
            * float(self.produto_convenio_saque.percentual_saque / 100),
            2,
        )
        self.dados_adicionais['valor_minimo_saque_parcelado'] = (
            self.produto_convenio_saque.saque_parc_val_total
        )
        if regra_idade:
            grupos_parcelas_saque_parcelado = [
                regra_idade.grupo_parcelas,
                regra_idade.grupo_parcelas_2,
                regra_idade.grupo_parcelas_3,
                regra_idade.grupo_parcelas_4,
            ]
            grupos_validos = [
                grupo for grupo in grupos_parcelas_saque_parcelado if int(grupo) > 0
            ]
            grupos_validos_ordenados = sorted(grupos_validos, key=lambda x: int(x))
            self.dados_adicionais['grupos_parcelas_saque_parcelado'] = (
                grupos_validos_ordenados
            )

        log_api_id, _ = LogCliente.objects.get_or_create(cliente=self.cliente)
        simulacao_obj = RealizaSimulacao.objects.create(
            log_api=log_api_id,
            cliente=self.cliente,
            matricula=self.cliente_cartao_beneficio.numero_matricula,
            limite_pre_aprovado=limite_pre_aprovado,
            convenio=self.convenio.id,
            valor_saque=valor_saque,
        )

        serializer_simulacao = SimulacaoSerializer(simulacao_obj)
        return serializer_simulacao.data, self.dados_adicionais, simulacao
