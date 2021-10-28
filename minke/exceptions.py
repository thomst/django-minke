# -*- coding: utf-8 -*-

from rest_framework.exceptions import APIException


class InvalidMinkeSetup(Exception):
    """
    Baseclass for all exceptions concerning the minke-setup
    """


class SessionError(Exception):
    """
    Exception that could be raised within Session.process.

    Raising this Exception is a convenient way for sessions to stop themselves.
    In consequence the session status will be set to error and whatever was
    passed as arguments will be printed as error message.
    """


class SessionRegistrationError(InvalidMinkeSetup):
    """
    Exception for failing session-registration.
    """
    MSG = '`{}` couldn\'t be registerd: '

    def __init__(self, session, msg):
        msg = self.MSG.format(session.__name__) + msg
        super().__init__(msg)


class InvalidURLQuery(APIException):
    status_code = 400
    default_detail = 'Invalid url-query.'
    default_code = 'invalid_urlquery'
