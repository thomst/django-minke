# -*- coding: utf-8 -*-
from django.template import Library
from django.contrib.admin.templatetags.admin_list import result_list
from django.contrib.admin.templatetags.admin_list import admin_actions

from ..models import MinkeSession
from ..utils import item_by_attr

register = Library()


@register.inclusion_tag('minke/change_list_results.html')
def minke_result_list(cl):
    """
    Zip results and sessions.
    """
    context = result_list(cl)
    context['results'] = zip(context['results'], cl.sessions)
    return context


@register.inclusion_tag('minke/session_bar.html', takes_context=True)
def minke_session_bar(context):
    """
    Render the session-select-form from within the actions-template.
    """
    cl = context['cl']
    request = context['request']
    form = cl.model_admin.get_session_select_form(request)
    context['session_select_form'] = form
    context['session_count'] = cl.session_count
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
