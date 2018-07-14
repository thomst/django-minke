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


def process(session_cls, queryset, messenger, session_data):
    """Initiate fabric's session-processing."""

    # get players per host
    players_per_host = dict()
    for player in queryset:
        host = player if isinstance(player, Host) else player.get_host()
        if not players_per_host.has_key(host):
            players_per_host[host] = list()
        players_per_host[host].append(player)

    # validate hosts and prepare sessions
    sessions_per_host = dict()
    for host, players in players_per_host.items():

        # skip invalid hosts (disabled or locked)
        invalid = None
        if host.disabled:
            invalid = Message('Host were disabled!', 'ERROR')

        # Never let a host be involved in two simultaneous sessions...
        elif not Host.objects.get_lock(id=host.id):
            invalid = Message('Host were locked!', 'ERROR')

        if invalid:
            error = minke.sessions.Session.ERROR
            for player in players:
                messenger.store(player, [invalid], error)
        else:
            # Grouping sessions by hosts.
            sessions = [session_cls(host, p, **session_data) for p in players]
            sessions_per_host[host.hoststring] = sessions

    # Stop here if no valid hosts are left...
    if not sessions_per_host: return

    try:
        host_sessions = HostSessions(sessions_per_host)
        result = execute(host_sessions.run, hosts=sessions_per_host.keys())
    finally:
        # disconnect fabrics ssh-connections
        disconnect_all()

        # release the lock
        Host.objects.release_lock(hoststring__in=sessions_per_host.keys())

    # finish up...
    for host_sessions in result.values():
        for session in host_sessions:
            # Use rework for final db-actions.
            session.rework()

            # store session-status and messages
            messenger.store(session.player, session.news, session.status)

    messenger.process()


class HostSessions(object):
    """
    Wrapper-class for session-processing with fabric.

    The run-method will be executed in a parallized multiprocessing
    context that is orchestrated by fabric. Itself processes sessions
    grouped by the associated host. This way we beware the parallel
    execution of two sessions on one host.
    """
    def __init__(self, sessions_per_host):
        self.sessions_per_host = sessions_per_host

    def run(self):
        sessions = self.sessions_per_host[env.host_string]
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
