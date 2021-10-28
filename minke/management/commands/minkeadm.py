# -*- coding: utf-8 -*-

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from ...models import Host
from ...models import MinkeSession
from ...sessions import REGISTRY


class Command(BaseCommand):
    help = 'Some cleanup-actions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-L', '--release-locks',
            action='store_true',
            help='Release locks on all hosts.')
        parser.add_argument(
            '-C', '--clear-current-sessions',
            action='store_true',
            help='Set current to False for all sessions.')
        parser.add_argument(
            '-S', '--clear-all-sessions',
            action='store_true',
            help='Delete all sessions.')
        parser.add_argument(
            '-s', '--list-sessions',
            action='store_true',
            help='List available sessions.')
        parser.add_argument(
            '-p', '--create-run-permission',
            help='Create permission for a session.')
        parser.add_argument(
            '-P', '--create-run-permissions',
            action='store_true',
            help='Create permissions for all sessions.')
        parser.add_argument(
            '-D', '--delete-run-permissions',
            action='store_true',
            help='Delete all run-permissions.')

    def handle(self, *args, **options):
        if options['release_locks']:
            print(Host.objects.update(lock=None))

        if options['clear_current_sessions']:
            print(MinkeSession.objects.update(current=False))

        if options['clear_all_sessions']:
            print(MinkeSession.objects.all().delete())

        if options['list_sessions']:
            REGISTRY.reload()
            for session_cls in REGISTRY.values():
                print(session_cls.__name__)

        if options['create_run_permission']:
            REGISTRY.reload()
            session = options['create_run_permission']
            try:
                session_cls = REGISTRY[session]
            except KeyError:
                msg = 'Unknown session: {}'.format(session)
                raise CommandError(msg)
            permission, created = session_cls.create_permission()
            if created:
                print('Created permission: {}'.format(permission))

        if options['create_run_permissions']:
            REGISTRY.reload()
            for session_cls in REGISTRY.values():
                if not session_cls.auto_permission:
                    continue
                permission, created = session_cls.create_permission()
                if created:
                    print('Created permission: {}'.format(permission))

        if options['delete_run_permissions']:
            print(Permission.objects.filter(codename__startswith='run_').delete())

