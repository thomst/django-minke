# -*- coding: utf-8 -*-

from minke.models import Host
from minke.sessions import Session
from minke.sessions import SingleCommandSession
from minke.sessions import CommandChainSession
from minke.sessions import SessionChain
from minke.messages import Message
from minke.messages import ExecutionMessage
from minke.messages import PreMessage
from minke.messages import TableMessage

from .models import Server
from .models import AnySystem
from .forms import TestForm


class DummySession(Session):
    verbose_name = 'Do nothing'
    work_on = (Host, Server, AnySystem)

    def process(self):
        pass


class SingleModelDummySession(Session):
    verbose_name = 'Do nothing (one-model-session).'
    work_on = (Server,)

    def process(self):
        pass


class ExceptionSession(Session):
    verbose_name = 'Raise an exception.'
    work_on = (Host, Server, AnySystem)

    ERR_MSG = '¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ'
    def process(self):
        raise Exception(self.ERR_MSG)


class SingleActionDummySession(SingleCommandSession):
    verbose_name = 'Single-action-session.'
    work_on = (Host, Server, AnySystem)
    command = True


class EchoUnicodeSession(Session):
    verbose_name = 'Echo unicode-literals.'
    work_on = (Server,)

    def process(self):
        cmd = 'echo "¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ"'
        result = self.run(self.format_cmd(cmd))
        self.add_msg(ExecutionMessage(result))


class TestUpdateFieldSession(Session):
    verbose_name = 'Update hostname.'
    work_on = (Server,)

    def process(self):
        self.update_field('hostname', 'hostname', '^[a-z0-9._-]+$')


class TestFormSession(Session):
    verbose_name = 'Test the session form.'
    work_on = (Host, Server, AnySystem)
    form = TestForm

    def process(self):
        one = self.data['one']
        two = self.data['two']
        msg = '{:d} + {:d} = {:d}'.format(one, two, one + two)
        self.add_msg(Message(msg, 'WARNING'))


class LeaveAMessageSession(Session):
    verbose_name = 'Leave a message.'
    work_on = (Host, Server, AnySystem)

    MSG = '¡ ¢ £ ¤ ¥ ¦ § ¨ © ª « ¬ ­ ® ¯ ° ± ² ³ ´ µ'
    def process(self):
        self.add_msg(Message(self.MSG, 'info'))


class MethodTestSession(Session):
    verbose_name = 'Test session-methods'
    work_on = (Host, Server, AnySystem)

    def process(self):
        return getattr(self, 'test_' + self.data['test'])()

    def test_execute(self):
        # execute-calls: valid, valid + stderr, invalid
        self.xrun('echo "hello wörld"')
        self.xrun('echo "hello wörld" 1>&2')
        self.xrun('[ 1 == 2 ]')
        return self

    def test_unicode_result(self):
        return self.run('(echo "hällo"; echo "wörld" 1>&2)')

    def test_update(self):
        self.update_field('hostname', 'echo "foobär"')
        self.minkeobj.save()
        return self

    def test_update_regex(self):
        self.update_field('hostname', 'echo "foobär"', '(foo).+')
        self.minkeobj.save()
        return self

    def test_update_regex_fails(self):
        self.update_field('hostname', 'echo "foobär"', 'fails')
        self.minkeobj.save()
        return self


class RunCommands(CommandChainSession):
    work_on = (Host, Server, AnySystem)
    commands = (
        'echo "hello wörld"',
        'echo "hello wörld" 1>&2',
        '[ 1 == 2 ]')


class InfoCommand(SingleCommandSession):
    work_on = (Host, Server, AnySystem)
    command = 'echo "hello wörld"'


class WarningCommand(SingleCommandSession):
    work_on = (Host, Server, AnySystem)
    command = 'echo "hello wörld" 1>&2'


class ErrorCommand(SingleCommandSession):
    work_on = (Host, Server, AnySystem)
    command = '[ 1 == 2 ]'


class RunSessions(SessionChain):
    work_on = (Host, Server, AnySystem)
    sessions = (InfoCommand, WarningCommand, ErrorCommand)
