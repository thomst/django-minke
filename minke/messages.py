
import sys
import traceback

from django.contrib import admin
from django.db import models


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
    def __init__(self):
        self.data = dict()
        self.table = list()

    def colorize(self, text, key, header=False):
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
            name, status, row_type = obj_data['name'], obj_data['status'], 0
            self.table.append([row_type, model, name, status])
            for news in obj_data.get('news', list()):
                msg, level = news['text'], news['level']
                row_type = 1
                for line in msg.splitlines():
                    self.table.append([row_type, model, name, status, level, line])
                    row_type = 2

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
                prefix = self.colorize(prefix, row[3])
                level = self.colorize(row[-2], row[-2])
                line = prefix + spacer[0] + level + spacer[row[0]] + row[-1]
            print line

    def process(self):
        self.build_table()
        self.normalize_cols()
        self.print_table()


class Message(object):
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'

    def __init__(self, data, level='INFO'):
        self.data = data
        try: level = getattr(self, level)
        except AttributeError: pass
        if level in (self.INFO, self.WARNING, self.ERROR): self.level = level
        else: raise ValueError('Invalid message-level: {}'.format(level))

    @property
    def text(self):
        return str(self.data)

    @property
    def html(self):
        return str(self.data)


class PreMessage(Message):
    @property
    def html(self):
        return '<pre>{}</pre>'.format(self.data)


class TableMessage(Message):
    def __init__(self, data, level='info', css=None):
        self.css = css or dict()
        super(TableMessage, self).__init__(data, level)

    @property
    def text(self):
        widths = dict()
        for row_data in self.data:
            for i, col in enumerate(row_data):
                if widths.get(i, -1) < len(col):
                    widths[i] = len(col)
        rows = list()
        spacer = '    '
        for row_data in self.data:
            ljust_row = [s.ljust(widths[i]) for i, s in enumerate(row_data)]
            rows.append(spacer.join(ljust_row))
        return '\n'.join(rows)

    @property
    def html(self):
        css_params = dict(width='680px', color='#666')
        css_params.update(self.css)
        style = ['{}:{};'.format(k, v) for k, v in css_params.items()]
        style = 'style="{}"'.format(' '.join(style))
        columns = ['</td><td>'.join(columns) for columns in self.data]
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

    @property
    def text(self):
        lines = list()
        rtn, cmd = self.data.return_code, self.data.command
        stdout, stderr = self.data.stdout, self.data.stderr
        lines.append('code[{}]'.format(rtn).ljust(10) + cmd)
        for line in stdout.splitlines(): lines.append('stdout'.ljust(10) + line)
        for line in stderr.splitlines(): lines.append('stderr'.ljust(10) + line)
        return '\n'.join(lines)

    @property
    def html(self):
        template = """
            <table>
                <tr><td><code>[{rtn}]</code></td><td><code>{cmd}</code></td></tr>
                <tr><td>stdout:</td><td><pre>{stdout}</pre></td></tr>
                <tr><td>stderr:</td><td><pre>{stderr}</pre></td></tr>
            </table>
            """
        return template.format(
            cmd=self.data.command,
            rtn=self.data.return_code,
            stdout=self.data.stdout or None,
            stderr=self.data.stderr or None)


class ExceptionMessage(PreMessage):
    def __init__(self, level='error', print_tb=False):
        if print_tb:
            data = traceback.format_exc()
        else:
            type, value, trb = sys.exc_info()
            data = "{}: {}".format(type.__name__, value)
        super(ExceptionMessage, self).__init__(data, level)
