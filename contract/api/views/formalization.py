import logging
from typing import Literal

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey

from contract.services.registration.formalization import (
    FinalizeClientFormalizationProcessor,
    BaseFinalizeFormalization,
    FinalizeRogadoFormalizationProcessor,
)
from core.models import Cliente


class BaseFinalizeFormalizationView(APIView):
    permission_classes = [HasAPIKey | AllowAny]
    formalization_type: Literal['cliente', 'rogado'] = None
    finalization_class: BaseFinalizeFormalization = BaseFinalizeFormalization

    def post(self, request, *args, **kwargs):
        token_envelope = request.data['token_envelope']
        try:
            self.finalization_class(
                client=Cliente.objects.get(nu_cpf=request.data['cpf']),
                token_envelope=request.data['token_envelope'],
                geolocation={
                    'latitude': request.data['latitude'],
                    'longitude': request.data['longitude'],
                    'public_ip': request.data['ip_publico'],
                },
            ).process()

            return Response(
                {'Sucesso': 'Formalização finalizada com sucesso'},
                status=status.HTTP_200_OK,
            )
        except KeyError as e:
            logging.error(
                f'Envelope: ({token_envelope}) - Erro ao finalizar formalização ({self.formalization_type}): Chave não encontrada: {e}'
            )
            return Response(
                {'Erro': 'Verifique os parâmetros enviados'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Cliente.DoesNotExist as e:
            logging.error(
                f'Envelope: ({token_envelope}) - Erro ao finalizar formalização ({self.formalization_type}): Cliente não encontrado {e}'
            )
            return Response(
                {'Erro': 'Verifique os parâmetros enviados'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logging.error(
                f'Envelope: ({token_envelope}) - Erro ao finalizar formalização ({self.formalization_type}): {e}'
            )
            return Response(
                {'Erro': 'Erro ao finalizar formalização'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FinalizeClientFormalizationView(BaseFinalizeFormalizationView):
    formalization_type = 'cliente'
    finalization_class = FinalizeClientFormalizationProcessor


class FinalizeRogadoFormalizationView(BaseFinalizeFormalizationView):
    formalization_type = 'rogado'
    finalization_class = FinalizeRogadoFormalizationProcessor
