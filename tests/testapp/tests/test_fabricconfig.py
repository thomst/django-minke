from django.test import TestCase
from django.forms import ValidationError

from minke.fabrictools import FabricConfig
from minke.models import Host
from minke.exceptions import InvalidMinkeSetup

from ..sessions import DummySession
from .utils import create_hosts
from .utils import create_hostgroups
from .utils import AlterSettings
from .utils import AlterObject


YAML_CONFIG = """
run:
    pty: true
    hide: false
foo:
    bar: 123
foobar: 456
"""


class FabricConfigTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_hosts()
        create_hostgroups()

    def setUp(self):
        self.host = Host.objects.get(pk=1)

    def test_runtime_data(self):
        # Test with runtime-data.
        runtime_data = {'foo': 'bar', 'fabric_run_foo': 'bar'}
        config = FabricConfig(self.host, DummySession, runtime_data)
        self.assertTrue(hasattr(config, 'session_data'))
        self.assertTrue(hasattr(config.session_data, 'foo'))
        self.assertEqual(config.session_data.foo, 'bar')
        self.assertTrue(hasattr(config.run, 'foo'))
        self.assertEqual(config.run.foo, 'bar')

        # Test with invalid runtime-config.
        runtime_data = {'fabric_foo_bar': 'bar'}
        self.assertRaises(InvalidMinkeSetup, FabricConfig, self.host, DummySession, runtime_data)

    def test_global_data(self):
        with AlterSettings(FABRIC_RUN_PTY=True):
            config = FabricConfig(self.host, DummySession, dict())
            self.assertTrue(config.run.pty)

        # Overwrite required default.
        with AlterSettings(FABRIC_RUN_HIDE=False):
            config = FabricConfig(self.host, DummySession, dict())
            self.assertTrue(config.run.hide)

        # Test with invalid global-config.
        with AlterSettings(FABRIC_THIS_IS_NO_CONFIG=False):
            self.assertRaises(InvalidMinkeSetup, FabricConfig, self.host, DummySession, dict())

    def test_session_data(self):
        session_data = dict(invoke_config={'foo': 'bar'})
        session_cls = type('Dummy', (DummySession,), session_data)
        config = FabricConfig(self.host, session_cls, dict())
        self.assertTrue(hasattr(config, 'foo'))
        self.assertEqual(config.foo, 'bar')

    def test_host_config(self):
        # Invalid yaml-data.
        with AlterObject(self.host, config='foobar'):
            self.assertRaises(ValidationError, self.host.save)

        # With valid yaml-data.
        with AlterObject(self.host, config=YAML_CONFIG):
            config = FabricConfig(self.host, DummySession, dict())
            self.assertTrue(config.run.pty)
            self.assertTrue(config.run.hide) # Not overwritten by yaml data
            self.assertTrue(hasattr(config, 'foo'))
            self.assertTrue(hasattr(config.foo, 'bar'))
            self.assertEqual(config.foo.bar, 123)

    def test_hostgroup_config(self):
        hostgroup = self.host.groups.all()[0]

        # Invalid yaml-data.
        with AlterObject(hostgroup, config='foobar'):
            self.assertRaises(ValidationError, hostgroup.save)

        # With valid yaml-data.
        with AlterObject(hostgroup, config=YAML_CONFIG):
            hostgroup.save()
            config = FabricConfig(self.host, DummySession, dict())
            self.assertTrue(config.run.pty)
            self.assertTrue(config.run.hide) # Not overwritten by yaml data
            self.assertTrue(hasattr(config, 'foo'))
            self.assertTrue(hasattr(config.foo, 'bar'))
            self.assertEqual(config.foo.bar, 123)
        hostgroup.save()
