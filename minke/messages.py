# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import traceback

from django.utils.html import escape

from .models import MessageData


class Printer:
    STATUS_COLORS = dict(
        success = '\033[1;37;42m',
        warning = '\033[1;37;43m',
        error   = '\033[1;37;41m')

    LEVEL_COLORS = dict(
        info    = '\033[32m',
        warning = '\033[33m',
        error   = '\033[31m')

    LEVEL_COLORS_UNDERSCORE = dict(
        info    = '\033[4;32m',
        warning = '\033[4;33m',
        error   = '\033[4;31m')

    CLEAR = '\033[0m'
    CLEAR_FG = '\033[39m'
    WIDTH = 40
    PREFIX_WIDTH = 7
    DELIMITER = ': '

    @classmethod
    def prnt(cls, session):
        minkeobj = unicode(session.minkeobj).ljust(cls.WIDTH)
        status = session.session_status.upper().ljust(cls.PREFIX_WIDTH)
        color = cls.STATUS_COLORS[session.session_status]
        delimiter = cls.DELIMITER
        print color + status + cls.DELIMITER + minkeobj + cls.CLEAR

        msgs = list(session.messages.all())
        msg_count = len(msgs)
        for i, msg in enumerate(msgs, start=1):
            underscore = True if i < msg_count else False
            cls.prnt_msg(msg, underscore)

    @classmethod
    def prnt_msg(cls, msg, underscore=False):
        color = cls.LEVEL_COLORS[msg.level]
        level = msg.level.ljust(cls.PREFIX_WIDTH)
        lines = msg.text.splitlines()

        for line in lines[:-1 if underscore else None]:
            print color + level + cls.CLEAR + cls.DELIMITER + line

        if underscore:
            color = cls.LEVEL_COLORS_UNDERSCORE[msg.level]
            line = lines[-1].ljust(cls.WIDTH)
            print color + level + cls.CLEAR_FG + cls.DELIMITER + line + cls.CLEAR


# We declare the Meta-class whithin a mixin.
# Otherwise the proxy-attribute won't be inherited by child-classes of Session.
class ProxyMixin(object):
    class Meta:
        proxy = True


class Message(ProxyMixin, MessageData):

    def __init__(self, data, level='info'):
        super(Message, self).__init__()
        self.text = self.get_text(data)
        self.html = self.get_html(data)

        levels = dict(self.LEVELS).keys()
        if type(level) == bool:
            self.level = 'info' if level else 'error'
        elif level.lower() in levels:
            self.level = level.lower()
        else:
            msg = 'message-level must be one of {}'.format(levels)
            raise InvalidMinkeSetup(msg)

    def get_text(self, data):
        return data

    def get_html(self, data):
        return escape(data)


class PreMessage(Message):
    def get_html(self, data):
        return '<pre>{}</pre>'.format(escape(self.get_text(data)))


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
    def _get_chunk(self, prefix, lines, max_lines):
        if max_lines:
            diff = len(lines) - max_lines
            lines = lines[-max_lines:]
            if diff > 0:
                lines.insert(0, '[{}] ... ...'.format(diff))

        new_lines = list()
        for line in lines:
            new_lines.append(prefix.ljust(10) + line)
            prefix = str()
        return new_lines

    def get_text(self, data, max_lines=10):
        lines = list()
        prefix = 'code[{}]'.format(data.return_code)
        lines += self._get_chunk(prefix, data.command.split('\n'), None)
        lines += self._get_chunk('stdout:', data.stdout.splitlines(), max_lines)
        lines += self._get_chunk('stderr:', data.stderr.splitlines(), max_lines)
        return '\n'.join(lines)


class ExceptionMessage(PreMessage):
    def __init__(self, level='error', print_tb=False):
        type, value, tb = sys.exc_info()
        if print_tb:
            data = traceback.format_exception(type, value, tb)
        else:
            data = traceback.format_exception_only(type, value)
        data = str().join(data).decode('utf-8')
        super(ExceptionMessage, self).__init__(data, level)
