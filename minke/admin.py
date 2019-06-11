# -*- coding: utf-8 -*-
from pydoc import locate

from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin import helpers
from django.contrib import messages
from django.contrib import admin
from django.utils.translation import gettext as _
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.core.exceptions import PermissionDenied

from . import settings
from . import engine
from .sessions import REGISTRY
from .models import MinkeSession
from .forms import MinkeForm
from .forms import SessionSelectForm


class MinkeAdmin(admin.ModelAdmin):
    change_form_template = 'minke/change_form.html'
    change_list_template = 'minke/change_list.html'
    session_select_form = SessionSelectForm

    def get_changelist_instance(self, request):
        try:
            return super().get_changelist_instance(request)
        except AttributeError:
            # prior django-2.0 get_changelist_instance does not exists
            list_display = self.get_list_display(request)
            list_display_links = self.get_list_display_links(request, list_display)
            list_filter = self.get_list_filter(request)
            search_fields = self.get_search_fields(request)
            list_select_related = self.get_list_select_related(request)

            # Check actions to see if any are available on this changelist
            actions = self.get_actions(request)
            if actions:
                # Add the action checkboxes if there are any actions available.
                list_display = ['action_checkbox'] + list(list_display)

            ChangeList = self.get_changelist(request)
            return ChangeList(
                request, self.model, list_display,
                list_display_links, list_filter, self.date_hierarchy,
                search_fields, list_select_related, self.list_per_page,
                self.list_max_show_all, self.list_editable, self)

    def permit_session(self, request, session):
        permitted = request.user.has_perms(session.permissions)
        permitted &= self.model in session.work_on
        return permitted

    def get_session_options(self, request):
        """
        Get sessions  valid for the user and model of this request.
        Return a list of tuples like with session-name and -verbose-name.
        """
        REGISTRY.reload()
        sessions = [(None, '---------')]

        # filter sessions in respect to their permissions- and work_on-attrs
        for session in REGISTRY.values():
            if not self.permit_session(request, session): continue
            sessions.append((session.__name__, session.verbose_name))
        return sessions

    def get_session_select_form(self, request, data=None):
        """
        Return SessionSelectForm-instance with apropriate session-choices.
        """
        form = self.session_select_form(data or dict())
        form.fields['session'].choices = self.get_session_options(request)
        return form

    def get_current_sessions(self, request):
        """
        Return current sessions - those that should be rendered for this request.
        """
        # Getting the changelist should work since an IncorrectLookupParameters
        # would have been already raised.
        cl = self.get_changelist_instance(request)
        queryset = cl.get_queryset(request)
        sessions = MinkeSession.objects.get_currents(request.user, queryset)
        return sessions.prefetch_related('messages')

    def get_session_cls(self, request):
        session_name = request.POST.get('session', None)
        if not session_name:
            msg = _("No session were selected that should be run.")
            self.message_user(request, msg, messages.WARNING)
            return None
        else:
            REGISTRY.reload()
            return REGISTRY.get(session_name, None)

    def run_sessions(self, request, session_cls, queryset, force_confirm=False):
        wait = session_cls.wait_for_execution
        confirm = force_confirm or session_cls.confirm
        fabric_config = None
        session_data = dict()
        session_form_cls = session_cls.get_form()
        fabric_form_cls = None
        render_params = dict()

        # import fabric-form if needed...
        if settings.MINKE_FABRIC_FORM:
            fabric_form_cls = locate(settings.MINKE_FABRIC_FORM)
            if not fabric_form_cls:
                msg = '{} could not be loaded'.format(settings.MINKE_FABRIC_FORM)
                raise InvalidMinkeSetup(msg)

        # Do we have to work with a minke-form?
        if confirm or fabric_form_cls or session_form_cls:

            # Do we come from a minke-form?
            from_form = request.POST.get('minke_form', False)
            if from_form:
                minke_form = MinkeForm(request.POST, auto_id=False)
                valid = minke_form.is_valid()
                form_data = [request.POST]
            else:
                minke_form = MinkeForm(initial=request.POST, auto_id=False)
                valid = False
                form_data = list()

            # initiate fabric-form
            if fabric_form_cls:
                fabric_form = fabric_form_cls(*form_data, auto_id=False)
                render_params['fabric_form'] = fabric_form
                valid &= fabric_form.is_valid()

            # initiate session-form
            if session_form_cls:
                session_form = session_cls.form(*form_data, auto_id=False)
                render_params['session_form'] = session_form
                valid &= session_form.is_valid()

            # render minke-form first time or if form-data is invalid
            if not from_form or not valid:
                render_params['title'] = session_cls.verbose_name,
                render_params['minke_form'] = minke_form
                render_params['objects'] = queryset
                render_params['object_list'] = confirm
                return render(request, 'minke/minke_form.html', render_params)

            else:
                # collect form-data
                if fabric_form_cls: fabric_config = fabric_form.cleaned_data
                if session_form_cls: session_data = session_form.cleaned_data

        # lets rock...
        engine.process(session_cls, queryset, session_data, request.user,
                       fabric_config=fabric_config, wait=wait)

    def changelist_view(self, request, extra_context=None):
        """
        Extend the modeladmin-changelist_view by session-processing.
        """
        # Does the request something to do with sessions at all?
        if ('run_sessions' not in request.POST
        and 'clear_sessions' not in request.POST):
            return super().changelist_view(request, extra_context)

        # setup
        force_confirm = False
        selected = request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
        select_across = bool(int(request.POST.get('select_across', 0)))
        session_form = self.get_session_select_form(request, request.POST)
        redirect_url = request.get_full_path()

        try:
            cl = self.get_changelist_instance(request)
        except IncorrectLookupParameters:
            # Since we are coming from a form-subimission our url-query
            # should be valid. So this shouldn't happen at all.
            return HttpResponseRedirect(redirect_url)

        # Do we have any selected items? Else leave a message and redirect.
        if not selected:
            msg = _("No items selected.")
            self.message_user(request, msg, messages.WARNING)
            return HttpResponseRedirect(redirect_url)

        # get queryset
        queryset = cl.get_queryset(request)
        if not select_across:
            queryset = queryset.filter(pk__in=selected)

        # clear session-infos for selected items
        if 'clear_sessions' in request.POST:
            MinkeSession.objects.clear_currents(request.user, queryset)
            return HttpResponseRedirect(redirect_url)

        # run sessions
        elif 'run_sessions' in request.POST:

            # get session_cls.
            session_form = self.get_session_select_form(request, request.POST)
            if session_form.is_valid():
                session_name = session_form.cleaned_data['session']
                REGISTRY.reload()
                session_cls = REGISTRY[session_name]
            else:
                msg = _("No session selected.")
                self.message_user(request, msg, messages.WARNING)
                return HttpResponseRedirect(redirect_url)

            # Do the user have permissions to run this session-type?
            if not self.permit_session(request, session_cls):
                raise PermissionDenied

            # If this is a select-across-request, we force confirmation
            # and redirect to a show-all-changelist.
            if select_across:
                force_confirm = True
                delimiter = '&' if '?' in redirect_url else '?'
                redirect_url += delimiter + 'all='

            # run_sessions might want to render a minke- or session-form
            response = self.run_sessions(request, session_cls, queryset, force_confirm)
            return response or HttpResponseRedirect(redirect_url)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """
        Add session-history-view to the changeform-view.
        """
        # Has been asked for a session-history?
        if object_id and 'session_history' in request.GET:
            ct = ContentType.objects.get_for_model(self.model)
            sessions = MinkeSession.objects.filter(
                minkeobj_type=ct,
                minkeobj_id=object_id,
                user=request.user,
                proc_status__in=('succeeded', 'stopped', 'failed')
                )[:int(request.GET['session_history'])]
            extra_context = dict(
                sessions=sessions,
                use_commands=bool(request.GET.get('use_commands', False)),
                show_session_date=True)

        # call super-changeform-view with our extra-context
        return super().changeform_view(request, object_id, form_url, extra_context)
