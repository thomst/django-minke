# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

from minke.models import Host
from minke.models import MinkeModel


class Server(MinkeModel):
    host = models.OneToOneField(Host, on_delete=models.CASCADE)
    hostname = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return self.hostname

class AnySystem(MinkeModel):
    HOST_LOOKUP = 'server__host'
    server = models.ForeignKey(Server, on_delete=models.CASCADE)

    def __str__(self):
        return self.server.hostname
