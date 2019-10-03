# -*- coding: utf-8 -*-

import re, logging, functools
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
from .utils import FormatDict


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
    Decorator for session-methods to defer their interrupt.
    """
    @functools.wraps(method)
    def wrapper(obj, *args, **kwargs):
        # are we already protected?
        if obj._busy:
            return method(obj, *args, **kwargs)
        # otherwise protect the method-call by setting the busy-flag
        obj._busy = True
        result = method(obj, *args, **kwargs)
        # if interruption was deferred now is the time to raise it
        if obj._interrupt:
            raise obj._interrupt
        obj._busy = False
        return result

    return wrapper


class Session(metaclass=SessionRegistration):
    """Base-class for all session-classes.

    All session-classes must inherit from Session. By defining a subclass of
    Session the subclass will be implicitly registered as session-class and also
    a run-permission will be created for it. To prevent this behavior use an
    abstract session by setting :attr:`.abstract` to True.

    Each session will be instantiated with a fabric-:doc:`fabric:api/connection`
    and an object of :class:`~.models.MinkeSession`. The connection-object
    provides the remote-access, while the minkesession is the database-
    representation of a specific session running for a specific
    :class:`minkemodel-object <.models.MinkeModel>`.

    For a session-class to be useful you at least has to define the
    :meth:`.process`-method and add one or more :class:`~.models.MinkeModel` to
    :attr:`.work_on`-attribute.

    """

    abstract = True
    """An abstract session-class won't be registered itself. Nor will a
    run-permission be created for it. This is useful if your session-class
    should be a base-class for other sessions.

    Abstract session-classes can be registered manually by calling its
    classmethod :meth:`~.SessionRegistration.register`::

        MySession.register()

    This will register the session but won't create any run-permissions."""

    verbose_name = None
    """Display-name for sessions."""

    work_on = tuple()
    """Tuple of minke-models. Models the session can be used with."""

    permissions = tuple()
    """Tuple of permission-strings. To be able to run a session a user must have
    all the permissions listed. The strings should have the following format:
    "<app-label>.<permission's-codename>"""

    form = None
    """An optional form that will be rendered before the session will be
    processed. The form-data will be accessible within the session as the
    data-property. Use it if the session's processing depends on additional
    user-input-data.

    Instead of setting the form-attribute you can also directly overwrite
    :meth:`.get_form`."""

    confirm = False
    """If confirm is true, the admin-site asks for a user-confirmation before
    processing a session, which also allows to review the objects the session
    was revoked with."""

    invoke_config = dict()
    """Session-specific fabric- and invoke-configuration-parameters which will
    be used to initialize a :class:`fabric-connection <fabric.connection.Connection>`.
    The keys must be formatted in a way that is accepted by
    :meth:`~.helpers.FabricConfig.load_snakeconfig`.

    See also the documentation for the configuration of
    :doc:`fabric <fabric:concepts/configuration>` and
    :doc:`invoke <invoke:concepts/configuration>`.
    """

    parrallel_per_host = False
    """Allow parrallel processing of multiple celery-tasks on a single host.
    If multiple minke-objects are associated with the same host all tasks
    running on them would be processed in a serial manner by default. This is
    to protect the ressources of the host-system. If you want to allow parrallel
    processing of multiple celery-tasks on a single host set parrallel_per_host
    to True.

    Note
    ----
    To perform parrallel task-execution on a single host we make use of celery's
    chords-primitive, which needs a functioning result-backend to be configured.
    Please see the :ref:`celery-documentation <chord-important-notes>`
    for more details."""

    def __init__(self, con, db):
        """Session's init-method.

        Parameters
        ----------
        con : obj of :class:`fabric.connection.Connection`
        db : obj of :class:`~.models.MinkeSession`
        """
        self._con = con
        self._db = db
        self._interrupt = None
        self._busy = False
        self.start = db.start
        self.end = db.end

    @classmethod
    def get_form(cls):
        """
        Return :attr:`.form` by default.

        Overwrite this method if you need to setup your form-class dynamically.
        """
        return cls.form

    @property
    def status(self):
        """
        Refers to :attr:`.models.MinkeSession.session_status`.
        """
        return self._db.session_status

    @property
    def minkeobj(self):
        """
        Refers to :attr:`.models.MinkeSession.minkeobj`.
        """
        return self._db.minkeobj

    @property
    def data(self):
        """
        Refers to :attr:`.models.MinkeSession.session_data`.
        This model-field holds all the data that comes from :attr:`.form`.
        """
        return self._db.session_data

    def cancel(self):
        """Interrupt the session's processing.

        This method could be called twice. The first time it will initiate a
        soft interruption which means a current remote-process won't be
        interrupted. The session will be stopped subsequently.
        If it is called meanwhile a second time, the session will be killed
        immediately.

        Note
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

    def process(self):
        """
        Real work is done here...

        This is the place for your own session-code.
        """
        raise NotImplementedError('Your session must define a process-method!')

    def add_msg(self, msg, level=None):
        """
        Add a message.

        Parameters
        ----------
        msg
            You could either pass an instance of any :mod:`message-class<.messages>`,
            or any type the different message-classes are initiated with:

            * a string for a :class:`~messages.PreMessage`

            * a tuple for a :class:`~messages.TableMessage`

            * an object of :class:`~fabric.runners.Result` for a
              :class:`~messages.ExecutionMessage`

        level : string or bool (optional)
            This could be one of 'info', 'warning' or 'error'. If you pass a
            bool True will be 'info' and False will be 'error'.
        """
        if isinstance(msg, str): msg = PreMessage(msg, level)
        elif isinstance(msg, tuple): msg = TableMessage(msg, level)
        elif isinstance(msg, Result): msg = ExecutionMessage(msg, level)
        elif isinstance(msg, BaseMessage): pass
        self._db.messages.add(msg, bulk=False)

    def set_status(self, status, update=True):
        """
        Set session-status. Pass a valid session-status or a bool.

        Parameters
        ----------
        status : string or bool
            Valid :attr:`status <models.MinkeSession.SESSION_STATES>` as string
            or True for 'success' and False for 'error'.
        update : bool (optional)
            If True the session-status could only be raised. Lower values as
            current will be ignored.
        """
        states = dict(self._db.SESSION_STATES)
        if type(status) == bool:
            status = 'success' if status else 'error'
        elif status.lower() in states.keys():
            status = status.lower()
        else:
            msg = 'session-status must be one of {}'.format(states.keys())
            raise InvalidMinkeSetup(msg)

        if not self.status or not update or states[self.status] < states[status]:
            self._db.session_status = status

    def format_cmd(self, cmd):
        """
        Use the :attr:`.data` and the fields of the :attr:`.minkeobj` as
        parameters for :func:`format` to prepare the given command.

        Parameters
        ----------
        cmd : string
            a format-string

        Returns
        -------
        string
            The formatted command.
        """
        cmd = cmd.format_map(FormatDict(self.data))
        cmd = cmd.format_map(FormatDict(vars(self.minkeobj)))
        return cmd

    @protect
    def run(self, cmd, regex=None, **invoke_params):
        """
        Run a command.

        Basically call :meth:`~fabric.connection.Connection.run` on the
        :class:`~fabric.connection.Connection`-object with the given command
        and invoke-parameters.

        Additionally save the :class:`~invoke.runners.Result`-object as an
        :class:`.models.CommandResult`-object.

        Parameters
        ----------
        cmd : string
            The shell-command to be run.
        regex: string (optional)
            A regex-pattern the :class:`.CommandResult` will be initialized with.
        **invoke_params (optional)
            Parameters that will be passed to
            :meth:`~fabric.connection.Connection.run`

        Returns
        -------
        object of :class:`.models.CommandResult`
        """
        result = self._con.run(cmd, **invoke_params)
        result = CommandResult(result, regex)
        self._db.commands.add(result, bulk=False)
        return result

    @protect
    def frun(self, cmd, regex=None, **invoke_params):
        """
        Same as :meth:`.run`, but use :meth:`~.format_cmd` to prepare the
        command-string.
        """
        return self.run(self.format_cmd(cmd), regex, **invoke_params)

    @protect
    def xrun(self, cmd, regex=None, **invoke_params):
        """
        Same as :meth:`.frun`, but also add a
        :class:`~.messages.ExecutionMessage` and update the session-status.
        """
        result = self.frun(cmd, regex, **invoke_params)
        self.add_msg(result)
        self.set_status(result.status, update=True)
        return result

    @protect
    def update_field(self, field, cmd, regex=None, **invoke_params):
        """
        Running a command and update a field of :attr:`~.minkeobj`.

        If the result is :attr:`~.models.CommandResult.valid` either the whole
        :attr:`~.models.CommandResult.stdout` is used or, if a regex is given
        and there is are matching regex-groups, the first group is used.
        If stdout is empty or if the result is not valid the field will be
        updated with None. In both cases a message will added.

        Parameters
        ----------
        field : string
            Name of the field that should be updated.
        cmd : string
            The shell-command to be run.
        regex: string (optional)
            A regex-pattern the :class:`.CommandResult` will be initialized with.
        **invoke_params (optional)
            Parameters that will be passed to
            :meth:`~fabric.connection.Connection.run`

        Returns
        -------
        bool
            False if the field was updated with None. True otherwise.

        Raises
        ------
        AttributeError
            If the given field does not exists on :attr:`.minkeobj`.
        """
        # is field a minkeobj-attribute?
        try:
            getattr(self.minkeobj, field)
        except AttributeError as e:
            raise e

        result = self.frun(cmd, regex, **invoke_params)

        if result.valid and result.stdout:
            if result.match and result.match.groups():
                value = result.match.group(1)
            else:
                value = result.stdout
        elif result.valid and not result.stdout:
            self.add_msg(result, 'warning')
            value = None
        else:
            self.add_msg(result, 'error')
            value = None

        setattr(self.minkeobj, field, value)
        return bool(value)


class SingleCommandSession(Session):
    """
    An abstract :class:`~.Session`-class for the execution of a single command.

    If you want your session to execute one single command and leave its output
    as message you simply can use SingleCommandSession as follows::

        class MySession(SingleCommandSession):
            work_on = (MyModel,)
            command = 'echo foobar'

    The command will be executed using :meth:`~.Session.xrun`.
    """
    abstract = True

    """Command that should be executed."""
    command = None

    def process(self):
        self.xrun(self.command)


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
            self.xrun(cmd)
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
