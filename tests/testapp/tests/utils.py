# -*- coding: utf-8 -*-

import getpass
import datetime
from fabric2 import Connection

from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.conf import settings

from minke.sessions import REGISTRY
from minke.models import Host
from minke.models import HostGroup
from minke.models import MinkeSession
from minke.fabrictools import FabricConfig
from ..models import Server
from ..models import AnySystem
from ..sessions import DummySession


class AlterSettings:
    def __init__(self, **kwargs):
        self.settings = kwargs
        self.origin = dict()

    def __enter__(self):
        for param, value in self.settings.items():
            if hasattr(settings, param):
                self.origin[param] = getattr(settings, param)
            setattr(settings, param, value)

    def __exit__(self, type, value, traceback):
        for param, value in self.settings.items():
            delattr(settings, param)
        for param, value in self.origin.items():
            setattr(settings, param, value)


class AlterObject:
    def __init__(self, obj, **kwargs):
        self.obj = obj
        self.params = kwargs
        self.origin = dict()

    def __enter__(self):
        for param, value in self.params.items():
            self.origin[param] = getattr(self.obj, param)
            setattr(self.obj, param, value)

    def __exit__(self, type, value, traceback):
        for param, value in self.origin.items():
            setattr(self.obj, param, value)


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

def create_permissions():
    REGISTRY.reload()
    for session_cls in REGISTRY.values():
        permission, created = session_cls.create_permission()

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
        hostname = f'host_{i}_{label}'
        Host.objects.create(
            name=hostname,
            hostname=hostname,
            username='user' + label)

def create_hostgroups():
    for name in ['group-one', 'group-two']:
        HostGroup.objects.create(name=name)

    i = 0
    for host in Host.objects.all():
        i += 1
        if i % 2:
            host.groups.add(HostGroup.objects.get(name='group-one'))
        if i % 3:
            host.groups.add(HostGroup.objects.get(name='group-two'))

def create_players():
    for host in Host.objects.all():
        server = Server.objects.create(host=host, hostname=host.hostname)
        AnySystem.objects.create(server=server)

def create_test_data():
    create_users()
    create_permissions()
    create_hosts()
    create_hostgroups()
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

def create_session(session_cls, minkeobj, data=None):
    minkesession = create_minkesession(minkeobj, session_cls)
    host = minkeobj.get_host()
    hostname = host.hostname or host.name
    config = FabricConfig(host, session_cls, data or dict())
    con = Connection(hostname, host.username, host.port, config=config)
    return session_cls(con, minkesession)
