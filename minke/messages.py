# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import traceback

from django.utils.html import escape

from .models import BaseMessage


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
