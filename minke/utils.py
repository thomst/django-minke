# -*- coding: utf-8 -*-
from __future__ import unicode_literals


class UnicodeResult(unicode):
    """
    Build an unicode-object equivalent to fabric's _AttributeString-object.
    """
    def __init__(self, result, encoding, errors):
        self.command = result.command
        self.real_command = result.real_command
        self.return_code = result.return_code
        self.succeeded = result.succeeded
        self.failed = result.failed
        self.stderr = result.stderr.decode(encoding, errors)

    @property
    def stdout(self):
        return self
