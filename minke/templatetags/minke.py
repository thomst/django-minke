# -*- coding: utf-8 -*-
from django.template import Library
from django.contrib.admin.templatetags.admin_list import result_list
from django.contrib.admin.templatetags.admin_list import admin_actions

from ..models import MinkeSession
from ..utils import item_by_attr

register = Library()


@register.inclusion_tag('minke/change_list_results.html', takes_context=True)
def minke_result_list(context):
    """
    Replacement of django's result_list-inclusion_tag.
    We use our own template and pass sessions as context.
    """
    cl = context['cl']
    cxt = result_list(cl)
    sessions = MinkeSession.objects.get_currents(context['user'], cl.result_list)
    sessions = list(sessions.prefetch_related('messages'))
    sorted = [item_by_attr(sessions, 'minkeobj_id', o.id) for o in cl.result_list]
    cxt['results'] = zip(cxt['results'], sorted)
    return cxt


@register.inclusion_tag('minke/admin_actions.html', takes_context=True)
def minke_admin_actions(context):
    """
    Same as django's admin_action-inclusion_tag but with our own template.
    """
    return admin_actions(context)


@register.inclusion_tag('minke/session_bar.html', takes_context=True)
def minke_session_bar(context):
    """
    Render the session-select-form from within the actions-template.
    """
    cl = context['cl']
    request = context['request']
    form = cl.model_admin.get_session_select_form(request)
    context['session_select_form'] = form
    context['current_sessions'] = cl.model_admin.get_current_sessions(request)
    return context


@register.inclusion_tag('minke/session.html', takes_context=True)
def minke_session(context):
    """
    Render the session-info-row.
    """
    return context


@register.simple_tag(takes_context=True)
def update_url_query(context, key, value=None):
    """
    Update the current url-query.
    """
    query_dict = context['request'].GET.copy()
    if value is None and key in query_dict:
        del query_dict[key]
    elif value is not None:
        query_dict[key] = value
    return '?' + query_dict.urlencode()
