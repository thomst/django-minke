from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.contrib.admin.options import IncorrectLookupParameters

from ...engine import process
from ...messages import ConsoleMessenger
from ...sessions import registry


class FilterArgumentError(Exception):
    pass


class Command(BaseCommand):
    help = 'Minke-Api (dev)'

    def usage(self, error_msg=None):
        if error_msg: print 'ERROR:', error_msg
        self.print_help('manage.py', 'minke')

    def get_queryset(self, model_cls, options):
        if options['url_query']:
            return self.get_changelist_queryset(model_cls, options['url_query'])
        else:
            return model_cls.objects.all()

    def get_changelist_queryset(self, model_cls, url_query):
        from django.contrib import admin
        from django.test import RequestFactory
        from django.core.urlresolvers import reverse
        from django.contrib.sessions.middleware import SessionMiddleware

        # get a request-instance with session-middleware
        model_label = model_cls._meta.label_lower.replace('.', '_')
        url_pattern = 'admin:' + model_label + '_changelist'
        url = reverse(url_pattern)
        url += '?' + url_query
        request_factory = RequestFactory()
        request = request_factory.get(url)
        middleware = SessionMiddleware()
        middleware.process_request(request)
        request.session.save()

        # get a changelist-class
        modeladmin = admin.site._registry[model_cls]
        # modeladmin = modeladmin_cls(model_cls, admin.site)
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
        except IncorrectLookupParameters:
            raise IncorrectLookupParameters

        # prepared to get the queryset
        return changelist.get_queryset(request)

    def filter_queryset(self, queryset, options):
        return queryset

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available sessions.')
        parser.add_argument(
            '-s',
            '--silent',
            action='store_true',
            help='Skip output of inconspicuous players.')
        parser.add_argument(
            '--no-prefix',
            action='store_true',
            help='Hide prefix.')
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
            '-o',
            '--offset',
            type=int,
            help='Offset')
        parser.add_argument(
            '-l',
            '--limit',
            type=int,
            help='Limit')

    def handle(self, *args, **options):
        session = options['session']
        model = options['model']

        # No session is given nor are we asked to list sessions.
        if not options['list'] and not session:
            self.usage()
            return

        # List available session-classes
        if options['list']:
            for session_cls in registry:
                print session_cls.__name__
            return

        # Do we have a valid session-class?
        session_cls = next((s for s in registry if s.__name__ == session), None)
        if not session_cls:
            self.usage('Unknown session: {}'.format(session))
            return

        # Do we have a valid model?
        if model:
            model_cls = next((m for m in session_cls.models if m.__name__ == model), None)
            if not model_cls:
                msg = 'Invalid model for {}: {}'.format(session_cls, model)
                self.usage(msg)
                return
        elif len(session_cls.models) > 1:
            msg = 'No model specified, but {} could be run with different models: {}'.format(
                session_cls,
                session_cls.models)
            self.usage(msg)
            return
        else:
            model_cls = session_cls.models[0]

        # get queryset
        try:
            queryset = self.get_queryset(model_cls, options)
        except IncorrectLookupParameters as error:
            self.usage('Incorrect url-query. {}'.format(error))
            return

        # filter queryset
        try:
            queryset = self.filter_queryset(queryset, options)
        except FilterArgumentError as error:
            self.usage(str(error))
            return

        # slicing the queryset
        offset = options['offset']
        limit = options['limit']
        if type(offset) is type(limit) is int: limit = offset + limit
        queryset = queryset[offset:limit]

        # initialize the messenger
        messenger = ConsoleMessenger(
            silent=options['silent'],
            no_color=options['no_color'],
            no_prefix=options['no_prefix'])

        # go for it...
        process(session_cls, queryset, messenger, dict())
