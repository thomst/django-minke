# -*- coding: utf-8 -*-

from rest_framework.exceptions import APIException


class InvalidMinkeSetup(Exception):
    pass


class InvalidURLQuery(APIException):
    status_code = 400
    default_detail = 'Invalid url-query.'
    default_code = 'invalid_urlquery'
