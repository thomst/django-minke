# -*- coding: utf-8 -*-

import re
from collections import OrderedDict

from django.db.utils import OperationalError
from django.db.utils import ProgrammingError
from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.text import camel_case_to_spaces

from .views import SessionView
from .models import Host
from .models import MinkeModel
from .models import MinkeSession
from .messages import ExecutionMessage
from .messages import PreMessage
from .exceptions import InvalidMinkeSetup


class SessionRegistry(type):
    """metaclass for Sessions that implements session-registration"""

    def __init__(cls, classname, bases, attr):
        super(SessionRegistry, cls).__init__(classname, bases, attr)
        if attr['__module__'] == 'minke.sessions': return

        # some sanity-checks
        if not cls.WORK_ON:
            msg = 'At least one minke-model must be specified for a session.'
            raise InvalidMinkeSetup(msg)

        for model in cls.WORK_ON:
            try:
                assert(model == Host or issubclass(model, MinkeModel))
            except (TypeError, AssertionError):
                msg = '{} is no minke-model.'.format(model)
                raise InvalidMinkeSetup(msg)

        # set verbose-name if missing
        if not cls.VERBOSE_NAME:
            cls.VERBOSE_NAME = camel_case_to_spaces(classname)

        # create session-permission...
        # Applying migrations tumbles over get_for_model if the
        # migrations for content-types aren't applied yet.
        try: content_type = ContentType.objects.get_for_model(MinkeSession)
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
        MinkeSession.REGISTRY[cls.__name__] = cls


class Session(metaclass=SessionRegistry):

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

    def __init__(self, connection, minkeobj, session_data=None):
        self.connection = connection
        self.minkeobj = minkeobj
        self.session_data = session_data or dict()
        self.status = 'success'
        self.messages = list()

    def process(self):
        """
        Real work is done here...
        """
        raise NotImplementedError('Your session must define a process-method!')

    def add_msg(self, msg):
        self.messages.append(msg)

    def set_status(self, status, alert=True):
        """
        Set session-status. Pass a valid session-status or a boolean.
        """
        statuus = {'success': 0, 'warning': 1, 'error': 2}
        if type(status) == bool:
            status = 'success' if status else 'error'
        elif status.lower() in statuus.keys():
            status = status.lower()
        else:
            msg = 'session-status must be one of {}'.format(statuus)
            raise InvalidMinkeSetup(msg)

        if not alert or statuus[self.status] < statuus[status]:
            self.status = status

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

    def run(self, cmd, *args, **kwargs):
        """
        run a command
        """
        return self.connection.run(cmd, *args, **kwargs)

    def execute(self, cmd, stderr_warning=True):
        """
        Run cmd, leave a message and set session-status.
        """
        result = self.run(cmd)
        if result.failed:
            self.add_msg(ExecutionMessage(result, 'error'))
            self.set_status('error')
        elif stderr_warning and result.stderr:
            self.add_msg(ExecutionMessage(result, 'warning'))
            self.set_status('warning')
        else:
            self.add_msg(ExecutionMessage(result, 'info'))
            self.set_status('success')

        return result.ok


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

        # do we have a regex? Then use the first captured group if there is one,
        # stdout otherwise...
        if valid and regex and result.stdout:
            groups = re.match(regex, result.stdout).groups()
            value = groups[0] if groups else result.stdout

        # no regex? just take stdout as it is...
        elif valid and result.stdout:
            value = result.stdout

        # valid but no stdout? Leave a warning...
        elif valid and not result.stdout:
            self.add_msg(ExecutionMessage(result, 'WARNING'))
            value = None

        # not valid - error-message...
        else:
            self.add_msg(ExecutionMessage(result, 'ERROR'))
            value = None

        setattr(self.minkeobj, field, value)
        return bool(value)

    def save_minkeobj(self, raise_exception=False):
        try:
            return self.minkeobj.save()
        except (ValidationError, IntegrityError):
            self.add_msg(ExceptionMessage())
            if raise_exception: raise
            else: return None


class SingleCommandSession(Session):
    COMMAND = None

    def process(self):
        if not self.COMMAND:
            msg = 'Missing COMMAND for SingleCommandSession!'
            raise InvalidMinkeSetup(msg)

        self.execute(self.format_cmd(self.COMMAND))


class CommandChainSession(Session):
    COMMANDS = tuple()
    BREAK_STATUUS = ('error',)

    def process(self):
        if not self.COMMANDS:
            msg = 'Missing COMMANDS for CommandChainSession!'
            raise InvalidMinkeSetup(msg)

        for cmd in self.COMMANDS:
            self.execute(self.format_cmd(cmd))
            if self.status in self.BREAK_STATUUS:
                break


class SessionChain(Session):
    SESSIONS = tuple()
    BREAK_STATUUS = ('error',)

    def process(self):
        for cls in self.SESSIONS:
            session = cls(self.connection, self.minkeobj, self.session_data)
            session.process()
            self.messages += session.messages
            self.set_status(session.status)
            if session.status in self.BREAK_STATUUS:
                break
