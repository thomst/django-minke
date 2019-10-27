# -*- coding: utf-8 -*-

from rest_framework.exceptions import APIException


class InvalidMinkeSetup(Exception):
    pass


class SessionReloadError(InvalidMinkeSetup):
    # TODO: Work out the error-message - containing the original_exception.
    def __init__(self, original_exception, session=None):
        self.original_exception = original_exception
        self.session = session


class SessionRegistrationError(InvalidMinkeSetup):
    MSG = '`{}` couldn\'t be registerd: '

    def __init__(self, session, msg):
        msg = self.MSG.format(session.__name__) + msg
        super().__init__(msg)


class InvalidURLQuery(APIException):
    status_code = 400
    default_detail = 'Invalid url-query.'
    default_code = 'invalid_urlquery'
