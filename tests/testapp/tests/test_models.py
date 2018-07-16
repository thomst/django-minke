# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.test import TestCase

from minke.models import Host, MinkeModel
from minke.exceptions import InvalidMinkeSetup
from ..models import Server, AnySystem
from .utils import create_multiple_hosts
from .utils import create_testapp_player


class MinkeModelTest(TestCase):

    def setUp(self):
        create_multiple_hosts()
        create_testapp_player()
        self.anysystem = AnySystem.objects.get(id=1)
        self.server = self.anysystem.server
        self.host = self.server.host

    def test_01_get_host(self):
        server_host = self.server.get_host()
        system_host = self.anysystem.get_host()
        self.assertTrue(type(server_host) == Host)
        self.assertTrue(type(system_host) == Host)

        # invalid MinkeModel
        class InvalidModel(MinkeModel):
            HOST_LOOKUP = 'no__host'

        # host-lookup should fail with InvalidMinkeSetup
        invalid_model = InvalidModel()
        self.assertRaises(InvalidMinkeSetup, invalid_model.get_host)

    def test_02_lock_host(self):
        host_id = self.host.id
        self.assertTrue(Host.objects.get_lock(id=host_id))
        self.assertFalse(Host.objects.get_lock(id=host_id))
        Host.objects.release_lock(id=host_id)
        self.assertFalse(self.host.locked)
