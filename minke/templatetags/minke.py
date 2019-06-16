# -*- coding: utf-8 -*-
from django.template import Library
from django.contrib.admin.templatetags.admin_list import result_list
from django.contrib.admin.templatetags.admin_list import admin_actions

from ..models import MinkeSession
from ..utils import item_by_attr

register = Library()


@register.inclusion_tag('minke/change_list_results.html', takes_context=True)
def minke_result_list(context, cl):
    """
    Support rendering of session-info-rows for changelist-results.
    """
    sessions = cl.sessions if hasattr(cl, 'sessions') else cl.result_list
    context.update(result_list(cl))
    context['results'] = zip(context['results'], sessions)
    return context


@register.inclusion_tag('minke/session_select.html', takes_context=True)
def minke_session_select(context):
    """
    Render the session-select-form.
    """
    cl = context['cl']
    request = context['request']
    form = cl.model_admin.get_session_select_form(request)
    context['session_select_form'] = form
    context['session_count'] = cl.session_count
    return context


@register.inclusion_tag('minke/session_switch.html', takes_context=True)
def minke_session_switch(context):
    """
    Render the session-switch-bar.
    """
    return context


@register.inclusion_tag('minke/session.html', takes_context=True)
def minke_session(context):
    """
    Render the session-info-row.
    """
    return context


@register.inclusion_tag('minke/session_history.html', takes_context=True)
def minke_session_history(context):
    """
    Render the session-history-table.
    """
    return context


@register.simple_tag(takes_context=True)
def update_url_query(context, *args):
    """
    Update the current url-query.
    """
    query_dict = context['request'].GET.copy()
    args = list(args)
    while args:
        key = args.pop(0)
        if key.startswith('-'):
            if key[1:] in query_dict: del query_dict[key[1:]]
        else:
            query_dict[key] = args.pop(0)
    return '?' + query_dict.urlencode()
