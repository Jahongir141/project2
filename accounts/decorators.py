from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def waiter_required(view):
    """Ofitsiant (yoki administrator) tizimga kirgan va faol bo'lishi shart."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not (user.is_active and (user.is_waiter_role or user.is_admin_role)):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    """Faqat administrator roli."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin_role:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
