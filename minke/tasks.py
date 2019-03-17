# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import logging, os

from django.contrib.contenttypes.models import ContentType

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
from .models import SessionData
from .messages import Message
from .messages import ExceptionMessage
from .settings import MINKE_FABRIC_CONFIG


logger = logging.getLogger(__name__)


@shared_task
def process_sessions(host_id, session_ids, fabric_config=None):

    # get host and sessions
    host = Host.objects.get(pk=host_id)
    sessions = SessionData.objects.filter(id__in=session_ids)

    # prepare the config and create a connection...
    config = MINKE_FABRIC_CONFIG.clone()
    config.load_snakeconfig(fabric_config or dict())
    config.connect_kwargs.hostname = host.hostname
    config.connect_kwargs.username = host.username
    con = Connection(host.name, config=config)

    # process the sessions...
    for session in sessions:
        session.start(con)
        try: session.proxy.process()

        # paramiko- and socket-related exceptions (ssh-layer)
        except (SSHException, GaiError, SocketError):
            session.session_status = 'error'
            session.messages.add(ExceptionMessage(), bulk=False)

        # invoke-related exceptions (shell-layer)
        except (Failure, ThreadException, UnexpectedExit):
            session.session_status = 'error'
            session.messages.add(ExceptionMessage(), bulk=False)

        # other exceptions
        except Exception:
            session.session_status = 'error'
            exc_msg = ExceptionMessage(print_tb=True)
            logger.error(exc_msg.text)
            if settings.MINKE_DEBUG:
                session.messages.add(exc_msg, bulk=False)
            else:
                msg = 'An error occurred.'
                session.messages.add(Message(msg, 'error'), bulk=False)

        finally:
            session.end()

    # to be explicit - close connection...
    con.close()

    # release the lock
    host.lock = None
    host.save(update_fields=['lock'])
