# -*- coding: utf-8 -*-
from __future__ import unicode_literals


class UnicodeResult(unicode):
    """
    A wrapper for fabric's result-object returned by run.

    We pass all values but decode the bytestrings of stdout and stderr.
    """
    def __init__(self, result, encoding='utf-8'):
        self.command = result.command
        self.real_command = result.real_command
        self.return_code = result.return_code
        self.succeeded = result.succeeded
        self.failed = result.failed
        self.stderr = result.stderr.decode(encoding, 'replace')
        unicode(result.decode(encoding, 'replace'))

    @property
    def stdout(self):
        return self
