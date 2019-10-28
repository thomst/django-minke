# -*- coding: utf-8 -*-

import getpass
import datetime

from django.contrib.auth.models import User
from django.contrib.auth.models import Permission

from minke.models import Host
from minke.models import MinkeSession
from ..models import Server
from ..models import AnySystem
from ..sessions import DummySession


def create_users():
    User.objects.create_superuser(
        'admin',
        'admin@testapp.org',
        'adminpassword')

    anyuser = User(username='anyuser', is_staff=True)
    anyuser.set_password('anyuserpassword')
    anyuser.save()
    change_perm = Permission.objects.get(codename='change_host')
    anyuser.user_permissions.add(change_perm)

def create_hosts():
    # create a localhost with the current user
    # this might have a chance to be accessible via ssh
    user = getpass.getuser()
    host = Host.objects.create(
        name='localhost',
        hostname='localhost',
        username=user)

    # create some dummy-hosts as well
    for i in range(20):
        label = 'label' + str(i % 4) * 3
        hostname = 'host_{}_{}'.format(str(i), label)
        Host.objects.create(
            name=hostname,
            hostname=hostname,
            username='user' + label)

def create_players():
    for host in Host.objects.all():
        server = Server.objects.create(host=host, hostname=host.hostname)
        AnySystem.objects.create(server=server)

def create_test_data():
    create_users()
    create_hosts()
    create_players()

def create_minkesession(minkeobj, session_cls=DummySession, data=None,
    status='success', user='admin', current=True, proc_status='completed'):
    user = User.objects.get(username=user)
    session = MinkeSession()
    session.user = user
    session.minkeobj = minkeobj
    session.proc_status = proc_status
    session.session_status = status
    session.session_name = session_cls.__name__
    session.session_verbose_name = session_cls.verbose_name
    session.session_description = session_cls.__doc__
    session.session_data = data or dict()
    session.start_time = datetime.datetime.now()
    session.end_time = datetime.datetime.now()
    session.run_time = session.end_time - session.start_time
    session.save()
    return session

def create_session(session_cls, minkeobj, data=None, con=None):
    minkesession = create_minkesession(minkeobj, session_cls, data=data or dict())
    return session_cls(con, minkesession)
