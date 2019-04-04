# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from . import sessions
from minke.admin import MinkeAdmin
from minke.models import Host
from minke.filters import StatusFilter
from .models import Server
from .models import AnySystem


@admin.register(Host)
class HostAdmin(MinkeAdmin):
    list_display = ('name', 'verbose_name', 'hostname')
    search_fields = ('name', 'hostname')
    ordering = ('name',)
    list_filter = (StatusFilter,)


@admin.register(Server)
class ServerAdmin(MinkeAdmin):
    list_display = ('name', 'host')
    search_fields = ('name', 'host', 'host__hostname')
    ordering = ('host', 'name')
    list_filter = (StatusFilter,)

    def get_queryset(self, request):
        qs = super(ServerAdmin, self).get_queryset(request)
        return qs.prefetch_related('host')


@admin.register(AnySystem)
class AnySystemAdmin(MinkeAdmin):
    list_display = ('name', 'server',)
    search_fields = ('name', 'server__name',)
    ordering = ('server', 'name')
    list_filter = (StatusFilter,)

    def get_queryset(self, request):
        qs = super(AnySystemAdmin, self).get_queryset(request)
        return qs.prefetch_related('server__host')
