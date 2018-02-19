# -*- coding: utf-8 -*-

import re
import datetime
import traceback

from django.utils.html import mark_safe
from django.core.exceptions import FieldDoesNotExist

from fabric.api import run, env, execute
from fabric.network import disconnect_all

from .models import Host
from .messages import store_msgs
from .messages import clear_msgs
from .messages import PreMessage
from .messages import ExecutionMessage
from .messages import ExceptionMessage
from .exceptions import Abortion
from .exceptions import NetworkError
from .exceptions import CommandTimeout


registry = list()
def register(session_cls, models=None, short_description=None):
    """Registered sessions will be automatically added as admin-actions by
    MinkeAdmin. Therefore at least one model must be specified for a session,
    either listed in session's model-attribute or passed to the register-method.
    """

    if models:
        if not type(models) == list: models = [models]
        session_cls.models = models

    if short_description:
        session_cls.short_description = short_description

    if not issubclass(session_cls, Session):
        raise ValueError('Registered class must subclass Session.')

    if not session_cls.models:
        raise ValueError('At least one model must be specified for a session.')

    for model in session_cls.models:
        try:
            assert model == Host or model._meta.get_field('host').rel.to == Host
        except (AssertionError, FieldDoesNotExist):
            raise ValueError('Sessions could only be used with Host '
                             'or a model with a relation to Host.')

    registry.append(session_cls)


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

def process(request, session_cls, queryset, modeladmin):
    """This method is called by actions.Action. It initiate and wrappes all work
    done by fabric using fabric's execute-function.
    """

    # clear already stored messages for these objects
    clear_msgs(request, modeladmin.model)

    session_pool = dict()
    hosts = get_hosts(queryset)

    for host in hosts:
        players = get_players(host, queryset)

        # skip invalid hosts (disabled or locked)
        invalid_host_msg = None
        if host.disabled:
            invalid_host_msg = dict(level='error', text='Host were disabled!')

        # Never let a host be involved in two simultaneous sessions...
        elif not Host.objects.get_lock(id=host.id):
            invalid_host_msg = dict(level='error', text='Host were locked!')

        if invalid_host_msg:
            for player in players:
                store_msgs(request, player, invalid_host_msg, 'error')
        else:
            sessions = [session_cls(host, p, request) for p in players]
            session_pool[host.hoststring] = sessions

    # here we stop if no valid host is left...
    if not session_pool: return

    try:
        processor = SessionTask(session_cls, session_pool)
        result = execute(processor.run, hosts=session_pool.keys())
    except Exception:
        # FIXME: This is debugging-stuff and should go into the log.
        # (Just leave a little msg to the user...)
        msg = '<pre>{}</pre>'.format(traceback.format_exc())
        modeladmin.message_user(request, mark_safe(msg), 'ERROR')
    else:
        sessions = list()
        for host_sessions in result.values():

            # If something unexpected hinders the processor to return the
            # session-objects, we've got to deal with it here...
            try:
                assert isinstance(host_sessions[0], Session)
            except (AssertionError, TypeError, IndexError):
                # FIXME: This should not happen. But we might put some
                # debugging-stuff here using logging-mechanisms
                msg = '<pre>{}</pre>'.format(traceback.format_exc())
                modeladmin.message_user(request, mark_safe(msg), 'ERROR')
            else:
                sessions += host_sessions

        for session in sessions:
            # Use rework for final db-actions.
            # To be able to add messsages we pass request.
            session.rework(request)

            # store session-status and messages
            store_msgs(request, session.player, session.msgs, session.status)

    finally:
        # disconnect fabrics ssh-connections
        disconnect_all()

        # release the lock
        for hoststring in session_pool.keys():
            Host.objects.release_lock(hoststring=hoststring)


class SessionTask(object):
    """
    Basically a wrapper-class for Session used with fabric's execute-function.

    The SessionTask's run-method is passed to fabric's execute-function.
    At this point a host-based and parallized multiprocessing will take place
    and orchestrated by fabric.

    This class allows us to serialize sessions that run with distinct objects
    associated with the same host in a parallized multiprocessing-context.

    Also we take care of exceptions that might be thrown within session.process.
    """
    def __init__(self, session_cls, session_pool):
        self.session_cls = session_cls
        self.session_pool = session_pool

    def run(self):
        sessions = self.session_pool[env.host_string]
        for session in sessions:

            try:
                session.process()
            except Abortion:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage()))
            except NetworkError:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage()))
            except CommandTimeout:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage()))

            # FIXME: This is debugging-stuff and should go into the log.
            # (Just leave a little msg to the user...)
            except Exception:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage(print_tb=True)))

            else:
                if not session.status:
                    session.status = 'success'
        return sessions


class Session(object):
    """This is the base-class for all your sessions."""

    short_description = None
    """Used as action's short_description."""

    models = list()
    """A list of models a session will be used with as admin-action."""

    def __init__(self, host, player, request):
        self.host = host
        self.player = player
        self.msgs = list()
        self.status = None

    def fcmd(self, cmd):
        return cmd.format(**self.player.__dict__)

    def validate(self, result, regex='.*'):
        if not re.match(regex, result.stdout):
            self.msgs.append(vars(ExecutionMessage(result, 'error')))
            self.status = 'warning'
            return False
        elif result.return_code or result.stderr:
            self.msgs.append(vars(ExecutionMessage(result, 'warning')))
            self.status = 'warning'
            return False
        else:
            return True

    # tasks
    def message(self, cmd, **kwargs):
        result = run(cmd, **kwargs)
        if self.validate(result):
            self.msgs.append(vars(PreMessage('info', result.stdout)))

    def update_field(self, field, cmd, regex='(.*)'):

        try: getattr(self.player, field)
        except AttributeError as e: raise e

        result = run(cmd)
        if self.validate(result, regex):
            try:
                value = re.match(regex, result.stdout).groups()[0]
            except IndexError:
                value = result.stdout or None
            finally:
                setattr(self.player, field, value)
        else:
            setattr(self.player, field, None)

    def process(self):
        """Real work is done here...

        This is the part of a session which is executed within fabric's
        multiprocessing-szenario. It's the right place for all
        fabric-operations. But keep it clean of all database-related stuff.
        Database-connections are multiplied with spawend processes and are not
        reliable anymore. Database-stuff should be done within __init__ or rework.
        """
        raise NotImplementedError('Got to define your own run-method for a session!')

    def rework(self, request):
        """This method is called after fabric's work is done."""

        # TODO: define a pre_save to check if changes has been done
        self.player.entries_updated = datetime.datetime.now()
        self.player.save()
