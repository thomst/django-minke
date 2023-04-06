# -*- coding: utf-8 -*-

from django.conf import settings
from .fabrictools import FabricConfig
from .fabrictools import FabricRemote


MINKE_DEBUG = getattr(settings, 'MINKE_DEBUG', False)
MINKE_FABRIC_FORM = getattr(settings, 'MINKE_FABRIC_FORM', None)
MINKE_CLI_USER = getattr(settings, 'MINKE_CLI_USER', 'admin')
MINKE_MESSAGE_WRAP = getattr(settings, 'MINKE_MESSAGE_WRAP', 120)
