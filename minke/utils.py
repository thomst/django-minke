# -*- coding: utf-8 -*-

import json
from fabric2.config import Config
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from .exceptions import InvalidMinkeSetup


def item_by_attr(list, attr, value, default=None):
    return next((i for i in list if hasattr(i, attr) and getattr(i, attr) == value), default)


class FabricConfig(Config):
    def load_snakeconfig(self, configdict):
        for param, value in configdict.items():
            # prevent overriding existing settings with None...
            if value == None: return

            # param must start with one of the existing config-keys
            try:
                key = next((k for k in self.keys() if param.startswith(k)))
            except StopIteration:
                msg = 'Invalid fabric-config-parameter: {}'.format(param)
                raise InvalidMinkeSetup(msg)

            # add data - one or two level of depth
            if param == key:
                self[key] = value
            else:
                key2 = param.replace(key + '_', '')
                if not self[key]: self[key] = dict()
                self[key][key2] = value


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
