from django import template

register = template.Library()


@register.filter
def money(value):
    try:
        return f"{int(value):,}".replace(",", "\u00a0")
    except (TypeError, ValueError):
        return value
