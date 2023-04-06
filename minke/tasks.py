# -*- coding: utf-8 -*-

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

from . import settings
from .models import Host
from .models import MinkeSession
from .exceptions import SessionError
from .sessions import REGISTRY
from .messages import ExceptionMessage
from .fabrictools import FabricConfig


logger = logging.getLogger(__name__)


class SessionProcessor:
    """
    Process sessions.
    """
    def __init__(self, host_id, session_id, runtime_data):
        minke_session = MinkeSession.objects.get(pk=session_id)
        REGISTRY.reload(minke_session.session_name)
        session_cls = REGISTRY[minke_session.session_name]
        host = Host.objects.get(pk=host_id)
        hostname = host.hostname or host.name
        config = FabricConfig(host, session_cls, runtime_data)
        self.con = Connection(hostname, host.username, host.port, config=config)
        self.session = session_cls(self.con, minke_session)

    def run(self):
        """
        Run the task.
        """
        try:
            started = self.session.start()
            if not started:
                return

            try:
                self.session.process()

            # A SessionError might be raised by from the process method of a
            # session itself. It is a convenient way to end a session with an
            # error status.
            except SessionError as exc:
                self.session.set_status('error')
                for msg in exc.args:
                    self.session.add_msg(msg, 'error')
                self.session.end()

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
                if settings.MINKE_DEBUG:
                    self.session.add_msg(exc_msg)
                else:
                    # TODO: relegate to the log.
                    self.session.add_msg('An error occurred.', 'error')

            else:
                self.session.end()

        # Since task-interruption could happen all along between session.start()
        # and session.end() we handle it in the outer try-construct.
        except KeyboardInterrupt:
            self.session.end()

        # at least close the ssh-connection
        finally:
            self.con.close()


@shared_task(bind=True)
def process_session(task, host_id, session_id, runtime_data):
    """
    Task for session-processing.
    """
    processor = SessionProcessor(host_id, session_id, runtime_data)
    signal.signal(signal.SIGUSR1, processor.session.stop)
    processor.run()

@shared_task
def cleanup(host_id):
    """
    Task to release the host's lock.
    """
    Host.objects.get(pk=host_id).release_lock()
