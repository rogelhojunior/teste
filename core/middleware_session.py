from django.contrib.sessions.models import Session

from custom_auth.models import UserSession


class OneSessionPerUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            current_session_key = request.session.session_key
            try:
                user_session = UserSession.objects.get(user=request.user)
                if user_session.session_key != current_session_key:
                    Session.objects.filter(
                        session_key=user_session.session_key
                    ).delete()
                user_session.session_key = current_session_key
                user_session.save()
            except UserSession.DoesNotExist:
                UserSession.objects.create(
                    user=request.user, session_key=current_session_key
                )
        return response
