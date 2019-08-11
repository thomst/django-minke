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
from .settings import MINKE_HOST_CONFIG
from .settings import MINKE_FABRIC_CONFIG


logger = logging.getLogger(__name__)


class SessionProcessor:
    """
    Process sessions.
    """
    def __init__(self, host_id, session_id, session_config):
        host = Host.objects.select_related('group').get(pk=host_id)
        hostname = host.hostname or host.name
        config = MINKE_FABRIC_CONFIG.clone()
        self.host = host

        # At first try to load the hostgroup- and host-config...
        for obj in (host.group, host):
            if not obj or not obj.config: continue
            if obj.config in MINKE_HOST_CONFIG:
                config.load_snakeconfig(MINKE_HOST_CONFIG[obj.config])
            else:
                msg = 'Invalid MINKE_HOST_CONFIG for {}'.format(obj)
                logger.warning(msg)

        # At least load the session-config...
        config.load_snakeconfig(session_config or dict())

        # Initialize the connection...
        self.con = Connection(hostname, host.username, host.port, config=config)

        # Initialize the session...
        self.minke_session = MinkeSession.objects.get(pk=session_id)
        REGISTRY.reload(self.minke_session.session_name)
        session_cls = REGISTRY[self.minke_session.session_name]
        self.session = session_cls(self.con, self.minke_session)

    def interrupt(self, signum, frame):
        # only stop a running session.
        if self.minke_session.is_running:
            self.session.cancel()

    def run(self):
        try:
            started = self.session.start()
            if not started: return

            try:
                self.session.process()

            # Since task-interruption could happen all along between
            # session.start() and session.end() we handle it in the outer
            # try-construct.
            except KeyboardInterrupt:
                raise

            # paramiko- and socket-related exceptions (ssh-layer)
            except (SSHException, GaiError, SocketError):
                self.session.end(failure=True)
                self.session.add_msg(ExceptionMessage())

            # invoke-related exceptions (shell-layer)
            except (Failure, ThreadException, UnexpectedExit):
                self.session.end(failure=True)
                self.session.add_msg(ExceptionMessage())

            # other exceptions raised by process (which is user-code)
            except Exception:
                self.session.end(failure=True)
                exc_msg = ExceptionMessage(print_tb=True)
                logger.error(exc_msg.text)
                if settings.MINKE_DEBUG: self.session.add_msg(exc_msg)
                else: self.session.add_msg('An error occurred.', 'error')

            else:
                self.session.end()

        # task-interruption
        except KeyboardInterrupt:
            self.session.end()

        # at least close the ssh-connection
        finally:
            self.con.close()


@shared_task(bind=True)
def process_session(task, host_id, session_id, config):
    """
    Task for session-processing.
    """
    processor = SessionProcessor(host_id, session_id, config)
    signal.signal(signal.SIGUSR1, processor.interrupt)
    processor.run()

@shared_task
def cleanup(host_id):
    """
    Task to release the host's lock.
    """
    Host.objects.get(pk=host_id).release_lock()
