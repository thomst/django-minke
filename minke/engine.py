# -*- coding: utf-8 -*-

from celery import chain

import minke.sessions
from .messages import Message
from .messages import ExceptionMessage
from .models import MinkeSession
from .tasks import process_session


def process(session_cls, queryset, session_data, user,
            fabric_config=None, wait=False, console=False):
    """Initiate fabric's session-processing."""

    MinkeSession.objects.clear_currents(user, queryset)
    hosts = queryset.get_hosts()
    lock = hosts.filter(disabled=False).get_lock()

    # group sessions by hosts
    session_groups = dict()
    for minkeobj in queryset.all():
        host = minkeobj.get_host()

        session = MinkeSession()
        session.init(user, minkeobj, session_cls, session_data)

        # Skip disabled or locked hosts...
        if host.disabled:
            msg = '{}: Host is disabled.'.format(minkeobj)
            session.messages.add(Message(msg, 'error'), bulk=False)
            session.cancel()
            if console: session.prnt()
        elif host.lock and host.lock != lock:
            msg = '{}: Host is locked.'.format(minkeobj)
            session.messages.add(Message(msg, 'error'), bulk=False)
            session.cancel()
            if console: session.prnt()

        # otherwise group sessions by hosts...
        else:
            if host not in session_groups:
                session_groups[host] = list()
            session_groups[host].append(session)

    # Stop here if no valid hosts are left...
    if not session_groups: return

    # merge fabric-config and invoke-config
    config = session_cls.invoke_config.copy()
    config.update(fabric_config or dict())

    # run celery-tasks to process the sessions...
    results = list()
    for host, sessions in session_groups.items():
        session_chain = [process_session.si(host.id, s.id, config) for s in sessions[:-1]]
        session_chain.append(process_session.si(host.id, sessions[-1].id, config, True))
        try:
            result = chain(*session_chain).delay()
            results.append((result, [s.id for s in sessions]))

        # FIXME: celery-4.2.1 fails to raise an exception if rabbitmq is
        # down or no celery-worker is running at all... hope for 4.3.x
        except process_session.OperationalError:
            host.release_lock()
            for session in sessions:
                msg = 'Could not process session.'
                session.add_msg(ExceptionMessage())
                session.end('failed')
                if console: session.prnt(session)


    # print sessions in cli-mode as soon as they are ready...
    if console:
        print_results = results[:]
        while print_results:
            # try to find a ready result...
            try: result, session_ids = next((r for r in print_results if r[0].ready()))
            except StopIteration: continue
            # reload session-objects
            sessions = MinkeSession.objects.filter(id__in=session_ids)
            # print and remove list-item
            for session in sessions: session.prnt()
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
