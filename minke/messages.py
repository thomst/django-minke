
import sys
import traceback

from django.contrib import admin
from django.db import models


# message-helper
def store_msgs(request, obj, msgs=None, status=None):
    model = obj.__class__.__name__
    id = str(obj.id)
    if msgs and not type(msgs) == list:
        msgs = [msgs]

    data = request.session.get('minke', dict())
    if not data.has_key(model):
        data[model] = dict()
    if not data[model].has_key(id):
        data[model][id] = dict()

    if not data[model][id].has_key('msgs'):
        data[model][id]['msgs'] = list()
    if msgs:
        data[model][id]['msgs'] += msgs
    if status:
        data[model][id]['status'] = status
    request.session['minke'] = data
    request.session.modified = True

def get_msgs(request, obj):
    model = obj.__class__.__name__
    id = str(obj.id)
    msgs = request.session
    for key in ['minke', model, id]:
        try: msgs = msgs[key]
        except KeyError: return None
    return msgs

def clear_msgs(request, model, objects=None):
    model = model.__name__

    if objects:
        # get objects as iterable
        try: iter(objects)
        except TypeError: objects = [objects]

        # delete object-specific messages
        for obj in objects:
            try: del request.session['minke'][model][str(obj.id)]
            except KeyError: pass
    else:
        # delete model-specific messages
        try: del request.session['minke'][model]
        except KeyError: pass

    request.session.modified = True


# Messages
class Message(object):
    def __init__(self, text, level='info'):
        self.level = level
        self.text = text


class PreMessage(object):
    def __init__(self, text, level='info'):
        self.level = level
        self.text = '<pre>{}</pre>'.format(text)


class ExecutionMessage(object):
    TEMPLATE = """
        <table>
            <tr><td><code>[{rtn}]</code></td><td><code>{cmd}</code></td></tr>
            <tr><td>stdout:</td><td><pre>{stdout}</pre></td></tr>
            <tr><td>stderr:</td><td><pre>{stderr}</pre></td></tr>
        </table>
        """

    def __init__(self, result, level='error'):
        self.level = level
        msg = self.TEMPLATE.format(
            cmd=result.command,
            rtn=result.return_code,
            stdout=result.stdout or None,
            stderr=result.stderr or None)
        self.text = msg


class ExceptionMessage(object):
    TEMPLATE = "<table><tr><td>{}</td><td><pre>{}</pre></td></tr></table>"

    def __init__(self, level='error', print_tb=False):
        self.level = level
        if print_tb:
            msg = traceback.format_exc()
            self.text = "<pre>{}</pre>".format(msg)
        else:
            type, value, trb = sys.exc_info()
            self.text = "<pre>{}: {}</pre>".format(type.__name__, value)
