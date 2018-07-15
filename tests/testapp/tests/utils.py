import getpass

from minke.models import Host
from ..models import Server, AnySystem


def setUpTestData():
    user = getpass.getuser()
    Host.objects.create(
        hostname='localhost',
        host='localhost',
        user=user)
