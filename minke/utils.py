# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .exceptions import InvalidMinkeSetup
from fabric2.config import Config


def item_by_attr(list, attr, value, default=None):
    return next((i for i in list if hasattr(i, attr) and getattr(i, attr) == value), default)


class FabricConfig(Config):
    def load_snakeconfig(self, configdict):
        for param, value in configdict.items():
            try:
                # param must start with one of the existing config-keys
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
