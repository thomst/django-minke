# -*- coding: utf-8 -*-

import re
from django.db import models

from .exceptions import InvalidMinkeSetup


class HostQuerySet(models.QuerySet):
    def get_lock(self, **kwargs):
        """Get a lock for a host."""
        # As the update action returns the rows that haven been updated
        # it will be 0 for an already locked host. An update is performed
        # by a single sql-statement and is therefore the most atomic way
        # to get a lock. This is the reason why we use a query instead of
        # the object himself.
        return bool(self.filter(locked=False, **kwargs).update(locked=True))

    def release_lock(self, **kwargs):
        """Release the lock for hosts."""
        return self.filter(locked=True, **kwargs).update(locked=False)


class Host(models.Model):
    host = models.SlugField(max_length=128, unique=True)
    user = models.SlugField(max_length=128)
    hostname = models.CharField(max_length=128)
    port = models.SmallIntegerField(blank=True, null=True)
    hoststring = models.CharField(max_length=255, unique=True)

    disabled = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)

    unique_together = (("user", "hostname"),)
    objects = HostQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if self.port: format = '{user}@{hostname}:{port}'
        else: format = '{user}@{hostname}'
        self.hoststring = format.format(**vars(self))
        super(Host, self).save(*args, **kwargs)

    class Meta:
        ordering = ['host']

    def __str__(self):
        return self.host


class MinkeManager(models.Manager):
    def get_queryset(self):
        queryset = super(MinkeManager, self).get_queryset()
        return queryset.select_related(self.model.HOST_LOOKUP)


class MinkeModel(models.Model):
    objects = MinkeManager()
    HOST_LOOKUP = 'host'

    def get_host(self):
        host = self
        for attr in self.HOST_LOOKUP.split('__'):
            host = getattr(host, attr, None)
        if not isinstance(host, Host):
            msg = "Invalid host-lookup: {}".format(self.HOST_LOOKUP)
            raise InvalidMinkeSetup(msg)
        else:
            return host

    class Meta:
        abstract = True
