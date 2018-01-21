# -*- coding: utf-8 -*-

import datetime
import re
import sys
import time
import paramiko
import traceback

from fabric.api import run, env, execute
from fabric.exceptions import *
from fabric.network import disconnect_all
from fabric.state import output

from django.shortcuts import render
from django.conf import settings
from django.utils.html import mark_safe

from .forms import SSHKeyPassPhrase
from .models import Host
from .messages import store_msgs
from .messages import clear_msgs
from .messages import PreMessage
from .messages import ExecutionMessage
from .messages import ExceptionMessage


# Exceptions
class Abortion(Exception):
    pass


class DisabledHost(Exception):
    pass


# general fabric-configuration
env.combine_stderr = False
env.parallel = True
env.linewise = True
env.warn_only = True
env.always_use_pty = False
env.skip_bad_hosts = False
env.abort_on_prompts = True
env.pool_size = settings.MINKE['pool_size']
env.abort_exception = Abortion

output.status = False
output.warnings = False
output.running = False
output.stdout = False
output.stderr = False
output.user = False
output.aborts = False


class Action(object):
    """
    Pass an instance of this class to the actions-list of a modeladmin.
    """
    def __init__(self, session_cls):
        self.session_cls = session_cls
        self.__name__ = self.session_cls.__name__

    def __call__(self, modeladmin, request, queryset):

        privkey = None
        if 'pass_phrase' in request.POST:
            form = SSHKeyPassPhrase(request.POST)
        else:
            form = SSHKeyPassPhrase()

        # Decrypt the ssh-key if we have a valid form...
        if form.is_valid():
            try:
                privkey = paramiko.RSAKey.from_private_key_file(
                    settings.SSH['priv_key'],
                    password=form.cleaned_data['pass_phrase'])
            except paramiko.SSHException as e:
                modeladmin.message_user(request, e, 'ERROR')

        # Either process the Action or render the pass-phrase-form
        if privkey:
            self.process(modeladmin, request, queryset, privkey)
        else:
            return render(request, 'config/ssh_private_key_form.html',
                {'title': u'Pass the pass-phrase to encrypt the ssh-key.',
                'action': self.__name__,
                'objects': queryset,
                'form': form})

    def get_hosts(self, queryset):
        if queryset.model == Host:
            return queryset
        else:
            host_ids = [o.host_id for o in queryset.all()]
            return Host.objects.filter(id__in=host_ids)

    def get_players(self, host, queryset):
        if queryset.model == Host:
            return [host]
        else:
            return list(queryset.filter(host=host))

    def process(self, modeladmin, request, queryset, privkey):
        # clear already stored messages for these objects
        # TODO: better to drop model-related or object-related messages?
        clear_msgs(modeladmin, request)

        host_strings = list()
        player_pool = dict()
        hosts = self.get_hosts(queryset)

        for host in hosts:
            players = self.get_players(host, queryset)

            # skip invalid hosts (disabled or locked)
            invalid_host_msg = None
            if host.disabled:
                invalid_host_msg = dict(level='error', text='Host were disabled!')

            # Never let a host be involved in two simultaneous sessions...
            # As the update action returns the rows that haven been updated
            # it will be 0 for already locked host.
            # This is the most atomic way to lock a host.
            elif not hosts.filter(id=host.id, locked=False).update(locked=True):
                invalid_host_msg = dict(level='error', text='Host were locked!')

            if invalid_host_msg:
                for player in players:
                    store_msgs(request, player, invalid_host_msg, 'error')
            else:
                player_pool[host] = players
                host_strings.append(host.host_string)

        # here we stop if no valid host is left...
        if not host_strings: return

        try:
            env.key = privkey
            processor = Processor(self.session_cls, player_pool)
            result = execute(processor.run, hosts=host_strings)
        except Exception as e:
            # FIXME: This is debugging-stuff and should go into the log.
            # (Just leave a little msg to the user...)
            msg = '<pre>{}</pre>'.format(traceback.format_exc())
            modeladmin.message_user(request, mark_safe(msg), 'ERROR')
        else:
            sessions = list()
            for host_string, host_sessions in result.items():

                # If something unexpected hinders the fabric-task to return its
                # session-object, we've got to deal with it here...
                if host_sessions and type(host_sessions) == list \
                    and isinstance(host_sessions[0], Session):
                    sessions += host_sessions
                else:
                    # FIXME: This is debugging-stuff and should go into the log.
                    # (Just leave a little msg to the user...)
                    pass

            for s in sessions:
                # call the sessions rework-method...
                # passing the request allows adding messages
                s.rework(request, *s.rework_args)

                # collect session-status and messages
                store_msgs(request, s.player, s.msgs, s.status)

        finally:
            # disconnect fabrics ssh-connections
            disconnect_all()

            # release the lock
            for host in player_pool.keys():
                host.locked = False
                host.save()



class Processor(object):
    """
    Basically a wrapper-class for Session used with fabric's execute-function.

    The processor's run-method is passed to the fabric's execute-function.
    At this point a host-based and parallized multiprocessing will take place
    and orchestrated by fabric.

    This class allows us to serialize sessions that run with distinct objects
    associated with the same host in a parallized multiprocessing-context.

    Also we take care of exceptions within session-calls.
    """
    def __init__(self, session_cls, player_pool):
        self.session_cls = session_cls
        self.player_pool = player_pool

    def get_players(self, host_string):
        for host, players in self.player_pool.items():
            if host.host_string == host_string:
                return host, players

    def run(self):
        sessions = list()
        host, players = self.get_players(env.host_string)
        for player in players:
            session = self.session_cls(host, player)
            sessions.append(session)

            try:
                session.process()
            except Abortion as e:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage()))
            except NetworkError as e:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage()))
            except CommandTimeout as e:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage()))

            # FIXME: This is debugging-stuff and should go into the log.
            # (Just leave a little msg to the user...)
            except Exception as e:
                session.status = 'error'
                session.msgs.append(vars(ExceptionMessage(print_tb=True)))

            else:
                if not session.status:
                    session.status = 'success'
        return sessions


class Session(object):
    """
    This is a base-class for all your sessions.
    Within a session's process-method the real work will be done.
    """
    short_description = None
    """Session.short_description will be the action's short_description"""

    @classmethod
    def as_action(cls):
        action = Action(cls)
        if cls.short_description:
            action.short_description = cls.short_description
        else:
            action.short_description = cls.__name__
        return action

    def __init__(self, host, player):
        self.host = host
        self.player = player
        self.msgs = list()
        self.rework_args = list()
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
        # this raises an Exception if field is not an attribute of players
        getattr(self.player, field)

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
        "Real work is done here..."
        raise NotImplementedError('Got to define your own run-method for a session!')

    def rework(self, request, *args):
        """This method is called after fabric's work is done.
        Actions that are not thread-safe should be done here.
        """
        # TODO: define a pre_save to check if changes has been done
        self.player.entries_updated = datetime.datetime.now()
        self.player.save()
