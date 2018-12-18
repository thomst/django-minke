# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from multiprocessing import Process
from multiprocessing import JoinableQueue
from threading import Thread

from fabric.api import env, execute
from fabric.network import disconnect_all

from django.utils.html import mark_safe
from django.contrib import messages

import minke.sessions
from .models import Host
from .models import BaseSession
from .messages import Message
from .messages import ExceptionMessage
from .exceptions import Abortion
from .exceptions import NetworkError
from .exceptions import SocketError
from .exceptions import CommandTimeout
from .management.commands import Printer


def process(session_cls, queryset, session_data, user, join, request=None):
    """Initiate fabric's session-processing."""

    hosts = queryset.get_hosts()
    lock = hosts.get_lock()
    active_hosts = hosts.get_actives(lock)
    active_players = queryset.host_filter(active_hosts)
    BaseSession.objects.clear_currents(user, active_players)

    # validate hosts and prepare sessions
    host_sessions = dict()
    for player in queryset.all():
        host = player.get_host()

        # Skip disabled or locked hosts...
        if host.disabled or host.locked and host.locked != lock:
            msg = 'disabled' if host.disabled else 'locked'
            msg = '{}: Host is {}.'.format(player, msg)
            if request: messages.warning(request, msg)
            else: print msg
            continue

        session = session_cls()
        session.user = user
        session.player = player
        session.session_data = session_data
        session.save()

        if not host_sessions.has_key(host.hoststring):
            host_sessions[host.hoststring] = list()
        host_sessions[host.hoststring].append(session)

    # Stop here if no valid hosts are left...
    if not host_sessions: return

    queue = JoinableQueue()
    consumer = Consumer(host_sessions, queue, bool(request))
    consumer.start()

    worker = Thread(target=run_fabric, args=(host_sessions, queue))
    worker.start()
    if join: worker.join()


def run_fabric(host_sessions, queue):
    try:
        session_processor = SessionProcessor(host_sessions, queue)
        execute(session_processor.run, hosts=host_sessions.keys())
    finally:
        disconnect_all()
        queue.put(('stop',))
        queue.join()


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
            self.queue.put(('start_session', session))
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
                session.status = 'error'
                session.news.append(ExceptionMessage(print_tb=True))
            finally:
                self.queue.put(('end_session', session))

        self.queue.put(('release_lock', session.player.get_host()))


class Consumer(Thread):
    def __init__(self, host_sessions, queue, prnt):
        super(Consumer, self).__init__()
        self.queue = queue
        self.host_sessions = host_sessions
        self.prnt = prnt

    def run(self):
        while True:
            directives = self.queue.get()
            action = directives[0]
            args = directives[1:]
            if action == 'stop':
                self.queue.task_done()
                break
            else:
                getattr(self, action)(*args)
                self.queue.task_done()

    def start_session(self, session):
        session.proc_status = 'running'
        session.save(update_fields=['proc_status'])

    def end_session(self, session):
        session.rework()
        session.proc_status = 'done'
        session.status = session.status or 'success'
        session.save(update_fields=['status', 'proc_status'])

        for message in session.news:
            session.messages.add(message, bulk=False)

        if not self.prnt:
            Printer.prnt(session)

    def release_lock(self, host):
        Host.objects.filter(id=host.id).release_lock()

    def save_message(self, message):
        message.save()
