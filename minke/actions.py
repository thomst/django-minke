# -*- coding: utf-8 -*-

from .messages import Messenger


def clear_news(modeladmin, request, queryset):
    messenger = Messenger(request)
    messenger.remove(objects=queryset)
clear_news.short_description = 'Clear minke-news'
