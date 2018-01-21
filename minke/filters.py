from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .messages import get_msgs


class StatusFilter(admin.SimpleListFilter):
    title = _('Minke-Status')
    parameter_name = 'minkestatus'

    def __init__(self, request, params, model, model_admin):
        super(StatusFilter, self).__init__(request, params, model, model_admin)
        self.states = ('success', 'warning', 'error')

        # are there messages for this model?
        try:
            assert bool(request.session['minke'][model.__name__])
        except (AssertionError, KeyError):
            self.msgs = None
        else:
            self.msgs = request.session['minke'][model.__name__]

    def has_output(self):
        return bool(self.msgs)

    def values(self):
        return self.value().split(',') if self.value() else list()

    def queryset(self, request, queryset):
        if self.value():
            ids = list()
            for status in self.values():
                ids += [int(id) for id, m in self.msgs.items() if m['status'] == status]
            return queryset.filter(id__in=ids)
        else:
            return queryset

    def choices(self, changelist):
        yield {
            'selected': not self.values(),
            'query_string': changelist.get_query_string({}, [self.parameter_name]),
            'display': _('All'),
        }
        for status in self.states:
            selected = status in self.values()
            if selected:
                values = set(self.values()) - set([status])
            else:
                values = set(self.values()) | set([status])
            if values:
                new_param = {self.parameter_name: ','.join(values)}
            else:
                new_param = dict()
            query_string = changelist.get_query_string(new_param, [self.parameter_name])
            yield {
                'selected': selected,
                'query_string': query_string,
                'display': status.title(),
            }

    def lookups(self, request, model_admin):
        return tuple()
