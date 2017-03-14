import os
import shutil
import sys
import zipfile
import logging
log = logging.getLogger(__name__)


############################################################################
def check_process_output(output):
    output=strip_output_lines(output)
    scenario_id=0
    network_id=None

    log.info("Check: %s", output)
    message='<message>'
    errors='<errors>'
    err=[]
    line1="<message>Run successfully</message>"
    line2 ="<message>Data import was successful.</message>"
    line3="<message>Export complete</message>"
    if (line2 in output or line1 in output or line3 in output):
        log.info("-----------------------------------------------------------")
        for line in output:
            if line.startswith('<network_id>'):
                network_id = (line.replace('<network_id>', '').replace('</network_id>', ''))
            elif line.startswith('<scenario_id>'):
                scenario_id = (line.replace('<scenario_id>', '').replace('</scenario_id>', ''))
        return ["Data import was successful", network_id, scenario_id]
    else:
        for line in output:
            if line.startswith(message):
                message=line.replace(message,'')
                message=message.replace('</message>','')
            elif line.strip().startswith(errors):
                for i in range (output.index    (line)+1, len(output)-1):
                    if output[i].strip().startswith('</errors>'):
                        return 'Error: '+'\n'.join(err)
                    else:
                        err.append(output[i].replace('<error>','').replace('</error>',''))

    return ["Error"]


def strip_output_lines (output):
    new_outpute=[]
    for line in output:
        new_outpute.append(line.strip())
    return new_outpute


def get_progress_from_output(output):
    progress=0
    total=100
    status='Pending'
    output =strip_output_lines(output)
    for i in range( 0, len(output)):

        line = (output[len(output)-1-i])
        if line.startswith("!!Progress"):
            line = line.replace('!!Progress', '')
            line = line.split('/')
            if len(line) == 2:
                progress = int(line[0])
                total = int(line[1])
                status='Running'
                break
    return  status, progress, total
