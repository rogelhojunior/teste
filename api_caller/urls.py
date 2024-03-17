from django.urls import path

from api_caller.views import api_caller_view

urlpatterns = [
    path('api-caller/', api_caller_view, name='api_caller'),
]
