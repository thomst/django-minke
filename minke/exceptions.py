# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from socket import error as SocketError
from socket import gaierror as GaiError
from rest_framework.exceptions import APIException


class Abortion(Exception):
    pass


class InvalidMinkeSetup(Exception):
    pass


class InvalidURLQuery(APIException):
    status_code = 400
    default_detail = 'Invalid url-query.'
    default_code = 'invalid_urlquery'
