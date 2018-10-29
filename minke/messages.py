# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import traceback

from django.utils.html import escape

from .models import BaseMessage


class MessengerMixin(object):
    def store(self, obj, news=None, status=None):
        model = obj.__class__.__name__
        id = str(obj.id)
        name = str(obj)

        if not self.data.has_key(model):
            self.data[model] = dict()
        if not self.data[model].has_key(id):
            self.data[model][id] = dict()
            self.data[model][id]['name'] = name

        if news:
            # We need a dictonary for json-serializing.
            news = [{'level': n.level, 'text': n.text, 'html': n.html} for n in news]
            self.data[model][id]['news'] = news
        if status:
            self.data[model][id]['status'] = status

    def remove(self, model=None, objects=None):
        if model:
            model = model.__name__
            try: del self.data[model]
            except KeyError: pass
        elif objects:
            model = objects[0]._meta.model.__name__
            for obj in objects:
                id = str(obj.id)
                try: del self.data[model][id]
                except KeyError: pass

    def get(self, model=None, object=None):
        if object:
            model = object.__class__.__name__
            id = str(object.id)
            try: return self.data[model][id]
            except KeyError: return None
        elif model:
            model = model.__name__
            try: return self.data[model]
            except KeyError: return None


class Messenger(MessengerMixin):
    def __init__(self, request):
        self.data = request.session.get('minke', dict())
        self.request = request

    def process(self):
        self.request.session['minke'] = self.data
        self.request.session.modified = True


class ConsoleMessenger(MessengerMixin):
    def __init__(self, silent=False, no_color=False, no_prefix=False):
        self.data = dict()
        self.table = list()
        self.silent = silent
        self.no_color = no_color
        self.no_prefix = no_prefix

    def colorize(self, text, key, header=False):
        if self.no_color: return text
        key = key.strip()
        codes = [
            dict(
                success = '\033[0;37;42m',
                warning = '\033[0;30;43m',
                error   = '\033[1;37;41m'),
            dict(
                success = '\033[0;32m',
                info    = '\033[0;32m',
                warning = '\033[0;33m',
                error   = '\033[1;31m')]
        end_code = '\033[0m'
        return codes[0 if header else 1][key] + text + end_code

    def build_table(self):
        model = self.data.keys()[0]
        model_data = self.data.values()[0]
        for id, obj_data in model_data.items():
            name = obj_data['name']
            status = obj_data['status']
            news = obj_data.get('news', list())
            type = 0
            if self.silent and status == 'success' and not news: continue
            self.table.append([type, model, name, status])
            for msgs in news:
                msg, level = msgs['text'], msgs['level']
                type = 1
                for line in msg.splitlines():
                    self.table.append([type, model, name, status, level, line])
                    type = 2

    def normalize_cols(self):
        col_width = dict()
        for row in self.table:
            for i, col in enumerate(row[1:5]):
                if col_width.get(i, 0) < len(col):
                    col_width[i] = len(col)

        for nrow, row in enumerate(self.table[:]):
            for ncol, col in enumerate(row[1:5]):
                if ncol == 2:
                    self.table[nrow][ncol+1] = col.rjust(col_width[ncol])
                else:
                    self.table[nrow][ncol+1] = col.ljust(col_width[ncol])

    def print_table(self):
        spacer = [' - ', ' *| ', '  | ']
        for row in self.table:
            prefix = spacer[0].join(row[2:4])
            if row[0] == 0:
                line = self.colorize(prefix, row[3], True)
            else:
                prefix = self.colorize(prefix, row[3]) + spacer[0]
                level = self.colorize(row[-2], row[-2])
                if self.no_prefix:
                    line = level + spacer[row[0]] + row[-1]
                else:
                    line = prefix + level + spacer[row[0]] + row[-1]
            print line.encode('utf-8')

    def process(self):
        if not self.data: return
        self.build_table()
        self.normalize_cols()
        self.print_table()


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
