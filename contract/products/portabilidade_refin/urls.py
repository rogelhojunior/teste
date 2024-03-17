from django.urls import include, path
from rest_framework.routers import DefaultRouter

from contract.products.portabilidade_refin.api import PortRefinViewSet

router = DefaultRouter()

router.register(
    '',
    PortRefinViewSet,
    basename='portabilidade-refin',
)

urlpatterns = [
    path('', include(router.urls)),
]
