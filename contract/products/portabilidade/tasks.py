import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils.timezone import now

from api_log.constants import EnumStatusCCB
from contract.constants import EnumContratoStatus, EnumTipoProduto
from contract.models.contratos import Contrato, Portabilidade, Refinanciamento
from contract.models.status_contrato import StatusContrato
from contract.models.validacao_contrato import ValidacaoContrato
from contract.products.cartao_beneficio.constants import ContractStatus
from contract.products.portabilidade_refin.handlers.proposal_financial_portability import (
    RefuseProposalFinancialPortability,
)
from contract.products.portabilidade_refin.handlers.refinancing import AcceptRefinancing

from contract.services.recalculation.portability import PortabilityRecalculation
from contract.services.recalculation.portability_refinancing import (
    RefinancingRecalculation,
)
from core.admin_actions.contrato_interface import ContratoInterface
from core.models.parametro_produto import ParametrosProduto
from custom_auth.models import UserProfile
from handlers.simulacao_portabilidade import simulacao_portabilidade_financeira_hub
from utils.tasks import get_default_task_args


def create_status_and_validation(contrato, user, msg, retorno_msg, portabilidade):
    portabilidade.status = ContractStatus.REPROVADA_POLITICA_INTERNA.value
    portabilidade.save()
    contrato.status = EnumContratoStatus.CANCELADO
    contrato.save()
    StatusContrato.objects.create(
        contrato=contrato,
        nome=ContractStatus.REPROVADA_POLITICA_INTERNA.value,
        descricao_mesa='O CONTRATO foi reprovado durante o RECALCULO,\n Validar na aba VALIDAÇÃO CONTRATOS',
        created_by=user,
    )
    validado, _ = ValidacaoContrato.objects.update_or_create(
        contrato=contrato, mensagem_observacao=msg
    )
    validado.checked = False
    validado.retorno_hub = retorno_msg
    validado.save()


def armazena_status_recalculo(
    taxa_juros_recalculada, parcela_recalculada, portabilidade, contrato, usuario
):
    portabilidade.taxa_contrato_recalculada = taxa_juros_recalculada * 100
    portabilidade.valor_parcela_recalculada = parcela_recalculada
    portabilidade.status_ccb = EnumStatusCCB.PENDING_ACCEPTANCE.value
    portabilidade.save()
    portabilidade.refresh_from_db()
    if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
        refin = Refinanciamento.objects.get(contrato=contrato)
        refin.nova_parcela = portabilidade.valor_parcela_recalculada
        refin.save()


def processar_divida_menor(
    contrato_id,
    portabilidade_id,
    parametros_produto_id,
    usuario_id,
    taxa_de_juros_mensal,
    numero_de_parcelas,
    saldo_devedor_atualizado,
    parcela_original,
):
    """Função que realiza o recálculo no caso do saldo devedor retornado ser menor que o digitado"""
    contrato = Contrato.objects.get(id=contrato_id)
    portabilidade = Portabilidade.objects.get(id=portabilidade_id)
    parametros_produto = ParametrosProduto.objects.get(id=parametros_produto_id)
    usuario = UserProfile.objects.get(id=usuario_id)

    taxa_maxima = float(parametros_produto.taxa_maxima / 100)
    taxa_minima = (
        parametros_produto.taxa_minima_recalculo or parametros_produto.taxa_minima
    )
    taxa_minima = float(taxa_minima / 100)
    retorno = simulacao_portabilidade_financeira_hub(
        taxa_de_juros_mensal, numero_de_parcelas, saldo_devedor_atualizado
    )

    parcela_fixa = parcela_original - float(
        parametros_produto.valor_de_seguranca_proposta
    )
    nova_parcela = retorno['total_amount']
    erro_parcela_minima = False
    recalculo_1 = False

    # Quando a parcela for menor que o valor minimo de parcela permitido
    if retorno['total_amount'] < parametros_produto.valor_minimo_parcela:
        teste_recalculo_taxa_maxima = simulacao_portabilidade_financeira_hub(
            taxa_maxima, numero_de_parcelas, saldo_devedor_atualizado
        )
        # Caso não consiga subir a parcela minima mesmo com a taxa maxima
        if (
            teste_recalculo_taxa_maxima['total_amount']
            < parametros_produto.valor_minimo_parcela
        ):
            portabilidade.taxa_contrato_recalculada = taxa_maxima * 100
            portabilidade.valor_parcela_recalculada = teste_recalculo_taxa_maxima[
                'total_amount'
            ]
            portabilidade.save()
            portabilidade.refresh_from_db()
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                refin = Refinanciamento.objects.get(contrato=contrato)
                refin.nova_parcela = portabilidade.valor_parcela_recalculada
                refin.save()
            msg = 'Valor Mínimo (Portabilidade)'
            create_status_and_validation(
                contrato,
                usuario,
                msg,
                'Reprovado no RECALCULO: valor da PARCELA menor que o valor minimo \n Mesmo com a taxa Maxima',
                portabilidade,
            )
            RefuseProposalFinancialPortability(contrato=contrato).execute()

        else:
            # Caso consiga, aumentar a taxa enquanto nao chega na parcela minima ate a taxa maxima
            while (
                nova_parcela < parametros_produto.valor_minimo_parcela
                and taxa_de_juros_mensal <= taxa_maxima
            ):
                parcela_recalculada = retorno['total_amount']
                nova_parcela = parcela_recalculada
                taxa_juros_recalculada = taxa_de_juros_mensal  # nao posso atualizar o juros na ultima repetição pois ele estará maior que a condição do while
                nova_taxa_juros = taxa_juros_recalculada
                taxa_de_juros_mensal += (
                    0.001  # Supondo que a taxa seja um valor decimal
                )
                retorno = simulacao_portabilidade_financeira_hub(
                    taxa_de_juros_mensal, numero_de_parcelas, saldo_devedor_atualizado
                )
            while (
                parcela_recalculada < parametros_produto.valor_minimo_parcela
                and taxa_juros_recalculada <= taxa_maxima
            ):
                nova_taxa_juros = taxa_juros_recalculada  # nao posso atualizar o juros na ultima repetição pois ele estará maior que a condição do while
                taxa_juros_recalculada += (
                    0.0001  # Supondo que a taxa seja um valor decimal
                )
                retorno = simulacao_portabilidade_financeira_hub(
                    taxa_juros_recalculada, numero_de_parcelas, saldo_devedor_atualizado
                )
                nova_parcela = parcela_recalculada
                parcela_recalculada = retorno['total_amount']
            # valido se mesmo chegandio na parcela minima parcela esta menor que a original
            if nova_parcela > parcela_fixa:
                portabilidade.taxa_contrato_recalculada = nova_taxa_juros * 100
                portabilidade.valor_parcela_recalculada = nova_parcela
                portabilidade.save()
                portabilidade.refresh_from_db()
                if (
                    contrato.tipo_produto
                    == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO
                ):
                    refin = Refinanciamento.objects.get(contrato=contrato)
                    refin.nova_parcela = portabilidade.valor_parcela_recalculada
                    refin.save()
                msg = 'Valor Mínimo (Portabilidade)'
                create_status_and_validation(
                    contrato,
                    usuario,
                    msg,
                    'Reprovado no RECALCULO: valor da PARCELA maior que a parcela original do contrao \n Mesmo com o recalculo ',
                    portabilidade,
                )
                RefuseProposalFinancialPortability(contrato=contrato).execute()
                erro_parcela_minima = True

            if not erro_parcela_minima:
                armazena_status_recalculo(
                    nova_taxa_juros,
                    parcela_recalculada,
                    portabilidade,
                    contrato,
                    usuario,
                )

    elif nova_parcela > parcela_fixa:
        # Se estiver maior tento diminuir a taxa de forma que a parcela nao fique menor que a parcela minima
        while (
            nova_parcela >= parcela_fixa
            and taxa_de_juros_mensal >= taxa_minima
            and nova_parcela > parametros_produto.valor_minimo_parcela
        ):
            nova_taxa_juros = taxa_de_juros_mensal
            taxa_juros_recalculada = nova_taxa_juros
            parcela_recalculada = retorno['total_amount']
            nova_parcela = parcela_recalculada
            taxa_de_juros_mensal -= 0.001  # Supondo que a taxa seja um valor decimal
            retorno = simulacao_portabilidade_financeira_hub(
                taxa_de_juros_mensal, numero_de_parcelas, saldo_devedor_atualizado
            )
            recalculo_1 = True
        if recalculo_1:
            while (
                parcela_recalculada < parcela_fixa
                and nova_taxa_juros >= taxa_minima
                and nova_parcela > parametros_produto.valor_minimo_parcela
            ):
                taxa_juros_recalculada = nova_taxa_juros
                nova_parcela = parcela_recalculada
                nova_taxa_juros += 0.0001  # Supondo que a taxa seja um valor decimal
                retorno = simulacao_portabilidade_financeira_hub(
                    nova_taxa_juros, numero_de_parcelas, saldo_devedor_atualizado
                )
                parcela_recalculada = retorno['total_amount']
            while (
                parcela_recalculada >= parcela_fixa
                and nova_taxa_juros >= taxa_minima
                and nova_parcela > parametros_produto.valor_minimo_parcela
            ):
                taxa_juros_recalculada = nova_taxa_juros
                nova_taxa_juros -= 0.0001  # Supondo que a taxa seja um valor decimal
                retorno = simulacao_portabilidade_financeira_hub(
                    nova_taxa_juros, numero_de_parcelas, saldo_devedor_atualizado
                )
                parcela_recalculada = retorno['total_amount']
                nova_parcela = parcela_recalculada
        # se mesmo diminuido a taxa ate o limite ainda ficou maior que a parcela original
        if nova_parcela > parcela_fixa:
            portabilidade.taxa_contrato_recalculada = nova_taxa_juros * 100
            portabilidade.valor_parcela_recalculada = nova_parcela
            portabilidade.save()
            portabilidade.refresh_from_db()
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                refin = Refinanciamento.objects.get(contrato=contrato)
                refin.nova_parcela = portabilidade.valor_parcela_recalculada
                refin.save()
            msg = 'Valor Mínimo (Portabilidade)'
            create_status_and_validation(
                contrato,
                usuario,
                msg,
                'Reprovado no RECALCULO: valor da PARCELA maior que a parcela original do contrao \n Mesmo com o recalculo ',
                portabilidade,
            )
            RefuseProposalFinancialPortability(contrato=contrato).execute()
            erro_parcela_minima = True

        if not erro_parcela_minima:
            armazena_status_recalculo(
                taxa_juros_recalculada,
                nova_parcela,
                portabilidade,
                contrato,
                usuario,
            )

    else:
        armazena_status_recalculo(
            taxa_de_juros_mensal, nova_parcela, portabilidade, contrato, usuario
        )


def processar_divida_maior(
    contrato_id,
    portabilidade_id,
    parametros_produto_id,
    usuario_id,
    taxa_de_juros_mensal,
    numero_de_parcelas,
    saldo_devedor_atualizado,
    parcela_original,
):
    """Função que realiza o recálculo no caso do saldo devedor retornado ser maior que o digitado"""
    contrato = Contrato.objects.get(id=contrato_id)
    portabilidade = Portabilidade.objects.get(id=portabilidade_id)
    parametros_produto = ParametrosProduto.objects.get(id=parametros_produto_id)
    usuario = UserProfile.objects.get(id=usuario_id)
    taxa_minima = (
        parametros_produto.taxa_minima_recalculo or parametros_produto.taxa_minima
    )
    taxa_minima = round(float(taxa_minima / 100), 4)
    parcela_fixa = parcela_original - float(
        parametros_produto.valor_de_seguranca_proposta
    )
    nova_parcela = parcela_original
    erro_parcela_minima = False
    recalculo_1 = False

    teste_recalculo_taxa_minima = simulacao_portabilidade_financeira_hub(
        taxa_minima, numero_de_parcelas, saldo_devedor_atualizado
    )
    # Testo se a parcela consegue ficar menor do que a parcela maxima com a taxa minima e se a parcela consegue ficar menor que a original

    if (
        teste_recalculo_taxa_minima['total_amount']
        > parametros_produto.valor_maximo_parcela
        or teste_recalculo_taxa_minima['total_amount'] > parcela_fixa
    ):
        portabilidade.taxa_contrato_recalculada = taxa_minima * 100
        portabilidade.valor_parcela_recalculada = teste_recalculo_taxa_minima[
            'total_amount'
        ]
        portabilidade.save()
        portabilidade.refresh_from_db()
        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            refin = Refinanciamento.objects.get(contrato=contrato)
            refin.nova_parcela = portabilidade.valor_parcela_recalculada
            refin.save()
        RefuseProposalFinancialPortability(contrato=contrato).execute()
        msg = 'Valor Maximo Parcela (Portabilidade)'
        create_status_and_validation(
            contrato,
            usuario,
            msg,
            'Reprovado no RECALCULO: valor da PARCELA maior que o valor maximo ou maior que a parcela original '
            '\n Mesmo com A TAXA MINIMA '
            '\n Verifique na ABA Portabilidade ',
            portabilidade,
        )
    else:
        # Pega o valor da simulação com a própria taxa.
        retorno = simulacao_portabilidade_financeira_hub(
            taxa_de_juros_mensal, numero_de_parcelas, saldo_devedor_atualizado
        )
        nova_parcela = retorno['total_amount']
        taxa_juros_recalculada = round(taxa_de_juros_mensal, 4)
        # diminuo a taxa ate conseguir atigir uma parcela aceitavel
        while nova_parcela >= parcela_fixa and taxa_de_juros_mensal >= taxa_minima:
            nova_taxa_juros = taxa_de_juros_mensal
            taxa_juros_recalculada = nova_taxa_juros
            parcela_recalculada = retorno['total_amount']
            nova_parcela = parcela_recalculada
            taxa_de_juros_mensal -= 0.001  # Supondo que a taxa seja um valor decimal
            taxa_de_juros_mensal = round(taxa_de_juros_mensal, 4)
            retorno = simulacao_portabilidade_financeira_hub(
                taxa_de_juros_mensal, numero_de_parcelas, saldo_devedor_atualizado
            )
            recalculo_1 = True
        if recalculo_1:
            while parcela_recalculada < parcela_fixa:
                taxa_juros_recalculada = nova_taxa_juros
                nova_parcela = parcela_recalculada
                nova_taxa_juros += 0.0001  # Supondo que a taxa seja um valor decimal
                nova_taxa_juros = round(nova_taxa_juros, 4)
                retorno = simulacao_portabilidade_financeira_hub(
                    nova_taxa_juros, numero_de_parcelas, saldo_devedor_atualizado
                )
                parcela_recalculada = retorno['total_amount']
            while (
                parcela_recalculada >= parcela_fixa and nova_taxa_juros >= taxa_minima
            ):
                taxa_juros_recalculada = nova_taxa_juros
                nova_taxa_juros -= 0.0001  # Supondo que a taxa seja um valor decimal
                nova_taxa_juros = round(nova_taxa_juros, 4)
                retorno = simulacao_portabilidade_financeira_hub(
                    nova_taxa_juros, numero_de_parcelas, saldo_devedor_atualizado
                )
                parcela_recalculada = retorno['total_amount']
                nova_parcela = parcela_recalculada
        # valido se essa parcela é menor que a original
        if nova_parcela > parcela_fixa:
            portabilidade.taxa_contrato_recalculada = taxa_juros_recalculada * 100
            portabilidade.valor_parcela_recalculada = nova_parcela
            portabilidade.save()
            portabilidade.refresh_from_db()
            if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
                refin = Refinanciamento.objects.get(contrato=contrato)
                refin.nova_parcela = portabilidade.valor_parcela_recalculada
                refin.save()
            msg = 'Valor Mínimo (Portabilidade)'
            create_status_and_validation(
                contrato,
                usuario,
                msg,
                'Reprovado no RECALCULO: valor da PARCELA maior que a parcela original do contrao \n Mesmo com o recalculo ',
                portabilidade,
            )
            RefuseProposalFinancialPortability(contrato=contrato).execute()
            erro_parcela_minima = True
        if not erro_parcela_minima:
            armazena_status_recalculo(
                taxa_juros_recalculada, nova_parcela, portabilidade, contrato, usuario
            )


def verificar_enviar_proposta(
    saldo_devedor_atualizado,
    ultimo_devido_saldo,
    contrato,
    portabilidade,
    taxa_de_juros_mensal,
    numero_de_parcelas,
    usuario,
    parametros_produto,
    parcela_original,
):
    while True:
        if saldo_devedor_atualizado < ultimo_devido_saldo:
            processar_divida_menor(
                contrato.id,
                portabilidade.id,
                parametros_produto.id,
                usuario.id,
                taxa_de_juros_mensal,
                numero_de_parcelas,
                saldo_devedor_atualizado,
                parcela_original,
            )
        else:
            processar_divida_maior(
                contrato.id,
                portabilidade.id,
                parametros_produto.id,
                usuario.id,
                taxa_de_juros_mensal,
                numero_de_parcelas,
                saldo_devedor_atualizado,
                parcela_original,
            )
        break


@shared_task(**get_default_task_args(queue='recalculation'))
def retorno_saldo_portabilidade_assync(
    token,
    saldo_devedor_atualizado,
    user_id,
    numero_parcela_atualizada,
    parcela_original,
):
    from handlers.webhook_qitech import validar_in100_recalculo

    try:
        contrato = Contrato.objects.get(token_contrato=token)
        portabilidade = Portabilidade.objects.get(contrato=contrato)
        user = UserProfile.objects.get(identifier=user_id)

        # if Portabilidade
        if contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE:
            parametros_produto = ParametrosProduto.objects.filter(
                tipoProduto=contrato.tipo_produto
            ).first()
            taxa_de_juros_mensal = round(float(portabilidade.taxa) / 100, 4)
            numero_de_parcelas = int(numero_parcela_atualizada)
            ultimo_devido_saldo = float(portabilidade.saldo_devedor)
            verificar_enviar_proposta(
                saldo_devedor_atualizado,
                ultimo_devido_saldo,
                contrato,
                portabilidade,
                taxa_de_juros_mensal,
                numero_de_parcelas,
                user,
                parametros_produto,
                parcela_original,
            )
            portabilidade.refresh_from_db()
            if (
                contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE
                and portabilidade.status
                != ContractStatus.REPROVADA_POLITICA_INTERNA.value
            ):
                validar_in100_recalculo(contrato)

        # if Port + Refin
        elif contrato.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            PortabilityRecalculation(
                contract=contrato,
                user=user,
            ).execute()
            portabilidade.refresh_from_db()
            RefinancingRecalculation(
                contract=contrato,
                portability=portabilidade,
            ).execute()

    except Exception as e:
        logging.error(f' ERRO AO PROCESSAR RECALCULO {e}')
        raise


def status_que_reprova(portabilidade, contrato):
    """
    Função que irá verificar se o status do contrato está na lista dos status que serão reprovados
    """
    try:
        if portabilidade.status in (
            ContractStatus.AGUARDANDO_RETORNO_IN100.value,
            ContractStatus.AGUARDA_ENVIO_LINK.value,
            ContractStatus.FORMALIZACAO_CLIENTE.value,
            ContractStatus.PENDENTE_DADOS_DIVERGENTES.value,
            ContractStatus.AGUARDA_RETORNO_SALDO.value,
            ContractStatus.PENDENTE_DOCUMENTACAO_MESA_CORBAN.value,
            ContractStatus.CHECAGEM_MESA_FORMALIZACAO.value,
            ContractStatus.CHECAGEM_MESA_DE_FORMALIZACAO.value,
            ContractStatus.CHECAGEM_MESA_CORBAN.value,
            ContractStatus.INT_CONFIRMA_PAGAMENTO.value,
        ):
            contrato.status = EnumContratoStatus.CANCELADO
            contrato.save()
            portabilidade.status = ContractStatus.REPROVADO.value
            portabilidade.save()
            StatusContrato.objects.create(
                contrato=contrato,
                nome=ContractStatus.REPROVADO.value,
                descricao_mesa='Periodo do retorno da CIP expirado',
            )
            RefuseProposalFinancialPortability(contrato=contrato).execute()
    except Exception as e:
        print(e)


@shared_task
def automacao_reprova_contratos_async():
    """
    Função Assincrona que filtra os contratos que foram atualizados num periodo de 10 a 60 dias atras, e que a
    depender do status que o contrato tiver, ele será reprovado
    """
    try:
        dez_dias_atras = now() - timedelta(days=10)
        sessenta_dias_atras = now() - timedelta(days=60)
        contratos = Contrato.objects.filter(
            Q(ultima_atualizacao__gte=sessenta_dias_atras)
            & Q(ultima_atualizacao__lte=dez_dias_atras)
        )
        for contrato in contratos:
            portabilidades = Portabilidade.objects.filter(contrato=contrato)
            for portabilidade in portabilidades:
                status_que_reprova(portabilidade, contrato)
    except Exception as e:
        print(e)


@shared_task
def approve_portability_contract(contract_id: int, user_id: int):
    from contract.services.persistance.products import (
        SubmitPortabilityDocumentsAndSignature,
    )

    SubmitPortabilityDocumentsAndSignature(
        contract=Contrato.objects.get(id=contract_id),
        product=Portabilidade.objects.get(contrato_id=contract_id),
        user=UserProfile.objects.get(id=user_id),
    ).execute()


@shared_task(queue='light_operations')
def approve_refinancing(refinancing_id: int):
    AcceptRefinancing(
        refinancing=Refinanciamento.objects.get(pk=refinancing_id)
    ).execute()


@shared_task
def deny_portability_contract(contract_id: int, user_id: int, reason: str):
    from contract.services.persistance.products import (
        DenyPortabilityContract,
        DenyPortabilityRefinancingContract,
    )

    contract = Contrato.objects.get(id=contract_id)
    if contract.tipo_produto == EnumTipoProduto.PORTABILIDADE:
        DenyPortabilityContract(
            contract=Contrato.objects.get(id=contract_id),
            product=Portabilidade.objects.get(contrato_id=contract_id),
            user=UserProfile.objects.get(id=user_id),
            reason=reason,
        ).execute()
    elif contract.tipo_produto == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
        DenyPortabilityRefinancingContract(
            contract=Contrato.objects.get(id=contract_id),
            product=Portabilidade.objects.get(contrato_id=contract_id),
            refinancing=Refinanciamento.objects.get(contrato_id=contract_id),
            user=UserProfile.objects.get(id=user_id),
            reason=reason,
        ).execute()
    else:
        raise NotImplementedError('Apenas produtos de Portabilidade!!')


@shared_task(queue='recalculation')
def resimular_port_refin_para_contrato(contrato_id: int, user_id: int):
    # create interface
    contrato = Contrato.objects.get(id=contrato_id)
    user = UserProfile.objects.get(id=user_id)
    contract_interface = ContratoInterface(contrato)
    if not contract_interface.is_valid:
        logging.error('Contract error: %s' % contract_interface.error_message)
        return

    # save before value valor_parcela_recalculada
    before_parcela_recalculada = contract_interface.port.valor_parcela_recalculada
    before_valor_parcela_original = contract_interface.port.valor_parcela_original

    # apply function to perform re-simulation
    retorno_saldo_portabilidade_assync(
        token=contrato.token_contrato,
        user_id=user.identifier,
        saldo_devedor_atualizado=contract_interface.port.saldo_devedor_atualizado,
        numero_parcela_atualizada=contract_interface.port.valor_parcela_original,
        parcela_original=contract_interface.port.valor_parcela_original,
    )

    # change port status
    contract_interface.port.refresh_from_db()
    contract_interface.port.status = ContractStatus.INT_FINALIZADO.value
    contract_interface.port.valor_parcela_original = min(
        before_parcela_recalculada, before_valor_parcela_original
    )
    contract_interface.port.save(update_fields=['status', 'valor_parcela_original'])

    try:
        # confirm refin
        approve_refinancing.apply_async(
            args=[Refinanciamento.objects.get(contrato=contrato).pk]
        )
        contract_interface.port.valor_parcela_original = before_valor_parcela_original
        contract_interface.port.save(update_fields=['valor_parcela_original'])
    except Exception as exc:
        logging.exception('Unexpected error')
        contract_interface.port.valor_parcela_original = before_valor_parcela_original
        contract_interface.port.save(update_fields=['valor_parcela_original'])
        raise exc


@shared_task(bind=True, max_retries=0)
def insert_proposal_port_refin_async(self, contract_id, user_id, retry_count=0):
    from contract.products.portabilidade_refin.handle_response import (
        HandleQitechResponse,
    )
    from contract.products.portabilidade.views import status_envio_link_portabilidade

    logger = logging.getLogger('webhookqitech')

    try:
        contract = Contrato.objects.get(pk=contract_id)
        user = UserProfile.objects.get(pk=user_id)
        qi_tech = HandleQitechResponse(contract)
        status_code = qi_tech.insert_proposal_port_refin_response()
        if status_code in (200, 201, 202):
            user = UserProfile.objects.get(identifier=user.identifier)
            status_envio_link_portabilidade(contract, user)
            refin = Refinanciamento.objects.filter(contrato=contract).first()
            port = Portabilidade.objects.filter(contrato=contract).first()
            refin.status = port.status
            refin.save()
            return True
        else:
            if retry_count < 2:
                try:
                    message = (
                        f'{contract.cliente.id_unico} - Contrato(ID: {contract.pk}):'
                        f' Nova tentativa de inserção da proposta.'
                    )
                    logger.error(message)
                    retry_count = retry_count + 1
                    insert_proposal_port_refin_async.apply_async(
                        args=[contract_id, user_id, retry_count + 1], countdown=5 * 60
                    )
                    return False
                except Exception as ex:
                    print(ex)
    except Exception as e:
        message = (
            f'{contract.cliente.id_unico} - Contrato(ID: {contract.pk}):'
            f' Nova tentativa de inserção da proposta (Exception).'
        )
        logger.critical(message, extra={'extra': e})
        if retry_count < 3:
            try:
                retry_count = retry_count + 1
                insert_proposal_port_refin_async.apply_async(
                    args=[contract_id, user_id, retry_count + 1], countdown=5 * 60
                )
                return False
            except Exception as ex:
                print(ex)
