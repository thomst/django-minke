# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from minke.models import Host
from minke.sessions import Session
from minke.sessions import SingleActionSession
from minke.sessions import UpdateEntriesSession
from minke.messages import Message
from minke.messages import ExecutionMessage
from minke.messages import PreMessage
from minke.messages import TableMessage

from .models import Server
from .models import AnySystem
from .forms import TestForm


class DummySession(Session):
    VERBOSE_NAME = 'Do nothing'
    WORK_ON = (Host, Server, AnySystem)

    def process(self):
        pass


class SingleModelDummySession(Session):
    VERBOSE_NAME = 'Do nothing (one-model-session).'
    WORK_ON = (Server,)

    def process(self):
        pass


class ExceptionSession(Session):
    VERBOSE_NAME = 'Raise an exception.'
    WORK_ON = (Host, Server, AnySystem)

    ERR_MSG = '¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ'.encode('utf-8')
    def process(self):
        raise Exception(str('process: ') + self.ERR_MSG)


class SingleActionDummySession(SingleActionSession):
    VERBOSE_NAME = 'Single-action-session.'
    WORK_ON = (Host, Server, AnySystem)
    COMMAND = None


class EchoUnicodeSession(Session):
    VERBOSE_NAME = 'Echo unicode-literals.'
    WORK_ON = (Server,)

    def process(self):
        cmd = 'echo "¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ"'
        result = self.run(self.format_cmd(cmd))
        self.add_msg(ExecutionMessage(result))


class TestUpdateEntriesSession(UpdateEntriesSession):
    VERBOSE_NAME = 'Update hostname.'
    WORK_ON = (Server,)

    def process(self):
        self.update_field('hostname', 'hostname', '^[a-z0-9._-]+$')


class TestFormSession(Session):
    VERBOSE_NAME = 'Test the session form.'
    WORK_ON = (Host, Server, AnySystem)
    FORM = TestForm

    def process(self):
        one = self.session_data['one']
        two = self.session_data['two']
        msg = '{:d} + {:d} = {:d}'.format(one, two, one + two)
        self.add_msg(Message(msg, 'WARNING'))


class LeaveAMessageSession(Session):
    VERBOSE_NAME = 'Leave a message.'
    WORK_ON = (Host, Server, AnySystem)

    MSG = '¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ'
    def process(self):
        self.add_msg(Message(self.MSG, 'info'))


class MethodTestSession(UpdateEntriesSession):
    VERBOSE_NAME = 'Test session-methods'
    WORK_ON = (Host, Server, AnySystem)

    def process(self):
        return getattr(self, 'test_' + self.session_data['test'])()

    def test_execute(self):
        # execute-calls: valid, valid + stderr, invalid
        self.execute('echo "hello wörld"')
        self.execute('echo "hello wörld" 1>&2')
        self.execute('[ 1 == 2 ]')
        return self

    def test_update(self):
        self.update_field('hostname', 'echo "foobär"')
        return self

    def test_update_regex(self):
        self.update_field('hostname', 'echo "foobär"', '(foo).+')
        return self

    def test_update_regex_fails(self):
        self.update_field('hostname', 'echo "foobär"', 'fails')
        return self

    def test_unicode_result(self):
        return self.run('(echo "hällo"; echo "wörld" 1>&2)')
