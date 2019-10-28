# -*- coding: utf-8 -*-

from django.contrib import admin
from .models import Command
from .models import CommandGroup
from .models import CommandOrder


class CommandOrderInline(admin.TabularInline):
    model = CommandOrder
    fields = ('command',)
    extra = 1


class BaseCommandAdmin(admin.ModelAdmin):
    list_editable = ('active',)
    ordering = ('label',)
    list_filter = ('minketypes',)

    def minketypes_view(self, obj):
        types = (ct.model_class().__name__ for ct in obj.minketypes.all())
        return ', '.join(types)
    minketypes_view.short_description = 'Minke-Models'


@admin.register(Command)
class CommandAdmin(BaseCommandAdmin):
    list_display = ('cmd', 'label', 'minketypes_view', 'active')
    search_fields = ('label', 'cmd')


@admin.register(CommandGroup)
class CommandGroupAdmin(BaseCommandAdmin):
    inlines = (CommandOrderInline,)
    list_display = ('label', 'minketypes_view', 'active')
    search_fields = ('label',)
