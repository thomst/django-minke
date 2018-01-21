
import sys
import traceback


# message-helper
def store_msgs(request, obj, msgs=None, status=None):
    model = obj.__class__.__name__
    id = str(obj.id)
    if msgs and not type(msgs) == list: msgs = [msgs]
    if not request.session.has_key('minke'):
        request.session['minke'] = dict()
    if not request.session['minke'].has_key(model):
        request.session['minke'][model] = dict()
    if not request.session['minke'][model].has_key(id):
        request.session['minke'][model][id] = dict()
    if not request.session['minke'][model][id].has_key('msgs'):
        request.session['minke'][model][id]['msgs'] = list()
    if msgs:
        request.session['minke'][model][id]['msgs'] += msgs
    if status:
        request.session['minke'][model][id]['status'] = status
    # FIXME: call this any time a message is not smart
    request.session.modified = True

def get_msgs(request, obj):
    model = obj.__class__.__name__
    id = str(obj.id)
    msgs = request.session
    for key in ['minke', model, id]:
        try: msgs = msgs[key]
        except KeyError: return None
    return msgs

# this one works as an admin-action
def clear_msgs(modeladmin, request, queryset=None):
    model = modeladmin.model.__name__
    if queryset == None:
        try: del request.session['minke'][model]
        except KeyError: pass
    else:
        for obj in queryset.all():
            try: del request.session['minke'][model][str(obj.id)]
            except KeyError: pass
    request.session.modified = True
clear_msgs.short_description = 'clear minke-messages'


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
