from django import template

register = template.Library()


@register.filter
def name(user):
    return (user.first_name or user.username) if user else ""


@register.filter
def initial(user):
    return name(user)[:1].upper()


@register.filter
def money(value):
    try:
        return f"₹{value:,.2f}"
    except (TypeError, ValueError):
        return value


@register.filter
def absval(value):
    try:
        return abs(value)
    except TypeError:
        return value
