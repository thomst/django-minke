from django.conf import settings

from fabric.api import env
from fabric.state import output

from .decorators import register
from .exceptions import Abortion


# Some default fabric-settings:
# TODO: bugreport - seems that fabric misses to set the default.
# We get an AttributeError, if we do net set env.key explicitly.
env.key = None
env.pool_size = 24

# load django-settings for fabric
if hasattr(settings, 'FABRIC_ENV'):
    for key, value in settings.FABRIC_ENV.items():
        if hasattr(env, key):
            setattr(env, key, value)

# These configs are essential for minke to work with fabric
# in multiprocessing manner and should not be overwritten.
env.abort_exception = Abortion
env.combine_stderr = False
env.parallel = True
env.linewise = True
env.warn_only = True
env.always_use_pty = False
env.skip_bad_hosts = False
env.abort_on_prompts = True

# disable all fabric-output
output.status = False
output.warnings = False
output.running = False
output.stdout = False
output.stderr = False
output.user = False
output.aborts = False

# default-settings
if not hasattr(settings, 'MINKE_CLI_USER'):
    settings.MINKE_CLI_USER = 'admin'
