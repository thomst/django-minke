# -*- coding: utf-8 -*-

from fabric2.config import Config
from fabric2.runners import Remote

from .exceptions import InvalidMinkeSetup
from .models import CommandResult


class FabricConfig(Config):
    """
    A subclass of fabric's Config-class.
    Add a load_snakeconfig-method, that takes a plain dict and parses its
    snake-case-keys to fit into the nested default-config-structure.
    """
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


class FabricRemote(Remote):
    """
    A subclass of fabric's remote-runner to customize the result-class.
    """
    def generate_result(self, **kwargs):
        kwargs["connection"] = self.context
        return CommandResult(**kwargs)
