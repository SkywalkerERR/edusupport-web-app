from django import template

register = template.Library()


@register.filter
def spacenumber(value):
    """123000 → 123 000"""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (ValueError, TypeError):
        return value or "—"
