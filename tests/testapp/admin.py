# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

import sessions
from minke.admin import MinkeAdmin
from minke.models import Host
from minke.filters import StatusFilter
from .models import Server, AnySystem


@admin.register(Host)
class HostAdmin(MinkeAdmin):
    list_filter = ('name', 'hostname')
    search_fields = ('name',)
    ordering = ('name',)
    list_filter = (StatusFilter,)


@admin.register(Server)
class ServerAdmin(MinkeAdmin):
    list_filter = ('host', 'hostname')
    search_fields = ('hostname',)
    ordering = ('host',)


@admin.register(AnySystem)
class AnySystemAdmin(MinkeAdmin):
    list_filter = ('server',)
    search_fields = ('server__hostname',)
    ordering = ('server',)
