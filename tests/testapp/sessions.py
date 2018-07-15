
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


@register(Server, 'Update hostname.', create_permission=True)
class TestUpdateEntriesSession(UpdateEntriesSession):
    def process(self):
        self.update_field('hostname', 'hostname', '^[a-z0-9._-]+$')


@register((Host, Server, AnySystem), 'Test the session form.', create_permission=True)
class TestFormSession(Session):
    FORM = TestForm

    def process(self):
        one = self.session_data['one']
        two = self.session_data['two']
        msg = '{:d} + {:d} = {:d}'.format(one, two, one + two)
        self.news.append(Message(msg, 'WARNING'))
