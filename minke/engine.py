# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from multiprocessing import Process
from multiprocessing import JoinableQueue
from threading import Thread
import logging

from django.contrib import messages

import minke.sessions
from minke import settings
from .messages import Message
from .messages import Printer
from .models import BaseSession
from .tasks import process_sessions


logger = logging.getLogger(__name__)


def process(session_cls, queryset, session_data, user, join, console=False):
    """Initiate fabric's session-processing."""

    hosts = queryset.get_hosts()
    lock = hosts.get_lock()
    valid_hosts = hosts.filter(disabled=False).filter(locked=lock)
    valid_players = queryset.host_filter(valid_hosts)
    BaseSession.objects.clear_currents(user, valid_players)

    # group sessions by hosts
    session_groups = dict()
    for player in queryset.all():
        host = player.get_host()

        session = session_cls()
        session.user = user
        session.player = player
        session.session_data = session_data
        session.save()

        # Skip disabled or locked hosts...
        if host.disabled or host.locked and host.locked != lock:
            msg = 'disabled' if host.disabled else 'locked'
            msg = '{}: Host is {}.'.format(player, msg)
            session.messages.add(Message(msg, 'error'), bulk=False)
            session.status = 'error'
            session.proc_status = 'done'
            session.save(update_fields=['status', 'proc_status'])
            if console: Printer.prnt(session)
            continue

        if not session_groups.has_key(host):
            session_groups[host] = list()
        session_groups[host].append(session)

    # Stop here if no valid hosts are left...
    if not session_groups: return

    # start celery-worker
    results = list()
    for host, sessions in session_groups.items():
        try:
            results.append(process_sessions.delay(host, sessions))
        except process_sessions.OperationalError as exc:
            # TODO: What to do here?
            pass

    # print sessions in cli-mode
    while console and results:
        for result in results:
            if not result.ready(): continue
            sessions = result.get()
            for session in sessions:
                Printer.prnt(session)
            results.remove(result)
            break

    # wait and forget...
    for result in results:
        if join: result.wait()
        try: result.forget()
        except NotImplementedError: pass
