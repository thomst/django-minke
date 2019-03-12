# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import logging

from celery import shared_task
from fabric2 import Connection

from .models import Host
from .models import BaseSession
from .messages import Message
from .messages import ExceptionMessage
from socket import error as SocketError
from socket import gaierror as GaiError


logger = logging.getLogger(__name__)


@shared_task
def process_sessions(host, sessions):

    # TODO: use a default-port on model-basis
    # FIXME: Is there a timeout-option?
    con = Connection(user=host.user, host=host.hostname, port=host.port or 22)

    for session in sessions:
        session.initialize(con)

        try:
            session.process()

        # connection-related exceptions
        # FIXME: Exceptions could be invoke-, fabric-, paramiko-, socket-
        # or session-related. Research is needed...
        except (GaiError, SocketError):
            session.status = 'error'
            session.add_msg(ExceptionMessage())

        # other exceptions
        except Exception:
            session.status = 'error'
            exc_msg = ExceptionMessage(print_tb=True)
            logger.error(exc_msg.text)
            if settings.MINKE_DEBUG:
                session.add_msg(exc_msg)
            else:
                msg = 'An error occurred.'
                session.add_msg(Message(msg, 'error'))

        finally:

            # FIXME: with celery it should be possible accessing the database
            # within the process-method. rework should be superfluseous.
            # session's rework
            try:
                session.rework()
            except Exception as err:
                session.status = 'error'
                exc_msg = ExceptionMessage(print_tb=True)
                logger.error(exc_msg.text)
                if settings.MINKE_DEBUG:
                    session.add_msg(exc_msg)
                else:
                    msg = 'An error occurred.'
                    session.add_msg(Message(msg, 'error'))

            # update session-data
            session.proc_status = 'done'
            session.status = session.status or 'success'
            session.save(update_fields=['status', 'proc_status'])

            # TODO: the news-attr should not be used to store messages anymore.
            # Messages should be stored with add_msg().
            for message in session.news:
                session.add_msg(message)

    # release the lock
    host.locked = None
    host.save(update_fields=['locked'])

    # fabric-stuff cannot be pickled. So we just return the BaseSession-instance.
    return [BaseSession.objects.get(pk=s.pk) for s in sessions]
