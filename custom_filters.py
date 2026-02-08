# your_app/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def to(value):
    """返回一个从 1 到给定数字的范围列表"""
    try:
        return range(1, value + 1)
    except TypeError:
        return []
