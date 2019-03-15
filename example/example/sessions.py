# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from time import sleep
from random import randint, choice

from minke.models import Host
from minke.sessions import register
from minke.sessions import Session
from minke.sessions import SingleActionSession
from minke.sessions import UpdateEntriesSession
from minke.messages import Message
from minke.messages import ExecutionMessage
from minke.messages import PreMessage
from minke.messages import TableMessage

from .models import Server
from .models import AnySystem


@register(create_permission=True)
class ThisAndThat(Session):
    """
    A session like no other ;-)
    """
    VERBOSE_NAME = 'This and that'
    WORK_ON = (Host, Server, AnySystem)
    CONFIRM = True
    WAIT = False

    def process(self):
        # r = self.run('echo ehllo')
        # self.add_msg(ExecutionMessage(r))

        sec = randint(0, 4)
        sleep(sec)

        self.set_status(choice(['success', 'warning', 'error']))
        level = 'info' if self.status == 'success' else self.status

        msg = '{}: Waited {} sec.\n\nWhile you were sleeping...'
        self.add_msg(PreMessage(msg.format(self.player, sec), level))
