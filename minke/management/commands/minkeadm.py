# -*- coding: utf-8 -*-
import sys

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from ...models import Host
from ...models import MinkeSession


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
            print(Host.objects.update(lock=None))
        if options['clear_current_sessions']:
            print(MinkeSession.objects.update(current=False))
        if options['clear_sessions']:
            print(MinkeSession.objects.all().delete())
