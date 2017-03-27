var jobs = {}


/*********************Parameterising Apps******************************/


$(document).on('click', '.modelrun', function(){
    var app_id = $(this).attr('app-id');

    $('#run_app_modal .modal-body .alert').remove()
    $('#run_app_modal .modal-body tr').remove()

    get_app_details(app_id);
})

var get_app_details = function(app_id){

    var success = function(resp){
        populate_params(app_id, resp)
    }
    
    var error = function(resp){

        $('#run_app_modal .modal-body').append("<div class='alert alert-danger' role='alert'>An error has occurred retrieving the details for this app.</div>")
    }

    $.ajax({
        method: 'GET',
        url: get_app_details_url + app_id,
        success: success,
        error  : error,
    })

}

var populate_params = function(app_id, params){

    $("#run-app input[name='app-id'").val(app_id)
    
    var table = $('#app-params');
    
    $('#run_app_modal .modal-title').text(params.name)

    var mandatory= params['mandatory_args']
    var optional = params['non_mandatory_args']
    var switches = params['switches']
    for (var i=0; i<mandatory.length; i++){
        var param = mandatory[i];
        var row_text = get_param_row(param)
        table.append(row_text)
    }
    for (var i=0; i<optional.length; i++){
        var param = optional[i];

        var row_text = get_param_row(param)
        table.append(row_text)
    }
    for (var i=0; i<switches.length; i++){
        var param = switches[i];
        var val = ''
        if (param.defaultval != null){
            val = param.defaultval
        }
        table.append("<tr><td>"+param.name+"</td><td><input name='"+param.name+"' type='checkbox'></input></td></tr>");
    }

    $('.selectpicker', table).selectpicker({
        style: 'btn-default',
        size: 4
    });
}

var get_param_row = function(param){
    var inputtype = 'number'
    if (param.argtype == 'string'){
        inputtype = 'text'
    }else if(param.argtype == 'file'){
        inputtype = 'file'
    }

    var val = ''
    if (param.defaultval != null){
        val = param.defaultval
    }

    var current_scen = scenario_summaries[scenario_id]

    row_text = null;

     //Depending on the type of input specified, display an appropriate input (or indeed hide the inpyt if it's not necessary)
    if (param.argtype == 'network'){
        val =network_id 
        var input = "<input name='"+param.name+"' value='"+val+"' type='hidden'></input>";
        row_text = "<tr class='hidden'><td>"+param.name+"</td><td>"+input+"</td></tr>"
    }else if (param.name == 'session_id' || param.name == 'session-id'){
        
        if (session_id != undefined){
            var val = session_id;
        }else{
            var val = '';
        }
        var input = "<input name='"+param.name+"' value='' type='hidden'></input>";
        row_text = "<tr class='hidden'><td>"+param.name+"</td><td>"+input+"</td></tr>";

    }else if (param.name == 'server-url' || param.name == 'server_url'){
        
        var val = window.location.origin;
        var input = "<input name='"+param.name+"' value='"+val+"' type='hidden'></input>";
        row_text = "<tr class='hidden'><td>"+param.name+"</td><td>"+input+"</td></tr>";

    }else if (param.argtype == 'scenario'){
        val = "<select name='"+param.name+"' multiple class='selectpicker'>";
        Object.keys(scenario_name_lookup).forEach(function(k){
            val = val + "<option value='"+k+"' "+((k==scenario_id) ? 'selected' : '')+">"+scenario_name_lookup[k]+"</option>";
        })
        val = val + "</select>";
        var input = val;
        row_text = "<tr><td>"+param.name+"</td><td>"+input+"</td></tr>";
    }else if (param.argtype == 'starttime'){
        if (current_scen.start_time != undefined && current_scen.start_time != null){ 
            var input = "<input name='"+param.name+"' value='"+current_scen.start_time+"' type='date'></input>";
            row_text = "<tr><td>"+param.name+"</td><td>"+input+"</td></tr>"
        }
    }else if (param.argtype == 'endtime'){
        if (current_scen.end_time != undefined && current_scen.end_time != null){ 
            var input = "<input name='"+param.name+"' value='"+current_scen.end_time+"' type='date'></input>";
            row_text = "<tr><td>"+param.name+"</td><td>"+input+"</td></tr>"
        }
    }else if (param.argtype == 'timestep'){
        if (current_scen.time_step != undefined && current_scen.time_step != null){ 
            var input = "<input name='"+param.name+"' value='"+current_scen.time_step+"' type='text'></input>";
            row_text = "<tr><td>"+param.name+"</td><td>"+input+"</td></tr>"
        }
    }

    //Not created by a special case? Then use a default
    if (row_text == null){
        var input = "<input name='"+param.name+"' value='"+val+"' type='"+inputtype+"'></input>";
        row_text = "<tr><td>"+param.name+"</td><td>"+input+"</td></tr>"
    }

    return row_text 

}

/*********************Running Apps******************************/
$(document).on('click', '#run-app-button', function(){
    
    var success = function(resp){

        $('#run_app_modal').modal('hide');

        poll_jobs()
    }

    var error = function(){
        $('#run_app_modal .modal-body').prepend("<div class='alert alert-danger' role='alert'>An error has occurred retrieving the details for this app.</div>")
    }

    /*To run an app the following information needs to be transmitted as a json
    string:
    {'id': 'the app id',
     'network_id': number,
     'scenario_id': number,
     'options': {'option1': value1, 'option2': value2, ... }
     }*/
    
    var form_data = new FormData($('#run-app')[0]);
    $.ajax({
        method: 'POST',
        url: run_app_url,
        data: form_data,
        contentType: false,
        cache: false,
        processData: false,
        success: success,
        error: error
        
    })
})


/*********************Tracking Apps******************************/

var poll_jobs = function(repeat){

    var success = function(resp){
        if (resp.length == 0){
            setTimeout(poll_jobs, (36000*5)) // 5 minutes.
        }else{
            $('#joblist').empty()

            for (var i=0; i<resp.length; i++){
                var j = resp[i]
                jobs[j.jobid] = j
                if (j.status == 'queued'){
                    icon = 'fa fa-ellipsis-v'
                }else if (j.status == 'running'){
                    icon = 'fa fa-spinner fa-spin'
                }else if (j.status == 'finished'){
                    icon = 'fa fa-check'
                }else if (j.status == 'failed'){
                    icon = 'fa fa-exclamation-circle'
                }
                $('#joblist').append("<button class='btn jobstatus "+j.status+"' data-toggle='modal' data-target='#app_status_modal' job-id='"+j.jobid+"' app-id='"+j.app_id+"'>"+app_dict[j.app_id]['name']+"<span class='icon'><i class='"+icon+"'></i></span></button>")
            }
            if (repeat==undefined || repeat == true){
                setTimeout(poll_jobs, 5000) // 5 Seconds when there are active jobs
            }
        }
    }
    var error = function(){
        console.log('Error polling for jobs')
    }
    $.ajax(
        {
            method: 'POST',
            url: job_status_url,
            data: JSON.stringify({user_id: uid}),
            success: success,
            error: error,
        }
    )
}

$(document).on('click', '#joblist .jobstatus', function(){

    var app_id = $(this).attr('app-id')
    var job_id = $(this).attr('job-id')
    var app_details = app_dict[app_id]


    $('#app_status_modal .modal-title').empty()
    var modal = $('#app_status_modal .modal-title').text(app_details.name)

    $('#app_status_modal .alert').remove();

    $('#job_id_container').empty()
    $('#job_id_container').text(job_id)
    
    $('#app_status').empty()
    $('#app_status').text(jobs[job_id].status)


    $('#job_message').empty()

    $('#app_progressbar .progress').empty()

    $('#app_logs').empty()
   
    get_job_details(job_id)
 
})


var update_job_details = function(details){

    var progress = details['progress']
    var output   = details['output']
    var logs     = details['logs']

    if(output != undefined){
        $('#job_message').text(output[output.length-1])
    }

    if (progress != undefined){
        var prog = progress[0]/progress[1] * 100
        $('#app_progressbar .progress').append('<div class="progress-bar progress-bar-striped active" id="app_status_progress_bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100" style="width: '+prog+'%"></div>')
    }else{
        $('#app_progressbar').append("<div class='alert alert-info'>No progress available</div>")
    }

    if (logs != undefined){
        var logcontainer = $('#app_logs')
        for (var i=0; i<logs.length; i++){
            logcontainer.append("<div class='log'>"+logs[i]+"</div>")
        }
    }


}


var get_job_details = function(job_id){
    var success = function(resp){
        update_job_details(resp)
    }
    var error = function(resp){
        $('#app_status_modal .modal-body').append("<div class='alert alert-danger'>An error occurred getting the details for this job.</div>")
        
    }
    console.log(get_job_details_url + job_id)
    $.ajax({
        url: get_job_details_url + job_id,
        method: 'GET',
        success: success,
        error: error,
    })

}

$(document).ready(function(){
    poll_jobs(false)
})
