# -*- coding: utf-8 -*-

from fabric.api import env, execute
from fabric.network import disconnect_all

from django.utils.html import mark_safe

import minke.sessions
from .models import Host
from .messages import Message
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

def process(session_cls, queryset, messenger):
    """Initiate fabric's session-processing."""

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
            error = minke.sessions.Session.ERROR
            for player in players:
                messenger.store(player, [invalid], error)
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
