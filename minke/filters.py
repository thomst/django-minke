# -*- coding: utf-8 -*-

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import MinkeSession


class StatusFilter(admin.SimpleListFilter):
    """
    Filter objects by the session-status of their current sessions.
    """
    title = _('Session-Status')
    parameter_name = 'minkestatus'

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        self.states = (s[0] for s in MinkeSession.SESSION_STATES)
        qs = model_admin.get_queryset(request)
        self.sessions = MinkeSession.objects.get_currents(request.user, qs)

    def has_output(self):
        return bool(self.sessions)

    def values(self):
        return self.value().split(',') if self.value() else list()

    def queryset(self, request, queryset):
        if not self.value(): return queryset

        ids = list()
        for status in self.values():
            for session in self.sessions.all():
                if not session.session_status == status: continue
                ids.append(session.minkeobj_id)
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
