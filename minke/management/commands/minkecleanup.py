# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.core.management.base import BaseCommand

from ...models import Host
from ...models import BaseSession


class Command(BaseCommand):
    help = 'Some cleanup functions.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--release-locks',
            action='store_true',
            help='Release locks on all hosts.')
        parser.add_argument(
            '--clear-current-sessions',
            action='store_true',
            help='Set current to False for all sessions.')
        parser.add_argument(
            '--clear-sessions',
            action='store_true',
            help='Delete all sessions.')

    def handle(self, *args, **options):
        if options['release_locks']:
            Host.objects.release_lock()

        elif options['clear_current_sessions']:
            BaseSession.objects.update(current=False)

        elif options['clear_sessions']:
            BaseSession.objects.delete()

        else:
            self.print_help('manage.py', 'minkecleanup')
