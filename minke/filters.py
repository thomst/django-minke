from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class SelectStatus(admin.SimpleListFilter):
    title = _('Select Status')
    parameter_name = 'minkestatus'
    template = 'minke/selectstatus.html'

    def has_output(self):
        return True

    def lookups(self, request, model_admin):
        return tuple()

    def queryset(self, request, queryset):
        return queryset

    def choices(self, changelist):
        for status in ['success', 'warning', 'error']:
            yield {
                'query_string': changelist.get_query_string({}, [self.parameter_name]),
                'display': status.title(),
                'status': status,
            }
