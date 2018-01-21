
from django.template import Library

from django.contrib.admin.templatetags.admin_list import result_headers
from django.contrib.admin.templatetags.admin_list import result_hidden_fields
from django.contrib.admin.templatetags.admin_list import results

from ..engine import get_msgs

register = Library()


@register.inclusion_tag("admin/config_list_results.html")
def config_result_list(cl, request):

    # FIXME: got a good indicator here
    if True:
        result_list = list(results(cl))
        for result, obj in zip(result_list, cl.result_list):
            msgs = get_msgs(request, obj)
            if not msgs: continue
            result.minke_status = msgs.get('status', str())
            result.minke_messages = msgs.get('msgs', list())
    else:
        result_list = list(results(cl))

    headers = list(result_headers(cl))
    num_sorted_fields = 0
    for h in headers:
        if h['sortable'] and h['sorted']:
            num_sorted_fields += 1
    return {'cl': cl,
            'result_hidden_fields': list(result_hidden_fields(cl)),
            'result_headers': headers,
            'num_sorted_fields': num_sorted_fields,
            'results': result_list}
