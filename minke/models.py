# -*- coding: utf-8 -*-

import re
import datetime
from time import time
from collections import OrderedDict

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string

from .exceptions import InvalidMinkeSetup
from .utils import JSONField


class SessionDataQuerySet(models.QuerySet):
    def get_currents(self, user, minkeobjs):
        minkeobj_type = ContentType.objects.get_for_model(minkeobjs.model)
        minkeobj_ids = list(minkeobjs.all().values_list('id', flat=True))
        return self.filter(
            user=user,
            minkeobj_type=minkeobj_type,
            minkeobj_id__in=minkeobj_ids,
            current=True)

    def get_currents_by_model(self, user, model):
        minkeobj_type = ContentType.objects.get_for_model(model)
        return self.filter(
            user=user,
            minkeobj_type=minkeobj_type,
            current=True)

    def clear_currents(self, user, minkeobjs):
        return self.get_currents(user, minkeobjs).update(current=False)


class MinkeSession(models.Model):
    objects = SessionDataQuerySet.as_manager()

    RESULT_STATES = (
        ('success', 'success'),
        ('warning', 'warning'),
        ('error', 'error'),
    )
    PROC_STATES = (
        ('initialized', 'initialized'),
        ('running', 'running'),
        ('done', 'done'),
        ('aborted', 'aborted'),
    )

    # those fields will be derived from the session-class
    session_name = models.CharField(max_length=128)
    session_verbose_name = models.CharField(max_length=128)
    session_description = models.TextField(blank=True, null=True)
    session_status = models.CharField(max_length=128, choices=RESULT_STATES)
    session_data = JSONField(blank=True, null=True)

    # the minkeobj to work on
    minkeobj_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    minkeobj_id = models.PositiveIntegerField()
    minkeobj = GenericForeignKey('minkeobj_type', 'minkeobj_id')

    # execution-data of the session
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    current = models.BooleanField(default=True)
    proc_status = models.CharField(max_length=128, choices=PROC_STATES)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    run_time = models.DurationField(blank=True, null=True)

    def init(self, user, minkeobj, session_cls, session_data):
        self.proc_status = 'initialized'
        self.user = user
        self.minkeobj = minkeobj
        self.session_name = session_cls.__name__
        self.session_verbose_name = session_cls.verbose_name
        self.session_description = session_cls.__doc__
        self.session_data = session_data
        self.save()

    def start(self):
        self.proc_status = 'running'
        self.start_time = datetime.datetime.now()
        self.save(update_fields=['proc_status', 'start_time'])

    def end(self):
        self.proc_status = 'done'
        self.end_time = datetime.datetime.now()
        self.run_time = self.end_time - self.start_time
        update_fields = ['proc_status', 'session_status', 'end_time', 'run_time']
        self.save(update_fields=update_fields)

    def abort(self):
        self.proc_status = 'aborted'
        self.session_status = 'error'
        self.save(update_fields=['proc_status', 'session_status'])

    @property
    def proc_info(self):
        if self.proc_status == 'initialized':
            return '[waiting...]'
        elif self.proc_status == 'running':
            return '[running...]'
        elif self.proc_status == 'aborted':
            return '[aborted!]'
        elif self.proc_status == 'done':
            return '[completed in {0:.1f} seconds]'.format(self.run_time.total_seconds())

    def prnt(self):
        width = 60
        pre_width = 7
        sep = ': '
        bg = dict(
            success = '\033[1;37;42m{}\033[0m'.format,
            warning = '\033[1;37;43m{}\033[0m'.format,
            error   = '\033[1;37;41m{}\033[0m'.format)
        fg = dict(
            info    = '\033[32m{}\033[39m'.format,
            warning = '\033[33m{}\033[39m'.format,
            error   = '\033[31m{}\033[39m'.format)
        ul = '\033[4m{}\033[0m'.format

        # print header
        minkeobj = str(self.minkeobj).ljust(width)
        status = self.session_status.upper().ljust(pre_width)
        print(bg[self.session_status](status + sep + minkeobj))

        # print messages
        msgs = list(self.messages.all())
        msg_count = len(msgs)
        for i, msg in enumerate(msgs, start=1):
            underlined = i < msg_count
            level = msg.level.ljust(pre_width)
            lines = msg.text.splitlines()
            for line in lines[:-1 if underlined else None]:
                print(fg[msg.level](level) + sep + line)
            if underlined:
                line = lines[-1].ljust(width)
                print(ul(fg[msg.level](level) + sep + line[:width]) + line[width:])


class BaseMessage(models.Model):
    LEVELS = (
        ('info', 'info'),
        ('warning', 'warning'),
        ('error', 'error'))

    session = models.ForeignKey(MinkeSession, on_delete=models.CASCADE, related_name='messages')
    level = models.CharField(max_length=128, choices=LEVELS)

    text = models.TextField()
    html = models.TextField()


class HostGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    comment = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class HostQuerySet(models.QuerySet):
    def get_lock(self):
        # The most atomic way to get a lock is a update-query.
        # We use a timestamp to be able to identify the updated objects.
        timestamp = repr(time())
        self.filter(lock=None).update(lock=timestamp)
        return timestamp

    def get_hosts(self):
        return self

    def host_filter(self, hosts):
        return self & hosts


class Host(models.Model):
    name = models.SlugField(max_length=128, unique=True)
    verbose_name = models.CharField(max_length=255, blank=True, null=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    group = models.ForeignKey(HostGroup, blank=True, null=True, on_delete=models.SET_NULL)
    disabled = models.BooleanField(default=False)
    lock = models.CharField(max_length=20, blank=True, null=True)

    objects = HostQuerySet.as_manager()

    def get_host(self):
        return self

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


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

    class Meta:
        abstract = True

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
