(function($) {

var sessions = {};
var interval = 400;
var error_msg = 'minkeapi-error: ';
var summary_url = null;
var baseurl = window.location.protocol + '//'
            + window.location.host
            + '/minkeapi/sessions/?id__in=';

class Session {
    constructor(session_el) {
        this.id = $(session_el).data('id');
        this.session = $(session_el);
        this.minkeobj = $(session_el).prev('tr');
    }
    update(session) {
        if (session.proc_status != this.session.attr('data-proc-status')) {
            this.updateProcStatus(session);
        }
        if (session.messages.length > this.session.attr('data-msg-count')) {
            this.updateMessages(session);
        }
        if (session.is_done) {
            this.setStatus(session);
            delete sessions[session.id];
        }
    }
    updateProcStatus(session) {
        this.session.attr('data-proc-status', session.proc_status);
        this.session.find('div.session_proc_info > span').hide()
                    .text(session.proc_info).fadeIn();
        this.minkeobj.removeClass('initialized running stopping');
        this.minkeobj.addClass(session.proc_status);
        this.session.removeClass('initialized running stopping');
        this.session.addClass(session.proc_status);
    }
    updateMessages(session) {
        var that = this;
        session.messages.slice(this.session.attr('data-msg-count'))
            .forEach(function(msg) {that.addMessage(msg)});
        this.session.attr('data-msg-count', session.messages.length);
    }
    addMessage(msg) {
        var li = $('<li>' + msg.html + '</li>').addClass(msg.level).hide();
        this.session.find('ul').append(li);
        li.slideDown('fast').scrollTop(li[0].scrollHeight);
    }
    setStatus(session) {
        this.session.addClass(session.session_status);
        this.minkeobj.addClass(session.session_status);
    }
}

function updateSummary() {
    var updateSum = function(html){$('span.session-summary').replaceWith(html)}
    $.getJSON(summary_url, updateSum).fail(ajaxFail)
}

function getJson (url) {
    $.getJSON(url, processJson).fail(ajaxFail).done(updateSummary).done(run)
}

function processJson(json) {
    $.each(json, function(i, session) {sessions[session.id].update(session)})
}

function ajaxFail(result) {
    console.log(error_msg + result.responseJSON.detail)
}

function stopSession() {
    var url = baseurl + $(this).parent().parent().next().data('id');
    $.ajax({url: url, method: 'PUT'}).fail(ajaxFail)
}

function stopAllSessions() {
    var url = baseurl + $.map(sessions, function(session, i) {return session.id});
    $('table.sessions').addClass('stopping');
    $.ajax({url: url, method: 'PUT'}).fail(ajaxFail)
}

function toggleAllMessageLists() {
    var msglists = $('tr.session ul.messagelist');
    var msgtoggles = $('tr.session a.message-toggle');
    var button = $(this);
    if (button.text() == button.data('show')) {
        msglists.slideDown('fast');
        button.text(button.data('hide'));
        msgtoggles.text(button.data('hide'))
    } else {
        msglists.slideUp('fast');
        button.text(button.data('show'));
        msgtoggles.text(button.data('show'))
    }
}

function toggleMessageList() {
    var button = $(this);
    var msglist = $(this).parent().next('ul.messagelist');
    if (button.text() == button.data('show')) {
        msglist.slideDown('fast');
        button.text(button.data('hide'));
    } else {
        msglist.slideUp('fast');
        button.text(button.data('show'));
    }
}

function run() {
    // get session-ids
    var session_ids = $.map(sessions, function(session, i) {return session.id});

    // if we have sessions left... process
    if (session_ids.length) {
        var url = baseurl + session_ids;
        window.setTimeout(getJson, interval, url);
    } else {
        $('#action-toggle').prop('disabled', false);
        $('#result_list').removeClass('running', 'stopping');
    }
}

$(document).ready(function () {

    // initiate message-toggles
    $('div.session_select a.message-toggle').click(toggleAllMessageLists);
    $('tr.session a.message-toggle').click(toggleMessageList);

    // initialize session-objects...
    $('tr.session.initialized,tr.session.running,tr.session.stopping').each(
        function(i, e) {sessions[$(e).data('id')] = new Session(e)}
        );

    // do we work with sessions?
    if (!$.isEmptyObject(sessions)) {

        // setup header-csrf-token - to get it work with django-rest-framework
        $.ajaxSetup({headers: {'X-CSRFToken': $("[name=csrfmiddlewaretoken]").val()}});

        // prepare session-stopper...
        // FIXME: do not block the select-all box. Just make sure items with
        // running sessions won't be selected by it.
        var stop = $('<div></div>').addClass('session_stopper').click(stopSession);
        var stopall = $('<div></div>').addClass('session_stopper').click(stopAllSessions);
        $('td.action-checkbox').append(stop);
        $('th.action-checkbox-column').prepend(stopall);

        // deactivate action-toggle and add running-class
        $('#action-toggle').prop('disabled', true);
        $('#result_list').addClass('running');

        // get all session-ids
        var session_ids = [];
        $('tr.session').each(function(i, e) {session_ids.push($(e).data('id'))});

        // build the summary-url
        summary_url = baseurl + session_ids + '&summary=1';

        // start processing
        run();
    }
});

})(django.jQuery);
