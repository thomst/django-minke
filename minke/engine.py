# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from multiprocessing import Process
from multiprocessing import JoinableQueue
from threading import Thread
import logging

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType

import minke.sessions
from .messages import Message
from .messages import ExceptionMessage
from .messages import Printer
from .models import SessionData
from .tasks import process_sessions


logger = logging.getLogger(__name__)


def process(session_cls, queryset, session_data, user,
            fabric_config=None, wait=False, console=False):
    """Initiate fabric's session-processing."""

    SessionData.objects.clear_currents(user, queryset)
    hosts = queryset.get_hosts()
    lock = hosts.filter(disabled=False).get_lock()

    # group sessions by hosts
    session_groups = dict()
    for minkeobj in queryset.all():
        host = minkeobj.get_host()

        session = SessionData()
        session.init(user, minkeobj, session_cls, session_data)

        # Skip disabled or locked hosts...
        if host.disabled or host.lock and host.lock != lock:
            msg = '{}: Host is disabled.'.format(minkeobj)
            session.messages.add(Message(msg, 'error'), bulk=False)
            session.end()
            if console: Printer.prnt(session)
        elif host.lock and host.lock != lock:
            msg = '{}: Host is locked.'.format(minkeobj)
            session.messages.add(Message(msg, 'error'), bulk=False)
            session.end()
            if console: Printer.prnt(session)

        # otherwise group sessions by hosts...
        else:
            if not session_groups.has_key(host):
                session_groups[host] = list()
            session_groups[host].append(session)

    # Stop here if no valid hosts are left...
    if not session_groups: return

    # merge fabric-config and invoke-config
    config = session_cls.INVOKE_CONFIG.copy()
    config.update(fabric_config or dict())

    # run celery-tasks to process the sessions...
    results = list()
    for host, sessions in session_groups.items():
        try:
            # FIXME: celery-4.2.1 fails to raise an exception if rabbitmq is
            # down or no celery-worker is running at all... hope for 4.3.x
            session_ids = [s.id for s in sessions]
            result = process_sessions.delay(host.id, session_ids, config)
            results.append((result, [s.id for s in sessions]))
        except process_sessions.OperationalError:
            host.lock = None
            host.save(update_fields=['lock'])
            for session in sessions:
                msg = 'Could not process session.'
                session.add_msg(ExceptionMessage())
                session.end()
                if console: Printer.prnt(session)


    # print sessions in cli-mode as soon as they are ready...
    if console:
        print_results = results[:]
        while print_results:
            # try to find a ready result...
            try: result, session_ids = next((r for r in print_results if r[0].ready()))
            except StopIteration: continue
            # reload session-objects
            sessions = SessionData.objects.filter(id__in=session_ids)
            # print and remove list-item
            for session in sessions: Printer.prnt(session)
            print_results.remove((result, session_ids))

    # evt. wait till all tasks finished...
    elif wait:
        for result, sessions in results:
            result.wait()

    # At least call forget on every result - in case a result-backend is in use
    # that eats up ressources to store result-data...
    for result, sessions in results:
        try: result.forget()
        except NotImplementedError: pass
