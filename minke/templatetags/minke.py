# -*- coding: utf-8 -*-
from django.template import Library
from django.contrib.admin.templatetags.admin_list import result_list

from ..models import MinkeSession
from ..utils import item_by_attr

register = Library()


@register.inclusion_tag('minke/change_list_results.html', takes_context=True)
def minke_result_list(context, cl):
    cxt = result_list(cl)
    sessions = MinkeSession.objects.get_currents(context['user'], cl.result_list)
    sessions = list(sessions.prefetch_related('messages'))
    sorted = [item_by_attr(sessions, 'minkeobj_id', o.id) for o in cl.result_list]
    cxt['results'] = zip(cxt['results'], sorted)
    return cxt
