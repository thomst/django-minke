# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.contenttypes.models import ContentType

from minke.models import MinkeModel
from minke.models import MinkeSession
from minke.models import Host


class Command(models.Model):
    cmd = models.TextField()
    short_description = models.CharField(max_length=256, blank=True)
    description = models.TextField(blank=True)
    session_cls = models.CharField(max_length=128)
    active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # linux-shells will need \n as the newline-chars
        self.cmd = self.cmd.replace('\r\n', '\n').replace('\r', '\n')
        return super().save(*args, **kwargs)

    def __str__(self):
        if self.short_description:
            return self.short_description
        else:
            return self.cmd[:32] + (self.cmd[32:] and '..')
