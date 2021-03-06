import os
import sys
import glob
import uuid
import logging
import hashlib

from lxml import etree
from datetime import datetime
from dateutil import parser as date_parser

from hydra_base import config
import tempfile


log = logging.getLogger(__name__)


class AppInterface(object):
    """A class providing convenience functions for the flask UI. 
    """

    def __init__(self):

        self.app_registry = AppRegistry()
        self.job_queue = JobQueue(config.get('plugin', 'queue_directory', '/tmp'))
        self.job_queue.rebuild(self.app_registry)
        self.upload_dir = config.get('plugin', 'upload_dir', '/tmp/uploads')

    def installed_apps_as_dict(self):
        """Return a list if installed apps as dict.
        """
        
        installedapps = []
        for key, app in self.app_registry.installed_apps.iteritems():
            appinfo = dict(id=key,
                           name=app.info['name'],
                           description=app.info['description'],
                           category=app.info['category'])
            installedapps.append(appinfo)

        return installedapps

    def app_info(self, app_id):
        return self.app_registry.installed_apps[app_id].info

    def run_app(self, app_id, network_id, scenario_id, user, options={}, network_name='', scenario_name=''):
        app = self.app_registry.installed_apps[app_id]
        appjob = Job()
        appjob.create(app, app_id, network_id, scenario_id, str(user), options, scenario_name=scenario_name, network_name=network_name)
        self.job_queue.enqueue(app_id, appjob)
        return dict(jobid=appjob.id)

    def get_status(self, network_id=None, user_id=None, job_id=None):
        "Return the status of matching jobs."

        self.job_queue.rebuild(self.app_registry)
        if job_id is not None:
            if job_id in self.job_queue.jobs.keys():
                return [dict(jobid=job_id,
                             app_id=self.job_queue.jobs[job_id].app_id,
                             status=self.job_queue.jobs[job_id].status)]
            else:
                return []
        else:
            matching_jobs = []
            for jid, job in self.job_queue.jobs.iteritems():
                if network_id is not None and user_id is not None:
                    if int(job.network_id) == int(network_id) and int(job.owner) == int(user_id): 
                        matching_jobs.append(job)
                elif network_id is not None:
                    if int(job.network_id) == int(network_id):
                        matching_jobs.append(job)
                elif user_id is not None:
                    if int(job.owner) == int(user_id):
                        matching_jobs.append(job)

            response = []
            for job in sorted(matching_jobs, key=lambda x:x.enqueued_at, reverse=True):
                response.append(dict(scenario_id=job.scenario_id, network_id=job.network_id, owner=job.owner, app_id=job.app_id, jobid=job.id, status=job.status, scenario_name=job.scenario_name, network_name=job.network_name, started_at=job.enqueued_at.strftime('%d/%m/%Y - %H:%M:%S')))
            return response

    def get_native_logs(self, job_id):
        """
            If the app ran a model which produced its own log file, retrieve it here
        """
        if job_id in self.job_queue.jobs.keys():
            return self.job_queue.jobs[job_id].get_native_logs()
        else:
            return {}

    def get_native_output(self, job_id):

        """
            If the app ran a model which produced its own output file, retrieve it here
        """
        if job_id in self.job_queue.jobs.keys():
            return self.job_queue.jobs[job_id].get_native_output()
        else:
            return {}

    def get_job_details(self, job_id):
        """
            Return the status of matching jobs.
        """
        if job_id in self.job_queue.jobs.keys():
            return self.job_queue.jobs[job_id].get_details()
        else:
            return {}

    def delete_job(self, job_id):
        """
            Delete a job by removing it from the queued / finished / failed folder
        """
        if job_id not in self.job_queue.jobs:
            raise Exception("Cannot delete job %s, Job not found."%job_id)

        job = self.job_queue.jobs[job_id]
        
        job.delete()

        del(self.job_queue.jobs[job_id])

    def restart_job(self, job_id):
        """
            Restart a job by removing it from the finished / failed folder
            to the queued folder
        """
        if job_id not in self.job_queue.jobs:
            raise Exception("Cannot restart job %s, Job not found."%job_id)

        job = self.job_queue.jobs[job_id]
        
        job.restart()

class AppRegistry(object):
    """A class holding all necessary information about installed Apps. Each App
    needs to be install in a folder specified in the config file. An App is
    identified by a 'plugin.xml' file.

    This class is the point of contact for UI functions.
    """

    def __init__(self):
        """Initialise job queue and similar...
        """
        self.install_path = config.get('plugin', 'default_directory')
        if self.install_path is None:
            log.critical("Plugin folder not defined in config.ini! "
                         "Cannot scan for installed plugins.")
            return None
        self.installed_apps = scan_installed_apps(self.install_path)

    def scan_apps(self):
        """Manually scan for new apps.
        """

        self.installed_apps = scan_installed_apps(self.install_path)


class App(object):
    """A class representing an installed App.
    """

    def __init__(self, pxml=None):
        self.info = dict()
        self._from_xml(pxml=pxml)

    @property
    def unique_id(self):
        """Create a persistent and unique ID for the app.
        """
        with open(self.pxml, 'r') as pluginfile:
            return hashlib.md5(pluginfile.read()).hexdigest()

    def default_parameters(self):
        """Return default parameters defined in plugin.xml
        """
        pass

    def cli_command(self, app_id, network_id, scenario_id, options):
        """Generate a command line command based on the network and scenario ids
        and a given set of options.
        """
        command_elements = []
        command_elements.append(self.shell)
        command_elements.append(os.path.join(self.location, self.command))

        # Work out the commandline option for network id and scenario id
        netid_switch = self._get_switch('network')
        scenid_switch = self._get_switch('scenario')

        command_elements.append(netid_switch)
        command_elements.append(str(network_id))
        command_elements.append(scenid_switch)
        command_elements.append(str(scenario_id))

        for opt, val in options.iteritems():
            opt_switch = self._get_switch(opt)

            # Handle true/false switches
            for arg in self.info['switches']:
                if arg['name'] == opt:
                    if val is True:
                        command_elements.append(arg['switch'])

            if opt_switch is not None:
                command_elements.append(opt_switch)
                command_elements.append("'%s'"%(val))

        return ' '.join(command_elements)

    def _from_xml(self, pxml=None):
        """Initialise app info from a given plugin.xml file.
        """
        self.pxml = pxml
        with open(self.pxml, 'r') as pluginfile:
            xmlroot = etree.parse(pluginfile).getroot()

        log.debug("Loading xml: %s." % self.pxml)

        # Public properties
        self.info['name'] = xmlroot.find('plugin_name').text
        self.info['description'] = xmlroot.find('plugin_description').text
        self.info['category'] = xmlroot.find('plugin_category').text
        self.info['mandatory_args'] = \
                self._parse_args(xmlroot.find('mandatory_args'))
        self.info['non_mandatory_args'] = \
                self._parse_args(xmlroot.find('non_mandatory_args'))
        self.info['switches'] = \
                self._parse_args(xmlroot.find('switches'), isswitch=True)
        self.info['nativelogextension'] = xmlroot.find('plugin_nativelogextension').text
        self.info['nativeoutputextension'] = xmlroot.find('plugin_nativeoutputextension').text

        # Private properties
        self.command = xmlroot.find('plugin_command').text
        self.shell = xmlroot.find('plugin_shell').text
        self.location = os.path.join(os.path.dirname(pxml),
                                     xmlroot.find('plugin_location').text)

    def _parse_args(self, argroot, isswitch=False):
        """Parse arument block of plugin.xml.
        """

        args = []

        for arg in argroot.iterchildren():
            argument = AppArg()
            argument.from_xml(arg, isswitch=isswitch)
            args.append(argument)

        return args

    def _get_switch(self, resource):
        if resource == 'network':
            keywords = ['net', ]
        elif resource == 'scenario':
            keywords = ['scen', ]
        else:  # handle other options
            keywords = [resource]

        matching_args = dict()

        for arg in self.info['mandatory_args'] + \
                self.info['non_mandatory_args']:
            matchscore = 0
            for kw in keywords:
                if kw in arg['name']:
                    matchscore += 1

            # 'net_id' is better than 'net', 'id' is worse than 'net' --> 'id
            # gives half a point
            if 'id' in arg['name']:
                matchscore += .5
            matching_args[arg['switch']] = matchscore

        sortidx = sorted([(v,i) for i, v in enumerate(matching_args.values())])
        keyidx = sortidx[-1][1]
        if sortidx[-1][0] > 0.5:
            return matching_args.keys()[keyidx]
        else:
            return None


class AppArg(dict):
    """Extension of dict() read app arguments from an xml etree.
    """

    def from_xml(self, xmlarg, isswitch=False):
        """Create an argument from an lxml.Element object.
        """

        self.__setitem__('switch', xmlarg.find('switch').text 
                         if xmlarg.find('switch') is not None else None)
        self.__setitem__('name', xmlarg.find('name').text 
                         if xmlarg.find('name') is not None else None)
        self.__setitem__('help', xmlarg.find('help').text
                         if xmlarg.find('help') is not None else None)
        if isswitch is False:
            self.__setitem__('multiple', xmlarg.find('multiple').text
                             if xmlarg.find('multiple') is not None else False)
            self.__setitem__('argtype', xmlarg.find('argtype').text 
                             if xmlarg.find('argtype') is not None else None)
            self.__setitem__('defaultval', xmlarg.find('defaultval').text
                             if xmlarg.find('defaultval') is not None else None)
            self.__setitem__('allownew', xmlarg.find('allownew').text
                             if xmlarg.find('allownew') is not None else None)


class JobQueue(object):
    """Interact with a simple file based job queue. 

    The queue is organised using four folders:
    
    queued/
    running/
    finished/
    failed/
    logs/
    deleted/
    
    Each job is a separate file containing the commandline to be executed. The
    filename and the job ID are identical.
    """

    def __init__(self, root):
        self.root = root 
        if self.root is None:
            self.root = os.path.expanduser('~/.hydra/jobqueue')
        log.info('Establish job queue in %s.' % self.root)

        if not os.path.isdir(self.root):
            log.debug('Creating folder %s.' % self.root)
            os.mkdir(self.root)

        self.folders = {'queued'   : 'queued',
                        'running'  : 'running',
                        'tmp'      : 'tmp',
                        'finished' : 'finished',
                        'failed'   : 'failed',
                        'deleted'  : 'deleted',
                        'logs'     : 'logs',
                        'model'    : 'model',
                        'uploads'  : 'uploads'
                        }

        # Create folder structure if necessary
        for folder in self.folders.values():
            if not os.path.isdir(os.path.join(self.root, folder)):
                log.debug('Creating folder %s.' % folder)
                os.mkdir(os.path.join(self.root, folder))

        self.commentstr = '#'
        if 'win' in sys.platform:
            self.commentstr = 'rem'
        self.jobs = dict()

    def enqueue(self, app_id, job):
        job.enqueued_at = datetime.now()
        job.job_queue = self
        self.jobs[job.id] = job

        stderr = os.path.join(self.root, self.folders['logs'], "%s.log"%job.id)
        stdout = os.path.join(self.root, self.folders['logs'], "%s.out"%job.id)
        
        #Better way to do this? 
        job.logfile = stderr
        job.outfile = stdout

        with open(os.path.join(self.root, self.folders['queued'], job.file), 'w') \
                as jobfile:
            jobfile.write('\n'.join(["%s owner=%s"       % (self.commentstr,
                                                           job.owner),
                                     "%s app_id=%s"      % (self.commentstr,
                                                           job.app_id),
                                     "%s network_id=%s"  % (self.commentstr,
                                                           job.network_id),
                                     "%s network_name=%s"% (self.commentstr,
                                                           job.network_name),
                                     "%s scenario_id=%s" % (self.commentstr,
                                                            job.scenario_id),
                                     "%s scenario_name=%s"%(self.commentstr,
                                                            job.scenario_name),
                                     "%s created_at=%s"  % (self.commentstr,
                                                           job.created_at),
                                     "%s enqueued_at=%s" % (self.commentstr,
                                                            job.enqueued_at),
                                     "\n"]))
            
            cmd_with_outputs = job.command + ' 2> %s 1>%s' % (stderr, stdout)
            jobfile.write(cmd_with_outputs)


            jobfile.write('\n')

            job.path = self.folders['queued']

    def rebuild(self, app_registry):
        """Rebuild job queue after server restart.
        """
        self.jobs = dict()
        for folder in self.folders.values():
            if folder in ('logs', 'uploads', 'deleted', 'model'):
                continue
            for jr, jf, jobfiles in os.walk(os.path.join(self.root, folder)):
                for jfile in jobfiles:
                    if not jfile.endswith('job'):
                        continue
                    exjob = Job()
                    exjob.from_file(os.path.join(jr, jfile))
                    exjob.app = app_registry.installed_apps.get(exjob.app_id)
                    exjob.job_queue = self
                    self.jobs[exjob.id] = exjob
                    exjob.logfile = os.path.join(self.root, self.folders['logs'], "%s.log"%exjob.id)
                    exjob.outfile = os.path.join(self.root, self.folders['logs'], "%s.out"%exjob.id)


    def expunge_old_jobs(self):
        """Delete finished job from list as it reaches a certain age.
        Function for scheduled execution.
        """
        for key, job in self.jobs.iteritems():
            if job.is_finished is True and \
                    (datetime.now - job.enqueued_at).total_seconds() > 86400:
                job.cleanup()
                job.delete()
                del self.jobs[key]


class Job(object):
    """A job object. Each job owns a job file within the JobQueue structure and
    belongs to one network and a user.
    """

    def __init__(self):
        self.id = None
        self.app = None
        self.app_id=None
        self.owner = None
        self.network_id = None
        self.network_name = None
        self.scenario_id = None
        self.scenario_name = None
        self.command = None
        self.file = None
        self.path = None
        self.created_at = None
        self.job_queue = None
        self.enqueued_at = None

    def create(self, app, app_id, network_id, scenario_id, owner, options, network_name="", scenario_name=""):
        self.id = str(uuid.uuid4())
        self.app = app
        self.app_id=app_id
        self.owner = owner
        self.network_id = network_id
        self.network_name = network_name
        self.scenario_id = scenario_id
        self.scenario_name = scenario_name
        self.command = app.cli_command(app_id, network_id, scenario_id, options)
        self.file = '.'.join([self.id, 'job'])
        self.created_at = datetime.now()

    def delete(self):
        """
            Delete a job object
        """
        
        jobfile = os.path.basename(self.file)

        fullpath = os.path.join(self.path, self.file)
        delpath = os.path.join(self.path, os.path.pardir, 'deleted')

        log.info("Moving job %s from %s to deleted folder %s", jobfile, fullpath, delpath)
        os.rename(fullpath, os.path.join(delpath, jobfile))

    def restart(self):
        """
            Restart a job object
        """
        
        jobfile = os.path.basename(self.file)

        fullpath = os.path.join(self.path, self.file)
        delpath = os.path.join(self.path, os.path.pardir, 'queued')

        log.info("Moving job %s to queued folder", jobfile)
        os.rename(fullpath, os.path.join(delpath, jobfile))

    def from_file(self, jobfile):
        """
            Reconstruct Job object from a file in the job queue folder.
        """

        self.file = os.path.basename(jobfile)
        self.path = os.path.dirname(jobfile)
        self.id = self.file.split('.')[0]
        with open(jobfile, 'r') as jf:
            jobdata = jf.read()
        
        jobdata = jobdata.split('\n')
        for line in jobdata:
            if line.startswith('#') or line.startswith('rem'):
                if 'owner' in line:
                    self.owner = line.split('=')[-1]
                elif 'app_id' in line:
                    self.app_id = line.split('=')[-1]
                elif 'network_id' in line:
                    self.network_id = int(line.split('=')[-1])
                elif 'scenario_id' in line:
                    self.scenario_id = int(line.split('=')[-1])
                elif 'scenario_name' in line:
                    self.scenario_name = line.split('=')[-1]
                elif 'network_name' in line:
                    self.network_name = line.split('=')[-1]
                elif 'created_at' in line:
                    self.created_at = date_parser.parse(line.split('=')[-1])
                elif 'enqueued_at' in line:
                    self.enqueued_at = date_parser.parse(line.split('=')[-1])
            elif len(line) > 0:
                self.command = line

    def get_details(self):
        """
            Get logs, output text and progress of the job
        """
        logs = self.get_logs()
        output = self.get_output()
        progress = self.get_progress()

        return {'progress':progress, 'output':output, 'logs':logs}

    def get_logs(self, limit=100):
        """
            Get the log output. Limit to 100 lines to save time.
        """
        with open(self.logfile, 'r') as f:
            if limit is not None:
                return f.readlines()[0:limit]
            else:
                return f.readlines()

    def get_native_logs(self):
        """
            If the job has run a program which produces its own native log
            retrieve it here. Returns a file. A file containing
            "EXCLUDE_START" and "EXCLUDE_END" will exclude everything between these
            two tags. This is in case the log file contains sensitive information which
            can be controlled by the model (by placing the tags into the log)
        """
        all_lines = []
        ignoring = False

        if self.app is None:
            return "App for job cannot be found. Has it been removed?"
        
        log_extension = self.app.info.get('nativelogextension', 'log')

        error_flag    = self.app.info.get('errorflag', '**** ') #Default to GAMS error flag

        folder = os.path.join(self.job_queue.root, self.job_queue.folders['model'], self.id) 

        files = filter(os.path.isfile, glob.glob(folder + os.sep + "*.%s"%log_extension))

        if len(files) == 0:
            return "No log file found"

        files.sort(key=lambda x: os.path.getmtime(x))
        

        nativelogfile=files[0]

        with open(nativelogfile, 'r') as f:
            prev_line = ""
            for l in f.readlines():
                if l.find('EXCLUDE_START') >= 0:
                    ignoring = True
                    continue
                elif l.find('EXCLUDE_END') >= 0:
                    ignoring=False
                    continue

                #If an error is spotted, ouput that line and the one previous, regardless of
                #whether we're in ignore mode
                if l.find(error_flag) >= 0:
                    #Don't double-add if there's two lines like this in a row
                    if prev_line.find(error_flag) == -1:
                        all_lines.append(prev_line)
                    all_lines.append(l)
                elif ignoring is False:
                    all_lines.append(l)


                prev_line = l

        nativefilename = nativelogfile.split(os.sep)[-1]
        
        log.info("%s Lines", len(all_lines))
        with open(tempfile.gettempdir() + os.sep + nativefilename, 'w') as f:
            f.write("".join(all_lines))
            log.info("Return file at: %s", f.name)
            return f

    def get_native_output(self):
        """
            If the job has run a program which produces its own native log
            retrieve it here. Returns a file.
        """

        if self.app is None:
            return "App for job cannot be found. Has it been removed?"
        
        output_extension = self.app.info.get('nativeoutputextension', 'out')
        folder = os.path.join(self.job_queue.root, self.job_queue.folders['model'], self.id) 
        files = filter(os.path.isfile, glob.glob(folder + os.sep + "*.%s"%output_extension))

        if len(files) == 0:
            return "No output file found"

        files.sort(key=lambda x: os.path.getmtime(x))

        f =  open(files[-1], 'r')
        log.info("Return file at: %s", f.name)
        return f

    def get_output(self):
        output = []
        with open(self.outfile, 'r') as f:
            for line in f.readlines():
                line = line.strip()
                if line.startswith("!!Output"):
                    line = line.replace('!!Output ', '')
                    output.append(line)
        return  output

    def get_progress(self):
        progress=0
        total = None
        with open(self.outfile, 'r') as f:
            for line in f.readlines():
                line = line.strip()
                if line.startswith("!!Progress"):
                    line = line.replace('!!Progress', '')
                    line = line.split('/')
                    if len(line) == 2:
                        progress = int(line[0])
                        if total == None:
                            total = int(line[1])
        return  progress, total

    @property
    def status(self):
        jobfilepath = glob.glob(self.job_queue.root + os.sep + '*' + os.sep +
                                self.file)[0]
        status = jobfilepath.replace(self.job_queue.root + os.sep, '')
        status = status.replace(os.sep + self.file, '')
        return status

    @property
    def is_queued(self):
        """Convenience function.
        """
        return self.status == 'queued'

    @property
    def is_running(self):
        """Convenience function.
        """
        return self.status == 'running' or self.status == 'tmp'

    @property
    def is_finished(self):
        """Convenience function.
        """
        return self.status == 'finished'

    @property
    def is_failed(self):
        """Convenience function.
        """
        return self.status == 'failed'


def scan_installed_apps(plugin_path):
    """Scan installed Apps and retrieve necessary information. Returns a
    dictionary indexed by a hash of the 'plugin.xml' file to guarantee
    persistency after server restart and allow for the installation of
    different versions of the same App.
    """

    log.info("Scanning installed apps in %s", plugin_path)
    plugin_files = []
    for proot, pfolders, pfiles in os.walk(plugin_path, followlinks=True):
        for item in pfiles:
            if item == 'plugin.xml':
                plugin_files.append(os.path.join(proot, item))

    installed_apps = dict()
    for pxml in plugin_files:
        app = App(pxml=pxml)
        appkey = app.unique_id
        installed_apps[appkey] = app
    
    log.info("%s installed apps found", len(installed_apps))

    return installed_apps

def _strip_lines (output):
    new_output=[]
    for line in output:
        new_output.append(line.strip())
    return new_output

# for testing only
if __name__ == '__main__':
    appinterface = AppInterface()

    job1 = appinterface.run_app('b62f5945ee6e53130432c1747b27905e', 1, 1,
                                'root', 
                                options={'dummyswitch': True,
                                         'dummy3': 3.14,
                                         'failswitch': False})
    job2 = appinterface.run_app('b62f5945ee6e53130432c1747b27905e', 1, 1,
                                'another_user', 
                                options={'dummyswitch': True,
                                         'dummy3': 3.14,
                                         'failswitch': False})
    job3 = appinterface.run_app('b62f5945ee6e53130432c1747b27905e', 2, 1,
                                'root', 
                                options={'failswitch': True, 'dummy3': 3.14})

    status1 = appinterface.get_status(user_id='root')  # Should return job1 & 3
    status2 = appinterface.get_status(network_id=1)    # Should return job1 & 2
    status3 = appinterface.get_status(network_id=1, user_id='root')  # returns job1

    import pudb
    pudb.set_trace()

