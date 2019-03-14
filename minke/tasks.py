# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import logging, os

from socket import error as SocketError
from socket import gaierror as GaiError
from paramiko.ssh_exception import SSHException
from invoke.exceptions import Failure
from invoke.exceptions import ThreadException
from invoke.exceptions import UnexpectedExit
from celery import shared_task
from fabric2 import Connection

from minke import settings
from .models import Host
from .models import BaseSession
from .messages import Message
from .messages import ExceptionMessage
from .settings import MINKE_FABRIC_CONFIG


logger = logging.getLogger(__name__)


@shared_task
def process_sessions(host, sessions, fabric_config=None):

    # prepare the config and create a connection...
    config = MINKE_FABRIC_CONFIG.clone()
    config.load_snakeconfig(fabric_config or dict())
    con = Connection(
        host.hostname or host.host,
        user=host.user,
        port=host.port,
        config=config)

    # process the sessions...
    for session in sessions:
        session.initialize(con)

        try: session.process()

        # paramiko- and socket-related exceptions (ssh-layer)
        except (SSHException, GaiError, SocketError):
            session.status = 'error'
            session.add_msg(ExceptionMessage())

        # invoke-related exceptions (shell-layer)
        except (Failure, ThreadException, UnexpectedExit):
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

    # to be explicit - close connection...
    con.close()

    # release the lock
    host.locked = None
    host.save(update_fields=['locked'])
