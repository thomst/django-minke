from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .sessions import Session
from .messages import Messenger


class StatusFilter(admin.SimpleListFilter):
    title = _('Minke-Status')
    parameter_name = 'minkestatus'

    def __init__(self, request, params, model, model_admin):
        super(StatusFilter, self).__init__(request, params, model, model_admin)
        self.states = (Session.SUCCESS, Session.WARNING, Session.ERROR)

        # are there messages for this model?
        messenger = Messenger(request)
        self.reports = messenger.get(model)

    def has_output(self):
        return bool(self.reports)

    def values(self):
        return self.value().split(',') if self.value() else list()

    def queryset(self, request, queryset):
        if not self.value(): return queryset

        ids = list()
        for status in self.values():
            for id, report in self.reports.items():
                if not report['status'] == status: continue
                ids.append(int(id))
        return queryset.filter(id__in=ids)

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
