
import yaml
from fabric2.config import Config
from fabric2.runners import Remote

from django.conf import settings
from .exceptions import InvalidMinkeSetup
from .models import CommandResult


class FabricConfig(Config):
    """
    A minke specific implementation of fabric's :class:`~fabric.config.Config`.

    The :class:`~fabric.connection.Connection` which is used within a session to
    run commands on the remote host will be initialized with an object of
    :class:`~.Config`. This object holds all configuration parameters which are
    collected and applied from different places in a predefined order:

    * Project configuration file placed within django's BASE_DIR. See fabric's
      `documentation <https://docs.fabfile.org/en/stable/concepts/configuration.html>`_
      about configuration files for more informations about filename conventions.
    * Configurations from django's settings file.
    * Configurations from :meth:`~.models.Hostgroup.config` of hostgroups
      associated with the session's host.
    * Configurations from :meth:`~.models.Host.config` of the host itself.
    * Configurations from the session's
      :attr:`~.sessions.Session.invoke_config`.
    * Configurations coming from forms like :attr:`~.settings.MINKE_FABRIC_FORM`
      and :meth:`~.sessions.Session.get_form` that were rendered for the
      session.
    * Required defaults to make fabric work well in the deamonized context of
      minke.
    """
    def __init__(self, host, session_cls, runtime_config):
        super().__init__(project_location=getattr(settings, 'BASE_DIR', None), lazy=True)
        self.load_project()
        self.load_global_config()
        self.load_hostgroup_config(host)
        self.load_host_config(host)
        self.load_session_config(session_cls)
        self.load_runtime_config(runtime_config)
        self.set_required_defaults()

    def load_global_config(self):
        """
        Global configuration parameters could be defined within django's
        settings file. Therefore the parameters must be prefixed with
        ``FABRIC_``. To support nested configuration attributes we apply them
        using the :meth:`~._load_snake_case_config` method with the lower case
        parameter names without the prefix.

        A settings parameter like::

            FABRIC_RUN_PTY = True

        becomes::

            config.run.pty = True
        """
        config = dict()
        for param in dir(settings):
            if not param.startswith('FABRIC_'):
                continue
            config[param[7:].lower()] = getattr(settings, param)

        self._load_snake_case_config(config)

    def load_hostgroup_config(self, host):
        """
        Each :class:`~.models.HostGroup` can hold its own fabric configuration
        within the :attr:`~.models.HostGroup.config` field. The configuration
        must be a yaml formatted associative array.

        The configuration of each hostgroup associated with the host to work on
        will be applied.

        .. note::

            The order in which configurations from multiple hostgroups are
            applied is not defined.

        :param host host: host object
        """
        for group in host.groups.all():
            config = yaml.load(group.config, yaml.Loader)
            self.update(config or dict())

    def load_host_config(self, host):
        """
        Each :class:`~.models.Host` can hold its own fabric configuration within
        the :attr:`~.models.Host.config` field. The configuration must be a yaml
        formatted associative array.

        The configuration of the host to work on will be applied.

        :param host host: host object
        """
        config = yaml.load(host.config, yaml.Loader)
        self.update(config or dict())

    def load_session_config(self, session_cls):
        """
        Load config from session class

        :param session_cls: session class to work with
        :type session_cls: :class:`~.session.Session`
        """
        self.update(session_cls.invoke_config or dict())

    def load_runtime_config(self, runtime_config):
        """
        Load the data that was coming from forms. Form fields starting with
        'fabric_' are applied as configuration. The other fields are added in an
        extra section named 'session_data'.

        :param dict runtime_config: collected data from forms
        """
        session_data = dict()
        config = dict()
        for key, value in runtime_config.items():
            if key.startswith('fabric_'):
                config[key[7:]] = value
            else:
                session_data[key] = value

        self._load_snake_case_config(config)
        self.update(dict(session_data=session_data))

    def set_required_defaults(self):
        """
        To properly work with fabric in a deamon based context we need some
        defaults that must not be overwritten.
        """
        self.run.hide = True
        self.run.warn = True
        self.runners.remote = FabricRemote

    def _load_snake_case_config(self, config):
        """
        Load a plane config dictonary as a nested one using a simple convention:
        The snake case structure of a key represents the nested logic of the
        config object: A key like ``run_pty`` becomes ``config.run.pty``.

        Since some config attributes have underscores themselves we use a simple
        rule to prevent ambiguities:

        The first part of the snake case key must already exists on the config
        object. The remaining part of the snake case key will be used as a
        second level key: Something like ``connect_kwargs_my_special_key`` will
        become ``config.connect_kwargs.my_special_key`` on the config object.

        :param dict config: a plane snake case key configuration
        :raise InvalidMinkeSetup: If a key does not match an existing
            configuration attribute.
        """
        nested_config = dict()
        for param, value in config.items():
            snippets = param.split('_')
            key1 = key2 = None

            for i in range(len(snippets)):
                if '_'.join(snippets[:i+1]) in self:
                    key1 = '_'.join(snippets[:i+1])
                    key2 = '_'.join(snippets[i+1:])
                    break

            if not key1:
                msg = f'Invalid fabric-config-parameter: {param}'
                raise InvalidMinkeSetup(msg)

            if key2:
                nested_config[key1] = {key2: value}
            else:
                nested_config[key1] = value

        self.update(nested_config)


class FabricRemote(Remote):
    """
    A subclass of fabric's remote-runner to customize the result-class.
    """
    def generate_result(self, **kwargs):
        kwargs["connection"] = self.context
        return CommandResult(**kwargs)
