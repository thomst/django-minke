# -*- coding: utf-8 -*-

import re
import os
import signal
import datetime
from time import time
from fabric2.runners import Result

from django.db import models
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from .exceptions import InvalidMinkeSetup
from .utils import JSONField
from .utils import valid_yaml_configuration


class MinkeSessionQuerySet(models.QuerySet):
    """
    Working with current sessions.
    Which are those that are rendered within the changelist.
    """
    def get_currents(self, user, minkeobjs):
        """
        Get all current sessions for a given user and minke-objects.
        """
        ct_query = ContentType.objects.filter(model=minkeobjs.model.__name__.lower())[0]
        qs = self.filter(minkeobj_type=ct_query, minkeobj_id__in=minkeobjs)
        return qs.filter(user=user, current=True)

    def clear_currents(self, user, minkeobjs):
        """
        Clear all current sessions for a given user and minke-objects.
        """
        return self.get_currents(user, minkeobjs).update(current=False)


# TODO: Add indexes for sessions, messages and commandresults!
class MinkeSession(models.Model):
    """
    The MinkeSession holds the data of any executed session and tracks its process.
    """
    objects = MinkeSessionQuerySet.as_manager()

    SUCCESS = 'success'
    WARNING = 'warning'
    ERROR = 'error'
    INITIALIZED = 'initialized'
    RUNNING = 'running'
    COMPLETED = 'completed'
    STOPPING = 'stopping'
    STOPPED = 'stopped'
    CANCELED = 'canceled'
    FAILED = 'failed'

    SESSION_STATES = (
        (SUCCESS, 0),
        (WARNING, 1),
        (ERROR, 2))
    PROC_STATES = (
        (INITIALIZED, 'waiting...'),
        (RUNNING, 'running...'),
        (COMPLETED, 'completed in {0:.1f} seconds'),
        (STOPPING, 'stopping...'),
        (STOPPED, 'stopped after {0:.1f} seconds'),
        (CANCELED, 'canceled!'),
        (FAILED, 'failed!'))

    SESSION_CHOICES = ((s[0], _(s[0])) for s in SESSION_STATES)
    PROC_CHOICES = ((s[0], _(s[0])) for s in PROC_STATES)

    class Meta:
        ordering = ('minkeobj_type_id', 'minkeobj_id', '-created_time')
        verbose_name = _('Session')
        verbose_name_plural = _('Sessions')

    # those fields will be derived from the session-class
    session_name = models.CharField(
        max_length=128,
        verbose_name=_('Session-name'),
        help_text=_('Class-name of the session-class.'))
    session_verbose_name = models.CharField(
        max_length=128,
        verbose_name=_("Session's verbose-name"),
        help_text=_('Verbose-name-attribute of the session-class.'))
    session_description = models.TextField(
        blank=True, null=True, max_length=128,
        verbose_name=_("Session's description"),
        help_text=_('Doc-string of the session-class.'))
    session_status = models.CharField(
        max_length=128, choices=SESSION_CHOICES,
        verbose_name=_("Session-status"),
        help_text=_('Mostly set by the session-code itself.'))

    # the minkeobj to work on
    minkeobj_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    minkeobj_id = models.PositiveIntegerField()
    minkeobj = GenericForeignKey('minkeobj_type', 'minkeobj_id')

    # execution-data of the session
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        verbose_name=_("User"),
        help_text=_('User that run this session.'))
    proc_status = models.CharField(
        max_length=128, choices=PROC_CHOICES,
        verbose_name=_("Process-status"),
        help_text=_('Status of session-processing.'))
    pid = models.IntegerField(
        blank=True, null=True,
        verbose_name=_("PID"),
        help_text=_('Process-ID of the celery-task that run the session.'))
    start_time = models.DateTimeField(
        blank=True, null=True,
        verbose_name=_("Start-time"),
        help_text=_('Time the session has been started.'))
    end_time = models.DateTimeField(
        blank=True, null=True,
        verbose_name=_("End-time"),
        help_text=_('Time the session finished.'))
    run_time = models.DurationField(
        blank=True, null=True,
        verbose_name=_("Run-time"),
        help_text=_("Session's runtime."))
    created_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created-time"),
        help_text=_('Time the session has been initiated.'))
    current = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.session_name} on {self.minkeobj}'

    def init(self, user, minkeobj, session_cls):
        """
        Initialize a session. Setup the session-attributes and save it.
        """
        self.proc_status = 'initialized'
        self.user = user
        self.minkeobj = minkeobj
        self.session_name = session_cls.__name__
        self.session_verbose_name = session_cls.verbose_name
        self.session_description = session_cls.__doc__
        self.save()

    @transaction.atomic
    def start(self):
        """
        Start a session. Update proc_status, start_time and pid.
        Since the cancel-method is called asynchrouniously to the whole session-
        processing, the start-, end- and cancel-method are each wrapped within a
        atomic transaction using select_for_update to protect them from interfering.
        """
        # We use the reloaded session for checks but update and save self.
        # On the database-level it doesn't make a difference from which object
        # we call the save-method.
        session = MinkeSession.objects.select_for_update().get(pk=self.id)
        if session.is_waiting:
            self.pid = os.getpid()
            self.proc_status = 'running'
            self.start_time = datetime.datetime.now()
            self.save(update_fields=['proc_status', 'start_time', 'pid'])
            return True

    @transaction.atomic
    def cancel(self):
        """
        Cancel a session. Update proc_- and session_status.
        Since the cancel-method is called asynchrouniously to the whole session-
        processing, the start-, end- and cancel-method are each wrapped within a
        atomic transaction using select_for_update to protect them from interfering.
        This method is called by the api-view.
        """
        session = MinkeSession.objects.select_for_update().get(pk=self.id)
        if session.is_waiting:
            self.session_status = 'error'
            self.proc_status = 'canceled'
            self.save(update_fields=['proc_status', 'session_status'])
        elif session.is_running:
            self.proc_status = 'stopping'
            self.save(update_fields=['proc_status'])
            os.kill(session.pid, signal.SIGUSR1)
        elif session.is_stopping:
            os.kill(session.pid, signal.SIGUSR1)

    @transaction.atomic
    def end(self, failure=False):
        """
        End a session. Update proc_- and session_status, end_- and run_time.
        Since the cancel-method is called asynchrouniously to the whole session-
        processing, the start-, end- and cancel-method are each wrapped within a
        atomic transaction using select_for_update to protect them from interfering.
        """
        session = MinkeSession.objects.select_for_update().get(pk=self.id)
        if failure:
            self.session_status = 'error'
            self.proc_status = 'failed'
        elif session.is_running:
            self.session_status = self.session_status or 'success'
            self.proc_status = 'completed'
        elif session.is_stopping:
            self.session_status = 'error'
            self.proc_status = 'stopped'
        self.end_time = datetime.datetime.now()
        self.run_time = self.end_time - self.start_time
        fields = ['proc_status', 'session_status', 'end_time', 'run_time']
        self.save(update_fields=fields)

    @property
    def is_waiting(self):
        return self.proc_status == 'initialized'

    @property
    def is_running(self):
        return self.proc_status == 'running'

    @property
    def is_stopping(self):
        return self.proc_status == 'stopping'

    @property
    def is_done(self):
        return self.proc_status in ['completed', 'canceled', 'stopped', 'failed']

    @property
    def proc_info(self):
        """
        Infos about the session-processing
        that will be rendered within the session-template.
        """
        info = dict(self.PROC_STATES)[self.proc_status]
        if self.run_time:
            return gettext(info).format(self.run_time.total_seconds())
        else:
            return gettext(info)

    def prnt(self):
        """
        Print a session and its messages.
        """
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


class CommandResult(Result, models.Model):
    """
    Add a db-layer to invoke's :class:`~invoke.runners.Result`-class.

    The CommandResult is a place-in for :class:`~invoke.runners.Result` which
    reimplements the attributes as model-fields and adds a ForeignKey to
    :class:`.MinkeSession`. It also implements some helper-methods and
    properties as :meth:`.validate`, :attr:`.status` and :attr:`.match`.
    """
    command = models.TextField(
        verbose_name=_('Command'),
        help_text=_('The command which was executed.'))
    exited = models.SmallIntegerField(
        verbose_name=_('Exit-status'),
        help_text=_('Exit-status returned by the command.'))
    stdout = models.TextField(
        blank=True, null=True,
        verbose_name=_('Stdout'),
        help_text=_('Standard-output of the command.'))
    stderr = models.TextField(
        blank=True, null=True,
        verbose_name=_('Stderr'),
        help_text=_('Standard-error of the command. '
                    '(unless the process was invoked via a pty, '
                    'in which case stderr and stdout are merged into stdout)'))
    shell = models.CharField(
        max_length=128,
        verbose_name=_('Shell'),
        help_text=_('The shell binary used for execution.'))
    encoding = models.CharField(
        max_length=128,
        verbose_name=_('Encoding'),
        help_text=_('The string encoding used by the local shell environment.'))
    pty = models.BooleanField(
        verbose_name=_('Pty'),
        help_text=_('A boolean describing whether the command was invoked with a pty or not'))
    created_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Time of creation'),
        help_text=_('The datetime this command-result were added.'))
    session = models.ForeignKey(MinkeSession,
        on_delete=models.CASCADE,
        related_name='commands',
        verbose_name=_('Session'),
        help_text=_('Session whereas this command where executed.'))

    class Meta:
        ordering = ('session_id', 'created_time')
        verbose_name = _('Command-Result')
        verbose_name_plural = _('Command-Results')

    def __init__(self, *args, **kwargs):
        """
        This model could also be initialized as fabric's result-class.
        """
        try:
            # First we try to initiate the model.
            models.Model.__init__(self, *args, **kwargs)
        except TypeError:
            # If this fails, its a result-class-initiation.
            models.Model.__init__(self)
            Result.__init__(self, *args, **kwargs)
        self._match = None

    @property
    def status(self):
        """
        One of ``MinkeSession.SESSION_STATES``.

        * 'success' if ``result.ok`` is True and ``result.stderr`` is empty
        * 'warning' if ``result.ok`` is True but ``result.stderr`` is not empty
        * 'error' if ``result.failed`` is True
        """
        if self.failed:
            return MinkeSession.SESSION_STATES[2][0]
        elif self.stderr:
            return MinkeSession.SESSION_STATES[1][0]
        else:
            return MinkeSession.SESSION_STATES[0][0]

    @property
    def match(self):
        """
        Holds the match-object returned by :label:`re.match` within
        ``result.validate``.
        """
        return self._match

    def validate(self, regex):
        """
        Validate a result-object.

        A result is considered valid if ``result.ok`` is True and the
        regex-pattern matches ``result.stdout``.

        Parameter
        ---------
        regex (string):
            Regex-Pattern to match ``result.stdout``.

        Returns
        -------
        True for valid, False for invalid.
        """
        self._match = re.match(regex, self.stdout)
        return self.ok and self._match

    def as_message(self):
        """
        Return this instance as an ``messages.ExecutionMessage``.
        """
        # FIXME: messages imports from models and vice versa.
        # We should find another solution here. Maybe define message-proxies
        # right here in the models-module?
        from .messages import ExecutionMessage
        return ExecutionMessage(self)


class BaseMessage(models.Model):
    """
    Base-model for all :doc:`message-classes <.messages>`.

    All :doc:`message-classes <.messages>` are implemented as
    proxy-model-classes of BaseMessage.
    """
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    LEVELS = (
        (INFO, 'info'),
        (WARNING, 'warning'),
        (ERROR, 'error'))

    session = models.ForeignKey(MinkeSession,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Session'),
        help_text=_('Session the message belongs to.'))
    level = models.CharField(
        max_length=128,
        choices=LEVELS,
        verbose_name=_('Message-level'),
        help_text=_('Level with which the message were added.'))
    text = models.TextField(
        verbose_name=_('Text'),
        help_text=_('Message-Text'))
    html = models.TextField(
        verbose_name=_('HTML'),
        help_text=_('Message as HTML'))
    created_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Time of creation'),
        help_text=_('The datetime this message were added.'))

    class Meta:
        ordering = ('session_id', 'created_time')
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')


class HostGroup(models.Model):
    """
    A Group of hosts. (Not sure if this is practical.)
    """
    name = models.CharField(
        max_length=128, unique=True,
        verbose_name=_('Group-Name'),
        help_text=_('Unique group-name.'))
    comment = models.TextField(
        blank=True, null=True,
        verbose_name=_('Comment'),
        help_text=_('Something about the group.'))
    config = models.TextField(
        blank=True,
        validators=[valid_yaml_configuration],
        verbose_name=_('Fabric and invoke configuration'),
        help_text=_('A yaml formatted fabric/invoke configuration.')
        )

    class Meta:
        ordering = ['name']
        verbose_name = _('Host-Group')
        verbose_name_plural = _('Host-Groups')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class HostQuerySet(models.QuerySet):
    """
    Besides the get_lock-method this is an imitation of the minkemodel-queryset-api.
    """
    def get_lock(self):
        """
        Set a lock on all selected hosts.
        """
        # The most atomic way to get a lock is a update-query.
        # We use a timestamp to be able to identify the updated objects.
        timestamp = repr(time())
        self.filter(lock=None).update(lock=timestamp)
        return timestamp

    def get_hosts(self):
        """
        Return itself (minkemodel-api).
        """
        return self

    def host_filter(self, hosts):
        """
        Return an intersection of itself and the given hosts (minkemodel-api).
        """
        return self & hosts

    def select_related_hosts(self):
        """
        Return itself (minkemodel-api).
        """
        return self


class Host(models.Model):
    """
    This model is mainly a ssh-config.
    Each host represents an unique ssh-connection.
    It also imitates the minkemodel-api to normalize the way the engine
    runs sessions on them.
    """
    name = models.SlugField(
        max_length=128, unique=True,
        verbose_name=_('Name'),
        help_text=_('Unique name of the host. If Hostname is not specified fabric\'s '
                    'Connection-class will be initialized with this Name instead. '
                    'Specifying a Name only could be a sufficient Host-setup '
                    'if there is a valid ssh_config for it as lookup-pattern.'))
    verbose_name = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name=_('Verbose Name'),
        help_text=_('Verbose Host-Name.'))
    hostname = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name=_('HostName'),
        help_text=_('HostName could be either a ssh-config-lookup-pattern or a '
                    'real hostname to log into.'))
    username = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name=_('User'),
        help_text=_('User to login as.'))
    port = models.IntegerField(
        blank=True, null=True,
        verbose_name=_('Port number.'),
        help_text=_('Port number to connect on the remote host.'))
    comment = models.TextField(
        blank=True, null=True,
        verbose_name=_('Comment'),
        help_text=_('Something about the host.'))
    groups = models.ManyToManyField(
        HostGroup,
        blank=True,
        related_name="hosts",
        verbose_name=_('Hostgroup'),
        help_text=_('Hostgroups this host belongs to.')
        )
    config = models.TextField(
        blank=True,
        validators=[valid_yaml_configuration],
        verbose_name=_('Fabric and invoke configuration'),
        help_text=_('A yaml formatted fabric/invoke configuration.')
        )
    disabled = models.BooleanField(
        default=False,
        verbose_name=_('Disabled'),
        help_text=_('Disabled hosts won\'t be accessed by minke.'))
    lock = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name=_('Lock'),
        help_text=_('Locked hosts won\'t be accessed by minke.'
                    'To prevent intersection a host will be locked '
                    'while sessions are executed on it.'))

    objects = HostQuerySet.as_manager()
    sessions = GenericRelation(MinkeSession,
        content_type_field='minkeobj_type',
        object_id_field='minkeobj_id')

    def get_host(self):
        """
        Return itself (minkemodel-api).
        """
        return self

    def release_lock(self):
        """
        Release the host's lock.
        """
        self.lock = None
        self.save(update_fields=['lock'])

    class Meta:
        ordering = ['name']
        verbose_name = _('Host')
        verbose_name_plural = _('Hosts')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class MinkeQuerySet(models.QuerySet):
    """
    A queryset-api to work with related hosts.
    This api is mainly used by the engine-module.
    """
    def get_hosts(self):
        """
        Get all hosts related to the objects of this queryset.
        """
        lookup = self.model.get_reverse_host_lookup() + '__in'
        try:
            return Host.objects.filter(**{lookup:self})
        except FieldError:
            msg = "Invalid reverse-host-lookup: {}".format(lookup)
            raise InvalidMinkeSetup(msg)

    def host_filter(self, hosts):
        """
        Get all objects related to the given hosts.
        """
        lookup = self.model.HOST_LOOKUP + '__in'
        try:
            return self.filter(**{lookup:hosts})
        except FieldError:
            msg = "Invalid host-lookup: {}".format(lookup)
            raise InvalidMinkeSetup(msg)

    def select_related_hosts(self):
        """
        Return a queryset which selects related hosts.
        """
        try:
            return self.select_related(self.model.HOST_LOOKUP)
        except FieldError:
            msg = "Invalid host-lookup: {}".format(self.model.HOST_LOOKUP)
            raise InvalidMinkeSetup(msg)


class MinkeModel(models.Model):
    """
    An abstract baseclass for all models on which sessions should be run.
    """
    objects = MinkeQuerySet.as_manager()
    sessions = GenericRelation(MinkeSession,
        content_type_field='minkeobj_type',
        object_id_field='minkeobj_id')

    HOST_LOOKUP = 'host'
    REVERSE_HOST_LOOKUP = None

    class Meta:
        abstract = True

    @classmethod
    def get_reverse_host_lookup(cls):
        """
        Derive a reverse lookup-term from HOST_LOOKUP.
        """
        if cls.REVERSE_HOST_LOOKUP:
            lookup = self.REVERSE_HOST_LOOKUP
        else:
            lookup_list = cls.HOST_LOOKUP.split('__')
            lookup_list.reverse()
            lookup_list.append(cls.__name__.lower())
            lookup = '__'.join(lookup_list[1:])
        return lookup

    def get_host(self):
        """
        Return the related host-instance.
        """
        # return self.__class__.objects.filter(pk__in=self.pk).get_hosts()[0]
        host = self
        for attr in self.HOST_LOOKUP.split('__'):
            host = getattr(host, attr, None)
        if not isinstance(host, Host):
            msg = "Invalid host-lookup: {}".format(self.HOST_LOOKUP)
            raise InvalidMinkeSetup(msg)
        else:
            return host
