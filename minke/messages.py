
import sys
import traceback

from django.contrib import admin
from django.db import models


class Messenger(object):

    def __init__(self, request):
        self.data = request.session.get('minke', dict())
        self.request = request

    def save(self):
        self.request.session['minke'] = self.data
        self.request.session.modified = True

    def store(self, obj, news=None, status=None):
        model = obj.__class__.__name__
        id = str(obj.id)

        if not self.data.has_key(model):
            self.data[model] = dict()
        if not self.data[model].has_key(id):
            self.data[model][id] = dict()

        if news:
            # We need a dictonary for json-serializing.
            news = [vars(n) for n in news or list()]
            self.data[model][id]['news'] = news
        if status:
            self.data[model][id]['status'] = status

        self.save()

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

        self.save()

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


class Message(object):

    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'

    def __init__(self, text, level='INFO'):
        self.text = text
        self.set_level(level)

    def set_level(self, level):
        try: level = getattr(self, level)
        except AttributeError: pass

        if level in (self.INFO, self.WARNING, self.ERROR):
            self.level = level
        else:
            raise ValueError('Invalid message-level: {}'.format(level))


class PreMessage(Message):
    def __init__(self, text, level='info'):
        self.set_level(level)
        self.text = '<pre>{}</pre>'.format(text)


class ExecutionMessage(Message):
    TEMPLATE = """
        <table>
            <tr><td><code>[{rtn}]</code></td><td><code>{cmd}</code></td></tr>
            <tr><td>stdout:</td><td><pre>{stdout}</pre></td></tr>
            <tr><td>stderr:</td><td><pre>{stderr}</pre></td></tr>
        </table>
        """

    def __init__(self, result, level='error'):
        self.set_level(level)
        msg = self.TEMPLATE.format(
            cmd=result.command,
            rtn=result.return_code,
            stdout=result.stdout or None,
            stderr=result.stderr or None)
        self.text = msg


class ExceptionMessage(Message):
    TEMPLATE = "<table><tr><td>{}</td><td><pre>{}</pre></td></tr></table>"

    def __init__(self, level='error', print_tb=False):
        self.set_level(level)
        if print_tb:
            msg = traceback.format_exc()
            self.text = "<pre>{}</pre>".format(msg)
        else:
            type, value, trb = sys.exc_info()
            self.text = "<pre>{}: {}</pre>".format(type.__name__, value)
