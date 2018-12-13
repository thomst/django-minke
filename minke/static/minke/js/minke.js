(function($) {

var interval;
var baseurl = window.location.protocol + '//' + window.location.host + '/minke' + window.location.pathname;

function process_result(result) {
    $.each(result, function(id, data){
        var proc_statuus = 'initialized running';
        var tr = $('tr input.action-select[value='+id+']').closest('tr');
        tr.removeClass(proc_statuus).addClass(data.proc_status);
        if (data.status) tr.addClass(data.status);
        if (data.messages.length) {
            var msg_tr = $('<tr></tr>').addClass('minke_news').addClass(data.status).hide();
            var td = $('<td></td>').attr('colspan', 20);
            var ul = $('<ul></ul>').addClass('messagelist').hide();
            tr.after(msg_tr.append(td.append(ul)));
            $.each(data.messages, function(i, msg) {
                ul.append($('<li></li>').addClass(msg.level).append(msg.html));
            });
            msg_tr.show(2000);
            ul.slideDown('fast');
        }
    });
}

function get_data(object_ids) {
    if (!object_ids) {
        var object_ids = $('tr.initialized input.action-select, tr.running input.action-select')
            .map(function() {return $(this).val()}).get().join(',');
    }
    if (object_ids) {
        var url = baseurl + '?object_ids=' + object_ids;
        $.getJSON(url, process_result);
    } else {
        clearInterval(interval);
    }
}

$(document).ready(function() {
    var object_ids = $('tr:not(.done) input.action-select')
        .map(function() {return $(this).val()})
        .get().join(',');
    get_data(object_ids);
    interval = setInterval(get_data, 2000);
});

})(django.jQuery);
