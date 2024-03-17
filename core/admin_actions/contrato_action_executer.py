"""
This file implements ContratoActionExecuter class.
"""

from rest_framework.request import Request
from django.db.models.query import QuerySet


class ContratoActionExecuter:
    """
    This class can be used as parent class for all the action executer
    classes for Contrato model object.
    """

    def __init__(self, request: Request, queryset: QuerySet):
        self.request: Request = request
        self.queryset: QuerySet = queryset

    def execute(self):
        raise NotImplementedError
