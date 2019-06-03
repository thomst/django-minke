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
    def __init__(self, host_id, session_id, fabric_config, task_id, cleanup):
        self.task_id = task_id
        self.cleanup = cleanup
        self.host = Host.objects.get(pk=host_id)

        config = MINKE_FABRIC_CONFIG.clone()
        config.load_snakeconfig(fabric_config or dict())
        hostname = self.host.hostname or self.host.name
        self.con = Connection(hostname, self.host.username, config=config)

        REGISTRY.reload()
        self.minke_session = MinkeSession.objects.get(pk=session_id)
        session_cls = REGISTRY[self.minke_session.session_name]
        self.session = session_cls(self.con, self.minke_session)

    def interrupt(self, signum, frame):
        if self.minke_session.is_running:
            raise TaskInterruption

    def run(self):
        try:
            started = self.session.start(self.task_id)
            if not started: return

            try:
                self.session.process()

            # Since task-interruption could happen all along between
            # session.start() and session.end() we handle it in the outer
            # try-construct.
            except TaskInterruption:
                raise

            # paramiko- and socket-related exceptions (ssh-layer)
            except (SSHException, GaiError, SocketError):
                self.session.fail()
                self.session.add_msg(ExceptionMessage())

            # invoke-related exceptions (shell-layer)
            except (Failure, ThreadException, UnexpectedExit):
                self.session.fail()
                self.session.add_msg(ExceptionMessage())

            # other exceptions raised by process (which is user-code)
            except Exception:
                self.session.fail()
                exc_msg = ExceptionMessage(print_tb=True)
                logger.error(exc_msg.text)
                if settings.MINKE_DEBUG: self.session.add_msg(exc_msg)
                else: self.session.add_msg(Message('An error occurred.', 'error'))

            else:
                self.session.end()

        # task-interruption
        except TaskInterruption:
            self.session.end()

        # cleanup
        finally:
            self.con.close()
            if self.cleanup:
                self.host.release_lock()


@shared_task(bind=True)
def process_session(self, host_id, session_id, config, cleanup=False):
    task_id = self.request.id
    processor = SessionProcessor(host_id, session_id, config, task_id, cleanup)
    signal.signal(signal.SIGUSR1, processor.interrupt)
    processor.run()
