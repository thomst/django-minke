# -*- coding: utf-8 -*-

import re

from django.utils.html import mark_safe

from fabric.api import run, env, execute
from fabric.network import disconnect_all

from .models import Host
from .messages import Messenger
from .messages import Message
from .messages import ExecutionMessage
from .messages import ExceptionMessage
from .exceptions import Abortion
from .exceptions import NetworkError
from .exceptions import CommandTimeout


def get_hosts(queryset):
    if queryset.model == Host:
        return queryset
    else:
        host_ids = [o.host_id for o in queryset.all()]
        return Host.objects.filter(id__in=host_ids)

def get_players(host, queryset):
    if queryset.model == Host:
        return [host]
    else:
        return list(queryset.filter(host=host))

def process(request, session_cls, queryset):
    """Initiate fabric's session-processing."""

    # clear already stored messages for this model
    messenger = Messenger(request)
    messenger.remove(queryset.model)

    session_pool = dict()
    hosts = get_hosts(queryset)

    for host in hosts:
        players = get_players(host, queryset)

        # skip invalid hosts (disabled or locked)
        invalid = None
        if host.disabled:
            invalid = Message(level='ERROR', text='Host were disabled!')

        # Never let a host be involved in two simultaneous sessions...
        elif not Host.objects.get_lock(id=host.id):
            invalid = Message(level='ERROR', text='Host were locked!')

        if invalid:
            for player in players:
                messenger.store(player, [invalid], Session.ERROR)
        else:
            # Grouping sessions by hosts.
            sessions = [session_cls(host, p) for p in players]
            session_pool[host.hoststring] = sessions

    # Stop here if no valid hosts are left...
    if not session_pool: return

    try:
        session_task = SessionTask(session_cls, session_pool)
        result = execute(session_task.run, hosts=session_pool.keys())

        for host_sessions in result.values():
            for session in host_sessions:
                # Use rework for final db-actions.
                session.rework()

                # store session-status and messages
                messenger.store(session.player, session.news, session.status)

    finally:
        # disconnect fabrics ssh-connections
        disconnect_all()

        # release the lock
        for hoststring in session_pool.keys():
            Host.objects.release_lock(hoststring=hoststring)


class SessionTask(object):
    """
    Wrapper-class for session-processing with fabric.

    The run-method will be executed in a parallized multiprocessing
    context that is orchestrated by fabric. Itself processes sessions
    grouped by the associated host. This way we beware the parallel
    execution of two sessions on one host.
    """
    def __init__(self, session_cls, session_pool):
        self.session_cls = session_cls
        self.session_pool = session_pool

    def run(self):
        sessions = self.session_pool[env.host_string]
        for session in sessions:

            try:
                session.process()
            except (Abortion, NetworkError, CommandTimeout):
                session.set_status('ERROR')
                session.news.append(ExceptionMessage())
            except Exception:
                # FIXME: Actually this is debugging-stuff and should
                # not be handled as a minke-news! We could return the
                # exception instead of the session and raise it in the
                # main process.
                session.set_status('ERROR')
                session.news.append(ExceptionMessage(print_tb=True))

        return sessions


class BaseSession(object):
    """Implement the base-functionality of a session-class."""

    SUCCESS = 'success'
    WARNING = 'warning'
    ERROR = 'error'

    def __init__(self, host, player):
        self.host = host
        self.player = player
        self.news = list()
        self.status = self.SUCCESS

    def set_status(self, status):
        try: status = getattr(self, status)
        except AttributeError: pass

        if status in (self.SUCCESS, self.WARNING, self.ERROR):
            self.status = status
        else:
            raise ValueError('Invalid session-status: {}'.format(status))

    def process(self):
        """Real work is done here...

        This is the part of a session which is executed within fabric's
        multiprocessing-szenario. It's the right place for all
        fabric-operations. But keep it clean of database-related stuff.
        Database-connections are multiplied with spawend processes and
        then are not reliable anymore.
        """
        raise NotImplementedError('Your session must define a process-method!')

    def rework(self):
        """This method is called after fabric's work is done.
        Database-related actions should be done here."""
        pass


class ActionSession(BaseSession):
    """A session-class to be registered as an admin-action.

    Attributes:
        action_description  The action's short-description.
        action_models       Models that use the session as an action.
    """
    action_description = None
    action_models = list()


class Session(ActionSession):

    def format_cmd(self, cmd):
        return cmd.format(**vars(self.player))

    def validate(self, result, regex='.*'):
        return re.match(regex, result.stdout) and not result.return_code

    def message(self, cmd, **kwargs):
        result = run(cmd, **kwargs)
        valid = self.validate(result)

        if not valid: level = 'ERROR'
        elif result.stderr: level = 'WARNING'
        else: level = 'INFO'

        self.news.append(ExecutionMessage(result, level))

        return valid


class UpdateEntriesSession(Session):

    def update_field(self, field, cmd, regex='(.*)'):
        try: getattr(self.player, field)
        except AttributeError as e: raise e

        result = run(cmd)
        valid = self.validate(result, regex)

        if valid and result.stdout:
            try: value = re.match(regex, result.stdout).groups()[0]
            except IndexError: value = result.stdout
        else:
            value = None

        if not value:
            self.news.append(ExecutionMessage(result, 'ERROR'))

        setattr(self.player, field, value)
        return bool(value)

    def rework(self):
        self.player.save()
