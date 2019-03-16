# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
import datetime
import inspect

from fabric.api import run

from django.db.utils import OperationalError
from django.db.utils import ProgrammingError
from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify

from .views import SessionView
from .models import Host
from .models import MinkeModel
from .models import BaseSession
from .messages import ExecutionMessage
from .messages import PreMessage
from .exceptions import InvalidMinkeSetup


registry = list()
def register(session_cls=None, create_permission=False):
    """
    Register session-classes.
    This works also as a decorator for session-classes.
    """

    # If we got no session_cls we assume register were used as a decorator...
    if not session_cls:
        def wrapper(session_cls):
            register(session_cls, create_permission)
            return session_cls
        return wrapper

    try:
        assert(issubclass(session_cls, Session))
    except (TypeError, AssertionError):
        msg = 'Invalid session-class: {}'.format(session_cls)
        raise InvalidMinkeSetup(msg)

    if not session_cls.WORK_ON:
        msg = 'At least one minke-model must be specified for a session.'
        raise InvalidMinkeSetup(msg)

    for model in session_cls.WORK_ON:
        try:
            assert(model == Host or issubclass(model, MinkeModel))
        except (TypeError, AssertionError):
            msg = '{} is no minke-model.'.format(model)
            raise InvalidMinkeSetup(msg)

    if create_permission:
        # Applying minke-migrations tumbles over get_for_model if the
        # migrations for this model aren't applied yet.
        try: content_type = ContentType.objects.get_for_model(session_cls)
        except (OperationalError, ProgrammingError): return

        # We create one permission to run the session with all registered models.
        # codename looks like: run_thistask_on_thismodel_and_thatmodel
        models = '_and_'.join([slugify(m.__name__) for m in session_cls.WORK_ON])
        session_name = session_cls.__name__
        session_codename = slugify(session_name)
        codename = 'run_{}_on_{}'.format(session_codename, models)
        permission_name = '{}.{}'.format(model._meta.app_label, codename)
        permission = Permission.objects.get_or_create(
            name=codename.replace('_', ' '),
            codename=codename,
            content_type=content_type)

        # add permission to permission_required...
        session_cls.PERMISSIONS += (permission_name,)

    # register session-class
    registry.append(session_cls)

    # in case register were used as a decorator (without arguments)...
    return session_cls


# We declare the Meta-class whithin a mixin.
# Otherwise the proxy-attribute won't be inherited by child-classes of Session.
class ProxyMixin(object):
    class Meta:
        proxy = True


class Session(ProxyMixin, BaseSession):
    VERBOSE_NAME = None
    WORK_ON = tuple()
    PERMISSIONS = tuple()
    FORM = None
    CONFIRM = False
    WAIT = False

    @classmethod
    def as_action(cls):
        def action(modeladmin, request, queryset):
            session_view = SessionView.as_view()
            return session_view(request, session_cls=cls, queryset=queryset)
        action.__name__ = cls.__name__
        action.short_description = cls.VERBOSE_NAME
        return action

    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
        self.con = None
        self.session_name = self.__class__.__name__
        self.session_verbose_name = self.VERBOSE_NAME or self.session_name

    def init(self, user, player, session_data):
        self.proc_status = 'initialized'
        self.user = user
        self.player = player
        self.session_data = session_data
        self.save()

    def start(self, con):
        self.proc_status = 'running'
        self.con = con
        self.start_time = datetime.datetime.now()
        self.save(update_fields=['proc_status', 'start_time'])

    def end(self):
        if self.proc_status == 'initialized':
            self.proc_status = 'aborted'
            self.status = 'error'
            self.save(update_fields=['proc_status', 'status'])
        else:
            self.proc_status = 'done'
            self.status = self.status or 'success'
            self.end_time = datetime.datetime.now()
            self.run_time = self.end_time - self.start_time
            self.save(update_fields=['proc_status', 'status', 'end_time', 'run_time'])

    def process(self):
        """
        Real work is done here...
        """
        raise NotImplementedError('Your session must define a process-method!')

    def add_msg(self, msg):
        self.messages.add(msg, bulk=False)

    def set_status(self, status):
        """
        Set session-status. Pass a valid session-status or a boolean.
        """
        statuus = [s[0] for s in self.RESULT_STATES]
        if type(status) == bool:
            self.status = 'success' if status else 'error'
        elif status.lower() in statuus:
            self.status = status.lower()
        else:
            msg = 'session-status must be one of {}'.format(statuus)
            raise InvalidMinkeSetup(msg)

    # helper-methods
    def format_cmd(self, cmd):
        """
        Will format a given command-string using the player's attributes
        and the session_data while the session_data has precedence.
        """
        params = vars(self.player)
        params.update(self.session_data)
        return cmd.format(**params)

    def valid(self, result, regex=None):
        """
        Validate result.

        Return True if rtn-code is 0.
        If regex is given it must also match stdout.
        """
        if regex and result.ok:
            return bool(re.match(regex, result.stdout))
        else:
            return result.ok

    def run(self, cmd):
        return self.con.run(cmd, warn=True)

    def execute(self, cmd, **kwargs):
        """
        Just run cmd and leave a message.
        """
        result = self.run(cmd, **kwargs)

        if result.failed:
            self.add_msg(ExecutionMessage(result, 'ERROR'))
        elif result.stderr:
            self.add_msg(ExecutionMessage(result, 'WARNING'))
        elif result.stdout:
            self.add_msg(PreMessage(result.stdout, 'INFO'))

        return result.ok


class SingleActionSession(Session):
    COMMAND = None

    def get_cmd(self):
        if not self.COMMAND:
            msg = 'Missing COMMAND for SingleActionSession!'
            raise InvalidMinkeSetup(msg)
        else:
            return self.format_cmd(self.COMMAND)

    def process(self):
        valid = self.execute(self.get_cmd())
        self.set_status(valid)


class UpdateEntriesSession(Session):

    def update_field(self, field, cmd, regex=None):
        """
        Update a field using either the stdout or the first matching-group
        from regex.
        """
        # is field a player-attribute?
        try: getattr(self.player, field)
        except AttributeError as e: raise e

        # run cmd
        result = self.run(cmd)
        valid = self.valid(result, regex)

        # A valid call and stdout? Then try to use the first captured
        # regex-group or just use stdout as value.
        if valid and result.stdout:
            try:
                assert regex
                value = re.match(regex, result.stdout).groups()[0]
            except (AssertionError, IndexError):
                value = result.stdout

        # call were valid but no stdout? Leave a warning.
        elif valid and not result.stdout:
            self.add_msg(ExecutionMessage(result, 'WARNING'))
            value = None

        # call failed.
        else:
            self.add_msg(ExecutionMessage(result, 'ERROR'))
            value = None

        setattr(self.player, field, value)
        return bool(value)

    def rework(self):
        # TODO: catch exceptions that may be raised because of invalid values.
        self.player.save()
