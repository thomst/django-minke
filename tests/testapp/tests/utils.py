# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import getpass

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission

from minke.models import Host
from minke.models import BaseSession
from minke.models import BaseMessage
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
    change_perm = Permission.objects.get(name='Can change host')
    anyuser.user_permissions.add(change_perm)

def create_hosts():
    # create a localhost with the current user
    # this might have a chance to be accessible via ssh
    user = getpass.getuser()
    host = Host.objects.create(
        hostname='localhost',
        host='localhost',
        user=user)

    # create some dummy-hosts as well
    for i in range(20):
        label = 'label' + str(i % 4) * 3
        hostname = 'host_{}_{}'.format(str(i), label)
        Host.objects.create(
            hostname=hostname,
            host=hostname,
            user='user' + label)

def create_players():
    for host in Host.objects.all():
        server = Server.objects.create(host=host, hostname=host.hostname)
        AnySystem.objects.create(server=server)

def create_test_data():
    create_users()
    create_hosts()
    create_players()

def create_session(player, session_cls=DummySession, user='admin',
    current=True, status='success', proc_status='done'):
    content_type = ContentType.objects.get_for_model(player.__class__)
    user = User.objects.get(username=user)
    return BaseSession(
        object_id=player.id,
        content_type=content_type,
        session_name=session_cls.__name__,
        user=user,
        current=current,
        status=status,
        proc_status=proc_status)

def create_message(session, text, html=None, level='info'):
    return BaseMessage(
        session=session,
        text=text,
        html=html or text,
        level=level)
