# -*- coding: utf-8 -*-

from django.db import models


class Host(models.Model):
    host = models.SlugField(max_length=128, unique=True)
    hostname = models.CharField(max_length=128)
    user = models.SlugField(max_length=128)
    port = models.SmallIntegerField(blank=True, null=True)

    disabled = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)

    unique_together = (("user", "ip"),)

    def __str__(self):
        return self.host

    @property
    def host_string(self):
        if self.port:
            format = '{user}@{hostname}:{port}'
        else:
            format = '{user}@{hostname}'
        return format.format(**self.__dict__)
