# -*- coding: utf-8 -*-

import json
import yaml
from django.db import models
from django.forms import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext as _


def item_by_attr(list, attr, value, default=None):
    return next((i for i in list if hasattr(i, attr) and getattr(i, attr) == value), default)


def prepare_shell_command(cmd):
    # linux-shells need \n as newline
    return cmd.replace('\r\n', '\n').replace('\r', '\n')


def valid_yaml_configuration(value):
    """
    This validator will be used for model- and form-fields dealing with a yaml
    formatted fabric configuration. It accepts None, empty string or a string
    that could be parsed as a yaml formatted associative array.
    """
    if value is None or value == '':
        return

    try:
        data = yaml.load(value, yaml.Loader)
        assert(isinstance(data, dict))
    except yaml.YAMLError:
        raise ValidationError(_("Configuration must be valid yaml data."))
    except AssertionError:
        raise ValidationError(_("Configuration data must be an associative array."))


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


class FormatDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'
