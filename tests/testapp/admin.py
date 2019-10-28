# -*- coding: utf-8 -*-

from django.contrib import admin

from minke.admin import MinkeAdmin
from .models import Server
from .models import AnySystem


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
