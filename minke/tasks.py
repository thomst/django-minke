# -*- coding: utf-8 -*-

import logging
import os

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


logger = logging.getLogger(__name__)


@shared_task
def process_sessions(host_id, session_ids, fabric_config=None):

    # get host and sessions
    host = Host.objects.get(pk=host_id)
    minke_sessions = MinkeSession.objects.filter(id__in=session_ids)

    # prepare the config and create a connection...
    config = MINKE_FABRIC_CONFIG.clone()
    config.load_snakeconfig(fabric_config or dict())
    hostname = host.hostname or host.name
    con = Connection(hostname, host.username, config=config)
    REGISTRY.reload()

    # process the sessions...
    for minke_session in minke_sessions:
        session_cls = REGISTRY[minke_session.session_name]
        session = session_cls(con, minke_session)
        session.start()

        try: session.process()

        # paramiko- and socket-related exceptions (ssh-layer)
        except (SSHException, GaiError, SocketError):
            session.add_msg(ExceptionMessage())
            session.end('failed')

        # invoke-related exceptions (shell-layer)
        except (Failure, ThreadException, UnexpectedExit):
            session.add_msg(ExceptionMessage())
            session.end('failed')

        # other exceptions
        except Exception:
            exc_msg = ExceptionMessage(print_tb=True)
            logger.error(exc_msg.text)
            if settings.MINKE_DEBUG: session.add_msg(exc_msg)
            else: session.add_msg(Message('An error occurred.', 'error'))
            session.end('failed')

        # success
        else:
            session.end()

    # to be explicit - close connection...
    con.close()

    # release host's lock
    host.lock = None
    host.save(update_fields=['lock'])
