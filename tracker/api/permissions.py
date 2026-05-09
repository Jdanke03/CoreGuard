from rest_framework.permissions import BasePermission

from tracker.services.roles import is_physio


class IsPhysio(BasePermission):
    message = "Only physiotherapists can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_physio(request.user))


class IsClient(BasePermission):
    message = "Only clients can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and not is_physio(request.user))


class IsAssignedPhysioForAnalysis(BasePermission):
    message = "Only the assigned physiotherapist can manage analysis feedback."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_physio(request.user))

    def has_object_permission(self, request, view, obj):
        return bool(obj.plan and obj.plan.created_by_id == request.user.id)
