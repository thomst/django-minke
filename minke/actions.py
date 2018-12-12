# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType

from .models import BaseSession


def clear_news(modeladmin, request, queryset):
    content_type = ContentType.objects.get_for_model(modeladmin.model)
    BaseSession.objects.clear_currents(request.user, queryset)
clear_news.short_description = 'Clear minke-news'
