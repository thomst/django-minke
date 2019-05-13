# -*- coding: utf-8 -*-

from django.contrib.contenttypes.models import ContentType
from minke.sessions import CommandFormSession
from minke.sessions import SingleCommandSession
from minke.sessions import CommandChainSession
from minke.sessions import REGISTRY
from minke.models import Host
from .forms import CommandForm
from .models import Command
from .models import CommandGroup


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
    form = CommandForm
    model = None
    model_id = None

    @classmethod
    def get_form(cls):
        obj = cls.model.objects.get(pk=cls.model_id)
        cmds = obj.get_commands()
        cls.form.base_fields['cmd'].choices = ((c.id, str(c)) for c in cmds)
        return cls.form

    def format_cmd(self, cmd):
        cmd_obj = Command.objects.get(pk=self.data['cmd'])
        return super().format_cmd(cmd_obj.cmd)


def session_factory():
    def build_attrs(obj):
        attrs = dict()
        attrs['model'] = obj.__class__
        attrs['model_id'] = obj.id
        attrs['verbose_name'] = obj.label
        attrs['__doc__'] = obj.description
        attrs['work_on'] = tuple((ct.model_class() for ct in obj.minketypes.all()))
        return attrs

    objs = Command.objects.filter(active=True)
    for obj in objs:
        attrs = build_attrs(obj)
        attrs['command'] = obj.cmd
        cls_name = '%s_%d' % (Command.__name__, obj.id)
        type(cls_name, (BaseCommandSession,), attrs)

    objs = CommandGroup.objects.filter(active=True, as_options=False)
    for obj in objs:
        attrs = build_attrs(obj)
        attrs['commands'] = tuple((c for c in obj.get_commands().all()))
        cls_name = '%s_%d' % (CommandGroup.__name__, obj.id)
        type(cls_name, (BaseCommandChainSession,), attrs)

    objs = CommandGroup.objects.filter(active=True, as_options=True)
    for obj in objs:
        attrs = build_attrs(obj)
        cls_name = '%s_%d' % (CommandGroup.__name__, obj.id)
        type(cls_name, (BaseCommandChoiceSession,), attrs)


REGISTRY.add_session_factory(session_factory)
