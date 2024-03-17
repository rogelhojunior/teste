"""This function implements the view callback_confia."""

# thirds
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request

# local
from rest_framework.response import Response

from .confia_request_processor import ConfiaRequestProcessor


@api_view(['POST'])
@permission_classes((AllowAny,))
@method_decorator(csrf_exempt)
def callback_confia(request: Request) -> Response:
    """
    This function works as a view, responsible to handle the request
    sent by the system UNICO, this request contains data about an
    previous sent selfie.

    Args:
        request (Request): the incoming request.

    Returns:
        Response: the http response.
    """
    confia_request = ConfiaRequestProcessor(request)
    confia_request.process_request()
    return confia_request.make_success_response()
