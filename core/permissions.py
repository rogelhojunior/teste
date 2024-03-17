from rest_framework.permissions import BasePermission

from custom_auth.models import FeatureToggle


class IsAuthenticatedAndChecked(BasePermission):
    """
    Allows access only to authenticated users and is_checked.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        is_checked = user.is_checked
        is_staff = user.is_staff

        if not is_checked and not is_staff:
            is_checked = not FeatureToggle.is_feature_active(
                FeatureToggle.FACE_MATCHING
            )

        return bool(is_checked or is_staff)


# class IsCorban(BasePermission):
#     """
#     Allows access only to authenticated users and is_checked.
#     """

#     def has_permission(self, request, view):
#         user = request.user

#         return bool(
#             user and user.is_authenticated and (user.is_checked or user.is_staff)
#         )
