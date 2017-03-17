var jobs = {}

/*****************Management of Apps***********************/
$(document).on('click', '#create-app-button', function(){

    $('#create-app').submit()

})

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

        if (param.name == 'network-id' || param.name == 'network_id'){
            val =network_id 
        }

        if (param.name == 'scenario-id' || param.name == 'scenario_id'){
            val = scenario_id
        }

        table.append("<tr><td>"+param.name+"*</td><td><input name='"+param.name+"' value='"+val+"' type='"+inputtype+"'></input></td></tr>");
    }
    for (var i=0; i<optional.length; i++){
        var param = optional[i];
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

        if (param.name == 'network-id' || param.name == 'network_id'){
            val =network_id 
        }

        if (param.name == 'scenario-id' || param.name == 'scenario_id'){
            val = scenario_id
        }

        table.append("<tr><td>"+param.name+"</td><td><input name='"+param.name+"' value='"+val+"' type='"+inputtype+"'></input></td></tr>");
    }
    for (var i=0; i<switches.length; i++){
        var param = switches[i];
        var val = ''
        if (param.defaultval != null){
            val = param.defaultval
        }
        table.append("<tr><td>"+param.name+"</td><td><input name='"+param.name+"' type='checkbox'></input></td></tr>");
    }
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
    
    var form = $('#run-app')

    var data = form.serializeArray()
    var params = {id: null, scenario_id: null, network_id: null, options:{}}

    for (var i=0; i<data.length; i++){
        var name = data[i].name;
        var value = data[i].value;
        if (name == 'app-id' || name == 'app_id'){
            params['id'] = value;
        }else if (name == 'scenario-id' || name == 'scenario_id'){
            params['scenario_id'] = value;
        }else if (name == 'network-id' || name == 'network_id'){
            params['network_id'] = value;
        }else{
            params['options'][name] = value;
        }
    }

    $.ajax({
        method: 'POST',
        url: run_app_url,
        data: JSON.stringify(params),
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
