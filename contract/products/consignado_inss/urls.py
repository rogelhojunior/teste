from django.urls import path

import contract.products.consignado_inss.api.views as consig_view

urlpatterns = [
    # path('consulta-beneficios-inss/', consig_view.consulta_beneficios_inss.as_view()),
    path('realiza-simulacao/', consig_view.RealizaSimulacao.as_view()),
    path('atualizar-contrato/', consig_view.AtualizarContratoMargemLivre.as_view()),
    path('webhook-qitech/', consig_view.ReceberWebhookQitech.as_view()),
    path(
        'reapresentacao-pagamento/',
        consig_view.ReapresentacaoPagamentoMargemLivre.as_view(),
    ),
]
