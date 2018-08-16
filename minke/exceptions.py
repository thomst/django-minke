# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from fabric.exceptions import *
from socket import error as SocketError


class Abortion(Exception):
    pass


class InvalidMinkeSetup(Exception):
    pass
