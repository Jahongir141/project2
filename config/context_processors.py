from django.conf import settings


def brand(request):
    return {"RESTAURANT_NAME": settings.RESTAURANT_NAME}
