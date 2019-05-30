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
    def __init__(self, host_id, session_id, fabric_config, task_id):
        self.host = Host.objects.get(pk=host_id)
        config = MINKE_FABRIC_CONFIG.clone()
        config.load_snakeconfig(fabric_config or dict())
        hostname = self.host.hostname or self.host.name
        self.con = Connection(hostname, self.host.username, config=config)

        REGISTRY.reload()
        self.minke_session = MinkeSession.objects.get(pk=session_id)
        self.minke_session.track(task_id)
        session_cls = REGISTRY[self.minke_session.session_name]
        self.session = session_cls(self.con, self.minke_session)

    def interrupt(self, signum, frame):
        self.minke_session.cancel()
        raise TaskInterruption

    def run(self):
        if self.minke_session.is_done:
            return
        try:
            self.session.start()
            self.session.process()

        # paramiko- and socket-related exceptions (ssh-layer)
        except (SSHException, GaiError, SocketError):
            self.session.add_msg(ExceptionMessage())
            self.session.end('failed')

        # invoke-related exceptions (shell-layer)
        except (Failure, ThreadException, UnexpectedExit):
            self.session.add_msg(ExceptionMessage())
            self.session.end('failed')

        # task-interruption
        except TaskInterruption:
            self.session.end('stopped')

        # other exceptions
        except Exception:
            exc_msg = ExceptionMessage(print_tb=True)
            logger.error(exc_msg.text)
            if settings.MINKE_DEBUG: self.session.add_msg(exc_msg)
            else: self.session.add_msg(Message('An error occurred.', 'error'))
            self.session.end('failed')

        # success
        else:
            self.session.set_status(self.session.status or 'success')
            self.session.end()


@shared_task(bind=True)
def process_session(self, host_id, session_id, fabric_config, cleanup=False):
    task_id = self.request.id
    processor = SessionProcessor(host_id, session_id, fabric_config, task_id)
    signal.signal(signal.SIGUSR1, processor.interrupt)

    try:
        processor.run()
    except TaskInterruption:
        pass
    finally:
        processor.con.close()
        if cleanup:
            processor.host.release_lock()
