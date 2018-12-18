# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from fabric.api import run

from minke import register
from minke.models import Host
from minke.sessions import Session
from minke.sessions import UpdateEntriesSession
from minke.messages import Message
from minke.messages import ExecutionMessage
from minke.messages import PreMessage
from minke.messages import TableMessage

from .models import Server
from .models import AnySystem
from .forms import TestForm


@register((Host, Server, AnySystem), 'Do nothing.')
class DummySession(Session):
    def process(self):
        pass


@register(Server, 'Do nothing (one-model-session).')
class SingleModelDummySession(Session):
    def process(self):
        pass


@register(Server, 'Echo unicode-literals.')
class EchoUnicodeSession(Session):
    def process(self):
        cmd = 'echo "¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ"'
        result = self.run(self.format_cmd(cmd))
        self.news.append(ExecutionMessage(result))


@register(Server, 'Update hostname.')
class TestUpdateEntriesSession(UpdateEntriesSession):
    def process(self):
        self.update_field('hostname', 'hostname', '^[a-z0-9._-]+$')


@register((Host, Server, AnySystem), 'Test the session form.')
class TestFormSession(Session):
    FORM = TestForm

    def process(self):
        one = self.session_data['one']
        two = self.session_data['two']
        msg = '{:d} + {:d} = {:d}'.format(one, two, one + two)
        self.news.append(Message(msg, 'WARNING'))


@register((Host, Server, AnySystem), 'Leave a message.')
class LeaveAMessageSession(Session):
    MSG = '¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ'
    def process(self):
        self.news.append(Message(self.MSG, 'info'))


class MethodTestSession(UpdateEntriesSession):
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

    def test_unicode_result_replace(self):
        return self.run('(echo "hällo"; echo "wörld" 1>&2)', 'ascii')
