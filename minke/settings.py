# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings


MINKE_DEBUG = getattr(settings, 'MINKE_DEBUG', False)
MINKE_PASSWORD_FORM = getattr(settings, 'MINKE_PASSWORD_FORM', None)
MINKE_CLI_USER = getattr(settings, 'MINKE_CLI_USER', 'admin')
