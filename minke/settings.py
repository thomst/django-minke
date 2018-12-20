# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings


MINKE_DEBUG = getattr(settings, 'MINKE_DEBUG', False)
FABRIC_ENV = getattr(settings, 'FABRIC_ENV', dict())
MINKE_CLI_USER = getattr(settings, 'MINKE_CLI_USER', 'admin')
