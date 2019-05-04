# -*- coding: utf-8 -*-

from django.contrib import admin
from django.forms.widgets import Select
from minke.admin import MinkeAdmin
from minke.models import MinkeSession
from .models import Command
from .sessions import CommandChoicesSession


@admin.register(Command)
class CommandAdmin(MinkeAdmin):
    list_display = ('cmd', 'short_description', 'session_cls', 'active')
    list_editable = ('active',)
    search_fields = ('short_description', 'cmd')
    ordering = ('short_description', 'session_cls')
    list_filter = ('session_cls',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # set choices for session_cls to CommandChoicesSessions
        check = lambda s: issubclass(s, CommandChoicesSession)
        sessions = MinkeSession.REGISTRY.values()
        choices = [(s.__name__, s.VERBOSE_NAME) for s in sessions if check(s)]
        form.base_fields['session_cls'].widget = Select(choices=choices)
        form.base_fields['session_cls'].choices = choices
        return form
