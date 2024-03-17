from contract.products.cartao_beneficio.models.convenio import ProdutoConvenio

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from custom_auth.models import Corban
from .utils import get_subordinate_ids_at_all_levels


@api_view(['POST'])
@permission_classes((AllowAny,))
def get_entities(request):
    product_ids = request.data['products']
    entities = (
        ProdutoConvenio.objects.filter(produto__in=product_ids)
        .order_by('convenio__nome')
        .values('convenio__id', 'convenio__nome')
    )
    unique_entities = {
        entity['convenio__id']: {
            'id': entity['convenio__id'],
            'name': entity['convenio__nome'],
        }
        for entity in entities
    }.values()

    return JsonResponse({'entities': list(unique_entities)})


@api_view(['POST'])
@permission_classes((AllowAny,))
def get_stores(request):
    corban_ids = request.data['corbans']

    subordinate_ids = set()

    for id in corban_ids:
        corban = Corban.objects.get(id=id)

        subordinate_ids.update(get_subordinate_ids_at_all_levels(corban))

    stores = (
        Corban.objects.filter(id__in=subordinate_ids)
        .order_by('id')
        .values('id', 'corban_name')
    )

    unique_stores = {
        store['id']: {'id': store['id'], 'name': store['corban_name']}
        for store in stores
    }.values()

    return JsonResponse({'stores': list(unique_stores)})
