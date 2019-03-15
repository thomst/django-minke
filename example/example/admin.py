# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

import sessions
from minke.admin import MinkeAdmin
from minke.models import Host
from minke.filters import StatusFilter
from .models import Server
from .models import AnySystem


@admin.register(Host)
class HostAdmin(MinkeAdmin):
    list_filter = ('host', 'hostname')
    search_fields = ('host',)
    readonly_fields = ('hoststring',)
    ordering = ('host',)
    list_filter = (StatusFilter,)


@admin.register(Server)
class ServerAdmin(MinkeAdmin):
    list_filter = ('host', 'name')
    search_fields = ('name',)
    ordering = ('host',)


@admin.register(AnySystem)
class AnySystemAdmin(MinkeAdmin):
    list_filter = ('name', 'server',)
    search_fields = ('name', 'server__name',)
    ordering = ('name',)
