# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from ...models import Host
from ...models import BaseSession


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
            '-S', '--clear-sessions',
            action='store_true',
            help='Delete all sessions.')

    def handle(self, *args, **options):
        if options['release_locks']:
            Host.objects.update(lock=None)
            return
        elif options['clear_current_sessions']:
            BaseSession.objects.update(current=False)
            return
        elif options['clear_sessions']:
            BaseSession.objects.all().delete()
            return
