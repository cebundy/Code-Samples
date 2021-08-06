import time
import paramiko
import threading
import sys
import os
import re
import types
import logging
import inspect
from Queue import Queue
import MGComm
import MGGlobals
import MGUtils
import MGTest
import MGCluster
#from django.contrib.gis.geos import linestring


stop = 0
testinfo = None

class MGMonitor(object):
    ''' Class to monitor the MG MDS logs 
    There is a self.writeq in which the monitor write log messages that
    are defined in the report array. 
    A caller can add another q using the addwriteq method.  Additional queues my then be deleted by
    calling the removewriteq method.  This is helpful if there is more than one thread looking for items
    on the queue, and we don't want the items in the queue gobbled up by another thread.
    The self.reportlist is a list of strings that when encountered in the log file are written to the writeqs.
    Items can be added to the list at startup by including them in a file and then defining the file 
    in the opts['monitorfile'] variable.
    Items can then be added and deleted from the list by calling the reportlist_add, and reportlist_get.
    The self.ignorelist is a list of strings that should not be reported.  This is useful when we are 
    reporting all errors, but there are some that we want to ignore all together or and specific times.
    Items can be added to the list at startup by including them in a file and then defining the file 
    in the opts['monitorfile'] variable.
    Items can then be added and deleted from the list by calling the ignorelist_add, and ignorelist_get.
    The Monitor can be stopped by calling the stop_monitor method.
    '''
    def __init__(self,opts):
        thisfunc = inspect.stack()[0][3]
        if opts.has_key('ip'):
            self.ip = opts['ip']
        else:
            opts['error'] = thisfunc,": opts requires 'ip'"
            return None
        if opts.has_key('logdir'):
            self.logdir = opts['logdir']
        else:
            opts['error'] = "%s: opts requires 'logdir'" % thisfunc
            return None
        if opts.has_key('filename'):
            self.basename = opts['filename']
            self.filename = "/var/log/omneon/" + opts['filename']
        else:
            opts['error'] = thisfunc,": opts requires 'filename'"
            return
        if opts.has_key("logger"):
            self.testlog = opts['logger']
        else:
            self.testlog = logging.getLogger('mgtest')
        if opts.has_key('name'):
            self.name = opts['name']
        if opts.has_key('user'):
            self.user = opts['user']
        else:
            self.user = "root"
        if opts.has_key("password"):
            self.password = opts['password']
        else:
            self.password = "omneon"
        self.ignorelist = []
        self.reportlist = []
        self.stop = 0
        self.paused = 0
        self.trace = 0
        if opts.has_key('monitorfile'):
            self.monitorfile = opts['monitorfile']
            self.Processmonitorfile()
        self.ssh = MGComm.getssh(opts)
        if opts.has_key('error'):
            opts['error'] = "%s: Unable to ssh to %s: %s" \
                % (thisfunc,opts['ip'],opts['error'])
            print "%s: %s returning None" % (thisfunc,self.name)
            return None
        mytime = MGUtils.GetLogTime()
        self.logfile = self.logdir + "/" + self.name + '-' + mytime + ".log"
        self.readq = Queue()
        self.writeqs = []
        self.writeq = Queue()
        self.writeqs.append(self.writeq)
        self.paused = None
        self.StartMonitor()
        
        
        
    def Processmonitorfile(self):
        thisfunc = inspect.stack()[0][3]
        if not os.path.isfile(self.monitorfile):
            self.testlog.warn("%s: monitorfile %s: does not exist" % \
                             (thisfunc,self.monitorfile))
            return
        try:
            fh = open(self.monitorfile,"r")
        
        except IOError, e:
            self.testlog.error("%s: unable to open %s: %s" % \
                              (thisfunc,self.monitorfile,e))
            return -1
        foundit = 0
        for line in fh:
            line = line.strip()
            if self.basename in line:
                foundit = 1
                continue
            if not foundit: continue
            m = re.match(r"\[(ignore|capture)\]",line)
            if m:
                mytype = m.group(1)
                continue
            m = re.match(r"^\[",line) # this is for a different file
            if (m):
                if foundit: break
                continue
            m = re.match(r"\#",line)
            if m: continue
            if not foundit and not mytype:
                continue
            if mytype == "ignore":
                self.ignorelist.append(line)
            elif mytype == "capture":
                self.reportlist.append(line)
        self.testlog.debug("%s: reportlist: %s" % (self.name,self.reportlist))
        self.testlog.debug("%s: ignorelist: %s" % (self.name,self.ignorelist))
        
    def IgnorelistAdd(self,obj):
        if type(obj) is types.StringType:
            self.ignorelist.append(obj)
        else:
            self.ignorelist.extend(obj)
        return 0
    
    def IgnorelistRemove(self,obj):
        if type(obj) is types.StringType:
            self.ignorelist.remove(obj)
        else:
            for item in obj:
                self.ignorelist.remove(item)
        return 0
                
    def ReportlistAdd(self,obj):
        self.testlog.info("adding: %s" % obj)
        if type(obj) is types.StringType:
            self.reportlist.append(obj)
        else:
            self.reportlist.extend(obj)
        return 0

    def ReportlistGet(self):
        return self.reportlist
    
    def ReportlistRemove(self,obj):
        if type(obj) is types.StringType:
            self.reportlist.remove(obj)
        else:
            for item in obj:
                self.reportlist.remove(item)
        return None
    
    def IgnorelistGet(self):
        return self.ignorelist
    
    def addwriteq(self):
        wq = Queue()
        self.writeqs.append(wq)
        return wq
    
    def removewriteq(self,q):
        self.writeqs.remove(q)
        return 0
    
    def CheckReadQ(self):
        ''' we are looking for pause and resume
        TODO: need to think about if we want to throw away any log lines
        that were collected during the pause.  Or do we want pause to just
        not send any messages to the calling script for the duration of the
        pause?  Right now pause will just cause stdout to build up, probably
        not a good idea.
        '''
        while True:
            while not self.readq.empty():
                item = self.readq.get(block=0)
#                 print "%s:%s: got from readq:",item
                if item == 'pause':
                    self.testlog.debug("%s is paused" % self.name)
                    self.paused = 1
                elif item == 'resume':
                    self.testlog.debug("%s has resumed" % self.name)
                    self.paused = None
            break
        return None
    
    def ExamineLine(self):
        self.testlog.info("%s: starting",self.name)
        firsttime = 1
        while not self.stop:
            while not self.examq.empty():
                myline = self.examq.get()
                if "ssmd" in self.name:
                    self.testlog.info("trace = %d reportlist: %s" % (self.trace,self.reportlist))
                firsttime = None
                if "ssmd" in self.name:
                    self.testlog.info("%s: got line: %s" % (self.name,myline))
                reportit = None
                for reportstr in self.reportlist:
                    if reportstr in myline:
                        reportit = 1
                        for ignorestr in self.ignorelist:
                            if ignorestr in myline:
                                reportit = None
                                break
                        if reportit:
                            self.testlog.debug("%s: reporting line: %s" % (self.name,myline))
                            self.writeq.put(myline)
                        break
            if self.stop: break
        self.testlog.debug("%s: stopping  stop = %d" % (self.name,self.stop))
            

    def MonitorFile(self):
        ''' monitors a specific file.  The logline is written to the
            file in the log directory, then the log line is queued
            so that the ExamineLine method can pick it up and 
            check to see if we need to report that line.  We do it this
            way because examining the log line takes time, this way 
            the file containing the log line stay relatively
            up to date, and we can stop tailing the log when signalled, and
            then finish processing the log lines that are queued up
        '''
        thisfunc = inspect.stack()[0][3]
        self.testlog.info("%s: %s has started" % (thisfunc,self.name))
        print "%s: %s has started" % (thisfunc,self.name)
        global stop
        try:
            self.testlog.debug("%s opening %s" % (self.name,self.logfile))
            outf = open(self.logfile,"w")
        except IOError, e:
            self.testlog.error("%s: %s unable to open %s: %s" % \
                              (thisfunc,self.name,self.logfile,e))
            self.testlog.error("%s:  %s is stopping",thisfunc,self.name)
            return None
        self.examq = Queue()
        examthrd = threading.Thread(target=self.ExamineLine,name=self.name)
        examthrd.start()
        
        command = "tail -F -s 0 " + self.filename
        self.testlog.info("sending the command %s" % command)
        stdin, stdout, stderr = self.ssh.exec_command(command)
        stdout.channel.setblocking(0)
        while not stdout.channel.exit_status_ready():
            if self.stop == 1: break
#             self.testlog.debug("calling CheckReadQ")    
            self.CheckReadQ()
            while stdout.channel.recv_ready():
                try: 
                    line = stdout.readline()
                except Exception, e:
                    self.testlog.error("%s: exception: %s" % (self.name,e))
                if self.trace:
                    self.testlog.info("%s: logging line: %s" % (self.name,line))
                outf.write(line)
                self.examq.put_nowait(line.strip())
                if self.stop == 1: break
        self.testlog.info("%s stopping stop = %d",self.name,self.stop)
        outf.close()
        self.ssh.close()
        self.testlog.debug("joining ExamineLine")
        examthrd.join()
        return 0


    def StartMonitor(self):
        self.thrd = threading.Thread(target=self.MonitorFile,name=self.name)
        self.testlog.info("Starting Monitor %s" % self.name)
        self.thrd.start()
        return 0
    
    def StopMonitor(self):
        global stop
        self.testlog.info("Stopping Monitor %s" % self.name)
        self.stop = 1;
        self.thrd.join(timeout=10)
        return 0
    
    def PauseMonitor(self):
        self.testlog.info("Pausing Monitor %s" % self.name)
        self.readq.put_nowait("pause")
        return 0
    
    def ResumeMonitor(self):
        self.testlog.info("Resuming Monitor %s" % self.name)
        self.readq.put_nowait("resume")
        return 0
    
################ Test Code #################
    
def ReadMGMonitorQs():
    thisfunc = inspect.stack()[0][3]
    global testinfo, stop
    testinfo.testlog.debug("%s: started" % thisfunc)
    while not stop:
        for mdsname in testinfo.cluster.mds:
            mds = testinfo.cluster.mds[mdsname]
            for filename in mds.monitors:
                monq = mds.monitors[filename].writeq
                while not monq.empty():
                    msg = mds.monitors[filename].writeq.get_nowait()
                    if msg:
                        testinfo.testlog.info("received msg from %s: %s" %\
                                               (mds,msg))
    testinfo.testlog.info("%s: stopping" % thisfunc)
    return 0


    
def SetupGrid():
    global testinfo
    testlog = testinfo.testlog
    thisfunc = inspect.stack()[0][3]
    testlog.info("started")
    opts = {}
    opts['ip'] = testinfo.settings.get('gridip')
    opts['user'] = "root"
    opts['password'] = "omneon"
    testlog.debug("calling MGCluster")
    cluster = MGCluster.MGCluster(opts,testinfo)
    if testinfo.error:
        return -1
    testinfo.LogDict(cluster)
    setattr(testinfo,"cluster",cluster)
    opts['logdir'] = testinfo.log.get('logdir')
    opts['monitorfile'] = testinfo.settings.get('monitorfile')
    opts['user'] = 'root'
    opts['password'] = 'omneon'
    opts['logger'] = testlog
    monfiles = ['mdscore','ssmd','mdscorestats']  # put this back!!!
    for mdsname in testinfo.cluster.mds:
        mds = testinfo.cluster.mds[mdsname]
        setattr(mds,'monitors',{})
        opts['ip'] = mds.ip['public'][0]
        for thefile in monfiles:
            opts['filename'] = thefile
            opts['name'] = mdsname + "-" + thefile
            mds.monitors[thefile] = MGMonitor(opts)
            if opts.has_key('error') and opts['error']:
                testinfo.error = "%s: failed to setup Monitor for %s: %s" \
                                    % (thisfunc,mdsname,opts['error'])
                return -1
            if thefile == "mdscore":
                mds.monitors[thefile].ReportlistAdd("this is a NEW string")
        print "\n",thisfunc,": ",mdsname," settings",vars(mds),"\n"
    
    readmon = threading.Thread(target=ReadMGMonitorQs,name="readmonitorqs")
    readmon.start()
    setattr(testinfo,"readmonqs",readmon) 
    return 0
    
    
    
def TestSetup():
    '''Setup test environment and variables'''
    thisFunc = inspect.stack()[0][3]
    global testinfo
#    global DEBUG
    opts = {
        'cleanup'     : { 'value' : 0, 'required' : 0  },
        'debug'       : { 'value' : 1, 'required' : 0 },
        'duration'    : { 'value' : 600, 'required' : 0 },
        'gridip'      : { 'value' : None, 'required' : 1 },
        'logname'     : { 'value' : 'MGMonitor', 'required' : 0  },
        'monitorfile' : { 'value' : "mdsmon.txt", 'required' : 0  },
        'scriptname' : { 'value' : ( inspect.stack()[0][1] ), 'required' : 0 },
        'testname' : { 'value' : 'MGMonitor', 'required' : 1 },
    }
    testinfo = MGTest.MGTest(opts)
    rc = SetupGrid()
    if rc == -1: return -1
    return 0
            
    
def TestCleanup():    
    thisfunc = inspect.stack()[0][3]
    global testinfo, stop
    testinfo.testlog.info("starting")
    testinfo.testlog.info("stopping mds monitors")
    for mdsname in testinfo.cluster.mds:
        mds = testinfo.cluster.mds[mdsname]
        if hasattr(mds,"monitors"):
            for monfile in mds.monitors:
                mds.monitors[monfile].StopMonitor()
    stop = 1
    time.sleep(3)
    testinfo.testlog.info("joining readmonqs")
    testinfo.readmonqs.join()
                
    
def main():
    thisfunc = inspect.stack()[0][3]
    global testinfo
    rc = TestSetup()
    if rc == -1: return 0
    starttime = time.time()
    while (time.time() - starttime) < testinfo.settings['duration']:
        time.sleep(10)
    TestCleanup()
    testinfo.EndTest()
    return -1
    
    

if __name__ == '__main__':
    main()
    print "all done"
    exit(0)

