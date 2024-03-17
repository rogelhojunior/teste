from django.db.models import Q
from django_filters import rest_framework as filters

from custom_auth.models import UserProfile


class UserFilter(filters.FilterSet):
    search = filters.CharFilter(method='search_filter')

    class Meta:
        model = UserProfile
        fields = [
            'search',
        ]

    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(email__icontains=value)
            | Q(identifier__icontains=value)
        )
