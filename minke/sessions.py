# -*- coding: utf-8 -*-

import re, logging
from collections import OrderedDict
from fabric2.runners import Result

from django.db.utils import OperationalError
from django.db.utils import ProgrammingError
from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.text import camel_case_to_spaces
from django.dispatch import Signal

from .models import Host
from .models import MinkeModel
from .models import MinkeSession
from .models import BaseMessage
from .models import CommandResult
from .forms import CommandForm
from .messages import PreMessage
from .messages import TableMessage
from .messages import ExecutionMessage
from .exceptions import InvalidMinkeSetup


logger = logging.getLogger(__name__)


class SessionReloadError(Exception):
    # TODO: Work out the error-message - containing the original_exception.
    def __init__(self, original_exception, session=None):
        self.original_exception = original_exception
        self.session = session


class REGISTRY(OrderedDict):
    """
    A reload-able session-registry.
    """
    reload_sessions = Signal(providing_args=['session_name'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._static_sessions = None

    def reload(self, session_name=None):
        """
        Reload the registry by running the factories.
        """
        # We backup the static-sessions and reset the registry before each
        # reload. This way the reload algorithms doesn't have to unregister
        # obsolete sessions.
        if self._static_sessions:
            self.clear()
            self.update(self._static_sessions)
        else:
            self._static_sessions = self.copy()

        # no reloading needed for static sessions
        if session_name in self._static_sessions:
            return

        # trigger the reload signal
        try:
            self.reload_sessions.send(sender=self.__class__, session_name=session_name)
        except Exception as exc:
            # TODO: Workout print-version of SessionReloadError that will be
            # logged.
            exception = SessionReloadError(exc, session_name)
            logger.error(exception)
            raise exception


REGISTRY = REGISTRY()


class SessionRegistration(type):
    """
    metaclass for Sessions that implements session-registration
    """
    def __new__(cls, name, bases, dct):
        # Setting the abstract-attr explicitly avoids its inheritance.
        dct['abstract'] = dct.get('abstract', False)
        return super().__new__(cls, name, bases, dct)

    def __init__(cls, classname, bases, attrs):
        super().__init__(classname, bases, attrs)
        if not cls.abstract and not cls.__name__ in REGISTRY:
            cls.register()
            cls.create_permission()

    def register(cls):
        """
        Register the session-class.
        """
        # some sanity-checks
        if not cls.work_on:
            msg = 'At least one minke-model must be specified for a session.'
            raise InvalidMinkeSetup(msg)

        for model in cls.work_on:
            try:
                assert(model == Host or issubclass(model, MinkeModel))
            except (TypeError, AssertionError):
                msg = '{} is no minke-model.'.format(model)
                raise InvalidMinkeSetup(msg)

        if issubclass(cls, SingleCommandSession) and not cls.command:
            msg = 'SingleCommandSession needs to specify an command.'
            raise InvalidMinkeSetup(msg)

        if issubclass(cls, CommandChainSession) and not cls.commands:
            msg = 'CommandChainSession needs to specify commands.'
            raise InvalidMinkeSetup(msg)

        if issubclass(cls, SessionChain) and not cls.sessions:
            msg = 'SessionChain needs to specify sessions.'
            raise InvalidMinkeSetup(msg)

        # set verbose-name if missing
        if not cls.verbose_name:
            cls.verbose_name = camel_case_to_spaces(cls.__name__)

        # register session
        REGISTRY[cls.__name__] = cls

    def _get_permission(cls):
        codename = 'run_{}'.format(cls.__name__.lower())
        name = 'Can run {}'.format(camel_case_to_spaces(cls.__name__))
        lookup = 'minke.{}'.format(codename)
        return codename, name, lookup

    def create_permission(cls):
        """
        Create a run-permission for this session-class.
        """
        # create session-permission...
        # In some contexts get_for_model fails because content_types aren't
        # setup. This happens when applying migrations but also when testing
        # with sqlite3.
        try: content_type = ContentType.objects.get_for_model(MinkeSession)
        except (OperationalError, ProgrammingError): return
        codename, name, lookup = cls._get_permission()
        permission = Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults=dict(name=name))
        cls.permissions += (lookup,)

    def delete_permission(cls):
        codename, name, lookup = cls._get_permission()
        try:
            Permission.objects.get(codename=codename).delete()
        except Permission.DoesNotExist:
            pass
        else:
            cls.permissions = tuple(set(cls.permissions) - set((lookup,)))



def protect(method):
    """
    Decorator for session-methods to protect them from being interrupted by a
    soft-interruption.
    """
    def wrapper(obj, *args, **kwargs):
        # are we already protected?
        if obj._busy: return method(obj, *arg, **kwargs)
        # otherwise protect the method-call by setting the busy-flag
        obj._busy = True
        result = method(obj, *args, **kwargs)
        # if interruption was deferred now is the time to raise it
        if obj._interrupt: raise obj._interrupt
        obj._busy = False
        return result

    return wrapper


class Session(metaclass=SessionRegistration):
    abstract = True
    verbose_name = None
    work_on = tuple()
    permissions = tuple()
    form = None
    confirm = False
    invoke_config = dict()
    parrallel_per_host = False

    @classmethod
    def get_form(cls):
        return cls.form

    def __init__(self, con, db):
        self._con = con
        self._db = db
        self._interrupt = None
        self._busy = False
        self.start = db.start
        self.end = db.end

    def cancel(self):
        """
        This method could be called twice. The first time it will initiate a
        soft interruption which means a current remote-process won't be
        interrupted. The session will be stopped subsequently.
        If it is called meanwhile a second time, the session will be killed
        immediately.

        NOTE
        ----
        It seems that there is no chance to interrupt a shell-process
        started by fabric if no pty is in use.
        fabric.runners.Remote.send_interrupt says::

            ... in v1, we just reraised the KeyboardInterrupt unless a PTY was
            present; this seems to have been because without a PTY, the
            below escape sequence is ignored, so all we can do is immediately
            terminate on our end...

        Thus killing a session makes most sense if it has the run.pty-config
        in use. Otherwise you just will be disconnected from the remote-process.
        """
        if not self._busy or self._interrupt:
            raise self._interrupt
        else:
            self._interrupt = KeyboardInterrupt

    @property
    def status(self):
        return self._db.session_status

    @property
    def minkeobj(self):
        return self._db.minkeobj

    @property
    def data(self):
        return self._db.session_data

    def process(self):
        """
        Real work is done here...
        """
        raise NotImplementedError('Your session must define a process-method!')

    def add_msg(self, msg, level=None):
        """
        Add a message to the session.
        You could either pass an instance of a message-class, or any type the
        message-classes are initiated with (string, tuple or result-object).
        """
        if isinstance(msg, str): msg = PreMessage(msg, level)
        elif isinstance(msg, tuple): msg = TableMessage(msg, level)
        elif isinstance(msg, Result): msg = ExecutionMessage(msg, level)
        elif isinstance(msg, BaseMessage): pass
        self._db.messages.add(msg, bulk=False)

    def set_status(self, status, alert=True):
        """
        Set session-status. Pass a valid session-status or a boolean.
        """
        states = dict(self._db.SESSION_STATES)
        if type(status) == bool:
            status = 'success' if status else 'error'
        elif status.lower() in states.keys():
            status = status.lower()
        else:
            msg = 'session-status must be one of {}'.format(states.keys())
            raise InvalidMinkeSetup(msg)

        if not self.status or not alert or states[self.status] < states[status]:
            self._db.session_status = status

    def format_cmd(self, cmd):
        """
        Will format a given command-string using the minkeobj's attributes
        and the session_data while the session_data has precedence.
        """
        params = vars(self.minkeobj)
        params.update(self.data)
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

    def _run(self, cmd, **kwargs):
        """
        Run a command and save the result.
        """
        result = self._con.run(cmd, **kwargs)
        self._db.commands.add(result, bulk=False)
        return result

    @protect
    def run(self, cmd, **kwargs):
        """
        Run a command and return its response.
        """
        return self._run(cmd, **kwargs)

    @protect
    def execute(self, cmd, add_msg=True, set_status=True, **kwargs):
        """
        Run a command, leave a ExecutionMessage and set the session-status.
        """
        result = self._run(cmd, **kwargs)

        # choose session-status depending on result-characteristics
        if result.failed: status = 'error'
        elif result.stderr: status = 'warning'
        else: status = 'success'

        if add_msg: self.add_msg(result)
        if set_status: self.set_status(status)

        return result.ok


class UpdateEntriesSession(Session):
    abstract = True

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
            self.add_msg(result, 'warning')
            value = None

        # not valid - error-message...
        else:
            self.add_msg(result, 'error')
            value = None

        setattr(self.minkeobj, field, value)
        return bool(value)


class SingleCommandSession(Session):
    abstract = True
    command = None

    def process(self):
        self.execute(self.format_cmd(self.command))


class CommandFormSession(SingleCommandSession):
    abstract = True
    form = CommandForm
    command = '{cmd}'


class CommandChainSession(Session):
    abstract = True
    commands = tuple()
    break_states = ('error',)

    def process(self):
        for cmd in self.commands:
            self.execute(self.format_cmd(cmd))
            if self.status in self.break_states:
                break


class SessionChain(Session):
    abstract = True
    sessions = tuple()
    break_states = ('error',)

    def process(self):
        for cls in self.sessions:
            session = cls(self._con, self._db)
            session.process()
            if session.status in self.break_states:
                break
