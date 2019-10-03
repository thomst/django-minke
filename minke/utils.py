# -*- coding: utf-8 -*-

import json
from fabric2.config import Config
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder


def item_by_attr(list, attr, value, default=None):
    return next((i for i in list if hasattr(i, attr) and getattr(i, attr) == value), default)


def prepare_shell_command(cmd):
    # linux-shells need \n as newline
    return cmd.replace('\r\n', '\n').replace('\r', '\n')


class FabricConfig(Config):
    """
    A subclass of fabric's Config-class.
    Add a load_snakeconfig-method, that takes a plain dict and parses its
    snake-case-keys to fit into the nested default-config-structure.
    """
    def load_snakeconfig(self, configdict):
        for param, value in configdict.items():
            # We support two level of recursive config-keys. That means
            # something like 'connect_kwargs_my_special_key' will be applied as
            # 'config.connect_kwargs.my_special_key'. The key on the first level
            # must already exist. Otherwise we raise InvalidMinkeSetup.
            snippets = param.split('_')
            key1 = key2 = None

            for i, key in enumerate(snippets):
                if '_'.join(snippets[:i+1]) in self:
                    key1 = '_'.join(snippets[:i+1])
                    key2 = '_'.join(snippets[i+1:])
                    break

            if not key1:
                msg = 'Invalid fabric-config-parameter: {}'.format(param)
                raise InvalidMinkeSetup(msg)

            # apply config-data
            if not key2:
                self[key1] = value
            else:
                if not self[key1]: self[key1] = dict()
                self[key1][key2] = value


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
