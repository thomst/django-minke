(function($) {

var cf = {
    interval : 800,
    baseurl : window.location.protocol + '//'
              + window.location.host
              + '/minkeapi/currentsessions/'
              + window.location.pathname.split('/')[2],
    input_selector : 'tr.initialized input.action-select, tr.running input.action-select',
    proc_statuus : 'initialized running',
    error_msg : 'minkeapi-error: '
}

function process_session (i, session) {
    object_id = session.object_id;
    var tr = $('tr input.action-select[value='+object_id+']').closest('tr');
    tr.removeClass(cf.proc_statuus).addClass(session.proc_status);
    if (session.status) tr.addClass(session.status);
    if (session.messages.length) process_messages(tr, session);
}

function process_messages (tr, session) {
    var msgtr = $('<tr></tr>').addClass('minke_news')
        .addClass(session.status).hide();
    var td = $('<td></td>').attr('colspan', 20);
    var ul = $('<ul></ul>').addClass('messagelist').hide();
    tr.after(msgtr.append(td.append(ul)));
    $.each(session.messages, function(i, msg) {
        ul.append($('<li></li>').addClass(msg.level).append(msg.html));
    });
    msgtr.show(500);
    ul.slideDown('fast');
}

function get_json (url) {
    $.getJSON(url, function(result) {$.each(result, process_session)})
        .fail(function(result) {
            console.log(cf.error_msg + result.responseJSON.detail)})
        .done(process)
}

function process() {
    var object_ids = $(cf.input_selector)
        .map(function() {return $(this).val()}).get().join(',');
    if (object_ids) {
        $('#action-toggle').prop('disabled', true);
        $('#result_list').addClass('running');
        var url = cf.baseurl + '?object_ids=' + object_ids;
        window.setTimeout(get_json, cf.interval, url);
    } else {
        $('#action-toggle').prop('disabled', false);
        $('#result_list').removeClass('running');
    }
}

$(document).ready(process);

})(django.jQuery);
