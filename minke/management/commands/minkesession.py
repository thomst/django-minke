# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.contrib.admin.options import IncorrectLookupParameters
from django.core.exceptions import FieldError
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings

from ...engine import process
from ...sessions import registry
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
            '--url-query',
            help='Filter objects by url-query.')
        parser.add_argument(
            '--form-data',
            help='Key-value-pairs used for the session-form.')
        parser.add_argument(
            '--offset',
            type=int,
            help='Offset')
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit')
        parser.add_argument(
            '--list-sessions',
            action='store_true',
            help='List sessions. But do nothing.')
        parser.add_argument(
            '--list-players',
            action='store_true',
            help='List players. But do nothing.')

    def print_usage_and_quit(self, error=None):
        if error:
            print '\033[1;31m' + '[ERROR] ' + unicode(error) + '\033[0m'
            print
        self.print_help('manage.py', 'minkesessions')
        quit(1 if error else 0)

    def get_user(self, options):
        user = settings.MINKE_CLI_USER
        try:
            user = User.objects.get(username=user)
        except User.DoesNotExist:
            msg = 'MINKE_CLI_USER does not exist: {user}'
            raise InvalidMinkeSetup(msg)
        return user

    def get_session_cls(self, options):
        session = options['session']
        if not session:
            msg = 'Missing session-argument'
            raise CommandError(msg)

        session_cls = item_by_attr(registry, '__name__', session)
        if not session_cls:
            msg = 'Unknown session: {}'.format(session)
            raise CommandError(msg)

        return session_cls

    def get_model_cls(self, session_cls, options):
        model = options['model']

        if model:
            model_cls = item_by_attr(session_cls.models, '__name__', model)
            if not model_cls:
                msg = 'Invalid model for {}: {}'.format(session_cls.__name__, model)
                raise CommandError(msg)
        elif len(session_cls.models) == 1:
            model_cls = session_cls.models[0]
        else:
            msg = 'You need to specify a model to run {} with.'
            msg = msg.format(session_cls, session_cls.models)
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
        from django.core.urlresolvers import reverse
        from django.contrib.sessions.middleware import SessionMiddleware

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
        form_cls = session_cls.FORM
        if not session_cls.FORM: return dict()

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
                if field.help_text: print field.help_text
                form_data[field.name] = raw_input(field.name + ': ')
            form = form_cls(form_data)
            while not form.is_valid():
                for field, error in form.errors.items():
                    if error: print error[0]
                    form_data[field] = raw_input(field + ': ')
                form = form_cls(form_data)

        # got valid form-data now
        return form.cleaned_data

    def handle(self, *args, **options):
        if options['list_sessions']:
            for session_cls in registry:
                print session_cls.__name__
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
            for obj in queryset: print obj
        else:
            process(session_cls, queryset, form_data, user, True)