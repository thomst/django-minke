# -*- coding: utf-8 -*-

import os
import logging
import signal

from socket import error as SocketError
from socket import gaierror as GaiError
from paramiko.ssh_exception import SSHException
from fabric2 import Connection
from invoke.exceptions import Failure
from invoke.exceptions import ThreadException
from invoke.exceptions import UnexpectedExit
from celery import shared_task
from django.contrib.contenttypes.models import ContentType

from . import settings
from .models import Host
from .models import MinkeSession
from .sessions import REGISTRY
from .messages import Message
from .messages import ExceptionMessage
from .settings import MINKE_FABRIC_CONFIG
from .exceptions import TaskInterruption


logger = logging.getLogger(__name__)


class SessionProcessor:
    """
    Process sessions.
    """
    def __init__(self, host_id, session_ids, fabric_config):
        self.host = Host.objects.get(pk=host_id)
        config = MINKE_FABRIC_CONFIG.clone()
        config.load_snakeconfig(fabric_config or dict())
        hostname = self.host.hostname or self.host.name
        self.con = Connection(hostname, self.host.username, config=config)

        REGISTRY.reload()
        minke_sessions = MinkeSession.objects.filter(id__in=session_ids)
        session_cls = REGISTRY[minke_sessions[0].session_name]
        self.sessions = [session_cls(self.con, ms) for ms in minke_sessions]

        signal.signal(signal.SIGTERM, self.interrupt)

    def interrupt(self, signum, frame):
        for session in self.sessions: session.cancel()
        raise TaskInterruption

    def process_session(self, session):
        try:
            session.start()
            session.process()

        # paramiko- and socket-related exceptions (ssh-layer)
        except (SSHException, GaiError, SocketError):
            session.add_msg(ExceptionMessage())
            session.end('failed')

        # invoke-related exceptions (shell-layer)
        except (Failure, ThreadException, UnexpectedExit):
            session.add_msg(ExceptionMessage())
            session.end('failed')

        # task-interruption
        except TaskInterruption:
            session.end('stopped')
            raise TaskInterruption

        # other exceptions
        except Exception:
            exc_msg = ExceptionMessage(print_tb=True)
            logger.error(exc_msg.text)
            if settings.MINKE_DEBUG: session.add_msg(exc_msg)
            else: session.add_msg(Message('An error occurred.', 'error'))
            session.end('failed')

        # success
        else:
            session.set_status(session.status or 'success')
            session.end()

    def __call__(self):
        try:
            for session in self.sessions:
                self.process_session(session)
        except TaskInterruption:
            pass
        finally:
            self.con.close()
            self.host.lock = None
            self.host.save(update_fields=['lock'])

@shared_task
def process_sessions(host_id, session_ids, fabric_config=None):
    processor = SessionProcessor(host_id, session_ids, fabric_config)
    processor()
