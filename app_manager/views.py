
from flask import render_template, session, jsonify, redirect, url_for, request

import zipfile
import os
import json

from app_utilities import get_progress_from_output, check_process_output

from app_registry import AppInterface, AppRegistry
appinterface = AppInterface()

import logging
log = logging.getLogger(__name__)

from . import appmanager

@appmanager.route('/apps/')
def go_apps():
    app_list = appinterface.installed_apps_as_dict() 
    return render_template('app_manager/apps.html', apps=app_list)

@appmanager.route('/app/<app_id>')
def go_app(app_id):
    # Do some stuff
    app_info = appinterface.app_info(app_id)
    return render_template('app_manager/app.html', apps=[])

@appmanager.route('/apps/upload_app', methods=['POST'])
def do_upload_app():
    # Do some stuff

    app_zip = request.files['app_folder']

    install_path = appinterface.app_registry.install_path
    save_loc = os.path.join(install_path, app_zip.filename)

    app_zip.save(save_loc)

    zip_ref = zipfile.ZipFile(save_loc, 'r')
    zip_ref.extractall(install_path)
    zip_ref.close()

    return redirect(url_for('app_manager.go_apps'))

@appmanager.route('/apps/delete_app')
def do_delete_app():
    # Do some stuff
    return jsonify({'status': 'OK'})

@appmanager.route('/apps/installed', methods=['GET'])
def get_installed_apps():
    """Returns information on all installed apps as list of dict of the form

        [{'id': 'a8f43cfadc154b1dfbc98aa13aca38b8',
          'name': 'Debug Plugin',
          'description': 'A plugin that records input parameters ...'},
         ]
    """
    return jsonify(appinterface.installed_apps_as_dict())


@appmanager.route('/app/info/<app_id>', methods=['GET'])
@appmanager.route('/app/info/', methods=['GET'])
def get_app_info(app_id):
    """Returns the contents of the 'plugin.xml' as json string, except for the
    parts that are not of general interest, such as location and the exact
    command, etc.
    """

    log.info('Getting info for app %s', app_id)

    if app_id is None:
        parameters = json.loads(request.get_data())
        if parameters.get('app_id'):
            app_id = parameters['app_id']
        else:
            return render_template('page_not_found.html'), 404 

    return jsonify(appinterface.app_info(app_id))


@appmanager.route('/app/run', methods=['POST'])
def run_app():
    """To run an app the following information needs to be transmitted as a json
    string:
    {'id': 'the app id',
     'network_id': number,
     'scenario_id': number,
     'options': {'option1': value1, 'option2': value2, ... }
     }

    'options' is allowed to be empty; entries in the options dict need to
    correspond to a 'name' of a mandatory or non-mandatory argument or a switch
    of an app.
    """

    parameters = json.loads(request.get_data())

    log.info('Running App %s with parameters %s' , parameters['id'], parameters)
 
    job_id = appinterface.run_app(parameters['id'],
                                  parameters['network_id'],
                                  parameters['scenario_id'],
                                  session['user_id'],
                                  options=parameters['options'])
    return jsonify(job_id)

@appmanager.route('/app/status', methods=['POST'])
def job_status():
    """Get the job status for a given network or a given user by transmitting a
    json string that looks like this 
        '{"network_id": "3"}' 
    or this 
        '{"user_id": "whatever the user is identified by"}'
    or this 
        '{"job_id": "job_id" }'
    or any combination of the above, like this 
        '{"network_id": "3",
        "user_id": "whatever the user is identified by"}'

    Here, the user_id needs to be sent explicitly because it is allowed to be
    empty/non-existent.
    """

    parameters = json.loads(request.get_data())

    log.info('Polling jobs for: %s', parameters)

    status = \
        appinterface.get_status(network_id=parameters.get('network_id', None),
                                user_id=parameters.get('user_id', None),
                                job_id=parameters.get('job_id', None))

    return jsonify(status)
