# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from .messages import Messenger


def clear_news(modeladmin, request, queryset):
    messenger = Messenger(request)
    messenger.remove(objects=queryset)
    messenger.process()
clear_news.short_description = 'Clear minke-news'
