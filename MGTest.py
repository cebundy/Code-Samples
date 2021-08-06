import datetime
import errno
import getopt
import inspect
import json
import logging
import os
import platform
import Queue
import re
import sys
import time
import threading
import types
from time import sleep, ctime
import MGHost
import MGGlobals
import MGUtils

if os.name == "nt":
    import win32wnet

test = None
testid = None
testobj = None
recurse = 0

class ScriptError(KeyError):
    pass

class TestLogHandler(logging.Handler):
    def emit(self,record):
        msg = self.format(record)
        global testobj
        if ":INFO:" in msg: pass 
        elif ":DEBUG:" in msg: pass
        elif "ERROR" in msg:
#            print "TestLogHandler:emit: testobj:",vars(testobj)
            testobj.CountError(msg)
        elif "WARNING" in msg:
            testobj.CountWarning(msg)
            




class MGTest(object):
    '''MGTest class creates a test object that includes:
            test parameters, including processing test parameters
              that are passed in (opts) or read from a file
            object for the local host
            setup test logging to a remote share (static log server by default)
            test statistic object
    
    '''
    def __init__(self,opts):
        if 'testname' not in opts:
            raise ScriptError, "testname is required in opts structure."
        self.testid = opts['testname']['value']
        global testobj
        testobj = self
        self.log = {}
        self.settings = {}
        rc = self.SetParams(opts)
        if rc:
            return None
        self.SetUpStats()
        self.host = MGHost.MGHost(self)
        hostname = getattr(self.host,"hostname")
        if hostname: self.hostname = hostname
        self.SetUpLogging()
            
    def ProcessConfigFile(self):
        'Read a config file and parse the test parameters.'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        filename = self.settings['configfile']
        if not os.path.isfile(filename):
            self.error = "%s: %s does not exist" % (thisfunc,filename)
            return -1
        cfile = open(filename,'r')
        lines = cfile.readlines()
        for line in lines:
            line.strip()
            parts = line.split("=")
            for part in parts:
                part.strip()
            self.settings[parts[0]] = parts[1]
        return 0

    def SetParams(self,opts):
        'set the test object parameters from the command line, script and default parameters'
        thisfunc = inspect.stack()[0][3]
#        print thisfunc + " started"
        requiredparams = []
        defaultopts = { \
            'cfgfile': {'value': 0, 'type': "str" },  # configuration file
            'cleanup': {'value': 1, 'type': "int" },  # cleanup flag
            'cleanupall': {'value': 0,'type': "int" }, # adds another level of clean up for the script to implement
            'debug': {'value': 0,'type': "int" },    # debug level 
            'demo': {'value': 0,'type': "int" },     # set demo mode
            'emailto': {'value': None,'type': "str" }, # future email notification
            'emailcc': {'value': None,'type': "str" }, # future email notification
            'fspath': {'value': "",'type': "str" },  # file system path, usually the mounted path to the server/grid
            'help': {'value': 0,'type': "int" },      # help flag
            'hpqcid': {'value': None,'type': "str" },
            'interactive': {'value': 1,'type': "int" }, # displays log messages if set
            'logdir': {'value': None,'type': "str" },  # the log directory
            'logfile': {'value': None,'type': "str" }, # the log file
            'logtest': {'value': 1,'type': "str" },  # enable/disable logging, logging is not setup if value is 0
            'logshare': {'value': 'testfs','type': "str" }, # the default share on lrgecol
            'logmntpnt': {'value': '/mnt/logs','type': "str" }, # default mountpoint for mount the log server (adjusted later)
            'loghost': {'value': '10.4.14.10','type': "str" },  # default host for logging (lrgecol)
            'loguser' : {'value' : 'guest1','type': "str" }, # default log user
            'logpasswd': {'value': 'guest1','type': "str" }, # default log server password
            'savecfg': {'value': "",'type': "str" },  # future capability to save test configurations to be able to rerun
            }
        longopts = []
        for item in defaultopts:
            if item in opts: continue
            opts[item] = defaultopts[item]
        longopts.extend(opts.keys())
        if 'configfile' in self.settings:
            self.ProcessConfigFile()
            if "error" in self:
                if self.error: return 0
        longopts.sort()
#        print thisfunc,"longopts:",longopts
        prev = 0
        iteration = len(longopts)
        while (iteration > 0):
            iteration -= 1
            item = longopts.pop(0)
            item = item + "="
            longopts.append(item)

        try:
            clopts, args = getopt.getopt(sys.argv[1:],"",longopts)
        except getopt.GetoptError as err:
            self.error = 'option error: ' + str(err)
            print thisfunc,"error: ", self.error
            return -1
        
        # add cmdline args to the self.settings dictionary
        for opt, arg in clopts:
            opt = opt.replace("--","")
            if opts[opt]['type'] == 'int':
                self.settings[opt] = int(arg)
            else:
                self.settings[opt] = arg
                
        # add the opts (with the default opts folded in to the self.setting        
        for item in opts:
            if item in self.settings: continue
            self.settings[item] = opts[item]['value']
        self.error = 0
        self.errortype = 0


        print thisfunc,"checking required parameters:"
        for item in requiredparams:
            error = None
            if not item in self.settings or not self.settings[item]:
                error = "SETUPERROR: %s: %s is a required parameter" % \
                (thisfunc,item)
                print thisfunc,error
                if self.error:
                    self.error = self.error + "\n" + error
                else:
                    self.error = error
                      
        if self.error: print thisfunc,"self.error:",self.error    
        self.warningmsg = None
        self.currentsubtest = None
        self.aborted = None
        self.subtests = {}
        return 0
        
    
        
    def SetUpLogging(self):
        thisfunc = inspect.stack()[0][3]
        logging.basicConfig(format="%(asctime)s:%(name)s:%(levelname)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s",level=logging.INFO)
        if not self.settings['logdir']:
            rc = self.MountLogShare()
            if rc == -1:
                logging.error(self.error)
                return rc
        rc = self.CreateLogDir()
        if rc == -1:
            logging.error(self.error)
            return rc
        # create log file name
        logdir = self.log.get('logdir')
        host = re.sub('\..*','',self.host.hostname)
        logfile = logdir + "/" + self.testid + '-' + host + '-'
        if "logtag" in self.settings:
            logfile = logfile + self.settings['logtag'] + '-'
        logfile = logfile + "-" + self.GetLogTime() + ".log"
        self.log['logfile'] = logfile
        global logger
        logger = logging.getLogger('mgtest')

        logger.setLevel(logging.DEBUG)    
        fh = logging.FileHandler(logfile)
        if int(self.settings['debug']) > 0:
            print "setting level DEBUG"
            logger.setLevel(logging.DEBUG)
            fh.setLevel(logging.DEBUG)
        else:
            print "setting level INFO"
            logger.setLevel(logging.INFO)
            fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s:%(name)s:%(levelname)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s"))
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)
        h = TestLogHandler()
        h.setLevel(logging.WARNING)
        h.setFormatter(logging.Formatter("%(asctime)s:%(name)s:%(levelname)s:%(module)s:%(funcName)s:%(lineno)d: %(message)s"))
        h.setLevel(logging.DEBUG)
        logger.addHandler(h)
        
        
        self.LogTestParameters()
        self.LogHostInfo()
        self.testid = self.settings['testname']
        self.testlog = logger
        self.logstep = 1
        
        return 0
    def MountLogShare(self):
        'mount a remote share for logging.'
        thisfunc = inspect.stack()[0][3]
        mntopts = {}
        mntopts['host'] = self.settings['loghost']
        mntopts['share'] = self.settings.get('logshare')
        mntopts['user'] = self.settings.get('loguser')
        mntopts['passwd'] = self.settings.get('logpasswd')
        mntopts['error'] = 0
        osplat = self.host.osplat
        if osplat == "Darwin":
            mntopts['mntpnt'] = "/Volumes/logs"
        elif osplat == "Windows":
            mntopts['drive'] = "l:"
            mntopts['force'] = 1
        elif osplat == 'cygwin':
            mntopts['mntpnt'] = "l:"
        elif osplat == "Linux":
            mntopts['mntpnt'] = self.settings.get("logmntpnt")
        else:
            self.error = "%s: Platform not supported (%s)" % (thisfunc, osplat)
            print thisfunc,"ERROR:",self.error
            return -1
        rc = self.host.MountShare(self,mntopts)
        if mntopts['error'] != 0:
            self.error = mntopts['error']
            self.errortype = "CONFIGERROR"
            self.error = "%s: Platform not supported (%s)" % (thisfunc, osplat)
            return -1
        if os.name == "nt":
            print thisfunc,"rc from MountShare = ", rc
            if rc != -1:
                self.log['mntpnt'] = rc
            else:
                return -1
        else:
            self.log['mntpnt'] = mntopts.get('mntpnt')
        return 0
        
    def CreateLogDir(self):
    'create the log directory'
        thisfunc = inspect.stack()[0][3]
#        print thisfunc,": self.settings", self.settings
        if self.settings['logdir']:
            logdir = self.settings['logdir']
        else:
            host = re.sub('\..*','',self.host.hostname)
            logdir = self.log.get('mntpnt')
            logdir = logdir + "/testlogfiles/" + self.settings['testname'] + \
                '/' + host + self.GetLogTime()
            print "logdir:", logdir
        if not os.path.isdir(logdir):
            try:
                os.makedirs(logdir)
            except OSError as exception:
                if exception.errno != errno.EEXIST:
                    self.error = "SetUpLogging: unable to create %s: %s" % \
                                 (logdir,exception)
                    return -1
                else:
                    print logdir, " already exists."
        self.log['logdir'] = logdir
        return 0
        
        
    
    def CountError(self,msg):
        'counter for errors in a test or a subtest.'
        thisfunc = inspect.stack()[0][3]
        if hasattr(self,"currentsubtest"):
            if self.currentsubtest:
                self.subtests[self.currentsubtest]['stats']['errorcount'] += 1
                self.subtests[self.currentsubtest]['stats']['errors'].append(msg)
        self.stats['errorcount'] += 1
        if self.stats['errorcount'] <= 300:
            self.stats['errors'].append(msg)
        elif self.stats['errorcount']  > 300:
            self.stats['errors'].append("Too many errors to list them all") 
        return 0
            
    def CountWarning(self,msg):
        'counter for warnings in a test or a subtest.'

        thisfunc = inspect.stack()[0][3]
        if self.currentsubtest:
            self.subtests[self.currentsubtest]['stats']['warningcount'] += 1
            self.subtests[self.currentsubtest]['stats']['warnings'].append(msg)
        self.stats['warningcount'] += 1
        self.stats['warnings'].append(msg)
        return 0
        
    
    def LogTestParameters(self):
        'log basic test information and parameters to the test log'
        thisfunc = inspect.stack()[0][3]

        logger.info("Test Name: %s" % (self.settings.get('testname')))
        logger.info("Test Start Time: %s" % (datetime.datetime.fromtimestamp(self.stats.get('starttime'))))
        logger.info("\n\nTest Settings:")
        self.LogDict(self.settings)
        logger.info("Log Settings:")
        self.LogDict(self.log)
        logger.info ("End Test Settings\n\n")
        return 0
            
    def LogHostInfo(self):
        'log the local host information to the test log'
        'log host information'
        thisfunc = inspect.stack()[0][3]
        logger.info("\n\nHost Information:")
        self.LogDict(self.host)
        logger.info("End Host Information\n\n")
        return 0
        
    def LogDict(self,obj):
        'worker method to log a dictionary to the test log'
        thisfunc = inspect.stack()[0][3]
        global recurse
#        print thisfunc + " started - recurse = ", recurse
        tabs = "  " + "  " * (recurse)
        objtype = str(type(obj))
        if self.settings['debug']: print "%s: object type %s" % (thisfunc,objtype)
        if 'class' in objtype:
            logger.info('%s%s' % (tabs,objtype))
            print "object is a class type"
            obj = vars(obj)
        if "None" in objtype:
            return None
        for mykey in sorted(obj):
            mytype = type(obj[mykey])
            
            if mykey == "testinfo":
                logger.info('%s%s' % (tabs,mykey))
                continue
            if mykey == "ssh":
                logger.info('%s%s' % (tabs,mykey))
                continue
            if "logging" in str(mytype): continue
            if "class" in str(mytype): continue
            if 'method' in str(mytype): continue
            if "class" in str(mytype):
                newobj = vars(obj[mykey])
                logger.info('%s%s:' % (tabs,mykey))
                recurse = recurse + 1
                self.LogDict(newobj)
                recurse = recurse - 1
                continue
                
            if mytype is types.DictionaryType:
                logger.info('%s%s:' % (tabs,mykey))
                recurse = recurse + 1
                self.LogDict(obj[mykey])
                recurse = recurse - 1
                continue
            logger.info("%s%s = %s" % (tabs,mykey,obj.get(mykey)))
            
    def GetLogTime(self):
        'generate a timestamp for a log entry'
        thisfunc = inspect.stack()[0][3]
        mytime = datetime.datetime.now().isoformat()
        mytime = re.sub("[T|\.]","_",mytime)
        mytime = re.sub(':',"",mytime)
        return mytime
        
    def SetUpStats(self):
        'setup the initial test statistics'
        thisfunc = inspect.stack()[0][3]
        print thisfunc + " started"
        self.stats = { \
            'starttime': time.time(), # the test start time
            'endtime': 0, # the test end time
            'duration': 0, # the test duration
            'errors': [],  # list of errors
            'warnings': [], # list of warnings
            'msgs': [], # any messages to be printed with the stats at the end of the test
            'errorcount': 0,
            'warningcount': 0,
            'result': "PASS", # the test result
            }
        
    def LogTestStep(self,msg):
    'Log a test step to the test log'
        stack = inspect.stack()
        caller = stack[1][3]
        callerline = stack[1][2]
        logline = "%s:%s:%d: Step %d: " % (self.testid,caller,callerline,self.logstep)
        logline = logline + msg
        self.testlog.info(logline)
        self.logstep += 1
        return None
        

    def LogError(self,msg):
    'Log as error to the test log'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        if msg is "":
            return
        errorcount = self.stats.get('errorcount')
        print 'errorcount: ', errorcount
        errorcount = errorcount + 1
        if self.currentsubtest:
            self.subtests[self.currentsubtest]['stats']['errorcount'] = errorcount
            self.subtests[self.currentsubtest]['stats']['errors'].append(msg)
        self.stats['errorcount'] = errorcount
        self.stats['errors'].append(msg)
        logger.error(msg)
        
    def StartSubTest(self,opts):
        ' setup and start the subtest'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        if "testname" not in opts or "title" not in opts:
            self.testlog.error("opts requires testname and title parameters")
            return -1
        runno = 1
        tid = opts['testname'] + ":Run" + str(runno)
        while tid in self.subtests:
            runno += 1
            tid = opts['testname'] + ":Run" + str(runno)
        
        self.currentsubtest = tid
        self.testid = tid
        self.subtests[tid] = {}
        self.subtests[tid]['stats'] = {}
        self.subtests[tid]['hpqcid'] = None
        if "hpqcid" in opts: self.subtests[tid]['hpqcid'] = opts['hpqcid']
        # initialize the stats
        self.subtests[tid]['stats']['starttime'] = time.time()
        self.subtests[tid]['stats']['errorcount'] = 0
        self.subtests[tid]['stats']['warningcount'] = 0
        self.subtests[tid]['stats']['errors'] = []
        self.subtests[tid]['stats']['warnings'] = []
        self.subtests[tid]['stats']['result'] = "PASS"
        self.subtests[tid]['stats']['msgs'] = []
        self.subtests[tid]['logstep'] = 1
        self.subtests[tid]['title'] = opts['title']
        self.subtests[tid]['testname'] = opts['testname']
        msg = "%s Starting %s %s %s" %("*" * 15,tid,self.subtests[tid]['title'],"*" * 15)
        self.logstep = 1 
        self.testlog.info(msg)
        return tid    
    
    def ConvertSeconds(self,seconds,flag):
        thisfunc = inspect.stack()[0][3]
        flag = flag.lower()
        hours = 0
        seconds = 0
        minutes = 0
        days = 0
        
        if flag == 'seconds':
            mystr = str(seconds) + " seconds"
        elif flag == 'minutes':
            if seconds > 60:
                minutes = int(seconds/60)
                seconds = int(seconds%60)
            mystr = "%.2d:%.2d %s" % (minutes,seconds,"minutes:seconds")
        elif flag == 'hours':
            if seconds > 60:
                minutes = int(seconds / 60)
                seconds = int(seconds % 60)
            if minutes > 60:
                hours = int(minutes / 60)
                minutes = int(minutes % 60)
            mystr = "%.2d:%.2d:%.2d %s" % (hours,minutes,seconds,"hours:minutes:seconds")
        elif flag == 'days':
            if seconds > 60:
                minutes = int(seconds / 60)
                seconds = int(seconds % 60)
            if minutes > 60:
                hours = int(minutes / 60)
                minutes = int(minutes % 60)
            if hours > 24:
                days = int(hours / 24)
                hours = int(hours % 24)
            mystr = "%d:%.2d:%.2d:%.2d %s" % (days,hours,minutes,seconds,"days:hours:minutes:seconds")
        return mystr
            
    def SkipTest(self):
        'set the result of a test to skip'
        print "SkipTest: testid = %s" % self.testid
        stats = self.GetStats(self.testid)
        stats['result'] = "skip"
        return None        
        
        
    def EndSubTest(self):
        'end a subtest and log the results to the test log'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        testid = self.currentsubtest
        if not testid: return 0
        stats = self.subtests[testid]['stats']
        stats['endtime'] = time.time()
        if self.aborted:
            self.testlog.debug("self.aborted = %s" % str(self.aborted))
            stats['result'] = "ABORTED"
        elif stats['errorcount']:
            stats['result'] = "FAIL"
        duration = stats['endtime'] - stats['starttime']
        stats['duration'] = self.ConvertSeconds(duration,'hours')
        self.testlog.info("ENDSUBTEST: %s",testid)
        self.testlog.info('Subtest Duration: %s',stats['duration'])
        self.testlog.info('Errors: %d',stats['errorcount'])
        self.testlog.info('Warnings: %d',stats['warningcount'])
        self.testlog.info('Result: %s',stats['result'])
        if len(stats['msgs']) > 0:
            for msg in stats['msgs']:
                self.testlog.info(msg)
        self.testlog.info("End subtest: %s",testid)
        self.testlog.info("*"*80)
        self.currentsubtest = None
        self.testid = self.settings['testname']
        return 0
    
    def GetStats(self,testid):
        'return the statistics for the current test or subtest'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started: testid = %s" % testid)
        stats = None
        if testid == self.currentsubtest: 
            self.testlog.debug("self.subtest: %s" % self.subtests[testid])
            stats = self.subtests[testid]['stats']
        else:
            stats = self.stats
            if self.settings['debug']: print thisfunc + "returns: ", stats
        return stats
            
            
    
    def LogErrorReport(self,testid):

        ''' prints error and warning report    '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        stats = self.GetStats(testid)

        if stats['errorcount']: 
            self.testlog.info("************** ERROR REPORT ******************")
            
            for item in stats['errors']:
                self.testlog.info(item)
            self.testlog.info("************* END ERROR REPORT ***************\n")
        if stats['warningcount']:
            self.testlog.info("************** WARNING REPORT ******************")
            for item in stats['warnings']:
                self.testlog.info(item)
            self.testlog.info("************* END WARNING REPORT ***************\n")
        return 0
            
    
    def LogTestStats(self,testid):
        ''' logs test statistics.  Can be used for either a the test or a subtest.
        It logs the default parameters in the stats dictionary, and then any test specific
        parameters that may have been added during the test.
        It then logs any messages that may have been added during the test.
        the messages and the non-default parameters are a method that a test can use to log
        information that is specific to a particular test.
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        stats = self.GetStats(testid)
        self.testlog.info('*************** Test Stats ***************\n')
        self.testlog.info("Test Start Time: %s" %(MGUtils.GetLogTime(stats['starttime'])))
        self.testlog.info("Test End Time: %s" %(MGUtils.GetLogTime(stats['endtime'])))
        duration = stats['endtime'] - stats['starttime']
        duration = MGUtils.CalcDuration(duration)
        self.testlog.info("Test Duration: %s" % duration)
        self.testlog.info("Test Result: %s" % stats['result'])
        
        # log any statistics that are not default
        for item in stats:
            if not re.search("result|starttime|endtime|duration|errors|warnings|msgs",item):
                self.testlog.info("%s = %s" % (item,stats[item]))
        # log any messages that might be stored in statistics
        if len(stats['msgs']):
            for item in stats['msgs']:
                self.testlog.info(item)
        self.testlog.info('*************** End Test Stats ***************\n\n')
        return 0

    def LogTestResults(self,testid):
        ''' Logs the test and any subtest results to the test log'''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        stats = self.GetStats(testid)

        self.testlog.info('*************** Test Results ***************\n')
        if "description" in self.settings:
            self.testlog.info(self.settings['description'])
        if len(self.subtests):
            subtests = 0
            failedsubtests = 0
            passedsubtests = 0
            skippedsubtests = 0
            for item in self.subtests:
                subtests += 1
                subtest = self.subtests[item]
                msg = "subtest: %s HPQCID: %s title: %s result: %s" % \
                    (item,subtest['hpqcid'],subtest['title'],subtest['stats']['result'])
                self.testlog.info(msg)
                if subtest['stats']['result'] == "FAIL":
                    failedsubtests += 1
                elif subtest['stats']['result'].lower() == 'skip' or subtest['stats']['result'] == "ABORTED":
                    skippedsubtests += 1
                else:
                    passedsubtests += 1
            self.testlog.info("ran %d sub-tests: %d failed, %d passed and %d skipped" % \
                              (subtests,failedsubtests,passedsubtests,skippedsubtests))
        
        self.testlog.info("Testid: %s HPQCID: %s Result: %s" % \
                         (testid,self.settings['hpqcid'],stats['result']))
        self.testlog.info('*************** End Test Results ***************\n\n')
        return 0
        
        
    def LogTestReport(self,testid):
        '''Log the test report at the end of the test log. This info is
        usually extracted post test and used as a test summary
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        self.LogErrorReport(testid)
        self.LogTestStats(testid)
        self.LogTestResults(testid)
        self.stats['logfile'] = self.settings['logfile']
        return 0
        
        
    def EndTest(self):
        'End the current test'
        thisfunc = inspect.stack()[0][3]
        self.testlog.debug("Started")
        self.stats['endtime'] = time.time()
        if self.aborted:
            self.stats['result'] = "ABORTED"
        elif self.stats['errorcount']:
            self.stats['result'] = "FAIL"
        self.LogTestReport(self.testid)
        self.testid = self.settings['testname']
        self.testlog.info("Test Log: %s" % self.log['logfile'])
        self.host.UnMountShare(self, self.log)
            
        return 0
        
        

