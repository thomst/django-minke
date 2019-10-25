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
    def __init__(self, *args, **kwargs):
        # NOTE:
        # fabric has a rather dodgy way to check for optional config-files:
        #
        # > # Typically means 'no such file', so just note & skip past.
        # > except IOError as e:
        # >     # TODO: is there a better / x-platform way to detect this?
        # >     if "No such file" in e.strerror:
        # >         err = "Didn't see any {}, skipping."
        # >         debug(err.format(filepath))
        # >     else:
        # >         raise
        #
        # To prevent an accidentally raised IOError we catch it and re-try to
        # initialize Config with `lazy=True` (which means `Config` won't look for
        # config-files at all).
        try:
            super().__init__(*args, **kwargs)
        except IOError:
            kwargs['lazy'] = True
            super().__init__(*args, **kwargs)

    def load_snakeconfig(self, configdict):
        """
        Load a plane configdict as nested config - using the key's
        snake-structure as representation of the nest-logic.

        Two level of recursion are supported. That means something like
        'connect_kwargs_my_special_key' will be applied as
        'config.connect_kwargs.my_special_key'. To obviate ambiguity the key on
        the first level must already exist. Otherwise we raise InvalidMinkeSetup.

        Parameter
        ---------
        configdict : dict
        """
        for param, value in configdict.items():
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


class FabricRemote(Remote):
    """
    A subclass of fabric's remote-runner to customize the result-class.
    """
    def generate_result(self, **kwargs):
        kwargs["connection"] = self.context
        return CommandResult(**kwargs)
