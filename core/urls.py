from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.urls import re_path as url
from django.views.static import serve
from rest_framework.routers import DefaultRouter

import contract
import contract.views as contrato
import core.api.views
from core import views as core_views
from custom_auth.api.views import (
    AvailableGroupViewSet,
    AvailableProductsViewSet,
    HierarchyLevelsView,
    SupervisorsViewSet,
    UserViewSet,
)
from custom_auth.forms import UserLoginForm
from custom_auth.views import get_corban, upload_csv
from documentscopy.views import get_entities, get_stores

from . import settings

admin.autodiscover()
admin.site.login_form = UserLoginForm
admin.site.site_header = 'Back office '
admin.site.index_title = 'Administração'
admin.site.site_title = 'Back office'

router = DefaultRouter()
router.register(
    'termos-de-uso', core.api.views.LegalDocumentsViewSet, basename='termos_de_uso'
)
router.register('users', UserViewSet, basename='users')
router.register('supervisors', SupervisorsViewSet, basename='supervisors')
router.register('groups', AvailableGroupViewSet, basename='groups')
router.register('products', AvailableProductsViewSet, basename='groups')

urlpatterns = [
    path('admin/', admin.site.urls),
    url(r'^chaining/', include('smart_selects.urls')),
    path('', core_views.index, name='index'),
    # APIs para uso em todos os produtos
    path('api/auth/', include('custom_auth.api_urls')),
    path(
        'api/buscar-cep/',
        core.api.views.BuscarCEP.as_view(),
        name='search_cep',
    ),
    path(
        'api/validar-telefone/',
        core.api.views.ValidarTelefone.as_view(),
        name='validar_telefone',
    ),
    path(
        'api/tipos-de-conta-bancaria/',
        core.api.views.TipoContaAPIView.as_view(),
        name='tipos_de_conta',
    ),
    path(
        'api/bancos/',
        core.api.views.BancosBrasileirosAPIView.as_view(),
        name='bancos',
    ),
    path(
        'api/estado-civil/',
        core.api.views.EstadoCivilAPIView.as_view(),
        name='estado_civil',
    ),
    path(
        'api/listar-ufs/',
        core.api.views.UFSAPIView.as_view(),
        name='ufs_brasileiros',
    ),
    path(
        'api/listar-documentos/',
        core.api.views.TiposDocumentosAPIView.as_view(),
        name='tipo_documentos',
    ),
    path(
        'api/listar-sexos/',
        core.api.views.ListarSexosAPIView.as_view(),
        name='tipo_documentos',
    ),
    path(
        'api/update-face-match/',
        core.api.views.UpdateFaceMatching.as_view(),
        name='update_face_match',
    ),
    # path('api/formalizacao/enviar-link/', core.api.views.EnvioLinkFormalizacaoAPIView.as_view()),
    path(
        'api/criar-contrato/', contrato.CriarContrato.as_view(), name='criar-contrato'
    ),
    path('api/validar-contrato/', contrato.ValidarContrato.as_view()),
    path('api/validar-cliente/', core.api.views.ValidarCliente.as_view()),
    path('api/criar-ccb/', core.api.views.CriarCCB.as_view()),
    path('api/assinar-ccb/', core.api.views.AssinarCCB.as_view()),
    path(
        'api/detalhe-in100/<str:cpf>/<str:numero_beneficio>/',
        core.api.views.DetalheIN100.as_view(),
        name='detalhe-in100',
    ),
    path(
        'api/detalhe-in100/<str:cpf>/',
        core.api.views.DetalheIN100.as_view(),
        name='detalhe-in100-cpf',
    ),
    path(
        'api/criar-cliente/',
        core.api.views.CriacaoCliente.as_view(),
        name='api_cria_cliente',
    ),
    path(
        'api/validar-cliente-cpf/digimais',
        core.api.views.ValidarCPFCliente.as_view(),
        name='api_cria_cliente',
    ),
    path(
        'api/atualizar-cliente/',
        core.api.views.AtualizarCliente.as_view(),
        name='update_client',
    ),
    path(
        'api/atualizar-cliente-canais/',
        core.api.views.AtualizarClienteCanais.as_view(),
        name='atualizar_cliente_canais',
    ),
    path(
        'api/pesquisa-contrato/',
        contrato.PesquisaContratos.as_view(),
        name='pesquisa_contrato',
    ),
    path(
        'api/parametros-produto/',
        core.api.views.ParametroProdutoAPIView.as_view(),
        name='parametros-produto',
    ),
    path(
        'api/envio-documentos/',
        core.api.views.EnvioDocumentosCliente.as_view(),
        name='api_upload_documentos',
    ),
    path(
        'api/user-face-matching/',
        core.api.views.UserFaceMatching.as_view(),
        name='api_upload_documentos_face_matching',
    ),
    path(
        'api/facetec/config/',
        core.api.views.FacetecConfig.as_view(),
        name='facetec-config',
    ),
    path(
        'api/facetec/session-token/',
        core.api.views.FacetecSessionToken.as_view(),
        name='facetec-session-token',
    ),
    path(
        'api/facetec/blob-result/',
        core.api.views.FacetecBlobResult.as_view(),
        name='facetec-blob-result',
    ),
    path(
        'api/envio-documentos-formalizacao/',
        core.api.views.EnvioDocumentosClienteFormalizacao.as_view(),
        name='api_upload_documentos_formalalizacao',
    ),
    path(
        'api/atualiza-processo-formalizacao/',
        core.api.views.AtualizarProcessoFormalizacao.as_view(),
        name='api_atualizar_processos',
    ),
    path(
        'api/detalhe-formalizacao/<uuid:token>/',
        core.api.views.DetalheFormalizacao.as_view(),
        name='api_detalhes_formalizacao',
    ),
    # Geolocalizacao
    path(
        'api/verificar-exigencia-geolocalizacao/<str:token>/',
        core.api.views.ValidarExigenciaGeolocalizacao.as_view(),
        name='geolocalizacao-verificar-exigencia',
    ),
    path(
        'api/enviar-sms/',
        core.api.views.EnvioSmsCliente.as_view(),
        name='envia_sms_zenvia',
    ),
    path('api/taxa/', core.api.views.ListarTaxasAPIView.as_view(), name='taxa'),
    path(
        'api/assinatura-termos/',
        core.api.views.AssinaturaTermosFormalizacao.as_view(),
        name='assinatura_termos_formalizacao',
    ),
    path(
        'api/listar-parametros-backoffice/',
        core.api.views.ListarParametros.as_view(),
        name='listar-parametros-backoffice',
    ),
    path(
        'api/criar-envelope/',
        core.api.views.CriarEnvelope.as_view(),
        name='criar-envelope',
    ),
    # APIs Cartão Benficio
    path('api/cartao-beneficio/', include('contract.products.cartao_beneficio.urls')),
    # APIs Consignado INSS
    path('api/consig-inss/', include('contract.products.consignado_inss.urls')),
    path(
        'api/auth/unico/',
        core.api.views.JwtUnicoAPIView.as_view(),
        name='generate_token_unico',
    ),
    path(
        'api/unico/processes/',
        core.api.views.ProcessesUnicoAPIView.as_view(),
        name='unico_process',
    ),
    # APIs Portabilidade
    path(
        'api/calculo-portabilidade/',
        core.api.views.CalculoPortabilidade.as_view(),
        name='portabilidade',
    ),
    path('api/portabilidade/', include('contract.products.portabilidade.urls')),
    path(
        'api/simulacao-portabilidade/',
        contract.views.SimulacaoPortabilidade.as_view(),
        name='simulacao_portabilidade',
    ),
    # path('api/criar-ccb-contrato-portabilidade/',  contract.views.CriarContratoCCBPortabilidade.as_view(),
    #     name='criar_ccb_contrato_portabilidade', ),
    path(
        'api/atualizar-status-contrato/',
        contract.views.StatusContratoPortabilidade.as_view(),
        name='atualizar_status_contrato',
    ),
    path(
        'api/envio-documentos-portabilidade/',
        core.api.views.EnvioDocumentosPortabilidadeCliente.as_view(),
        name='api_upload_documentos_portabilidade',
    ),
    path(
        'api/criar-contrato-portabilidade/',
        contrato.CriarContratoPortabilidade.as_view(),
        name='contrato-portabilidade',
    ),
    path(
        'api/assinar-in100/', contrato.AssinarTermoIN100.as_view(), name='assinar-in100'
    ),
    path(
        'api/enviar-sms-in100/',
        contrato.EnvioSmsIN100.as_view(),
        name='envia_sms_in100',
    ),
    path('api/dados-in100/', contrato.DadosIn100APIView.as_view(), name='dados-in100'),
    # path('api/formalizacao_portabilidade/enviar-link/', core.api.views.EnvioLinkEnvelopeFormalizacaoAPIView.as_view()),
    # Listagem de Contratos Admin
    path('api/kpi/contratos/', contract.views.ContratoKPI.as_view()),
    path('tinymce/', include('tinymce.urls')),
    # URL's para configurações da MESA
    path(
        'mesa/aprovar-contrato/',
        core.api.views.aprova_contrato,
        name='aprovar_contrato',
    ),
    path(
        'mesa-revisao/revisar-contrato/',
        core.api.views.revisar_contrato,
        name='aprovar_contrato',
    ),
    path(
        'mesa/reprovar-contrato/',
        core.api.views.recusa_contrato,
        name='reprovar_contrato',
    ),
    path(
        'mesa/validar-contrato/',
        core.api.views.valida_contrato,
        name='validar_contrato',
    ),
    path(
        'mesa/pendenciar-contrato/',
        core.api.views.pendencia_contrato,
        name='pendenciar_contrato',
    ),
    path(
        'mesa/pendenciar-averbacao/',
        core.api.views.pendencia_averbacao,
        name='pendenciar_averbacao',
    ),
    path(
        'cancelamento/tem-saude/',
        core.api.views.cancelar_plano_tem_saude,
        name='cancelar_temsaude',
    ),
    path(
        'api/get-parametros/',
        core.api.views.GetParameters.as_view(),
        name='get_parametros',
    ),
    # Auth
    path('accounts/', include('django.contrib.auth.urls')),
    # Contratos
    path('api/contratos/', include('contract.urls')),
    # Token DOCK PROD
    # path('api/gerar-token/', core.api.views.GerarTokenDock.as_view()),
    # Legal Documents
    path('api/', include(router.urls)),
    # Simulação
    path('api/simulacao/', include('simulacao.urls')),
    path(
        'api/portabilidade-refin/',
        include('contract.products.portabilidade_refin.urls'),
    ),
    path('api/rest/', include('api_caller.urls')),
    path(
        'api/get-list-archive/',
        core.api.views.ListArchiveToFtp.as_view(),
        name='get_parametros',
    ),
    path(
        'api/test-create-archive/',
        core.api.views.TestCreateArchive.as_view(),
        name='get_parametros',
    ),
    path('import_excel/', core.api.views.import_excel_view, name='import_excel_cartao'),
    path('get-corban/<int:corban_id>', get_corban, name='get_corban'),
    path('get-entities/', get_entities, name='get_entities'),
    path('get-stores/', get_stores, name='get_stores'),
    path('custom_auth/upload-csv/', upload_csv, name='upload_csv'),
    path(
        'api/hierarchy-levels/', HierarchyLevelsView.as_view(), name='niveis-hierarquia'
    ),
    path(
        'api/available-offers/',
        core.api.views.AvailableOffersAPIView.as_view(),
        name='available-offers',
    ),
    path(
        'api/consultar-seguros-contratado/',
        core.api.views.ConsultarSegurosContratado.as_view(),
        name='consultar-seguros-contratado',
    ),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += staticfiles_urlpatterns()
urlpatterns += [
    url(
        r'^media/(?P<path>.*)$',
        serve,
        {
            'document_root': settings.MEDIA_ROOT,
        },
    ),
    url(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]
