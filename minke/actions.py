# -*- coding: utf-8 -*-

from django.contrib.contenttypes.models import ContentType
from .models import MinkeSession


def clear_news(modeladmin, request, queryset):
    content_type = ContentType.objects.get_for_model(modeladmin.model)
    MinkeSession.objects.clear_currents(request.user, queryset)
clear_news.short_description = 'Clear minke-news'
