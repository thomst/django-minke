# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

from minke.models import Host
from minke.models import MinkeModel


class Server(MinkeModel):
    host = models.OneToOneField(Host, on_delete=models.CASCADE)
    name = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return '[%s]' % self.name


class AnySystem(MinkeModel):
    HOST_LOOKUP = 'server__host'

    name = models.CharField(max_length=128)
    server = models.ForeignKey(Server, on_delete=models.CASCADE)

    def __str__(self):
        return '[%s] %s' % (self.server.name, self.name)
