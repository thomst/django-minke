# -*- coding: utf-8 -*-

import sys, traceback, textwrap

from django.utils.html import escape
from .models import BaseMessage
from .settings import MINKE_MESSAGE_WRAP


# We declare the Meta-class whithin a mixin.
# Otherwise the proxy-attribute won't be inherited by child-classes.
class ProxyMixin(object):
    class Meta:
        proxy = True


class Message(ProxyMixin, BaseMessage):
    def __init__(self, data, level=None):
        super().__init__()
        self.text = self.get_text(data)
        self.html = self.get_html(data)
        self.level = self.get_level(data, level)

    def get_level(self, data, level):
        """
        Normalize message-level.
        """
        levels = dict(self.LEVELS).keys()
        if level is None:
            # info as default-level
            return 'info'
        if isinstance(level, bool):
            # True as info and False as error
            return 'info' if level else 'error'
        elif isinstance(level, str) and level.lower() in levels:
            # level as it was given
            return level.lower()
        else:
            raise ValueError('invalid message-level: {}'.format(level))

    def get_text(self, data):
        """
        Derive message-text from data.
        """
        return data

    def get_html(self, data):
        """
        Derive message-html from data.
        """
        return escape(data)


class PreMessage(Message):
    def get_html(self, data):
        data = self.get_text(data)
        wrapped = list()
        for line in data.splitlines():
            wrapped += textwrap.wrap(line, MINKE_MESSAGE_WRAP)
        return '<pre>{}</pre>'.format(escape('\n'.join(wrapped)))


class TableMessage(PreMessage):
    def get_text(self, data):
        widths = dict()
        rows = list()
        spacer = '    '
        for row in data:
            for i, col in enumerate(row):
                if widths.get(i, -1) < len(col):
                    widths[i] = len(col)
        for row in data:
            ljust_row = [s.ljust(widths[i]) for i, s in enumerate(row)]
            rows.append(spacer.join(ljust_row))
        return '\n'.join(rows)


class ExecutionMessage(PreMessage):
    def get_level(self, data, level):
        # if a level-argument was passed just use it
        if not level is None:
            return super().get_level(data, level)
        # otherwise derive the level from result-characteristics
        elif data.failed:
            return 'error'
        elif data.stderr:
            return 'warning'
        else:
            return 'info'

    def _get_chunk(self, prefix, lines):
        wrapped = list()
        prefixed = list()
        for line in lines:
            wrapped += textwrap.wrap(line, MINKE_MESSAGE_WRAP - 10)
        for line in wrapped:
            prefixed.append(prefix.ljust(10) + line)
            prefix = str()
        return prefixed

    def get_text(self, data):
        lines = list()
        prefix = 'code[{}]'.format(data.return_code)
        lines += self._get_chunk(prefix, data.command.splitlines())
        lines += self._get_chunk('stdout:', data.stdout.splitlines())
        lines += self._get_chunk('stderr:', data.stderr.splitlines())
        return '\n'.join(lines)


class ExceptionMessage(PreMessage):
    def __init__(self, level='error', print_tb=False):
        type, value, tb = sys.exc_info()

        if print_tb:
            data = traceback.format_exception(type, value, tb)
        else:
            data = traceback.format_exception_only(type, value)

        data = str().join(data)
        super().__init__(data, level)
