# -*- coding: utf-8 -*-

from django.contrib.contenttypes.models import ContentType
from minke.sessions import CommandFormSession
from minke.sessions import SingleCommandSession
from minke.sessions import CommandChainSession
from minke.sessions import SessionRegistration
from minke.sessions import REGISTRY
from minke.models import Host
from .forms import CommandForm


class BaseCommandSession(SingleCommandSession):
    add_permission = False
    abstract = True
    model = None
    model_id = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.model.objects.get(pk=self.model_id)
        self.command = obj.cmd


class BaseCommandChainSession(CommandChainSession):
    add_permission = False
    abstract = True
    model = None
    model_id = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.model.objects.get(pk=self.model_id)
        self.commands = (c.cmd for c in obj.commands.all())


class BaseCommandChoiceSession(CommandFormSession):
    add_permission = False
    abstract = True
    model = None
    model_id = None
    form = CommandForm

    @classmethod
    def get_form(cls):
        obj = cls.model.objects.get(pk=cls.model_id)
        choices = ((c.id, str(c)) for c in obj.commands.all())
        cls.form.base_fields['cmd'].choices = choices
        return cls.form

    def format_cmd(self, cmd):
        cmd_obj = self.model.commands.get(pk=self.data['cmd'])
        return super().format_cmd(cmd_obj.cmd)


def session_factory():
    from .models import Command
    from .models import CommandGroup
    for obj in Command.objects.filter(active=True):
        session = obj.as_session()
        session.register()

    for obj in CommandGroup.objects.filter(active=True):
        session = obj.as_session()
        session.register()


REGISTRY.add_session_factory(session_factory)
