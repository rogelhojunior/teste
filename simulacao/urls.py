from django.urls import path

from simulacao.api import views

urlpatterns = [
    path('simular-contrato-margem-livre/', views.SimulateFreeMarginContract.as_view()),
]
