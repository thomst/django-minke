# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import traceback

from django.utils.html import escape

from .models import BaseMessage


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
        player = unicode(session.player).ljust(cls.WIDTH)
        status = session.status.upper().ljust(cls.PREFIX_WIDTH)
        color = cls.STATUS_COLORS[session.status]
        delimiter = cls.DELIMITER
        print color + status + cls.DELIMITER + player + cls.CLEAR

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


class Message(ProxyMixin, BaseMessage):

    def __init__(self, data, level='info'):
        super(Message, self).__init__()
        self.text = self.get_text(data)
        self.html = self.get_html(data)

        # deprecated - for backward-compatibility
        if type(level) == bool:
            self.level = 'info' if level else 'error'
        else:
            self.level = level.lower()

    def get_text(self, data):
        return data

    def get_html(self, data):
        return escape(data)


class PreMessage(Message):
    def get_html(self, data):
        return '<pre>{}</pre>'.format(escape(data))


class TableMessage(Message):
    def __init__(self, data, level='info', css=None):
        self.css = css or dict()
        super(TableMessage, self).__init__(data, level)

    def get_text(self, data):
        widths = dict()
        for row_data in data:
            for i, col in enumerate(row_data):
                if widths.get(i, -1) < len(col):
                    widths[i] = len(col)
        rows = list()
        spacer = '    '
        for row_data in data:
            ljust_row = [s.ljust(widths[i]) for i, s in enumerate(row_data)]
            rows.append(spacer.join(ljust_row))
        return '\n'.join(rows)

    def get_html(self, data):
        css_params = dict(width='680px', color='#666')
        css_params.update(self.css)
        style = ['{}:{};'.format(k, v) for k, v in css_params.items()]
        style = 'style="{}"'.format(' '.join(style))
        escaped_data = []
        for row in data:
            escaped_data.append(list())
            for column in row:
                escaped_data[-1].append(escape(column))
        columns = ['</td><td>'.join(columns) for columns in escaped_data]
        rows = '</td></tr><tr><td>'.join(columns)
        table = '<table {}><tr><td>{}</td></tr></table>'.format(style, rows)
        return table


# FIXME: Encoding should be done here
class ExecutionMessage(Message):
    TEMPLATE = """
        <table>
            <tr><td><code>[{rtn}]</code></td><td><code>{cmd}</code></td></tr>
            <tr><td>stdout:</td><td><pre>{stdout}</pre></td></tr>
            <tr><td>stderr:</td><td><pre>{stderr}</pre></td></tr>
        </table>
        """

    def get_text(self, data):
        lines = list()
        rtn, cmd = data.return_code, data.command
        lines.append('code[{}]'.format(rtn).ljust(10) + cmd)
        for line in data.stdout.splitlines():
            lines.append('stdout'.ljust(10) + line)
        for line in data.stderr.splitlines():
            lines.append('stderr'.ljust(10) + line)
        return '\n'.join(lines)

    def get_html(self, data):
        template = """
            <table>
                <tr><td><code>[{rtn}]</code></td><td><code>{cmd}</code></td></tr>
                <tr><td>stdout:</td><td><pre>{stdout}</pre></td></tr>
                <tr><td>stderr:</td><td><pre>{stderr}</pre></td></tr>
            </table>
            """
        return template.format(
            cmd=escape(data.command),
            rtn=data.return_code,
            stdout=escape(data.stdout),
            stderr=escape(data.stderr))


class ExceptionMessage(PreMessage):
    def __init__(self, level='error', print_tb=False):
        type, value, tb = sys.exc_info()
        if print_tb:
            data = traceback.format_exception(type, value, tb)
        else:
            data = traceback.format_exception_only(type, value)
        data = str().join(data).decode('utf-8')
        super(ExceptionMessage, self).__init__(data, level)
