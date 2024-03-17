from django.conf import settings


def front_login(request):
    return {'base_url': settings.BASE_URL}
