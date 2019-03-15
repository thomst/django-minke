(function($) {

var cf = {
    interval : 800,
    baseurl : window.location.protocol + '//'
              + window.location.host
              + '/minkeapi/currentsessions/'
              + window.location.pathname.split('/')[2],
    input_selector : 'tr.initialized input.action-select, tr.running input.action-select',
    error_msg : 'minkeapi-error: '
}

function process_session (i, session) {
    object_id = session.object_id;
    var tr = $('tr input.action-select[value='+object_id+']').closest('tr');
    tr.removeClass('initialized running').addClass(session.proc_status);
    if (session.ready) add_session_info(tr, session);
}

function add_session_info (tr, session) {
    tr.addClass(session.status);
    var session_tr = $(session.get_html).hide();
    var msgs_ul = session_tr.find('ul').hide();
    tr.after(session_tr);
    session_tr.show(500);
    msgs_ul.slideDown('fast');
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
