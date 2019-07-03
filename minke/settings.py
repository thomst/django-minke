# -*- coding: utf-8 -*-

from django.conf import settings
from .helpers import FabricConfig
from .helpers import FabricRemote


MINKE_DEBUG = getattr(settings, 'MINKE_DEBUG', False)
MINKE_FABRIC_FORM = getattr(settings, 'MINKE_FABRIC_FORM', None)
MINKE_CLI_USER = getattr(settings, 'MINKE_CLI_USER', 'admin')
MINKE_FABRIC_CONFIG = getattr(settings, 'MINKE_FABRIC_CONFIG', FabricConfig())
MINKE_HOST_CONFIG = getattr(settings, 'MINKE_HOST_CONFIG', dict())

# set defaults for fabric-/invoke-config
MINKE_FABRIC_CONFIG.runners.remote = FabricRemote
MINKE_FABRIC_CONFIG.run.hide = True
MINKE_FABRIC_CONFIG.run.warn = True

# All config-vars starting with FABRIC_ will be loaded into our fabric-config...
fabric_data = dict([(k[7:].lower(), getattr(settings, k)) for k in dir(settings) if k.startswith('FABRIC')])
MINKE_FABRIC_CONFIG.load_snakeconfig(fabric_data)
