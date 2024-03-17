from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework_api_key.permissions import HasAPIKey


class HasAPIKeyOrAllowAny(BasePermission):
    def has_permission(self, request, view):
        has_api_key = HasAPIKey().has_permission(request, view)
        allow_any = IsAuthenticated().has_permission(request, view)
        return has_api_key or allow_any
