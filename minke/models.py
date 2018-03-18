# -*- coding: utf-8 -*-

import re
from django.db import models


class HostManager(models.Manager):

    def get_lock(self, **kwargs):
        """Get a lock for a host."""
        # As the update action returns the rows that haven been updated
        # it will be 0 for an already locked host. An update is performed
        # by a single sql-statement and is therefore the most atomic way
        # to get a lock. This is the reason why we use a query instead of
        # the object himself.
        return bool(self.model.objects \
                    .filter(locked=False, **kwargs) \
                    .update(locked=True))

    def release_lock(self, **kwargs):
        """Release a lock for a host."""
        # This could be done by a model-method as well. To be consistent we
        # implemented it in the same style as get_lock.
        return self.model.objects \
                    .filter(locked=True, **kwargs) \
                    .update(locked=False)


class Host(models.Model):
    host = models.SlugField(max_length=128, unique=True)
    user = models.SlugField(max_length=128)
    hostname = models.CharField(max_length=128)
    port = models.SmallIntegerField(blank=True, null=True)
    hoststring = models.CharField(max_length=255, unique=True)

    disabled = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)

    unique_together = (("user", "hostname"),)
    objects = HostManager()

    def save(self, *args, **kwargs):
        if self.port: format = '{user}@{hostname}:{port}'
        else: format = '{user}@{hostname}'
        self.hoststring = format.format(**vars(self))
        super(Host, self).save(*args, **kwargs)

    def __str__(self):
        return self.host

    class Meta:
        permissions = (
            ('run_host_minke_sessions', 'Can run minke-sessions'),
        )
