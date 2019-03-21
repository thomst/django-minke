# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
from collections import OrderedDict

from fabric.api import run

from django.db.utils import OperationalError
from django.db.utils import ProgrammingError
from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.text import camel_case_to_spaces

from .views import SessionView
from .models import Host
from .models import MinkeModel
from .models import SessionData
from .messages import ExecutionMessage
from .messages import PreMessage
from .exceptions import InvalidMinkeSetup


class SessionRegistry(type):
    """metaclass for Sessions that implements session-registration"""

    def __init__(cls, classname, bases, attr):
        super(SessionRegistry, cls).__init__(classname, bases, attr)
        if attr['__module__'] == 'minke.sessions': return

        if not cls.WORK_ON:
            msg = 'At least one minke-model must be specified for a session.'
            raise InvalidMinkeSetup(msg)

        for model in cls.WORK_ON:
            try:
                assert(model == Host or issubclass(model, MinkeModel))
            except (TypeError, AssertionError):
                msg = '{} is no minke-model.'.format(model)
                raise InvalidMinkeSetup(msg)

        # create session-permission...
        # Applying migrations tumbles over get_for_model if the
        # migrations for content-types aren't applied yet.
        try: content_type = ContentType.objects.get_for_model(SessionData)
        except (OperationalError, ProgrammingError): return
        codename = 'run_{}'.format(classname.lower())
        permname = 'Can run {}'.format(camel_case_to_spaces(classname))
        permission = Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults=dict(name=permname))
        permission_name = 'minke.{}'.format(codename)
        cls.PERMISSIONS += (permission_name,)

        # register session
        SessionData.REGISTRY[cls.__name__] = cls


class Session(object):
    __metaclass__ = SessionRegistry

    VERBOSE_NAME = None
    WORK_ON = tuple()
    PERMISSIONS = tuple()
    FORM = None
    CONFIRM = False
    WAIT = False
    INVOKE_CONFIG = dict()

    @classmethod
    def as_action(cls):
        def action(modeladmin, request, queryset):
            session_view = SessionView.as_view()
            return session_view(request, session_cls=cls, queryset=queryset)
        action.__name__ = cls.__name__
        action.short_description = cls.VERBOSE_NAME
        return action

    def __init__(self, connection, minkeobj, session_data):
        self.connection = connection
        self.minkeobj = minkeobj
        self.session_data = session_data
        self.status = None
        self.messages = list()

    def process(self):
        """
        Real work is done here...
        """
        raise NotImplementedError('Your session must define a process-method!')

    def add_msg(self, msg):
        self.messages.append(msg)

    def set_status(self, status):
        """
        Set session-status. Pass a valid session-status or a boolean.
        """
        statuus = [s[0] for s in SessionData.RESULT_STATES]
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
        Will format a given command-string using the minkeobj's attributes
        and the session_data while the session_data has precedence.
        """
        params = vars(self.minkeobj)
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
        return self.connection.run(cmd, warn=True)

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
        # is field a minkeobj-attribute?
        try: getattr(self.minkeobj, field)
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

        setattr(self.minkeobj, field, value)
        return bool(value)

    def rework(self):
        # TODO: catch exceptions that may be raised because of invalid values.
        self.minkeobj.save()
