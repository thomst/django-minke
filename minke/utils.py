# -*- coding: utf-8 -*-

import json
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder


def item_by_attr(list, attr, value, default=None):
    return next((i for i in list if hasattr(i, attr) and getattr(i, attr) == value), default)


def prepare_shell_command(cmd):
    # linux-shells need \n as newline
    return cmd.replace('\r\n', '\n').replace('\r', '\n')


class JSONField(models.TextField):
    """
    A very raw and simple JSONField.
    (It is only used internally - so we know what we get.)
    """
    def from_db_value(self, value, *args):
        if value is None:
            return value
        else:
            return json.loads(value)

    def to_python(self, value):
        if type(value) is str:
            return json.loads(value)
        else:
            return value

    def get_prep_value(self, value):
        return json.dumps(value, cls=DjangoJSONEncoder)


def get_session_summary(sessions):
    """
    Takes a list of sessions and extract a summary-dictonary.
    """
    summary = dict()
    summary['all'] = len(sessions)
    summary['waiting'] = len([s for s in sessions if s.proc_status == 'initialized'])
    summary['running'] = len([s for s in sessions if s.proc_status in ('running', 'stopping')])
    summary['done'] = len([s for s in sessions if s.proc_status in ('completed', 'stopped', 'canceled', 'failed')])
    summary['success'] = len([s for s in sessions if s.session_status == 'success'])
    summary['warning'] = len([s for s in sessions if s.session_status == 'warning'])
    summary['error'] = len([s for s in sessions if s.session_status == 'error'])
    return summary
