# -*- coding: utf-8 -*-
from django.template import Library
from django.contrib.admin.templatetags.admin_list import result_list
from django.contrib.admin.templatetags.admin_list import admin_actions

from ..models import MinkeSession
from ..utils import item_by_attr

register = Library()


@register.inclusion_tag('minke/change_list_results.html', takes_context=True)
def minke_result_list(context):
    cl = context['cl']
    cxt = result_list(cl)
    sessions = MinkeSession.objects.get_currents(context['user'], cl.result_list)
    sessions = list(sessions.prefetch_related('messages'))
    sorted = [item_by_attr(sessions, 'minkeobj_id', o.id) for o in cl.result_list]
    cxt['results'] = zip(cxt['results'], sorted)
    return cxt

@register.inclusion_tag('minke/admin_actions.html', takes_context=True)
def minke_admin_actions(context):
    return admin_actions(context)

@register.inclusion_tag('minke/session_bar.html', takes_context=True)
def minke_session_bar(context):
    cl = context['cl']
    request = context['request']
    form = cl.model_admin.get_session_select_form(request)
    context['session_select_form'] = form
    context['current_sessions'] = cl.model_admin.get_current_sessions(request)
    return context
