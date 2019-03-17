# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

from minke.models import Host
from minke.models import MinkeModel
from minke.models import MinkeManager


class Server(MinkeModel):
    host = models.OneToOneField(Host, on_delete=models.CASCADE)
    name = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return '[%s]' % self.name


class AnySystemManager(MinkeManager):
    def get_queryset(self):
        queryset = super(AnySystemManager, self).get_queryset()
        return queryset.select_related('server', 'server__host')


class AnySystem(MinkeModel):
    HOST_LOOKUP = 'server__host'

    name = models.CharField(max_length=128)
    server = models.ForeignKey(Server, on_delete=models.CASCADE)
    objects = AnySystemManager()

    def __str__(self):
        return '[%s] %s' % (self.server.name, self.name)
