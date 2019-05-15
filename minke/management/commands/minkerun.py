# -*- coding: utf-8 -*-
import sys

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.contrib.admin.options import IncorrectLookupParameters
from django.core.exceptions import FieldError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate

from minke import settings
from ...engine import process
from ...sessions import REGISTRY
from ...utils import item_by_attr
from ...exceptions import InvalidMinkeSetup


class Command(BaseCommand):
    help = 'Run minke-sessions.'

    def add_arguments(self, parser):
        parser.add_argument(
            'session',
            nargs='?',
            help='Session to work with.')
        parser.add_argument(
            'model',
            nargs='?',
            help='Model to work with. (Only neccessary if a session '
                 'could be used on multiple models)')
        parser.add_argument(
            '-u', '--url-query',
            help='Filter objects by url-query.')
        parser.add_argument(
            '-f', '--form-data',
            help='Key-value-pairs used for the session-form.')
        parser.add_argument(
            '-o', '--offset',
            type=int,
            help='Offset')
        parser.add_argument(
            '-l', '--limit',
            type=int,
            help='Limit')
        parser.add_argument(
            '-s', '--list-sessions',
            action='store_true',
            help='List sessions. But do nothing.')
        parser.add_argument(
            '-p',
            '--list-players',
            action='store_true',
            help='List players. But do nothing.')

    def print_usage_and_quit(self, error=None):
        if error:
            print('\033[1;31m' + '[ERROR] ' + str(error) + '\033[0m')
            print()
        self.print_help('manage.py', 'minkesessions')
        sys.exit(1 if error else 0)

    def get_user(self, options):
        user = settings.MINKE_CLI_USER
        try:
            user = User.objects.get(username=user)
        except User.DoesNotExist:
            msg = 'MINKE_CLI_USER does not exist: {}'.format(user)
            raise InvalidMinkeSetup(msg)
        return user

    def get_session_cls(self, options):
        session = options['session']
        if not session:
            msg = 'Missing session-argument'
            raise CommandError(msg)

        try:
            session_cls = REGISTRY[session]
        except KeyError:
            msg = 'Unknown session: {}'.format(session)
            raise CommandError(msg)

        return session_cls

    def get_model_cls(self, session_cls, options):
        model = options['model']

        if model:
            model_cls = item_by_attr(session_cls.work_on, '__name__', model)
            if not model_cls:
                msg = 'Invalid model for {}: {}'.format(session_cls.__name__, model)
                raise CommandError(msg)
        elif len(session_cls.work_on) == 1:
            model_cls = session_cls.work_on[0]
        else:
            msg = 'You need to specify a model to run {} with.'
            msg = msg.format(session_cls, session_cls.work_on)
            raise CommandError(msg)

        return model_cls

    def get_queryset(self, model_cls, options):
        if options['url_query']:
            queryset = self.get_changelist_queryset(model_cls, options)
        else:
            queryset = model_cls.objects.all()

        # slicing the queryset
        offset = options['offset']
        limit = options['limit']
        if type(offset) is type(limit) is int:
            limit = offset + limit

        try:
            queryset = queryset[offset:limit]
        except AssertionError:
            msg = 'Invalid slicing: [{}:{}]'.format(offset, limit)
            raise CommandError(msg)

        # FIXME: OFFSET- and LIMIT-statements does not work in subqueries,
        # which we use to get the host-query. Therefor we need a workaround:
        if type(offset) is int or type(limit) is int:
            ids = list(queryset.values_list('id', flat=True))
            queryset = model_cls.objects.filter(id__in=ids)

        return queryset

    def get_changelist_queryset(self, model_cls, options):
        from django.contrib import admin
        from django.test import RequestFactory
        from django.urls import reverse

        url_query = options['url_query']

        # get a request-instance with session-middleware
        model_label = model_cls._meta.label_lower.replace('.', '_')
        url_pattern = 'admin:' + model_label + '_changelist'
        url = reverse(url_pattern) + '?' + url_query
        request_factory = RequestFactory()
        request = request_factory.get(url)
        request.user = self.get_user(options)

        # get a changelist-class
        modeladmin = admin.site._registry[model_cls]

        # get the changelist-instance the django-2-way
        try:
            try:
                changelist = modeladmin.get_changelist_instance(request)
            except (IncorrectLookupParameters, FieldError):
                msg = 'Invalid url-query: {}'.format(url_query)
                raise CommandError(msg)

        # fallback for django-1.11
        except AttributeError:
            changelist_cls = modeladmin.get_changelist(request)

            # get a changelist-instance
            list_display = modeladmin.get_list_display(request)
            list_display_links = modeladmin.get_list_display_links(request, list_display)
            list_filter = modeladmin.get_list_filter(request)
            search_fields = modeladmin.get_search_fields(request)
            list_select_related = modeladmin.get_list_select_related(request)
            try:
                changelist = changelist_cls(
                    request, modeladmin.model, list_display,
                    list_display_links, list_filter, modeladmin.date_hierarchy,
                    search_fields, list_select_related, modeladmin.list_per_page,
                    modeladmin.list_max_show_all, modeladmin.list_editable, modeladmin)
            except (IncorrectLookupParameters, FieldError):
                msg = 'Invalid url-query: {}'.format(url_query)
                raise CommandError(msg)

        # prepared to get the queryset
        return changelist.get_queryset(request)

    def get_form_data(self, session_cls, options):
        form_cls = session_cls.form
        if not session_cls.form: return dict()

        # form-data passed via command-line?
        form_data = options['form_data']
        if form_data:
            try:
                form_data = eval('dict({})'.format(form_data))
                form = form_cls(form_data)
                assert form.is_valid()
            except AssertionError:
                msg = 'Invalid form-data: {}\n'.format(form_data)
                for field, error in form.errors.items():
                    msg += '{}: {}'.format(field, error[0])
                raise CommandError(msg)
            except Exception as error:
                msg = 'Invalid form-data: {}\n{}'.format(form_data, error)
                raise CommandError(msg)

        # otherwise prompt for it
        else:
            form = form_cls()
            form_data = dict()
            fields = form.visible_fields()
            for field in fields:
                if field.help_text: print(field.help_text)
                form_data[field.name] = input(field.name + ': ')
            form = form_cls(form_data)
            while not form.is_valid():
                for field, error in form.errors.items():
                    if error: print(error[0])
                    form_data[field] = input(field + ': ')
                form = form_cls(form_data)

        # got valid form-data now
        return form.cleaned_data

    def handle(self, *args, **options):
        REGISTRY.reload()

        if options['list_sessions']:
            for session_cls in REGISTRY.values():
                print(session_cls.__name__)
            return

        try:
            user = self.get_user(options)
        except CommandError as err:
            self.print_usage_and_quit(err)

        try:
            session_cls = self.get_session_cls(options)
        except CommandError as err:
            self.print_usage_and_quit(err)

        try:
            model_cls = self.get_model_cls(session_cls, options)
        except CommandError as err:
            self.print_usage_and_quit(err)

        try:
            queryset = self.get_queryset(model_cls, options)
        except CommandError as err:
            self.print_usage_and_quit(err)

        try:
            form_data = self.get_form_data(session_cls, options)
        except CommandError as err:
            self.print_usage_and_quit(err)

        if options['list_players']:
            for obj in queryset: print(obj)
        else:
            process(session_cls, queryset, form_data, user, console=True)
