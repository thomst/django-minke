# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from multiprocessing import Process
from multiprocessing import Queue
from threading import Thread

from fabric.api import env, execute
from fabric.network import disconnect_all

from django.utils.html import mark_safe

import minke.sessions
from .models import Host
from .messages import Message
from .messages import ExceptionMessage
from .exceptions import Abortion
from .exceptions import NetworkError
from .exceptions import SocketError
from .exceptions import CommandTimeout


def process(session_cls, queryset, session_data, user):
    """Initiate fabric's session-processing."""

    # get players per host
    host_players = dict()
    for player in queryset:
        host = player if isinstance(player, Host) else player.get_host()
        if not host_players.has_key(host):
            host_players[host] = list()
        host_players[host].append(player)

    # validate hosts and prepare sessions
    host_sessions = dict()
    for host, players in host_players.items():
        for player in players:
            session = session_cls()
            session.user = user
            session.player = player
            session.session_data = session_data
            session.save()

            if host.disabled:
                message = Message('Host were disabled!', 'error')
                session.message_set.add(message, bulk=False)
                session.status = 'error'
                session.proc_status = 'done'
                session.save()

            # Never let a host be involved in two simultaneous sessions...
            elif not Host.objects.get_lock(id=host.id):
                message = Message('Host were locked!', 'error')
                session.message_set.add(message, bulk=False)
                session.status = 'error'
                session.proc_status = 'done'
                session.save()

        else:
            # Grouping sessions by hosts.
            host_sessions[host.hoststring] = sessions

    # Stop here if no valid hosts are left...
    if not host_sessions: return

    queue = Queue()
    queue_processor = QueueProcessor(host_sessions, queue)
    queue_processor.start()

    initiator_thread = Thread(target=initiator, args=(host_sessions, queue))
    initiator_thread.start()
    # initiator_thread.join()


def initiator(host_sessions, queue):
    try:
        session_processor = SessionProcessor(host_sessions, queue)
        execute(session_processor.run, hosts=host_sessions.keys())
    finally:
        queue.put(('stop', None))


class SessionProcessor(object):
    """
    Wrapper-class for session-processing with fabric.

    The run-method will be executed in a parallized multiprocessing
    context that is orchestrated by fabric. Itself processes sessions
    grouped by the associated host. This way we beware the parallel
    execution of two sessions on one host.
    """
    def __init__(self, host_sessions, queue):
        self.host_sessions = host_sessions
        self.queue = queue

    def run(self):
        sessions = self.host_sessions[env.host_string]
        for session in sessions:
            self.queue.put(('start_session', (session, 'running')))
            try:
                session.process()
            except (Abortion, NetworkError, CommandTimeout, SocketError):
                session.status = 'error'
                session.news.append(ExceptionMessage())
            except Exception:
                # FIXME: Actually this is debugging-stuff and should
                # not be handled as a minke-news! We could return the
                # exception instead of the session and raise it in the
                # main process.
                session.set_status('error')
                session.news.append(ExceptionMessage(print_tb=True))
            finally:
                self.queue.put(('end_session', session))

        self.queue.put(('release_lock', session.host))


class QueueProcessor(Thread):
    def __init__(self, queue, host_sessions):
        super(ProcessQueue, self).__init__()
        self.queue = queue
        self.host_sessions = host_sessions

    def run(self):
        while True:
            action, arg = self.queue.get()
            if action == 'stop':
                disconnect_all()
                break
            else:
                get_attr(self, action)(arg)

    def start_session(self, session):
        session.proc_status = 'running'
        session.save()

    def end_session(self, session):
        session.rework()
        session.proc_status = 'done'
        session.save()
        for message in session.news:
            session.message_set.add(message, bulk=False)

    def release_lock(self, host):
        Host.objects.release_lock(id=host.id)

    def save_message(self, message):
        message.save()
