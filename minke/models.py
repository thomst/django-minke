# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
from time import time

from picklefield.fields import PickledObjectField

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError

from .exceptions import InvalidMinkeSetup


class BaseSessionQuerySet(models.QuerySet):
    def get_currents(self, user, players):
        content_type = ContentType.objects.get_for_model(players.model)
        return self.filter(
            user=user,
            content_type=content_type,
            object_id__in=list(players.all().values_list('id', flat=True)),
            current=True)

    def get_currents_by_model(self, user, model):
        content_type = ContentType.objects.get_for_model(model)
        return self.filter(
            user=user,
            content_type=content_type,
            current=True)

    def clear_currents(self, user, players):
        return self.get_currents(user, players).update(current=False)


class BaseSession(models.Model):
    objects = BaseSessionQuerySet.as_manager()

    RESULT_STATES = (
        ('success', 'success'),
        ('warning', 'warning'),
        ('error', 'error'),
    )
    PROC_STATES = (
        ('initialized', 'initialized'),
        ('running', 'running'),
        ('done', 'done'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    player = GenericForeignKey('content_type', 'object_id')
    session_name = models.CharField(max_length=128)
    session_data = PickledObjectField(blank=True)
    current = models.BooleanField(default=True)
    status = models.CharField(max_length=128, choices=RESULT_STATES)
    proc_status = models.CharField(max_length=128, choices=PROC_STATES, default='initialized')


class BaseMessage(models.Model):
    LEVELS = (
        ('info', 'info'),
        ('warning', 'warning'),
        ('error', 'error'))

    session = models.ForeignKey(BaseSession, on_delete=models.CASCADE, related_name='messages')
    level = models.CharField(max_length=128, choices=LEVELS)
    text = models.TextField()
    html = models.TextField()


class HostQuerySet(models.QuerySet):
    def release_lock(self):
        return self.update(locked=None)

    def get_lock(self):
        # The most atomic way to get a lock is a update-query.
        # We use a timestamp to be able to identify the updated objects.
        timestamp = repr(time())
        self.filter(locked=None).update(locked=timestamp)
        return timestamp

    def get_actives(self, lock):
        return self.filter(disabled=False).filter(locked=lock)

    def get_hosts(self):
        return self

    def host_filter(self, hosts):
        return self & hosts


class Host(models.Model):
    host = models.SlugField(max_length=128, unique=True)
    user = models.SlugField(max_length=128)
    hostname = models.CharField(max_length=128)
    port = models.SmallIntegerField(blank=True, null=True)
    hoststring = models.CharField(max_length=255, unique=True)

    disabled = models.BooleanField(default=False)
    locked = models.CharField(max_length=20, blank=True, null=True)

    unique_together = (("user", "hostname"),)
    objects = HostQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if self.port: format = '{user}@{hostname}:{port}'
        else: format = '{user}@{hostname}'
        self.hoststring = format.format(**vars(self))
        super(Host, self).save(*args, **kwargs)

    def get_host(self):
        return self

    class Meta:
        ordering = ['host']

    def __str__(self):
        return self.host


class MinkeQuerySet(models.QuerySet):
    def get_hosts(self):
        lookup = self.model.get_reverse_host_lookup() + '__id__in'
        ids = self.values_list('id', flat=True)
        try:
            return Host.objects.filter(**{lookup:ids})
        except FieldError:
            msg = "Invalid reverse-host-lookup: {}".format(lookup)
            raise InvalidMinkeSetup(msg)

    def host_filter(self, hosts):
        lookup = self.model.HOST_LOOKUP + '__id__in'
        ids = hosts.values_list('id', flat=True)
        try:
            return self.filter(**{lookup:ids})
        except FieldError:
            msg = "Invalid host-lookup: {}".format(lookup)
            raise InvalidMinkeSetup(msg)


class MinkeManager(models.Manager):
    def get_queryset(self):
        queryset = MinkeQuerySet(self.model, using=self._db)
        try:
            return queryset.select_related(self.model.HOST_LOOKUP)
        except FieldError:
            msg = "Invalid host-lookup: {}".format(self.model.HOST_LOOKUP)
            raise InvalidMinkeSetup(msg)


class MinkeModel(models.Model):
    objects = MinkeManager()
    HOST_LOOKUP = 'host'
    REVERSE_HOST_LOOKUP = None

    @classmethod
    def get_reverse_host_lookup(cls):
        if cls.REVERSE_HOST_LOOKUP:
            lookup = self.REVERSE_HOST_LOOKUP
        else:
            lookup_list = cls.HOST_LOOKUP.split('__')
            lookup_list.reverse()
            lookup_list.append(cls.__name__.lower())
            lookup = '__'.join(lookup_list[1:])
        return lookup

    def get_host(self):
        host = self
        for attr in self.HOST_LOOKUP.split('__'):
            host = getattr(host, attr, None)
        if not isinstance(host, Host):
            msg = "Invalid host-lookup: {}".format(self.HOST_LOOKUP)
            raise InvalidMinkeSetup(msg)
        else:
            return host

    # sessions = GenericRelation(BaseSession, related_query_name='players')

    class Meta:
        abstract = True
