from django.db.models import Q

from contract.constants import EnumTipoProduto
from contract.models.contratos import Contrato, MargemLivre
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.choices import STATUS_NAME
from contract.products.cartao_beneficio.constants import ContractStatus
from core.choices import TIPOS_CONTA
from core.constants import EnumNivelHierarquia
from core.settings import ENVIRONMENT
from custom_auth.models import UserProfile


def get_viewable_contracts(user) -> Contrato.objects:
    """
    Verifica quais os contratos que aquele usuário logado pode visualizar. Coleta todos os contratos associados
    aos Corbans na hierarquia abaixo do Corban do usuário e depois aplica restrições adicionais com base na hierarquia
    do usuário. Isso garante que a visualização dos contratos seja consistente tanto com a hierarquia do Corban
    quanto com as permissões dos grupos do usuário.

    :param user: Usuário para que seus grupos sejam verificados.
    :return: Queryset de Contrato
    """
    if ENVIRONMENT == 'STAGING' or ENVIRONMENT == 'DEV':
        nivel_hierarquia_usuario = user.nivel_hierarquia
        # Verificar se o usuário é um representante comercial
        is_representante_comercial = user.representante_comercial
        # Verificar se o usuário é parte do grupo Mesa Corban
        is_mesa_corban = user.groups.filter(name='Mesa Corban').exists()
        is_corban_master = user.groups.filter(name='Corban Master').exists()

        # Obter os Corbans subordinados
        subordinate_corbans = user.corban.get_subordinate_hierarchy()
        corban_ids = [corban.id for corban in subordinate_corbans]

        if is_representante_comercial:
            return Contrato.objects.filter(corban__id__in=corban_ids).order_by(
                '-criado_em'
            )

        if nivel_hierarquia_usuario is None and not is_mesa_corban:
            # Se o usuário não tem um nível hierárquico definido e não é Mesa Corban, retorna uma lista vazia
            return Contrato.objects.none()

        # Filtro inicial com base nos subordinados do Corban
        qs_filters = Q(corban__id__in=corban_ids)

        # Aplicar filtros adicionais com base no nível hierárquico do usuário
        if nivel_hierarquia_usuario == EnumNivelHierarquia.ADMINISTRADOR:
            # Administrador pode ver todos os contratos
            return Contrato.objects.all().order_by('-criado_em')

        elif nivel_hierarquia_usuario == EnumNivelHierarquia.DONO_LOJA:
            # Dono da Loja pode ver todos os contratos dos Corbans subordinados
            pass

        elif nivel_hierarquia_usuario == EnumNivelHierarquia.GERENTE:
            # Gerentes veem contratos dos Corbans subordinados e criados por eles, pelos supervisores subordinados,
            # e pelos digitadores subordinados a esses supervisores.
            # Primeiro, encontramos os supervisores subordinados ao gerente
            subordinate_supervisor_profiles = UserProfile.objects.filter(
                corban__id__in=corban_ids,
                nivel_hierarquia=EnumNivelHierarquia.SUPERVISOR,
                supervisor=user,
            )
            subordinate_supervisor_ids = subordinate_supervisor_profiles.values_list(
                'id', flat=True
            )
            # Em seguida, encontramos os digitadores subordinados a esses supervisores
            subordinate_digitador_profiles = UserProfile.objects.filter(
                corban__id__in=corban_ids,
                nivel_hierarquia=EnumNivelHierarquia.DIGITADOR,
                supervisor__id__in=subordinate_supervisor_ids,
            )
            subordinate_digitador_ids = subordinate_digitador_profiles.values_list(
                'id', flat=True
            )
            # Incluindo no filtro os contratos criados pelos supervisores e digitadores subordinados
            qs_filters &= (
                Q(created_by=user)
                | Q(created_by__id__in=subordinate_supervisor_ids)
                | Q(created_by__id__in=subordinate_digitador_ids)
            )

        elif nivel_hierarquia_usuario == EnumNivelHierarquia.SUPERVISOR:
            # Supervisores veem contratos dos Corbans subordinados e criados por eles ou seus Digitadores subordinados
            subordinate_digitador_profiles = UserProfile.objects.filter(
                corban__id__in=corban_ids,
                nivel_hierarquia=EnumNivelHierarquia.DIGITADOR,
                supervisor=user,
            )
            subordinate_digitador_ids = subordinate_digitador_profiles.values_list(
                'id', flat=True
            )
            qs_filters &= Q(created_by=user) | Q(
                created_by__id__in=subordinate_digitador_ids
            )
        elif nivel_hierarquia_usuario == EnumNivelHierarquia.DIGITADOR:
            # Digitadores veem apenas os contratos dos Corbans subordinados criados por eles mesmos
            qs_filters &= Q(created_by=user)

        # Filtros específicos para o grupo Mesa Corban
        if is_mesa_corban:
            return mesa_corban_contracts(user)
        if is_corban_master:
            return corban_master_contracts(user)

    else:
        qs_filters = Q()
        for group in user.groups.all():
            group_name = group.name
            if group_name in ['Correspondente', 'Gerente']:
                qs_filters |= Q(corban=user.corban)

            elif group_name == 'Supervisor':
                qs_filters |= Q(
                    corban=user.corban,
                    created_by__groups__name__in=['Supervisor', 'Consultor'],
                )

            elif group_name == 'Consultor':
                qs_filters |= Q(
                    corban=user.corban,
                    created_by__unique_id=user.unique_id,
                )
            if user.groups.filter(name='Mesa Corban').exists():
                return mesa_corban_contracts(user)
            if user.groups.filter(name='Corban Master').exists():
                return corban_master_contracts(user)

    return (
        Contrato.objects.filter(qs_filters).order_by('-criado_em')
        if qs_filters
        else Contrato.objects.none()
    )


def mesa_corban_contracts(usuario):
    mesa_corban_filter = Q(corban=usuario.corban) & (
        Q(contrato_portabilidade__status=ContractStatus.CHECAGEM_MESA_CORBAN.value)
        | Q(contrato_margem_livre__status=ContractStatus.CHECAGEM_MESA_CORBAN.value)
        | Q(contrato_cartao_beneficio__status=ContractStatus.CHECAGEM_MESA_CORBAN.value)
    )
    return Contrato.objects.filter(mesa_corban_filter).order_by('-criado_em')


def corban_master_contracts(usuario):
    corban_master_filter = Q(corban=usuario.corban) & (
        Q(
            contrato_portabilidade__status=ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value
        )
        | Q(
            contrato_margem_livre__status=ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value
        )
        | Q(
            contrato_cartao_beneficio__status=ContractStatus.PENDENTE_APROVACAO_RECALCULO_CORBAN.value
        )
    )
    return Contrato.objects.filter(corban_master_filter).order_by('-criado_em')


def get_subordinate_ids_at_all_levels(user):
    """
    Recupera todos os IDs dos subordinados do usuário, incluindo subordinados de seus subordinados.

    :param user: Instância do UserProfile do usuário.
    :return: Set de IDs de subordinados.
    """
    subordinate_ids = set(
        UserProfile.objects.filter(supervisor=user)
        .exclude(id=user.id)
        .values_list('id', flat=True)
    )
    for sub_id in list(subordinate_ids):
        subordinate_ids.update(
            get_subordinate_ids_at_all_levels(UserProfile.objects.get(id=sub_id))
        )

    return subordinate_ids


def atualizar_status_contratos(
    contrato,
    status_macro,
    status_nome,
    descricao_mesa,
    user=None,
):
    if contrato.tipo_produto in {EnumTipoProduto.MARGEM_LIVRE, EnumTipoProduto.INSS}:
        contrato.status = status_macro
        contrato.save()
        produto = MargemLivre.objects.filter(contrato=contrato).first()
        produto.status = status_nome
        produto.save()
        StatusContrato.objects.create(
            contrato=contrato,
            nome=status_nome,
            descricao_mesa=descricao_mesa,
            created_by=user,
        )


def get_contrato_status_name(number: int) -> str:
    """
    Given a status number, return the name for this status displayed on
    BackOffice, this means, an human readable name.
    """
    for item in STATUS_NAME:
        if item[0] == number:
            return item[1]
    return None


def get_tipo_conta_name(number: int) -> str:
    """
    Given a status number, return the name for this status displayed on
    BackOffice, this means, an human readable name.
    """
    for item in TIPOS_CONTA:
        if item[0] == number:
            return item[1]
    return None
