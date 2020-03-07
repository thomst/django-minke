# -*- coding: utf-8 -*-

import re
from django.dispatch import receiver

from minke.sessions import CommandFormSession
from minke.sessions import SingleCommandSession
from minke.sessions import CommandChainSession
from minke.sessions import REGISTRY
from .forms import CommandForm


class BaseCommandSession(SingleCommandSession):
    abstract = True
    model = None
    model_id = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.model.objects.get(pk=self.model_id)
        self.command = obj.cmd


class BaseCommandChainSession(CommandChainSession):
    abstract = True
    model = None
    model_id = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.model.objects.get(pk=self.model_id)
        self.commands = (c.cmd for c in obj.commands.all())


class BaseCommandChoiceSession(CommandFormSession):
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


@receiver(REGISTRY.reload_sessions)
def session_factory(sender, **kwargs):

    # FIXME: Prevent those inline-imports!
    from .models import Command
    from .models import CommandGroup

    # do we have a session-name and does it match our regex?
    session_name = kwargs.get('session_name', None)
    pattern = r'^(Command|CommandGroup)_(\d+)'
    match = re.match(pattern, session_name or '')

    # if we have no session-name, register all command-sessions
    if not session_name:
        for obj in Command.objects.filter(active=True):
            session = obj.as_session()
            session.register()
            session.add_permission()
            session.create_permission()

        for obj in CommandGroup.objects.filter(active=True):
            session = obj.as_session()
            session.register()
            session.add_permission()
            session.create_permission()

    # if we have a session-name that matches, register this session only
    elif match:
        clsname, id = match.groups()
        cls = Command if clsname == 'Command' else CommandGroup
        cmd = cls.objects.get(pk=id)
        session = cmd.as_session()
        session.register()
        session.add_permission()
        session.create_permission()
