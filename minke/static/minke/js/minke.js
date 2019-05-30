(function($) {

sessions = {};
var interval = 400;
var error_msg = 'minkeapi-error: ';
var end_statuus = ['succeeded', 'stopped', 'canceled', 'failed']
var baseurl = window.location.protocol + '//'
            + window.location.host
            + '/minkeapi/sessions/'

class Session {
    constructor(session_el) {
        this.id = $(session_el).data('id');
        this.session = $(session_el);
        this.minkeobj = $(session_el).prev('tr');
    }
    update(session) {
        if (session.proc_status != this.session.data('procStatus')) {
            this.updateProcStatus(session);
        }
        if (session.messages.length > this.session.data('msgCount')) {
            this.updateMessages(session);
        }
        if ($.inArray(session.proc_status, end_statuus) > -1) {
            this.setStatus(session);
            delete sessions[session.id];
        }
    }
    updateProcStatus(session) {
        this.session.data('procStatus', session.proc_status);
        this.session.find('span.session_proc_info').text(session.proc_info)
            .css('fontSize', '110%').animate({fontSize: '100%'}, 'fast');
        this.minkeobj.removeClass(['initialized', 'running']);
        this.minkeobj.addClass(session.proc_status);
        this.session.removeClass(['initialized', 'running']);
        this.session.addClass(session.proc_status);
    }
    updateMessages(session) {
        var that = this;
        // if (this.session.data('msgCount') == 0) addMessageList();
        session.messages.slice(this.session.data('msgCount'))
            .forEach(function(msg) {that.addMessage(msg)});
        this.session.data('msgCount', session.messages.length);
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

function processJson(json) {
    $.each(json, function(i, session) {sessions[session.id].update(session)})
}

function getJson (url) {
    $.getJSON(url, processJson)
        .fail(function(result) {console.log(error_msg + result.responseJSON.detail)})
        .done(run)
}

function run() {
    var session_ids = $.map(sessions, function(session, i) {return session.id});
    if (session_ids.length) {
        $('#action-toggle').prop('disabled', true);
        $('#result_list').addClass('running');
        var url = baseurl + '?id__in=' + session_ids;
        window.setTimeout(getJson, interval, url);
    } else {
        $('#action-toggle').prop('disabled', false);
        $('#result_list').removeClass('running');
    }
}

$(document).ready(function () {
    // scroll all minke-messages to the bottom...
    $('ul.messagelist > li').each(function (i,e) {$(e).scrollTop($(e)[0].scrollHeight)});
    // initialize session-objects...
    $('tr.session[data-proc-status="initialized"],tr.session[data-proc-status="running"]').each(function(i, e) {sessions[$(e).data('id')] = new Session(e)});
    // run...
    run();
});

})(django.jQuery);
