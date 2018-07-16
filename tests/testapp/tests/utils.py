import getpass

from django.contrib.auth.models import User

from minke.models import Host
from ..models import Server, AnySystem


def create_supersuer():
    User.objects.create_superuser(
        'admin',
        'admin@testapp.org',
        'adminpassword')

def create_localhost():
    user = getpass.getuser()
    Host.objects.create(
        hostname='localhost',
        host='localhost',
        user=user)

def create_multiple_hosts():
    for i in range(20):
        label = 'label' + str(i % 4) * 3
        hostname = 'host_{}_{}'.format(str(i), label)
        Host.objects.create(
            hostname=hostname,
            host=hostname,
            user='user' + label)

def create_testapp_player():
    for host in Host.objects.all():
        server = Server.objects.create(host=host, hostname=host.hostname)
        AnySystem.objects.create(server=server)
