"""This module implements callback_unico_score view."""

# thirds
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request

# local
from rest_framework.response import Response

from .unico_request_processor import UnicoRequestProcessor


@api_view(['POST'])
@permission_classes((AllowAny,))
@method_decorator(csrf_exempt)
def callback_unico_score(request: Request) -> Response:
    """
    This function works as a view, responsible to handle the request
    sent by the system UNICO, this request contains data about an
    previous sent selfie.

    Args:
        request (Request): the incoming request.

    Returns:
        Response: the http response.
    """
    unico_request = UnicoRequestProcessor(request)
    unico_request.process_request()
    return unico_request.make_success_response()
