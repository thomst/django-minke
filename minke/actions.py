# -*- coding: utf-8 -*-

from .messages import clear_msgs


def clear_messages(modeladmin, request, queryset):
    clear_msgs(request, modeladmin.model, queryset)
clear_messages.short_description = 'Clear minke-messages'
