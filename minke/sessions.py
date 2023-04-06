# -*- coding: utf-8 -*-

import logging
import functools
from collections import OrderedDict
from fabric2.runners import Result

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.text import camel_case_to_spaces
from django.dispatch import Signal

from .models import Host
from .models import MinkeModel
from .models import MinkeSession
from .models import BaseMessage
from .forms import CommandForm
from .messages import PreMessage
from .messages import TableMessage
from .messages import ExecutionMessage
from .exceptions import InvalidMinkeSetup
from .exceptions import SessionRegistrationError
from .utils import FormatDict


logger = logging.getLogger(__name__)


class RegistryDict(OrderedDict):
    """
    A reload-able session-registry.
    """
    reload_sessions = Signal(providing_args=['session_name'])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._static_sessions = None

    def reload(self, session_name=None):
        """
        Load dynamical sessions into the registry.

        Reset the registry to the static sessions. Then send a reload-signal.
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
        if session_name and session_name in self:
            return

        # trigger the reload signal
        self.reload_sessions.send(sender=self.__class__, session_name=session_name)


REGISTRY = RegistryDict()


class SessionGroup:
    """
    A group of session - displayed as optgroups in the select-widget.
    Create a group and use it as decorator for Sessions::

        my_group = SessionGroup('My Group')

        @my_group
        class MySession(Session):
            pass
    """
    def __init__(self, name=None):
        self.name = name

    def __call__(self, cls, name=None):
        cls.group = name or self.name
        return cls


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
        if not cls.abstract:
            cls.register()
            if cls.auto_permission:
                cls.add_permission()

    def register(cls):
        """
        Register the session-class.
        """
        # some sanity-checks
        if cls.__name__ in REGISTRY:
            msg = 'A session with that name was already registered.'
            raise SessionRegistrationError(cls, msg)

        if not cls.work_on:
            msg = 'At least one minke-model must be specified.'
            raise SessionRegistrationError(cls, msg)

        for model in cls.work_on:
            try:
                assert(model == Host or issubclass(model, MinkeModel))
            except (TypeError, AssertionError):
                msg = '{} is no minke-model.'.format(model)
                raise SessionRegistrationError(cls, msg)

        if issubclass(cls, SingleCommandSession) and not cls.command:
            msg = 'SingleCommandSession needs to specify an command.'
            raise SessionRegistrationError(cls, msg)

        if issubclass(cls, CommandChainSession) and not cls.commands:
            msg = 'CommandChainSession needs to specify commands.'
            raise SessionRegistrationError(cls, msg)

        # TODO: Check for recursion in SessionChains
        # TODO: Check SessionChain's sessions
        if issubclass(cls, SessionChain) and not cls.sessions:
            msg = 'SessionChain needs to specify sessions.'
            raise SessionRegistrationError(cls, msg)

        # set verbose-name if missing
        if not cls.verbose_name:
            cls.verbose_name = camel_case_to_spaces(cls.__name__)

        # register session
        REGISTRY[cls.__name__] = cls

    def _get_permission(cls):
        codename = 'run_{}'.format(cls.__name__.lower())
        name = 'Can run {}'.format(cls.__name__)
        lookup = 'minke.{}'.format(codename)
        return codename, name, lookup

    def create_permission(cls):
        """
        Create a run-permission for this session-class.
        """
        content_type = ContentType.objects.get_for_model(MinkeSession)
        codename, name, lookup = cls._get_permission()
        permission, created = Permission.objects.update_or_create(
            codename=codename,
            content_type=content_type,
            defaults=dict(name=name))
        return permission, created

    def delete_permission(cls):
        codename, name, lookup = cls._get_permission()
        try:
            Permission.objects.get(codename=codename).delete()
        except Permission.DoesNotExist:
            pass
        else:
            cls.permissions = tuple(set(cls.permissions) - set((lookup,)))

    def add_permission(cls):
        codename, name, lookup = cls._get_permission()
        cls.permissions = tuple(set(cls.permissions) | set((lookup,)))


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
        if obj._stopped:
            raise KeyboardInterrupt
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
    """
    An abstract session-class won't be registered itself. This is useful if your
    session-class should be a base-class for other sessions.

    Abstract session-classes can be registered manually by calling its
    classmethod :meth:`~.SessionRegistration.register`::

        MySession.register()

    This won't add a run-permission-lookup-string to :attr:`.permissions`. To do so
    use the classmethod :meth:`.SessionRegistration.add_permission`::

        MySession.add_permission()
    """

    verbose_name = None
    """Display-name for sessions."""

    group = None
    """
    Group-name used as optgroup-tag in the select-widget.
    Best practice to group sessions is to use a :class:`.SessionGroup`.
    """

    work_on = tuple()
    """Tuple of minke-models. Models the session can be used with."""

    permissions = tuple()
    """
    Tuple of permission-strings. To be able to run a session a user must have
    all the permissions listed. The strings should have the following format:
    "<app-label>.<permission's-codename>.
    """

    auto_permission = True
    """
    If True a lookup-string for a session-specific run-permission will be
    automatically added to :attr:`.permissions`.

    Note
    ----
    To avoid database-access on module-level we won't create the permission itself.
    Once you setup your sessions you could create run-permissions for all sessions
    using the api-command::

        $ ./manage.py minkeadm --create-permissions
    """

    # TODO: Make this a tuple or list of forms to render.
    form = None
    """
    An optional form that will be rendered before the session will be
    processed. The form-data will be accessible within the session as the
    data-property. Use it if the session's processing depends on additional
    user-input-data.

    Instead of setting the form-attribute you can also directly overwrite
    :meth:`.get_form`.
    """

    confirm = False
    """
    If confirm is true, the admin-site asks for a user-confirmation before
    processing a session, which also allows to review the objects the session
    was revoked with.
    """

    # TODO: This should be renamed to something like context.
    invoke_config = dict()
    """
    Session-specific fabric- and invoke-configuration-parameters which will
    be used to initialize a :class:`fabric-connection <fabric.connection.Connection>`.
    The keys must be formatted in a way that is accepted by
    :meth:`~.fabrictools.FabricConfig.load_snakeconfig`.

    See also the documentation for the configuration of
    :doc:`fabric <fabric:concepts/configuration>` and
    :doc:`invoke <invoke:concepts/configuration>`.
    """

    parrallel_per_host = False
    """
    Allow parrallel processing of multiple celery-tasks on a single host.
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
    for more details.
    """

    def __init__(self, con, db, minkeobj=None):
        """Session's init-method.

        Parameters
        ----------
        con : obj of :class:`fabric.connection.Connection`
        db : obj of :class:`~.models.MinkeSession`
        minkeobj : obj of :class:`~.models.Minkeobj` (optional)
            Only required if you want to initialize a session out of another
            session and let it work on a different minkeobj.
        """
        # TODO: Update the connection dict with the minkeobj.data.
        # Maybe use a prefix on form fields for context data.
        self._c = con
        self._db = db
        self._minkeobj = minkeobj
        self._stopped = False
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
    def c(self):
        """
        Refers to the :class:`fabric.connection.Connection`-object the session
        was initialized with.
        """
        return self._c

    @property
    def minkeobj(self):
        """
        Refers to :attr:`.models.MinkeSession.minkeobj`.
        """
        return self._minkeobj or self._db.minkeobj

    @property
    def status(self):
        """
        Refers to :attr:`.models.MinkeSession.session_status`.
        """
        return self._db.session_status

    @property
    def data(self):
        """
        Refers to :attr:`.models.MinkeSession.session_data`.
        This model-field holds all the data that comes from :attr:`.form`.
        """
        return self._c.session_data

    def stop(self, *arg, **kwargs):
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
        if not self._busy or self._stopped:
            raise KeyboardInterrupt
        else:
            self._stopped = True

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

            * a tuple or list for a :class:`~messages.TableMessage`

            * an object of :class:`~fabric.runners.Result` for a
              :class:`~messages.ExecutionMessage`

        level : string or bool (optional)
            This could be one of 'info', 'warning' or 'error'. If you pass a
            bool True will be 'info' and False will be 'error'.
        """
        if isinstance(msg, str):
            msg = PreMessage(msg, level)
        elif isinstance(msg, tuple) or isinstance(msg, list):
            msg = TableMessage(msg, level)
        elif isinstance(msg, Result):
            msg = ExecutionMessage(msg, level)
        elif isinstance(msg, BaseMessage):
            pass
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
        # FIXME: Do we need this complexity here? Won't it be more clear to
        # overwrite the process method of CommandFormSession?
        cmd = cmd.format_map(FormatDict(self.data))
        cmd = cmd.format_map(FormatDict(vars(self.minkeobj)))
        return cmd

    @protect
    def run(self, cmd, **invoke_params):
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
        **invoke_params (optional)
            Parameters that will be passed to
            :meth:`~fabric.connection.Connection.run`

        Returns
        -------
        object of :class:`.models.CommandResult`
        """
        result = self.c.run(cmd, **invoke_params)
        self._db.commands.add(result, bulk=False)
        return result

    @protect
    def frun(self, cmd, **invoke_params):
        """
        Same as :meth:`.run`, but use :meth:`~.format_cmd` to prepare the
        command-string.
        """
        return self.run(self.format_cmd(cmd), **invoke_params)

    @protect
    def xrun(self, cmd, **invoke_params):
        """
        Same as :meth:`.frun`, but also add a
        :class:`~.messages.ExecutionMessage` and update the session-status.
        """
        result = self.frun(cmd, **invoke_params)
        self.add_msg(result)
        self.set_status(result.status)
        return result

    @protect
    def update_field(self, field, cmd, regex=None, **invoke_params):
        """
        Running a command and update a field of :attr:`~.minkeobj`.

        Assign either result.stdout or if available the first matched
        regex-group. If result.failed is True or result.stdout is empty
        or the given regex does not match, the field is updated with None.
        In this case an error-message will be added.

        Parameters
        ----------
        field : string
            Name of the field that should be updated.
        cmd : string
            The shell-command to be run.
        regex: string (optional)
            A regex-pattern the :class:`.CommandResult` will be validated with.
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

        result = self.frun(cmd, **invoke_params)

        if regex and result.validate(regex):
            try:
                value = result.match.group(1)
            except IndexError:
                value = result.stdout
        elif not regex and result.ok and result.stdout:
            value = result.stdout
        else:
            self.add_msg(result, 'error')
            self.set_status('warning')
            value = None

        setattr(self.minkeobj, field, value)
        return bool(value)


class SingleCommandSession(Session):
    """
    An abstract :class:`.Session`-class to execute a single command.

    If you want your session to execute a single command simply create a
    subclass of SingleCommandSession and overwrite the
    :attr:`.command`-attribute. The command will be executed with
    :meth:`~.Session.xrun`.

    Example
    -------
    ::

        class MyDrupalModel(models.Model):
            root = models.CharField(max_length=255)

        class MySession(SingleCommandSession):
            work_on = (MyDrupalModel,)
            command = 'drush --root={root} cache-clear all'
    """
    abstract = True

    command = None
    """Shell-command to be executed."""

    def process(self):
        self.xrun(self.command)


class CommandFormSession(SingleCommandSession):
    """
    Same as class:`.SingleCommandSession` but rendering a TextField to enter
    the command.

    Example
    -------
    ::

        class MySession(CommandFormSession):
            work_on = (MyModel,)
    """
    abstract = True
    form = CommandForm
    command = '{cmd}'


class CommandChainSession(Session):
    """
    An abstract :class:`.Session`-class to execute a sequence of commands.

    The commands will be invoked one after another. If one of the commands
    return with a state defined in :attr:`.break_states` no further commands
    will be executed.

    Example
    -------
    ::

        class MySession(CommandChainSession):
            work_on = (MyServer,)
            commands = (
                'a2ensite mysite'
                'apachectl configtest',
                'service apache2 reload')
    """
    abstract = True

    commands = tuple()
    """tuple of shell-commands"""

    break_states = ('error',)
    """
    tuple of :attr:`.models.CommandResult.status` on which the session will
    be interrupted
    """

    def process(self):
        for cmd in self.commands:
            result = self.xrun(cmd)
            if result.status in self.break_states:
                break


class SessionChain(Session):
    """
    An abstract :class:`.Session`-class to execute a sequence of sessions.

    If you have some sessions you want to be able to process separately or as
    a sequence you could make use of a :class:`.SessionChain`.

    All sessions have to work with the same :attr:`~.Session.minkeobj`. If one
    of the sessions ends up with a status defined in :attr:`.break_states` no
    further sessions will be executed.

    Example
    -------
    ::

        class MySession(SessionChain):
            work_on = (MyServer,)
            sessions = (
                UpdateSQLServer,
                RestartSQLServer,
                UpdateApache,
                RestartApache)

    Note
    ----
    It is possible to add abstract sessions to :attr:`.sessions`.

    Warnings
    --------
    Only the :attr:`~.Session.invoke_config` of the main session will be applied.
    The :attr:`~.Session.invoke_config` of the sessions in :attr:`.sessions`
    will be ignored.

    The same is true for :meth:`~.Session.get_form()`. Only the form returned
    by the main session's :meth:`~.Session.get_form()` will be rendered.
    """
    abstract = True

    sessions = tuple()
    """
    tuple of :class:`.Session`
    """

    break_states = ('error',)
    """
    tuple of :attr:`.Session.status` on which further processing will be skipped.
    """

    def process(self):
        for cls in self.sessions:
            session = cls(self.c, self._db, self.minkeobj)
            msg = 'Run {}'.format(session.verbose_name)
            self.add_msg(msg)
            session.process()
            if session.status in self.break_states:
                msg = '{} finished with status {}'.format(session.verbose_name, session.status)
                self.add_msg(msg, 'error')
                break
