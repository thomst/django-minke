# -*- coding: utf-8 -*-

from celery import chain
from celery import group

from .messages import Message
from .messages import ExceptionMessage
from .models import MinkeSession
from .tasks import process_session
from .tasks import cleanup


def process(session_cls, queryset, user, runtime_data=None, wait=False, console=False):
    """
    Initiate and run celery-tasks.
    """
    # TODO: Add a MinkeSession lock. To lock the host should be optional.
    MinkeSession.objects.clear_currents(user, queryset)
    hosts = queryset.get_hosts()
    lock = hosts.filter(disabled=False).get_lock()

    # group sessions by hosts
    session_groups = dict()
    for minkeobj in queryset.select_related_hosts():
        host = minkeobj.get_host()

        session = MinkeSession()
        session.init(user, minkeobj, session_cls)

        # Skip disabled or locked hosts...
        if host.disabled:
            msg = f'{minkeobj}: Host is disabled.'
            session.messages.add(Message(msg, 'error'), bulk=False)
            session.cancel()
            if console:
                session.prnt()
        elif host.lock and host.lock != lock:
            msg = f'{minkeobj}: Host is locked.'
            session.messages.add(Message(msg, 'error'), bulk=False)
            session.cancel()
            if console:
                session.prnt()

        # otherwise group sessions by hosts...
        else:
            if host not in session_groups:
                session_groups[host] = list()
            session_groups[host].append(session)

    # Stop here if no valid hosts are left...
    if not session_groups:
        return


    # run celery-tasks...
    results = list()
    for host, sessions in session_groups.items():

        # get process_session_signatures for all sessions
        signatures = [process_session.si(host.id, s.id, runtime_data) for s in sessions]

        # To support parrallel execution per host we wrap the signatures in a group.
        # NOTE: Since we append the cleanup-task the construct is essentially the
        # same as a chord which is not supported by all result-backends (s. celery-docs).
        if session_cls.parrallel_per_host:
            signatures = [group(*signatures)]

        # append the cleanup-task
        signatures.append(cleanup.si(host.id))

        try:
            result = chain(*signatures).delay()

        # NOTE: celery-4.2.1 fails to raise an exception if rabbitmq is
        # down or no celery-worker is running at all... hope for 4.3.x
        except process_session.OperationalError:
            host.release_lock()
            for session in sessions:
                session.add_msg(ExceptionMessage())
                session.cancel()
                if console: session.prnt(session)

        else:
            results.append((result, (s.id for s in sessions)))


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
