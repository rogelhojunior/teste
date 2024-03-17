from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def get_settings_value(name):
    """
    Gets specified config name, with default ""

    Usage:
        In top of .html file
            {% load settings %}
        Inside your code
            {% get_settings_value "ENVIRONMENT" %}
    Args:
        name: Settings variable name

    Returns:
        Value of specified variable name
    """
    return getattr(settings, name, '')
