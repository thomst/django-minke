# -*- coding: utf-8 -*-

import re
from collections import OrderedDict

from django.db.utils import OperationalError
from django.db.utils import ProgrammingError
from django.core.exceptions import FieldDoesNotExist
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.text import camel_case_to_spaces

from .models import Host
from .models import MinkeModel
from .models import MinkeSession
from .forms import CommandForm
from .messages import ExecutionMessage
from .messages import PreMessage
from .exceptions import InvalidMinkeSetup


class REGISTRY(OrderedDict):
    _session_factories = list()

    @classmethod
    def add_session_factory(cls, factory):
        cls._session_factories.append(factory)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dict = None

    def reload(self):
        if self._dict:
            self.clear()
            self.update(self._dict)
        else:
            self._dict = self.copy()
        for factory in self._session_factories:
            factory()


REGISTRY = REGISTRY()


class SessionRegistration(type):
    """
    metaclass for Sessions that implements session-registration
    """
    def __new__(cls, name, bases, dct):
        dct['abstract'] = dct.get('abstract', False)
        return super().__new__(cls, name, bases, dct)

    def __init__(cls, classname, bases, attr):
        super().__init__(classname, bases, attr)
        if cls.abstract: return
        if cls.__name__ in REGISTRY: return

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
            cls.verbose_name = camel_case_to_spaces(classname)

        # register session
        REGISTRY[cls.__name__] = cls

        if cls.create_permissions:
            # create session-permission...
            # In some contexts get_for_model fails because content_types aren't
            # setup. This happens when applying migrations but also when testing
            # with sqlite3.
            try: content_type = ContentType.objects.get_for_model(MinkeSession)
            except (OperationalError, ProgrammingError): return
            codename = 'run_{}'.format(classname.lower())
            permname = 'Can run {}'.format(camel_case_to_spaces(classname))
            permission = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults=dict(name=permname))
            permission_name = 'minke.{}'.format(codename)
            cls.permissions += (permission_name,)


class Session(metaclass=SessionRegistration):
    abstract = True
    verbose_name = None
    work_on = tuple()
    permissions = tuple()
    form = None
    confirm = False
    wait_for_execution = False
    create_permissions = True
    invoke_config = dict()

    @classmethod
    def get_form(cls):
        return cls.form

    def __init__(self, connection, db):
        self.connection = connection
        self._db = db
        self.start = db.start
        self.end = db.end
        self.fail = db.fail

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

    def add_msg(self, msg):
        self._db.messages.add(msg, bulk=False)

    def set_status(self, status, alert=True):
        """
        Set session-status. Pass a valid session-status or a boolean.
        """
        states = dict(self._db.RESULT_STATES)
        if type(status) == bool:
            status = 'success' if status else 'error'
        elif status.lower() in states.keys():
            status = status.lower()
        else:
            msg = 'session-status must be one of {}'.format(states)
            raise InvalidMinkeSetup(msg)

        if not self.status or not alert or states[self.status] < states[status]:
            self._db.session_status = status

    # helper-methods
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

    def run(self, cmd, *args, **kwargs):
        """
        run a command
        """
        return self.connection.run(cmd, *args, **kwargs)

    def execute(self, cmd, *args, **kwargs):
        """
        Run cmd, leave a message and set session-status.
        """
        result = self.run(cmd, *args, **kwargs)
        if result.failed:
            self.add_msg(ExecutionMessage(result, 'error'))
            self.set_status('error')
        elif result.stderr:
            self.add_msg(ExecutionMessage(result, 'warning'))
            self.set_status('warning')
        else:
            self.add_msg(ExecutionMessage(result, 'info'))
            self.set_status('success')

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
            self.add_msg(ExecutionMessage(result, 'WARNING'))
            value = None

        # not valid - error-message...
        else:
            self.add_msg(ExecutionMessage(result, 'ERROR'))
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
            session = cls(self.connection, self._db)
            session.process()
            if session.status in self.break_states:
                break
