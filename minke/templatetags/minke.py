# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.template import Library

register = Library()

@register.simple_tag(takes_context=True)
def get_session(context, cl, index):
    context['session'] = cl.minke_sessions[index]
    return str()
