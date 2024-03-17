from django.urls import path

import contract.products.portabilidade.api.views as portabilidade_views

urlpatterns = [
    path('acao-corban/', portabilidade_views.AcaoCorban.as_view()),
    path(
        'aprova-contrato/',
        portabilidade_views.botao_aprovar_contrato,
    ),
    path(
        'recusa-contrato/',
        portabilidade_views.botao_recusar_contrato,
    ),
    path(
        'pedencia-contrato/',
        portabilidade_views.botao_pendenciar_contrato,
    ),
    path('atualiza-pendencia/', portabilidade_views.update_issue_button),
    path('consulta-beneficio-in100/', portabilidade_views.consulta_beneficio_in100),
    path(
        'aceite-proposta-portabilidade/', portabilidade_views.aceita_proposta_qitech_cip
    ),
    path(
        'recusa-proposta-portabilidade/', portabilidade_views.recusa_proposta_qitech_cip
    ),
    path(
        'valida-cpf-receita-corban/',
        portabilidade_views.ValidarCPFReceitaCorban.as_view(),
    ),
    path(
        'consulta-autorizacao-in100/',
        portabilidade_views.ConsultaAutorizacaoIN100.as_view(),
    ),
    path(
        'regras-elegibilidade/',
        portabilidade_views.RegrasElegibilidade.as_view(),
        name='regras_elegibilidade_portabilidade',
    ),
    path(
        'regras-elegibilidade-especifica/',
        portabilidade_views.RegrasElegibilidadeEspecies.as_view(),
        name='regras_elegibilidade_especifica',
    ),
]
