from django.urls import path

import contract
import contract.api.views as contrato_view
from contract.api.views.formalization import (
    FinalizeRogadoFormalizationView,
    FinalizeClientFormalizationView,
)
from contract.api.views.get_qi_tech_data import GetAPIQiTech, GetDebtAPIQiTech

urlpatterns = [
    path('detalhe-contratos/', contrato_view.DetalheContrato.as_view()),
    path('listar-contratos/', contract.api.views.ListarContratos.as_view()),
    path('listar-especie/', contract.api.views.ListarEspecie.as_view()),
    path(
        'formalizacao/enviar-link/',
        contrato_view.EnvioLinkFormalizacaoAPIView.as_view(),
    ),
    path(
        'formalizacao/fluxo-proposta/',
        contrato_view.ModificaFluxoPortabilidadeAPIView.as_view(),
    ),
    # path('finalizar-formalizacao/', contrato_view.FinalizarFormalizacao.as_view()),
    path('finalizar-formalizacao-cliente/', FinalizeClientFormalizationView.as_view()),
    path('finalizar-formalizacao-rogado/', FinalizeRogadoFormalizationView.as_view()),
    path(
        'confirma-score/',
        contrato_view.CallbackUnico.as_view(),
        name='callback_unico_score',
    ),
    path('confirma-resultado-confia/', contrato_view.CallbackConfia.as_view()),
    path(
        'retorno-saque/',
        contrato_view.RetornoSaqueAPIView.as_view(),
        name='retorno_saque',
    ),
    path('excluir-anexo/', contrato_view.ExcluirDocumento.as_view()),
    path('regularizar-pendencia/', contrato_view.RegularizarPendencia.as_view()),
    path(
        'regularizar-pendencia-averbacao/',
        contrato_view.RegularizarPendenciaAverbacao.as_view(),
    ),
    path(
        'consulta-documentos-produto/',
        contrato_view.VerificaDocumentacaoProduto.as_view(),
    ),
    path(
        'consulta-status-produto/',
        contrato_view.TipoProdutoStatusMapping.as_view(),
    ),
    path('historico-teimosinha-inss/', contrato_view.HistoricoTeimosinhaInss.as_view()),
    path(
        'detalhe-contrato-callcenter/',
        contrato_view.DetalheContratoCallCenter.as_view(),
    ),
    path(
        'detalhe-cliente-callcenter/', contrato_view.DetalheClienteCallCenter.as_view()
    ),
    path('typists/', contrato_view.TypistListView.as_view(), name='typist-list'),
    path('relatorios/', contrato_view.ExportarContratos.as_view()),
    path(
        'get-qitech/<str:proposal_key>/',
        GetAPIQiTech.as_view(),
        name='get-qitech',
    ),
    path(
        'get-debt-qitech/<str:proposal_key>/',
        GetDebtAPIQiTech.as_view(),
        name='get-debt-qitech',
    ),
    path(
        'webhook/pay/digimais/',
        contrato_view.PaymentResubmissionView.as_view(),
        name='pay-digimais',
    ),
]
