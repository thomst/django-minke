# -*- coding: utf-8 -*-

from django.contrib.contenttypes.models import ContentType
from minke.sessions import CommandFormSession
from .forms import CommandForm
from .models import Command


class CommandChoicesSession(CommandFormSession):
    FORM = CommandForm
    ABSTRACT = True

    @classmethod
    def get_form(cls):
        cmds = Command.objects.filter(session_cls=cls.__name__, active=True)
        cls.FORM.base_fields['cmd'].choices = [(c.id, str(c)) for c in cmds]
        return cls.FORM

    def format_cmd(self, cmd):
        cmd_obj = Command.objects.get(pk=self.session_data['cmd'])
        return super().format_cmd(cmd_obj.cmd)
