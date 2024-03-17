# views.py
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from core.choices import NIVEIS_HIERARQUIA
from core.constants import EnumNivelHierarquia
from core.filters.user import UserFilter

from ..models import UserProfile
from .serializers import (
    GroupSerializer,
    ListSupervisorsSerializer,
    ListUserProfileSerializer,
    ProductsSerializer,
    UserProfileDetailSerializer,
    UserProfileSerializer,
)


class HierarchyLevelsView(APIView):
    def get(self, request):
        user_nivel_hierarquia = (
            request.user.nivel_hierarquia
        )  # Obter o nível hierárquico do usuário logado

        # Filtrar os níveis hierárquicos que estão abaixo do nível do usuário logado
        niveis_filtrados = [
            {'id': nivel[0], 'nome': nivel[1]}
            for nivel in NIVEIS_HIERARQUIA
            if nivel[0] < user_nivel_hierarquia
        ]

        return Response(niveis_filtrados)


class AvailableProductsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    A viewset that provides `list` actions.

    To use it, override the class and set the `.queryset` and
    `.serializer_class` attributes.
    """

    serializer_class = ProductsSerializer

    def get_queryset(self):
        user = self.request.user

        return user.corban.produtos.all()


class AvailableGroupViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    A viewset that provides `list` actions.

    To use it, override the class and set the `.queryset` and
    `.serializer_class` attributes.
    """

    serializer_class = GroupSerializer

    def get_queryset(self):
        qp = self.request.query_params

        name = qp.get('name') or [
            'Mesa Corban',
            'Corban Master',
        ]
        return Group.objects.filter(name__in=name)


class SupervisorsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    A viewset that provides `list` actions.

    To use it, override the class and set the `.queryset` and
    `.serializer_class` attributes.
    """

    serializer_class = ListSupervisorsSerializer

    def get_nivel_acima(self, nivel_hierarquia):
        try:
            nivel_selecionado = int(nivel_hierarquia)
        except ValueError:
            nivel_selecionado = EnumNivelHierarquia.DIGITADOR

        return nivel_selecionado + 1

    def get_queryset(self):
        qp = self.request.query_params
        user = self.request.user
        return UserProfile.objects.filter(
            corban_id=user.corban_id,
            nivel_hierarquia=self.get_nivel_acima(qp.get('nivel_hierarquia')),
        )


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    A viewset that provides `retrieve`, `create`, and `list` actions.

    To use it, override the class and set the `.queryset` and
    `.serializer_class` attributes.
    """

    filterset_class = UserFilter
    filter_backends = (filters.DjangoFilterBackend,)
    lookup_field = 'unique_id'

    def create(self, request, *args, **kwargs):
        cpf = request.data.get('cpf')
        identifier = cpf.replace('.', '').replace('-', '')
        if request.data.get('supervisor'):
            supervisor_id = get_object_or_404(
                UserProfile, unique_id=request.data.get('supervisor')
            ).id
        else:
            supervisor_id = None

        request.data['identifier'] = identifier
        request.data['supervisor'] = supervisor_id
        request.data['created_by'] = request.user.id
        request.data['corban'] = request.user.corban.id

        return super(UserViewSet, self).create(request, *args, **kwargs)

    # List
    def get_queryset(self):
        return UserProfile.objects.filter(corban=self.request.user.corban).exclude(
            identifier=self.request.user.identifier
        )

    def get_serializer_class(self):
        if self.action == 'list':
            return ListUserProfileSerializer
        elif self.action == 'retrieve':
            return UserProfileDetailSerializer
        else:
            return UserProfileSerializer
